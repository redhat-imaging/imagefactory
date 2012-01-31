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
import re
import guestfs
import libxml2
import traceback
import json
import ConfigParser
import subprocess
from string import split
from time import *
from tempfile import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.BuildDispatcher import BuildDispatcher
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from copy import deepcopy

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


class Fedora_rhevm_Builder(BaseBuilder):
    """docstring for Fedora_rhevm_Builder"""
    zope.interface.implements(IBuilder)

    def __init__(self, template, target, config_block = None):
        super(Fedora_rhevm_Builder, self).__init__(template, target, config_block)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']

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

    def build_upload(self, build_id):
        self.log.debug("build_upload() called on Fedora_rhevm_Builder...")
        self.log.debug("Building for target %s with warehouse config %s" % (self.target, self.app_config['warehouse']))
        self.status="BUILDING"

        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml, rootpw_required=True)
        # Add in target specific content
        self.add_target_content()
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

        guest = oz.GuestFactory.guest_factory(self.tdlobj, oz_config, None)
        guest.diskimage = self.app_config["imgdir"] + "/rhevm-image-" + self.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees
        # they are not unique.  We don't really care about the name so just
        # force uniqueness
        guest.name = guest.name + "-" + self.new_image_id

        guest.cleanup_old_guest()
        self.threadsafe_generate_install_media(guest)
        self.percent_complete=10

        # We want to save this later for use by RHEV-M and Condor clouds
        libvirt_xml=""

        try:
            guest.generate_diskimage()
            try:
                # TODO: If we already have a base install reuse it
                #  subject to some rules about updates to underlying repo
                self.log.debug("Doing base install via Oz")
                libvirt_xml = guest.install(self.app_config["timeout"])
                self.image = guest.diskimage
                self.log.debug("Base install complete - Doing customization and ICICLE generation")
                self.percent_complete = 30
                self.output_descriptor = guest.customize_and_generate_icicle(libvirt_xml)
                self.log.debug("Customization and ICICLE generation complete")
                self.percent_complete = 50
            except:
                guest.cleanup_old_guest()
                raise
        finally:
            guest.cleanup_install()

        self.log.debug("Generated disk image (%s)" % (guest.diskimage))
        # OK great, we now have a customized KVM image
        # Now we do some target specific transformation

        # Add the cloud-info file
        self.modify_oz_filesystem()

        # Finally, if our format is qcow2, do the transformation here
        if ("rhevm_image_format" in self.app_config) and  (self.app_config["rhevm_image_format"] == "qcow2"):
            self.log.debug("Converting RAW image to compressed qcow2 format")
            qemu_img_cmd = [ "qemu-img", "convert", "-c", "-O", "qcow2", guest.diskimage, guest.diskimage + ".tmp.qcow2" ]
            (stdout, stderr, retcode) = subprocess_check_output(qemu_img_cmd)
            os.unlink(guest.diskimage)
            os.rename(guest.diskimage + ".tmp.qcow2", guest.diskimage)

        if (self.app_config['warehouse']):
            self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
            # TODO: Revisit target_parameters for different providers

            target_parameters=libvirt_xml

            self.store_image(build_id, target_parameters)
            self.log.debug("Image warehouse storage complete")
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

        self.log.info("Updating rc.local with Audrey conditional")
        g.write("/tmp/rc.local", self.rc_local_all)
        g.sh("cat /tmp/rc.local >> /etc/rc.local")
        # It's possible the above line actually creates rc.local
        # Make sure it is executable
        g.sh("chmod a+x /etc/rc.local")

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
        provider_data = BuildDispatcher().get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("RHEV-M instance not found in local configuration file /etc/imagefactory/rhevm.json or as XML or JSON")

        if provider_data['target'] != 'rhevm':
            raise ImageFactoryException("Got a non-rhevm target in the vsphere builder.  This should never happen.")

        self.generic_decode_credentials(credentials, provider_data)

        # Deal with case where these are not set in the config file
        # or are overridden via the credentials argument
        # note - rhevm external util wants no dashes
        provider_data['apiuser'] = self.username
        provider_data['apipass'] = self.password

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

        # This is where the image should be after a local build
        input_image = self.app_config['imgdir'] + "/rhevm-image-" + target_image_id + ".dsk"
        # Grab from Warehouse if it isn't here
        self.retrieve_image(target_image_id, input_image)

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

    def generic_decode_credentials(self, credentials, provider_data):
        # convenience function for simple creds (rhev-m and vmware currently)
        doc = libxml2.parseDoc(credentials)

        self.username = None
        _usernodes = doc.xpathEval("//provider_credentials/%s_credentials/username" % (self.target))
        if len(_usernodes) > 0:
            self.username = _usernodes[0].content
        else:
            try:
                self.username = provider_data['username']
            except KeyError:
                raise ImageFactoryException("No username specified in config file or in push call")
        self.provider_account_identifier = self.username

        _passnodes = doc.xpathEval("//provider_credentials/%s_credentials/password" % (self.target))
        if len(_passnodes) > 0:
            self.password = _passnodes[0].content
        else:
            try:
                self.password = provider_data['password']
            except KeyError:
                raise ImageFactoryException("No password specified in config file or in push call")

        doc.freeDoc()

    def abort(self):
        pass

    rc_local_all="""
# This conditionally runs Audrey if it exists
[ -f /usr/bin/audrey ] && /usr/bin/audrey
"""
