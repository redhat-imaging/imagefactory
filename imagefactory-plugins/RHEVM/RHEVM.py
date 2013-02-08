#
#   Copyright 2011 Red Hat, Inc.
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

import os
import zope
import oz.GuestFactory
import oz.TDL
import guestfs
import libxml2
import traceback
import json
import ConfigParser
import subprocess
import logging
from time import *
from tempfile import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist, create_cloud_info
from xml.etree.ElementTree import fromstring
from RHEVMHelper import RHEVMHelper


def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    stdout, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = ' '.join(*popenargs)
        raise ImageFactoryException("'%s' failed(%d): %s\nstdout: %s" % (cmd, retcode, stderr, stdout))
    return (stdout, stderr, retcode)


class RHEVM(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        super(RHEVM, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_should_create_target_image() called on RHEVM plugin - returning True')
        return True


    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        # Nothing really to do here
        pass

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())

    def build_image(self, build_id=None):
        try:
            self.build_upload(build_id)
        except:
            self.log_exc()
            self.status="FAILED"
            raise

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in RHEVM plugin')
        self.status="BUILDING"

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.target_image.identifier

        # TODO: More convenience vars - revisit
        self.template = template
        self.target = target
        self.builder = builder

        # This lets our logging helper know what image is being operated on
        self.active_image = self.builder.target_image

        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml, rootpw_required=True)

        # Add in target specific content
        #TODO-URGENT: Work out how to do this in the new framework
        #self.add_target_content()

        # Oz assumes unique names - TDL built for multiple backends guarantees
        # they are not unique.  We don't really care about the name so just
        # force uniqueness
        #  Oz now uses the tdlobject name property directly in several places
        # so we must change it
        self.tdlobj.name = "factory-build-" + self.new_image_id

        # populate a config object to pass to OZ; this allows us to specify our
        # own output dir but inherit other Oz behavior
        oz_config = ConfigParser.SafeConfigParser()
        oz_config.read("/etc/oz/oz.cfg")
        oz_config.set('paths', 'output_dir', self.app_config["imgdir"])

        # In contrast to our original builders, we enter the cloud plugins with a KVM file already
        # created as the base_image.  As a result, all the Oz building steps are gone (and can be found
        # in the OS plugin(s)

        # OS plugin has already provided the initial file for us to work with
        # which we can currently assume is a raw KVM compatible image
        self.image = builder.target_image.data

        # Add the cloud-info file
        self.modify_oz_filesystem()

        # Finally, if our format is qcow2, do the transformation here
        if ("rhevm_image_format" in self.app_config) and  (self.app_config["rhevm_image_format"] == "qcow2"):
            self.log.debug("Converting RAW image to compressed qcow2 format")
            # TODO: When RHEV adds support, use the -c option to compress these images to save space
            qemu_img_cmd = [ "qemu-img", "convert", "-O", "qcow2", self.image, self.image + ".tmp.qcow2" ]
            (stdout, stderr, retcode) = subprocess_check_output(qemu_img_cmd)
            os.unlink(self.image)
            os.rename(self.image + ".tmp.qcow2", self.image)

        self.percent_complete=100
        self.status="COMPLETED"

    def modify_oz_filesystem(self):
        self.log.debug("Doing further Factory specific modification of Oz image")
        guestfs_handle = launch_inspect_and_mount(self.builder.target_image.data)
        remove_net_persist(guestfs_handle)
        create_cloud_info(guestfs_handle, self.target)
        shutdown_and_close(guestfs_handle)

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        self.log.info('push_image_to_provider() called in RHEVM')

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier

        self.tdlobj = oz.TDL.TDL(xmlstring=builder.target_image.template, rootpw_required=True)
        self.builder = builder
        self.active_image = self.builder.provider_image
        self.push_image(target_image, provider, credentials)

    def push_image(self, target_image_id, provider, credentials):
        try:
            self.status = "PUSHING"
            self.percent_complete = 0
            self.rhevm_push_image_upload(target_image_id, provider, credentials)
        except:
            self.log_exc()
            self.status="FAILED"
            raise
        self.status = "COMPLETED"

    def rhevm_push_image_upload(self, target_image_id, provider, credentials):
        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("RHEV-M instance not found in XML or JSON provided")

        self.generic_decode_credentials(credentials, provider_data, "rhevm")

        self.log.debug("Username: %s" % (self.username))

        helper = RHEVMHelper(url=provider_data['api-url'], username=self.username, password=self.password)
        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.data
        rhevm_uuid = helper.import_template(input_image, provider_data['nfs-host'], provider_data['nfs-path'], 
                                            provider_data['nfs-dir'], provider_data['cluster'], ovf_name=str(self.new_image_id), 
                                            ovf_desc = "Template name (%s) from base image (%s)" % (self.tdlobj.name, str(self.builder.base_image.identifier)) )

        if rhevm_uuid is None:
            raise ImageFactoryException("Failed to obtain RHEV-M UUID from helper")

        self.log.debug("New RHEVM Template UUID: %s " % (rhevm_uuid))

        self.builder.provider_image.identifier_on_provider = rhevm_uuid
        self.builder.provider_image.provider_account_identifier = self.username
        self.percent_complete = 100

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        self.log.debug("Deleting RHEVM template (%s)" % (self.builder.provider_image.identifier_on_provider))
        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("RHEV-M instance not found in XML or JSON provided")

        self.generic_decode_credentials(credentials, provider_data, "rhevm")

        self.log.debug("Username: %s" % (self.username))

        helper = RHEVMHelper(url=provider_data['api-url'], username=self.username, password=self.password)
        if not helper.delete_template(self.builder.provider_image.identifier_on_provider):
            raise ImageFactoryException("Delete of template failed")


    def generic_decode_credentials(self, credentials, provider_data, target):
        # convenience function for simple creds (rhev-m and vmware currently)
        doc = libxml2.parseDoc(credentials)

        self.username = None
        _usernodes = doc.xpathEval("//provider_credentials/%s_credentials/username" % (target))
        if len(_usernodes) > 0:
            self.username = _usernodes[0].content
        else:
            try:
                self.username = provider_data['username']
            except KeyError:
                raise ImageFactoryException("No username specified in config file or in push call")
        self.provider_account_identifier = self.username

        _passnodes = doc.xpathEval("//provider_credentials/%s_credentials/password" % (target))
        if len(_passnodes) > 0:
            self.password = _passnodes[0].content
        else:
            try:
                self.password = provider_data['password']
            except KeyError:
                raise ImageFactoryException("No password specified in config file or in push call")

        doc.freeDoc()

    def get_dynamic_provider_data(self, provider):
        # Get provider details for RHEV-M or VSphere
        # First try to interpret this as an ad-hoc/dynamic provider def
        # If this fails, try to find it in one or the other of the config files
        # If this all fails return None
        # We use this in the builders as well so I have made it "public"

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

    def abort(self):
        pass
