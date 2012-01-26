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
import oz.GuestFactory
import oz.TDL
import os
import shutil
import guestfs
import traceback
import pycurl
import ConfigParser
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder

class Fedora_condorcloud_Builder(BaseBuilder):
    """docstring for Fedora_condorcloud_Builder"""
    zope.interface.implements(IBuilder)

    def __init__(self, template, target, config_block = None):
        super(Fedora_condorcloud_Builder, self).__init__(template, target)
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
        self.log.debug("build_upload() called on Fedora_condorcloud_Builder...")
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
        guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"
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

        if (self.app_config['warehouse']):
            self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
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
            self.status="PUSHING"
            self.percent_complete=0
            self.condorcloud_push_image_upload(target_image_id, provider,
                                               credentials)
        except:
            self.log_exc()
            self.status="FAILED"
            raise
        self.status="COMPLETED"

    def condorcloud_push_image_upload(self, target_image_id, provider, credentials):
        # condorcloud is a simple local cloud instance using Condor
        # The push action in this case simply requires that we copy the image to a known
        # location and then move it to another known loacation

        # This is where the image should be after a local build
        input_image = self.app_config["imgdir"] + "/base-image-" + target_image_id + ".dsk"
        # Grab from Warehouse if it isn't here
        self.retrieve_image(target_image_id, input_image)

        storage = "/home/cloud/images"
        if not os.path.isdir(storage):
            raise ImageFactoryException("Storage dir (%s) for condorcloud is not present" % (storage))

        staging = storage + "/staging"
        if not os.path.isdir(staging):
            raise ImageFactoryException("Staging dir (%s) for condorcloud is not present" % (staging))

        image_base = "/condorimage-" + self.new_image_id + ".img"
        staging_image = staging + image_base

        # Copy to staging location
        # The os-native cp command in Fedora and RHEL does sparse file detection which is good
        self.log.debug("Copying (%s) to (%s)" % (input_image, staging_image))
        shutil.copyfile(input_image, staging_image)

        # Retrieve original XML and write it out to the final dir
        image_xml_base="/condorimage-" + self.new_image_id + ".xml"
        image_xml_file= storage + image_xml_base

        image_metadata = self.warehouse.metadata_for_id_of_type(("target_parameters",), target_image_id, "target_image")
        self.log.debug("Got metadata output of: %s", repr(image_metadata))
        libvirt_xml = image_metadata["target_parameters"]

        f = open(image_xml_file, 'w')
        f.write(libvirt_xml)
        f.close()

        # Now move the image file to the final location
        final_image = storage + image_base
        self.log.debug("Moving (%s) to (%s)" % (staging_image, final_image))
        shutil.move(staging_image, final_image)

        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=self.new_image_id)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        self.percent_complete = 100

    def retrieve_image(self, target_image_id, local_image_file):
        # Grab target_image_id from warehouse unless it is already present as local_image_file
        # TODO: Use Warehouse class instead
        if not os.path.isfile(local_image_file):
            if not (self.app_config['warehouse']):
                raise ImageFactoryException("No warehouse configured - cannot retrieve image")
            url = "%simages/%s" % (self.app_config['warehouse'], target_image_id)
            self.log.debug("Image %s not present locally - Fetching from %s" % (local_image_file, url))
            fp = open(local_image_file, "wb")
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, url)
            curl.setopt(pycurl.WRITEDATA, fp)
            curl.perform()
            curl.close()
            fp.close()
        else:
            self.log.debug("Image file %s already present - skipping warehouse download" % (local_image_file))

    def abort(self):
        pass

    rc_local_all="""
# This conditionally runs Audrey if it exists
[ -f /usr/bin/audrey ] && /usr/bin/audrey
"""
