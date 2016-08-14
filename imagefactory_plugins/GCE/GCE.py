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
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.CloudDelegate import CloudDelegate

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

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        raise Exception('push_image_to_provider() not yet implemented for GCE')

    def abort(self):
        pass
