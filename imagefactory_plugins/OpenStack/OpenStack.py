#!/usr/bin/python
#
#   Copyright 2012 Red Hat, Inc.
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

import logging
import zope
import libxml2
import json
import os
from xml.etree.ElementTree import fromstring
from imgfac.Template import Template
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist, create_cloud_info
from imgfac.FactoryUtils import check_qcow_size, subprocess_check_output, qemu_convert_cmd
try:
    from keystoneclient.v2_0 import client
    import glanceclient as glance_client
    GLANCE_VERSION = 2
except ImportError:
    try:
       # backward compatible
       from glance import client as glance_client
       GLANCE_VERSION = 1
    except ImportError:
       raise ImageFactoryException("Glance client not found.")

class OpenStack(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        # Note that we are now missing ( template, target, config_block = None):
        super(OpenStack, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.version = GLANCE_VERSION
        if self.version == 2:
            self.credentials_attrs = [ 'auth_url', 'password', 'tenant', 'username']
        else:
             self.credentials_attrs = [ 'auth_url', 'password', 'strategy', 'tenant', 'username']

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        # Our target_image is already a raw KVM image.  All we need to do is upload to glance
        self.builder = builder
        self.active_image = self.builder.provider_image
        self.openstack_decode_credentials(credentials)

        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("OpenStack KVM instance not found in XML or JSON provided")

        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.data

        # If the template species a name, use that, otherwise create a name
        # using provider_image.identifier.
        template = Template(self.builder.provider_image.template)
        if template.name:
            image_name = template.name
        else:
            image_name = 'ImageFactory created image - %s' % (self.builder.provider_image.identifier)

        if check_qcow_size(input_image):
            self.log.debug("Uploading image to glance, detected qcow format")
            disk_format='qcow2'
        else:
            self.log.debug("Uploading image to glance, assuming raw format")
            disk_format='raw'

        # Support openstack grizzly keystone authentication and glance upload
        if self.version == 2:
            if self.credentials_token is None:
                self.credentials_token = self.keystone_authenticate(**self.credentials_dict)

            provider_data['name']  = image_name
            provider_data['disk_format'] = disk_format

            image_id = self.glance_upload_v2(input_image, self.credentials_token, **provider_data)
        else:
            # Also support backward compatible for folsom
            image_id = self.glance_upload(input_image, creds = self.credentials_dict, token = self.credentials_token,
                                     host=provider_data['glance-host'], port=provider_data['glance-port'],
                                     name=image_name, disk_format=disk_format)

        self.builder.provider_image.identifier_on_provider = image_id
        if 'username' in self.credentials_dict:
            self.builder.provider_image.provider_account_identifier = self.credentials_dict['username']
        self.percent_complete=100

    def openstack_decode_credentials(self, credentials):
        self.activity("Preparing OpenStack credentials")
        # TODO: Validate these - in particular, ensure that if some nodes are missing at least
        #       a minimal acceptable set of auth is present
        doc = libxml2.parseDoc(credentials)

        self.credentials_dict = { }
        for authprop in self.credentials_attrs:
            value = self._get_xml_node(doc, authprop)
            if value is not None:
                self.credentials_dict[authprop] = value
        self.credentials_token = self._get_xml_node(doc, 'token')

    def _get_xml_node(self, doc, credtype):
        nodes = doc.xpathEval("//provider_credentials/openstack_credentials/%s" % (credtype))
        # OpenStack supports multiple auth schemes so not all nodes are required
        if len(nodes) < 1:
            return None

        return nodes[0].content

    def snapshot_image_on_provider(self, builder, provider, credentials, template, parameters):
        # TODO: Implement snapshot builds
        raise ImageFactoryException("Snapshot builds not currently supported on OpenStack KVM")

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        return True

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        pass

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.target=target
        self.builder=builder 
        self.modify_oz_filesystem()

        # OS plugin has already provided the initial file for us to work with
        # which we can currently assume is a raw image
        input_image = builder.target_image.data

        # Support conversion to alternate preferred image format
        # Currently only handle qcow2, but the size reduction of
        # using this avoids the performance penalty of uploading
        # (and launching) raw disk images on slow storage
        if self.app_config.get('openstack_image_format', 'raw') == 'qcow2':
            # None of the existing input base_image plugins produce compressed qcow2 output
            # the step below is either going from raw to compressed qcow2 or
            # uncompressed qcow2 to compressed qcow2
            self.log.debug("Converting image to compressed qcow2 format")
            tmp_output = input_image + ".tmp.qcow2"
            convert_cmd = qemu_convert_cmd(input_image, tmp_output, True)
            (stdout, stderr, retcode) = subprocess_check_output(convert_cmd)
            os.unlink(input_image)
            os.rename(tmp_output, input_image)

    def modify_oz_filesystem(self):
        self.log.debug("Doing further Factory specific modification of Oz image")
        guestfs_handle = launch_inspect_and_mount(self.builder.target_image.data)
        remove_net_persist(guestfs_handle)
        create_cloud_info(guestfs_handle, self.target)
        shutdown_and_close(guestfs_handle)

    def get_dynamic_provider_data(self, provider):
        try:
            xml_et = fromstring(provider)
            return xml_et.attrib
        except Exception as e:
            self.log.debug('Testing provider for XML: %s' % e)
            pass

        try:
            jload = json.loads(provider)
            return jload
        except ValueError as e:
            self.log.debug('Testing provider for JSON: %s' % e)
            pass

        return None

    def keystone_authenticate(self, **kwargs):
        user = kwargs.get('username')
        pwd = kwargs.get('password')
        tenant = kwargs.get('tenant')
        url = kwargs.get('auth_url', 'http://127.0.0.1:5000/v2.0')

        keystone = client.Client(username=user, password=pwd, tenant_name=tenant, auth_url=url)
        keystone.authenticate()
        return keystone.auth_token

    def glance_upload(self, image_filename, creds = {'auth_url': None, 'password': None, 'strategy': 'noauth', 'tenant': None, 'username': None},
                      host = "0.0.0.0", port = "9292", token = None, name = 'Factory Test Image', disk_format = 'raw'):

        image_meta = {'container_format': 'bare',
         'disk_format': disk_format,
         'is_public': True,
         'min_disk': 0,
         'min_ram': 0,
         'name': name,
         'properties': {'distro': 'rhel'}}


        c = glance_client.Client(host=host, port=port,
                                 auth_tok=token, creds=creds)
        image_data = open(image_filename, "r")
        image_meta = c.add_image(image_meta, image_data)
        image_data.close()
        return image_meta['id']

    def glance_upload_v2(self, image, auth_token=None, **kwargs):
        if image is None:
             raise ImageFactoryException("No image is provided")

        glance_host = kwargs.setdefault("glance-host", "127.0.0.1")
        glance_port = kwargs.setdefault("glance-port", "9292")
        glance_url = "http://%s:%s" % (glance_host, glance_port)

        image_data = open(image, "r")

        image_meta = {
         'container_format': kwargs.setdefault('container_format', 'bare'),
         'disk_format': kwargs.setdefault('disk_format', 'raw'),
         'is_public': kwargs.setdefault('is_public', False),
         'min_disk': kwargs.setdefault('min_disk', 0),
         'min_ram': kwargs.setdefault('min_ram', 0),
         'name': kwargs.setdefault('name', 'Factory Test Image'),
         'data': image_data,
        }

        c = glance_client.Client('1', glance_url, token=auth_token)
        image_meta = c.images.create(**image_meta)
        image_data.close()
        return image_meta.id
