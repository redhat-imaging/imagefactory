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

from builtins import object
import zope
import os
import logging
import json

from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.CloudDelegate import CloudDelegate

from requests import Session


class AtlasClient(Session):

    default_url = 'https://atlas.hashicorp.com/api/v1'

    def __init__(self, token):
        super(AtlasClient, self).__init__()
        self.headers['X-Atlas-Token'] = token

    def request(self, method, url, **kwargs):
        if url.startswith('/'):
            url = self.default_url + url
        return super(AtlasClient, self).request(method, url, **kwargs)


class Atlas(object):
    """Atlas provider plugin"""
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        super(Atlas, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        # We are not building target images in this plugin.
        self.log.info('builder_should_create_target_image() called in Atlas plugin')
        return False

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        self.log.info('push_image_to_provider() called in Atlas plugin')

        box = builder.target_image
        image = builder.base_image
        image_format = image.target
        box_format = box.parameters.get('{}_ova_format'.format(image_format))
        self.log.debug('box format {}, disk format {}'.format(box_format, image_format))

        if box.target != 'ova' or not box_format.startswith('vagrant-'):
            raise ImageFactoryException('image {} is not a Vagrant box'.format(box.identifier))

        box_name = parameters.get('atlas_box_name', box.identifier)
        box_version = parameters.get('atlas_box_version', '1.0.0')
        box_provider = box_format[8:]

        keyfile = json.loads(credentials)
        client = AtlasClient(keyfile['token'])
        username = keyfile['username']

        # Create the box if it doesn't exist.

        r = client.get('/box/{0}/{1}'.format(username, box_name))
        if r.status_code == 404:
            new_box = {'box': {'name': box_name, 'username': username}}
            r = client.post('/boxes', json=new_box)
        r.raise_for_status()

        # Create the version if it doesn't exist.

        r = client.get('/box/{0}/{1}/version/{2}'.format(username, box_name, box_version))
        if r.status_code == 404:
            new_version = {'version': {'version': box_version}}
            r = client.post('/box/{0}/{1}/versions'.format(username, box_name), json=new_version)
        r.raise_for_status()
        version = r.json()

        # Create the provider if it doesn't eixst.

        r = client.get('/box/{0}/{1}/version/{2}/provider/{3}'
                            .format(username, box_name, box_version, box_provider))
        if r.status_code == 404:
            new_provider = {'provider': {'name': box_provider}}
            r = client.post('/box/{0}/{1}/version/{2}/providers'
                                .format(username, box_name, box_version), json=new_provider)
        r.raise_for_status()

        # Now upload the actual data. We use a chunked upload, and it's pretty cool that
        # requests can do that.  Chunking also allows us to keep track of progress.

        r = client.get('/box/{0}/{1}/version/{2}/provider/{3}/upload'
                            .format(username, box_name, box_version, box_provider))
        r.raise_for_status()
        upload = r.json()

        self.status = 'UPLOADING'
        self.percent_complete = 0
        
        with open(box.data, 'rb') as fin:
            r = client.put(upload['upload_path'], data=fin)
            r.raise_for_status()

        # Release the version.

        if version['status'] != 'active':
            r = client.put('/box/{0}/{1}/version/{2}/release'.format(username, box_name, box_version))
            r.raise_for_status()

        image_id = '{0}/box/{1}/{2}/version/{3}/provider/{4}' \
                            .format(client.default_url, username, box_name, box_version, box_provider)
        builder.provider_image.identifier_on_provider = image_id
        self.status = 'DONE'
        self.percent_complete = 100
