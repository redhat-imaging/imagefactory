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
import stat
import zope
import oz.GuestFactory
import oz.TDL
import re
import guestfs
import libxml2
import traceback
import json
import ConfigParser
import subprocess
import logging
import shutil
from string import split
from time import *
from tempfile import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.BuildDispatcher import BuildDispatcher
from copy import deepcopy
from imgfac.CloudDelegate import CloudDelegate
from xml.etree.ElementTree import fromstring

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

        # First, we populate our target_image bodyfile with the original base image
        # which we do not want to modify in place
        self.activity("Copying BaseImage to modifiable TargetImage")
        self.log.debug("Copying base_image file (%s) to new target_image file (%s)" % (builder.base_image.data, builder.target_image.data))
        shutil.copy2(builder.base_image.data, builder.target_image.data)
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

        self.log.debug("init guestfs")
        g = guestfs.GuestFS ()

        self.log.debug("add input image")
        g.add_drive (self.image)

        self.log.debug("launch guestfs")
        g.launch ()

        g.mount_options("", "/dev/VolGroup00/LogVol00", "/")
        # F16 and upwards end up with boot on sda2 due to GRUB changes
        if (self.tdlobj.distro == 'Fedora') and (int(self.tdlobj.update) >= 16):
            g.mount_options("", "/dev/sda2", "/boot")
        else:
            g.mount_options("", "/dev/sda1", "/boot")

        self.log.info("Creating cloud-info file indicating target (%s)" % (self.target))
        tmpl = 'CLOUD_TYPE="%s"\n' % (self.target)
        g.write("/etc/sysconfig/cloud-info", tmpl)

        # In the cloud context we currently never need or want persistent net device names
        # This is known to break networking in RHEL/VMWare and could potentially do so elsewhere
        # Just delete the file to be safe
        if g.is_file("/etc/udev/rules.d/70-persistent-net.rules"):
            g.rm("/etc/udev/rules.d/70-persistent-net.rules")

        # Also clear out the MAC address this image was bound to.
        g.aug_init("/", 1)
        if g.aug_rm("/files/etc/sysconfig/network-scripts/ifcfg-eth0/HWADDR"):
            self.log.debug("Removed HWADDR from image's /etc/sysconfig/network-scripts/ifcfg-eth0")
            g.aug_save()
        else:
            self.log.debug("Failed to remove HWADDR from image's /etc/sysconfig/network-scripts/ifcfg-eth0")
        g.aug_close()

        g.sync ()
        g.umount_all ()

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
        # We now call the RHEVM push command from iwhd directly without making a REST call

        # BuildDispatcher is now the only location for the logic to map a provider to its data and target
        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("RHEV-M instance not found in local configuration file /etc/imagefactory/rhevm.json or as XML or JSON")

        #if provider_data['target'] != 'rhevm':
        #    raise ImageFactoryException("Got a non-rhevm target in the vsphere builder.  This should never happen.")

        self.generic_decode_credentials(credentials, provider_data, "rhevm")

        # Deal with case where these are not set in the config file
        # or are overridden via the credentials argument
        # note - rhevm external util wants no dashes
        provider_data['apiuser'] = self.username
        provider_data['apipass'] = self.password

        self.log.debug("Username: %s - Password: %s" % (self.username, self.password))

        # Fix some additional dashes
        # This is silly but I don't want to change the format at this point
        provider_data['nfsdir'] = provider_data['nfs-dir']
        provider_data['nfshost'] = provider_data['nfs-host']
        provider_data['nfspath'] = provider_data['nfs-path']
        provider_data['apiurl'] = provider_data['api-url']

        del provider_data['nfs-dir']
        del provider_data['nfs-host']
        del provider_data['nfs-path']
        del provider_data['api-url']

        #provider_data['site'] = provider_data['name']

        # We no longer need the name or target values in this dict and they may confuse the POST
        #del provider_data['name']
        #del provider_data['target']

        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.data

        # Make it readable by the KVM group - required for the way we currently do the push to
        # an export domain - Change group to 36 and make file group readable
        # Required by the way RHEV-M NFS pushes work
        # TODO: Look at how to fix this when we move RHEV-M push into Factory proper
        #       This is just messy
        os.chown(input_image, 0, 36)
        os.chmod(input_image, stat.S_IRUSR | stat.S_IRGRP)

        # This, it turns out, is the easiest way to give our newly created template the correct name
        image_link = "/tmp/" + str(self.new_image_id)
        os.symlink(input_image, image_link)

        # iwhd 0.99 and above expect this to be set
        # we default to 30 minutes as these copies can sometimes take a long time
        if not 'timeout' in provider_data:
            provider_data['timeout'] = 1800

        # Populate the last field we need in our JSON command file
        provider_data['image'] = image_link

        # Redact password when logging
        provider_data_log = deepcopy(provider_data)
        provider_data_log['apipass'] = "REDACTED"
        provider_json_log = json.dumps(provider_data_log, sort_keys=True, indent=4)
        self.log.debug("Produced provider json: \n%s" % (provider_json_log))

        # Shove into a named temporary file
        provider_json = json.dumps(provider_data, sort_keys=True, indent=4)
        json_file_object = NamedTemporaryFile()
        json_file_object.write(provider_json)
        json_file_object.flush()

        # TODO: Test for presence of this at the very start and fail right away if it is not there
        rhevm_push_cname = "/usr/bin/dc-rhev-image"
        rhevm_push_command = [ rhevm_push_cname, json_file_object.name ]
        self.log.debug("Executing external RHEV-M push command (%s)" % (str(rhevm_push_command)))

        (stdout, stderr, retcode) = subprocess_check_output(rhevm_push_command)
        json_file_object.close()
        os.unlink(image_link)

        self.log.debug("Command retcode %s" % (retcode))
        self.log.debug("Command stdout: (%s)" % (stdout))
        self.log.debug("Command stderr: (%s)" % (stderr))

        m = re.match("^IMAGE ([a-fA-F0-9-]+)", stdout)

        rhevm_uuid = None
        # I had no luck getting re.MULTILINE to work - so we loop
        for line in split(stdout, "\n"):
            m = re.match(r"IMAGE ([a-fA-F0-9-]+)", line)
            if m:
                rhevm_uuid =  m.group(1)
                break

        if rhevm_uuid is None:
            raise ImageFactoryException("Failed to extract RHEV-M UUID from command stdout: %s" % (stdout))

        self.log.debug("Extracted RHEVM UUID: %s " % (rhevm_uuid))

        # Create the provdier image
        metadata = dict(target_image=target_image_id, provider=provider_data['name'], icicle="none", target_identifier=rhevm_uuid, provider_account_identifier=self.username)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        self.percent_complete = 100

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
