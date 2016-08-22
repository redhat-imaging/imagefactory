#
#   Copyright 2016 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import zope
import os
import traceback
import logging
import subprocess
import json
import time

from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.CloudDelegate import CloudDelegate

try:
    from oauth2client.service_account import ServiceAccountCredentials
    from googleapiclient import discovery, http
    _gcloud_sdk_available = True
except ImportError:
    _gcloud_sdk_available = False


class GCE(object):
    """GCE target plugin"""
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        super(GCE, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def activity(self, activity):
        # Activity should be a one line human-readable string indicating the task in progress.
        # We log it at DEBUG and also set it as the status_detail on our active image.
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def log_exc(self):
        # Log an exception.
        self.log.debug('Exception caught in ImageFactory')
        self.log.debug(traceback.format_exc())

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        raise Exception('delete_from_provider not yet implemented for GCE')

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_should_create_target_image() called on GCE plugin - returning True')
        return True

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        pass

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in GCE plugin')
        self.status = 'BUILDING'

        # On entry the image points to either a raw or qcow2 image. First step is to conver to a RAW
        # image. We always run the convert command even if the image is already raw. It should't be
        # a problem, and has a slight benefit that the image is re-sparsified after the Oz install.
        # See: https://cloud.google.com/compute/docs/tutorials/building-images
        image = builder.target_image.data
        tmp_image = image + '.tmp'
        self.log.debug('Converting input image (%s) to RAW (%s) using qemu-img' % (image, tmp_image))
        qemu_img_cmd = [ 'qemu-img', 'convert', '-O', 'raw', image, tmp_image ]
        subprocess.check_call(qemu_img_cmd)
        self.log.debug('RAW conversion complete')
        os.unlink(image)

        # Second step is to create the tar file. Unfortunately the tarfile module doesn't support
        # sparse files, so we call "tar" from the command line.
        self.percent_complete = 50
        self.log.debug('Converting RAW image (%s) to GCE TAR format (%s)' % (tmp_image, image))
        tar_cmd = [ 'tar', 'cfz', image, tmp_image, '--sparse', '--transform=s/.*tmp/disk.raw/' ]
        subprocess.check_call(tar_cmd)
        self.log.debug('TAR creation complete')
        os.unlink(tmp_image)

        # We are done!
        self.percent_complete = 100
        self.status = 'COMPLETED'

    def _wait_for_global_operation(self, result, service, project):
        # Wait for a global operation to complete. Then raise an error if it failed, or
        # return the operation if it succeeded.
        while result['status'] != 'DONE':
            self.log.debug('operation {0}, wait until DONE'.format(result['status']))
            time.sleep(5)
            result = service.globalOperations().get(project=project, operation=result['name']).execute()
        error = result.get('error')
        if error:
            self.status = 'FAILED'
            raise ImageFactoryException('failed to build image: {0!r}'.format(error))
        return result

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        self.log.info('push_image_to_provider() called in GCE plugin')

        # Fail gracefully if the Google API client library is not installed.
        # Building images will still work without it.
        if not _gcloud_sdk_available:
            raise ImageFactoryException('Google Cloud SDK is not availabe - cannot push to provider')

        self.log.debug('GCE plugin - target: {0!r}'.format(target))
        self.log.debug('GCE plugin - target_image: {0!r}'.format(target_image))
        self.log.debug('GCE plugin - parameters: {0!r}'.format(parameters))

        bucket = provider
        keyfile = json.loads(credentials)
        project = keyfile['project_id']
        source = builder.target_image
        object_name = parameters.get('gce_object_name', source.identifier + '.tar.gz')
        image_name = parameters.get('gce_image_name', source.identifier)
        family = parameters.get('gce_image_family')

        self.status = 'PUSHING'
        self.percent_complete = 0

        # The credentials must be a Service Account JSON file, which can be
        # created and downloaded using the Google Cloud Platform console. See
        # https://cloud.google.com/storage/docs/authentication#generating-a-private-key
        creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile)

        # Create the Object in the object store. This will overwrite any
        # object with the same name already present.
        storage = discovery.build('storage', 'v1', credentials=creds)
        with open(source.data, 'rb') as fin:
            body = http.MediaIoBaseUpload(fin, 'application/octet-stream')
            self.log.info('uploading {0} => {1}/{2}'.format(source.data, bucket, object_name))
            blob = storage.objects().insert(bucket=bucket, name=object_name, media_body=body).execute()

        # Use the uploaded object to create an image. Images are global resources in GCE
        # so we don't have to worry about regions. Unlike storage blobs though, image
        # don't automatically overwrite if they already exist. The result of this is a
        # 'compute#operation', and we need to wait until it's complete before we can move on.
        compute = discovery.build('compute', 'v1', credentials=creds)
        self.log.info('deleting image {0} if it exists'.format(image_name))
        try:
            result = compute.images().delete(project=project, image=image_name).execute()
        except http.HttpError as e:
            if e.resp['status'] != '404':
                raise
        else:
            self._wait_for_global_operation(result, compute, project)

        # Now we can upload. The result is also a 'compute#operation'. Wait for it to
        # complete so that we know if it succeeded.
        image = {'name': image_name, 'rawDisk': {'source': blob['selfLink']}}
        if family:
            image['family'] = family
        self.log.info('creating image {0} from uploaded blob'.format(image_name))
        result = compute.images().insert(project=project, body=image).execute()
        self._wait_for_global_operation(result, compute, project)

        # Return status.
        builder.provider_image.identifier_on_provider = result['targetId']
        self.status = 'COMPLETE'
        self.percent_complete = 100

    def abort(self):
        pass
