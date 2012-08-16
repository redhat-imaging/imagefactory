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
import logging
import shutil
from xml.etree.ElementTree import fromstring
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from VSphereHelper import VSphereHelper
from imgfac.BuildDispatcher import BuildDispatcher
from VMDKstream import convert_to_stream
from imgfac.CloudDelegate import CloudDelegate

rhel5_module_script='''echo "alias scsi_hostadapter2 mptbase" >> /etc/modprobe.conf
echo "alias scsi_hostadapter3 mptspi" >> /etc/modprobe.conf
KERNEL=`grubby --default-kernel`
KERNELVERSION=`grubby --default-kernel | cut -f 2- -d "-"`
NEWINITRD="`grubby --info=$KERNEL | grep initrd | cut -f 2 -d "="`-vsphere"
mkinitrd $NEWINITRD $KERNELVERSION
grubby --add-kernel=$KERNEL --copy-default --make-default --initrd=$NEWINITRD --title="Red Hat Enterprise Linux Server ($KERNELVERSION) Image Factory vSphere module update"
rm /root/vsphere-module.sh'''

class vSphere(object):
    """docstring for Fedora_vsphere_Builder"""
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        super(vSphere, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

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

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        self.log.debug("Deleting vSphere image (%s)" % (self.builder.provider_image.identifier_on_provider))

        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("VMWare instance not found in local configuration file /etc/imagefactory/vsphere.json or as XML or JSON")
        self.generic_decode_credentials(credentials, provider_data, "vsphere")
        helper = VSphereHelper(provider_data['api-url'], self.username, self.password)
        # This call raises an exception on error
        helper.delete_vm(self.builder.provider_image.identifier_on_provider)

    def builder_cleanup(self):
        # Sub-classes may need an opportunity to do their own cleanup
        pass

    def modify_guest(self):
        pass

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_should_create_target_image() called on vSphere plugin - returning True')
        return True

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        tdlobj = oz.TDL.TDL(xmlstring=template.xml, rootpw_required=True)
        if tdlobj.distro == "RHEL-5":
            merge_content = { "commands": [ { "name": "execute-module-script", "type": "raw" , "command": "/bin/sh /root/vsphere-module.sh" } ],
                              "files" : [ { "name": "/root/vsphere-module.sh", "type": "raw", "file": rhel5_module_script } ] }
            try:
                builder.os_plugin.add_cloud_plugin_content(merge_content)
            except e:
                self.log.error("Failed to add RHEL-5 specific vSphere customization to cloud plugin tasks")
                raise

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in vSphere plugin')
        self.status="BUILDING"

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.target_image.identifier

        # TODO: More convenience vars - revisit
        self.template = template
        self.target = target
        self.builder = builder
        self.image = builder.target_image.data

        # This lets our logging helper know what image is being operated on
        self.active_image = self.builder.target_image

        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml, rootpw_required=True)
        # Add in target specific content
        #TODO - URGENT - make this work again
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

        # Add the cloud-info file
        self.modify_oz_filesystem()

        self.log.info("Transforming image for use on VMWare")
        self.vmware_transform_image()

        self.percent_complete=100
        self.status="COMPLETED"

    def vmware_transform_image(self):
        # On entry the image points to our generic KVM raw image
        # Convert to stream-optimized VMDK and then update the image property
        target_image = self.image + ".tmp.vmdk"
        self.log.debug("Converting raw kvm image (%s) to vmware stream-optimized image (%s)" % (self.image, target_image))
        convert_to_stream(self.image, target_image)
        self.log.debug("VMWare stream conversion complete")
        os.unlink(self.image)
        os.rename(self.image + ".tmp.vmdk", self.image)

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
        self.log.info('push_image_to_provider() called in vSphere')

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier

        self.tdlobj = oz.TDL.TDL(xmlstring=builder.target_image.template, rootpw_required=True)
        self.builder = builder
        self.active_image = self.builder.provider_image
        self.push_image(target_image, provider, credentials)

    def push_image(self, target_image_id, provider, credentials):
        try:
            self.push_image_upload(target_image_id, provider, credentials)
        except:
            self.log_exc()
            self.status="FAILED"

    def vmware_push_image_upload(self, target_image_id, provider, credentials):
        # BuildDispatcher is now the only location for the logic to map a provider to its data and target
        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data is None:
            raise ImageFactoryException("VMWare instance not found in local configuration file /etc/imagefactory/vsphere.json or as XML or JSON")

        self.generic_decode_credentials(credentials, provider_data, "vsphere")

        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.data

        # Example of some JSON for westford_esx
        # {"westford_esx": {"api-url": "https://vsphere.virt.bos.redhat.com/sdk", "username": "Administrator", "password": "changeme",
        #       "datastore": "datastore1", "network_name": "VM Network" } }

        vm_name = "factory-image-" + self.new_image_id
        helper = VSphereHelper(provider_data['api-url'], self.username, self.password)
        helper.create_vm(input_image, vm_name, provider_data['compute_resource'], provider_data['datastore'], 
                         str(10*1024*1024 + 2) + "KB", [ { "network_name": provider_data['network_name'], "type": "VirtualE1000"} ], 
                         "512MB", 1, 'otherLinux64Guest')
        self.builder.provider_image.identifier_on_provider = vm_name
        self.builder.provider_account_identifier = self.username
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
