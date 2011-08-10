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
import guestfs
import libxml2
import traceback
import pycurl
import json
import ConfigParser
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.VMWare import VMImport
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from VMDKstream import convert_to_stream

class Fedora_vsphere_Builder(BaseBuilder):
    """docstring for Fedora_vsphere_Builder"""
    zope.interface.implements(IBuilder)

    def __init__(self, template, target):
        super(Fedora_vsphere_Builder, self).__init__(template, target)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        # May not be necessary to do both of these
        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml)
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        # 18-Jul-2011 - Moved to constructor and modified to change TDL object name itself
        #   Oz now uses the tdlobject name property directly in several places so we must change it
        self.tdlobj.name = self.tdlobj.name + "-" + self.new_image_id

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
        self.log.debug("build_upload() called on Fedora_vsphere_Builder...")
        self.log.debug("Building for target %s with warehouse config %s" % (self.target, self.app_config['warehouse']))
        self.status="BUILDING"

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

        try:
            guest.cleanup_old_guest()
            guest.generate_install_media(force_download=False)
            self.percent_complete=10
        except:
            self.log_exc()
            self.status="FAILED"
            raise

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
                self.log_exc()
                guest.cleanup_old_guest()
                self.status="FAILED"
                raise
        finally:
            guest.cleanup_install()

        self.log.debug("Generated disk image (%s)" % (guest.diskimage))
        # OK great, we now have a customized KVM image
        # Now we do some target specific transformation

        # Add the cloud-info file
        self.modify_oz_filesystem()

        self.log.info("Transforming image for use on VMWare")
        self.vmware_transform_image()

        if (self.app_config['warehouse']):
            self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
            # TODO: Revisit target_parameters for different providers

            target_parameters="No target parameters for cloud type %s" % (self.target)

            self.store_image(build_id, target_parameters)
            self.log.debug("Image warehouse storage complete")
        self.percent_complete=100
        self.status="COMPLETED"

    def vmware_transform_image(self):
        # On entry the image points to our generic KVM raw image
        # Convert to stream-optimized VMDK and then update the image property
        target_image = self.app_config['imgdir'] + "/vmware-image-" + self.new_image_id + ".vmdk"
        self.log.debug("Converting raw kvm image (%s) to vmware stream-optimized image (%s)" % (self.image, target_image))
        convert_to_stream(self.image, target_image)
        self.log.debug("VMWare stream conversion complete")
        # Save the original image file name but update our property to point to new VMWare image
        # TODO: Delete the original image?
        self.original_image = self.image
        self.image = target_image

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

    def vmware_push_image_upload(self, target_image_id, provider, credentials):
        # Decode the config file, verify that the provider is in it - err out if not
        # TODO: Make file location CONFIG value
        cfg_file = open("/etc/vmware.json","r")
        vmware_json = cfg_file.read()
        local_vmware=json.loads(vmware_json)

        provider_data = None
        try:
            provider_data = local_vmware[provider]
        except KeyError:
            raise ImageFactoryException("VMWare instance (%s) not found in local configuraiton file /etc/vmware.json" % (provider))

        self.generic_decode_credentials(credentials, provider_data)

        # This is where the image should be after a local build
        input_image = self.app_config['imgdir'] + "/vmware-image-" + target_image_id + ".vmdk"
        # Grab from Warehouse if it isn't here
        self.retrieve_image(target_image_id, input_image)

        # Example of some JSON for westford_esx
        # {"westford_esx": {"api-url": "https://vsphere.virt.bos.redhat.com/sdk", "username": "Administrator", "password": "changeme",
        #       "datastore": "datastore1", "network_name": "VM Network" } }

        vm_name = "factory-image-" + self.new_image_id
        vm_import = VMImport(provider_data['api-url'], self.username, self.password)
        vm_import.import_vm(datastore=provider_data['datastore'], network_name = provider_data['network_name'],
                       name=vm_name, disksize_kb = (10*1024*1024 + 2 ), memory=512, num_cpus=1,
                       guest_id='otherLinux64Guest', imagefilename=input_image)

        # Create the provdier image
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=vm_name)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        self.percent_complete = 100


    def push_image_upload(self, target_image_id, provider, credentials):
        self.status="PUSHING"
        self.percent_complete=0
        try:
            self.vmware_push_image_upload(target_image_id, provider,
                                          credentials)
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
