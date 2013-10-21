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

import hashlib
import logging
import zope
import libxml2
import json
import os
import struct
from xml.etree.ElementTree import fromstring
from imgfac.Template import Template
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist, create_cloud_info
from keystoneclient.v2_0 import client
import glanceclient as glance_client

def keystone_authenticate(**kwargs):
    user = kwargs.get('username')
    pwd = kwargs.get('password')
    tenant = kwargs.get('tenant')
    url = kwargs.get('auth_url', 'http://127.0.0.1:35357/v2.0')

    keystone = client.Client(username=user, password=pwd, tenant_name=tenant, auth_url=url)
    return keystone.auth_ref

def glance_upload(image, auth_token=None, **kwargs):

    if image is None:
         raise ImageFactoryException("No image is provided")

    url = kwargs.setdefault("url", "http://127.0.0.1:9292")
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

    c = glance_client.Client('1', url, token=auth_token)
    image_meta = c.images.create(**image_meta)
    image_data.close()
    return image_meta.id

# Copied from Keystone's keystone/common/cms.py file.
PKI_ANS1_PREFIX = 'MII'

def is_ans1_token(token):
    '''
    thx to ayoung for sorting this out.

    base64 decoded hex representation of MII is 3082
    In [3]: binascii.hexlify(base64.b64decode('MII='))
    Out[3]: '3082'

    re: http://www.itu.int/ITU-T/studygroups/com17/languages/X.690-0207.pdf

    pg4: For tags from 0 to 30 the first octet is the identfier
    pg10: Hex 30 means sequence, followed by the length of that sequence.
    pg5: Second octet is the length octet
    first bit indicates short or long form, next 7 bits encode the number
    of subsequent octets that make up the content length octets as an
    unsigned binary int

    82 = 10000010 (first bit indicates long form)
    0000010 = 2 octets of content length
    so read the next 2 octets to get the length of the content.

    In the case of a very large content length there could be a requirement to
    have more than 2 octets to designate the content length, therefore
    requiring us to check for MIM, MIQ, etc.
    In [4]: base64.b64encode(binascii.a2b_hex('3083'))
    Out[4]: 'MIM='
    In [5]: base64.b64encode(binascii.a2b_hex('3084'))
    Out[5]: 'MIQ='
    Checking for MI would become invalid at 16 octets of content length
    10010000 = 90
    In [6]: base64.b64encode(binascii.a2b_hex('3090'))
    Out[6]: 'MJA='
    Checking for just M is insufficient

    But we will only check for MII:
    Max length of the content using 2 octets is 7FFF or 32767
    It's not practical to support a token of this length or greater in http
    therefore, we will check for MII only and ignore the case of larger tokens
    '''
    return token[:3] == PKI_ANS1_PREFIX

class OpenStack(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        # Note that we are now missing ( template, target, config_block = None):
        super(OpenStack, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

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

        if self.check_qcow_size(input_image):
            self.log.debug("Uploading image to glance, detected qcow format")
            disk_format='qcow2'
        else:
            self.log.debug("Uploading image to glance, assuming raw format")
            disk_format='raw'

        if self.credentials_token is None:
            auth_ref = keystone_authenticate(**self.credentials_dict)
            if is_ans1_token(auth_ref.auth_token):
                self.credentials_token = hashlib.md5(auth_ref.auth_token).hexdigest()
            else:
                self.credentials_token = auth_ref.auth_token

        provider_data['name']  = image_name
        provider_data['disk_format'] = disk_format

        image_id = glance_upload(input_image, self.credentials_token, **provider_data)

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
        for authprop in [ 'auth_url', 'password', 'tenant', 'username']:
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

            # Prevent double convert if the image is already qcow2
            if self.check_qcow_size(input_image) is not None:
                self.log.debug("No conversion require. Image already in qcow2 format.")
                return

            self.log.debug("Converting RAW image to compressed qcow2 format")
            rc = os.system("qemu-img convert -c -O qcow2 %s %s" %
                            (input_image, input_image + ".tmp.qcow2"))
            if rc == 0:
                os.unlink(input_image)
                os.rename(input_image + ".tmp.qcow2", input_image)
            else:
                raise ImageFactoryException("qemu-img convert failed!")

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

    # FIXME : cut/paste from RHEVMHelper.py, should refactor into a common utility class
    def check_qcow_size(self, filename):
        # Detect if an image is in qcow format
        # If it is, return the size of the underlying disk image
        # If it isn't, return None

        # For interested parties, this is the QCOW header struct in C
        # struct qcow_header {
        #    uint32_t magic;
        #    uint32_t version;
        #    uint64_t backing_file_offset;
        #    uint32_t backing_file_size;
        #    uint32_t cluster_bits;
        #    uint64_t size; /* in bytes */
        #    uint32_t crypt_method;
        #    uint32_t l1_size;
        #    uint64_t l1_table_offset;
        #    uint64_t refcount_table_offset;
        #    uint32_t refcount_table_clusters;
        #    uint32_t nb_snapshots;
        #    uint64_t snapshots_offset;
        # };

        # And in Python struct format string-ese
        qcow_struct=">IIQIIQIIQQIIQ" # > means big-endian
        qcow_magic = 0x514649FB # 'Q' 'F' 'I' 0xFB

        f = open(filename,"r")
        pack = f.read(struct.calcsize(qcow_struct))
        f.close()

        unpack = struct.unpack(qcow_struct, pack)

        if unpack[0] == qcow_magic:
            return unpack[5]
        else:
            return None
