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

import zope
import oz.Fedora
import oz.TDL
import re
import guestfs
import libxml2
import traceback
import json
import ConfigParser
from time import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder

class Fedora_rhevm_Builder(BaseBuilder):
    """docstring for Fedora_rhevm_Builder"""
    zope.interface.implements(IBuilder)

    def __init__(self, template, target):
        super(Fedora_rhevm_Builder, self).__init__(template, target)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        # May not be necessary to do both of these
        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml)
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        # 18-Jul-2011 - Moved to constructor and modified to change TDL object name itself
        #   Oz now uses the tdlobject name property directly in several places so we must change it
        self.tdlobj.name = self.tdlobj.name + "-" + self.new_image_id

    def init_guest(self):
        # populate a config object to pass to OZ
        # This allows us to specify our own output dir but inherit other Oz behavior
        # TODO: Messy?
        config_file = "/etc/oz/oz.cfg"
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)
        config.set('paths', 'output_dir', self.app_config["imgdir"])
        self.guest = oz.Fedora.get_class(self.tdlobj, config, None)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())

    def build_image(self, build_id=None):
        try:
            self.init_guest()
            self.build_upload(build_id)
        except:
            self.log_exc()
            self.status="FAILED"
            raise

    def build_upload(self, build_id):
        self.log.debug("build_upload() called on Fedora_rhevm_Builder...")
        self.log.debug("Building for target %s with warehouse config %s" % (self.target, self.app_config['warehouse']))
        self.status="BUILDING"
        try:
            self.guest.cleanup_old_guest()
            self.guest.generate_install_media(force_download=False)
            self.percent_complete=10
        except:
            self.log_exc()
            self.status="FAILED"
            raise

        # We want to save this later for use by RHEV-M and Condor clouds
        libvirt_xml=""

        try:
            self.guest.generate_diskimage()
            try:
                # TODO: If we already have a base install reuse it
                #  subject to some rules about updates to underlying repo
                self.log.debug("Doing base install via Oz")
                libvirt_xml = self.guest.install(self.app_config["timeout"])
                self.image = self.guest.diskimage
                self.log.debug("Base install complete - Doing customization and ICICLE generation")
                self.percent_complete = 30
                self.output_descriptor = self.guest.customize_and_generate_icicle(libvirt_xml)
                self.log.debug("Customization and ICICLE generation complete")
                self.percent_complete = 50
            except:
                self.log_exc()
                self.guest.cleanup_old_guest()
                self.status="FAILED"
                raise
        finally:
            self.guest.cleanup_install()

        self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
        # OK great, we now have a customized KVM image
        # Now we do some target specific transformation

        # Add the cloud-info file
        self.modify_oz_filesystem()

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
        g.mount_options("", "/dev/sda1", "/boot")

        self.log.info("Creating cloud-info file indicating target (%s)" % (self.target))
        tmpl = 'CLOUD_TYPE="%s"\n' % (self.target)
        g.write("/etc/sysconfig/cloud-info", tmpl)

        # EC2 does this in its modify step - all other upload clouds get it here
        if self.target != "ec2":
            self.log.info("Updating rc.local with Audrey conditional")
            g.write("/tmp/rc.local", self.rc_local_all)
            g.sh("cat /tmp/rc.local >> /etc/rc.local")

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
            self.push_image_upload(target_image_id, provider, credentials)
        except:
            self.log_exc()
            self.status="FAILED"

    def rhevm_push_image_upload(self, target_image_id, provider, credentials):
        # ****** IMPORTANT NOTE ********
        # This is currently the only cloud for which we delegate the push
        # function to the Warehouse
        # This has proven to be a debugging challenge and we may, in future,
        # pull this back into Factory

        # Decode the config file, verify that the provider is in it - err out if not
        # TODO: Make file location CONFIG value
	file = open("/etc/rhevm.json","r")
	rhevm_json = file.read()
	local_rhevm=json.loads(rhevm_json)

        post_data = None
        try:
            post_data = local_rhevm[provider]
        except KeyError:
            raise ImageFactoryException("RHEV-M instance (%s) not found in local configuraiton file /etc/rhevm.json" % (provider))

        self.generic_decode_credentials(credentials, post_data)

        # Deal with case where these are not set in the config file
        # or are overridden via the credentials argument
        post_data['api-key'] = self.username
        post_data['api-secret'] = self.password

        post_data['op'] = "register"
        post_data['site'] = provider

        response = self.warehouse.post_on_object_with_id_of_type(target_image_id, "target_image", post_data)

        m = re.match("^OK ([a-fA-F0-9-]+)", response)
        rhevm_uuid = None
        if m:
            rhevm_uuid = m.group(1)
        else:
            raise ImageFactoryException("Failed to extract RHEV-M UUID from warehouse POST reponse: %s" % (response))

	self.log.debug("Extracted RHEVM UUID: %s " % (rhevm_uuid))

        # Create the provdier image
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=rhevm_uuid)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        self.percent_complete = 100


    def push_image_upload(self, target_image_id, provider, credentials):
        self.status="PUSHING"
        self.percent_complete=0
        try:
            self.rhevm_push_image_upload(target_image_id, provider, credentials)
        except:
            self.log_exc()
            self.status="FAILED"
            raise
        self.status="COMPLETED"

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
