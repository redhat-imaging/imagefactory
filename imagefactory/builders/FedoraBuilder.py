#
# Copyright (C) 2010-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import logging
import zope
import oz.Fedora
import oz.TDL
import subprocess
import os
import re
import sys
import guestfs
import string
import libxml2
import httplib2
import traceback
import pycurl
import json
from cloudservers import CloudServers
import ConfigParser
import boto.ec2
from time import *
from tempfile import *
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageFactoryException import ImageFactoryException
from imagefactory.VMWare import VMImport
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from boto.s3.connection import S3Connection
from boto.s3.connection import Location
from boto.exception import *
from boto.ec2.blockdevicemapping import EBSBlockDeviceType, BlockDeviceMapping
from VMDKstream import convert_to_stream

# Boto is very verbose - shut it up
logging.getLogger('boto').setLevel(logging.INFO)

def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    stdout, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = ' '.join(*popenargs)
        raise ImageFactoryException("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)

# This allows us to use the utility methods in Oz without errors due to lack of libvirt
class FedoraRemoteGuest(oz.Fedora.FedoraGuest):
    def __init__(self, tdl, config, auto, nicmodel, haverepo, diskbus,
                 brokenisomethod):
        # The debug output in the Guest parent class needs this property to exist
        self.host_bridge_ip = "0.0.0.0"
        oz.Fedora.FedoraGuest.__init__(self, tdl, config, auto, nicmodel, haverepo, diskbus,
                 brokenisomethod)

    def connect_to_libvirt(self):
        pass


class FedoraBuilder(BaseBuilder):
    """docstring for FedoraBuilder"""
    zope.interface.implements(IBuilder)

    # Reference vars - don't change these
    # EC2 is a special case as it can be either and is set in the config file
    upload_clouds = [ "rhevm", "vsphere", "condorcloud" ]
    nonul_clouds = [ "rackspace", "gogrid" ]

    def __init__(self, template, target):
        super(FedoraBuilder, self).__init__(template, target)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        # May not be necessary to do both of these
        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml)

    def init_guest(self, guesttype):
        # populate a config object to pass to OZ
        # This allows us to specify our own output dir but inherit other Oz behavior
        # TODO: Messy?
        config_file = "/etc/oz/oz.cfg"
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)
        config.set('paths', 'output_dir', self.app_config["imgdir"])
        if guesttype == "local":
            self.guest = oz.Fedora.get_class(self.tdlobj, config, None)
        else:
            self.guest = FedoraRemoteGuest(self.tdlobj, config, None, "virtio", True, "virtio", True)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + self.new_image_id

    def log_exc(self, location = None, message = None):
        if message:
            self.log.debug(message)
        elif location:
            self.log.debug("Exception encountered in (%s)" % location)
        else:
            self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())


    def build_image(self, build_id=None):
        try:
            if  self.target in self.upload_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "upload"):
                self.init_guest("local")
                self.build_upload(build_id)
            elif self.target in self.nonul_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "snapshot"):
                # No actual need to have a guest object here so don't bother
                self.build_snapshot(build_id)
            else:
                raise ImageFactoryException("Invalid build target (%s) passed to build_image()" % (self.target))
        except:
            self.log_exc()
            self.status="FAILED"
            raise

    def build_snapshot(self, build_id):
        # All we need do here is store the relevant bits in the Warehouse
        self.log.debug("Building Linux for non-upload cloud (%s)" % (self.target))
        self.image = "%s/placeholder-linux-image-%s" % (self.app_config['imgdir'], self.new_image_id)
        image_file = open(self.image, 'w')
        image_file.write("Placeholder for non upload cloud Linux image")
        image_file.close()
        self.output_descriptor = None
        self.log.debug("Storing placeholder object for non upload cloud image")
        self.store_image(build_id)
        self.percent_complete = 100
        self.status = "COMPLETED"
        self.log.debug("Completed placeholder warehouse object for linux non-upload image...")
        sleep(5)

    def build_upload(self, build_id):
        self.log.debug("build_upload() called on FedoraBuilder...")
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
                self.log.debug("Base install complete - Doing customization")
                self.percent_complete=30
                self.guest.customize(libvirt_xml)
                self.log.debug("Customization complete")
                self.percent_complete=50
                self.log.debug("Generating ICICLE")
                self.output_descriptor = self.guest.generate_icicle(libvirt_xml)
                self.log.debug("ICICLE generation complete")
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
        self.tag_oz_filesystem()

        if self.target == "ec2":
            self.log.info("Transforming image for use on EC2")
            self.ec2_transform_image()
        elif self.target == "vsphere":
            self.log.info("Transforming image for use on VMWare")
            self.vmware_transform_image()

        if (self.app_config['warehouse']):
            self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
            # TODO: Revisit target_parameters for different providers

            if self.target in [ "condorcloud", "rhevm" ]:
                # TODO: Prune any unneeded elements
                target_parameters=libvirt_xml
            else:
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

    def ec2_transform_image(self):
        # On entry the image points to our generic KVM image - we transform image
        #  and then update the image property to point to our new image and update
        #  the metadata
        try:
            output_dir=self.app_config['imgdir']
            self.ec2_copy_filesystem(output_dir)
            self.ec2_modify_filesystem()
        except:
            self.log_exc()
            self.status="FAILED"
            raise

    def tag_oz_filesystem(self):
        self.log.debug("Adding cloud-info to local image")

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

        g.sync ()
        g.umount_all ()


    def ec2_copy_filesystem(self, output_dir):
        target_image=output_dir + "/ec2-image-" + self.new_image_id + ".dsk"

        self.log.debug("init guestfs")
        g = guestfs.GuestFS ()

        self.log.debug("add input image")
        g.add_drive (self.image)

        self.log.debug("creat target image")
        f = open (target_image, "w")
        # TODO: Can this be larger, smaller - should it be?
        f.truncate (10000 * 1024 * 1024)
        f.close ()
        g.add_drive(target_image)

        self.log.debug("creat tmp image")
        # We need a small FS to mount target and dest on - make image file for it
        # TODO: Use Marek's create mount point trick instead of a temp file
        tmp_image_file = "/tmp/tmp-img-" + self.new_image_id
        f = open (tmp_image_file, "w")
        f.truncate (10 * 1024 * 1024)
        f.close
        g.add_drive(tmp_image_file)

        self.log.debug("launch guestfs")
        g.launch ()

        # TODO: Re-enable this?
        # Do inspection here, as libguestfs prefers we do it before mounting anything
        #inspection = g.inspect_os()
        # This assumes, I think reasonably, only one OS on the disk image provided by Oz
        #rootdev = inspection[0]

        # At this point sda is original image - sdb is blank target - sdc is small helper
        self.log.info("Making filesystems for EC2 transform")
        # TODO: Make different FS types depending on the type of the original root fs
        g.mkfs ("ext3", "/dev/sdb")
        g.set_e2label ("/dev/sdb", "/")
        g.mkfs ("ext3", "/dev/sdc")
        self.log.info("Done")
        g.mount_options ("", "/dev/sdc", "/")
        g.mkdir("/in")
        g.mkdir("/out")
        # Yes, this looks odd but it is the easiest way to use cp_a from guestfs
        #  because we cannot use wildcards directly with guestfs
        g.mkdir("/out/in")
        g.mount_ro ("/dev/VolGroup00/LogVol00", "/in")
        g.mount_ro ("/dev/sda1", "/in/boot")
        g.mount_options ("", "/dev/sdb", "/out/in")

        self.log.info("Copying image contents to EC2 flat filesystem")
        g.cp_a("/in/", "/out")
        self.log.info("Done")

        g.sync ()
        g.umount_all ()
        os.unlink(tmp_image_file)

        # Save the original image file name but update our property to point to new EC2 image
        # TODO: Delete the original image?
        self.original_image = self.image
        self.image = target_image

    def ec2_modify_filesystem(self):
        # Modifications
        # Many of these are more or less directly ported from BoxGrinder
        # Boxgrinder is written and maintained by Marek Goldmann and can be found at:
        # http://boxgrinder.org/

        # TODO: This would be safer and more robust if done within the running modified
        # guest - in this would require tighter Oz integration

        g = guestfs.GuestFS ()

        g.add_drive(self.image)
        g.launch ()

        # Do inspection here, as libguestfs prefers we do it before mounting anything
        inspection = g.inspect_os()
        # This should always be /dev/vda or /dev/sda but we do it anyway to be safe
        osroot = inspection[0]

        # eg "fedora"
        distro = g.inspect_get_distro(osroot)
        arch = g.inspect_get_arch(osroot)
        major_version = g.inspect_get_major_version(osroot)
        minor_version = g.inspect_get_minor_version(osroot)

        self.log.debug("distro: %s - arch: %s - major: %s - minor %s" % (distro, arch, major_version, minor_version))

        g.mount_options ("", osroot, "/")

        self.log.info("Modifying flat FS contents to be EC2 compatible")

        self.log.info("Disabling SELINUX")
        tmpl = '# Factory Disabled SELINUX - sorry\nSELINUX=permissive\nSELINUXTYPE=targeted\n'
        g.write("/etc/sysconfig/selinux", tmpl)

        # Make a /data directory for 64 bit hosts
        # Ephemeral devs come pre-formatted from AWS - weird
        if arch == "x86_64":
            self.log.info("Making data directory")
            g.mkdir("/data")

        # BG - Upload one of two templated fstabs
        # Input - root device name
        # PREFIX is xv unless we are dealing with RHEL5, which is interesting - must mean we hack
        # the pv kernel for RHEL5 to present PV block devices as sd*.  Is this true?
        # UPDATE: clalance indicates that this works but is not advisable
        # the xv devices are present in RHEL5, work, and should be used
        # Filesystem type - ext3 for now everywhere
        # TODO: Match OS default behavior and/or what is found in the existing image
        prefix="xv"
        fstype="ext3"

        self.log.info("Modifying and uploading fstab")
        # Make arch conditional
        if arch == "x86_64":
            tmpl=self.fstab_64bit
        else:
            tmpl=self.fstab_32bit

        tmpl = string.replace(tmpl, "#DISK_DEVICE_PREFIX#", prefix)
        tmpl = string.replace(tmpl, "#FILESYSTEM_TYPE#", fstype)
        g.write("/etc/fstab", tmpl)

        # BG - Enable networking
        # Upload a known good ifcfg-eth0 and then chkconfig on networking
        self.log.info("Enabling networking and uploading ifcfg-eth0")
        g.sh("/sbin/chkconfig network on")
        g.write("/etc/sysconfig/network-scripts/ifcfg-eth0", self.ifcfg_eth0)

        # Disable first boot - this slows things down otherwise
        if g.is_file("/etc/init.d/firstboot"):
            g.sh("/sbin/chkconfig firstboot off")

        # BG - Upload rc.local extra content
        # Again, this uses a static copy - this bit is where the ssh key is downloaded
        # TODO: Is this where we inject puppet?
        # TODO - Possibly modify the key injection from rc_local to be only non-root
        #  and add a special user to sudoers - this is what BG has evolved to do
        self.log.info("Updating rc.local for key injection")
        g.write("/tmp/rc.local", self.rc_local)
        g.sh("cat /tmp/rc.local >> /etc/rc.local")

        # Install menu list
        # Derive the kernel version from the last element of ls /lib/modules and some
        # other magic - look at linux_helper for details

        # Look at /lib/modules and assume that the last kernel listed is the version we use
        self.log.info("Modifying and updating menu.lst")
        kernel_versions = g.ls("/lib/modules")
        kernel_version = None
        if (distro == "rhel") and (major_version == 5):
            xenre = re.compile("xen$")
            for kern in kernel_versions:
                if xenre.search(kern):
                    kernel_version = kern
        elif (len(kernel_versions) > 1) and (arch == "i386"):
            paere = re.compile("PAE$")
            for kern in kernel_versions:
                if paere.search(kern):
                    kernel_version = kern
        else:
            kernel_version = kernel_versions[len(kernel_versions)-1]

        if not kernel_version:
            raise ImageFactoryException("Unable to extract kernel version")

        self.log.debug("Using kernel version: %s" % (kernel_version))


        # We could deduce this from version but it's easy to inspect
        bootramfs = int(g.sh("ls -1 /boot | grep initramfs | wc -l"))
        ramfs_prefix = "initramfs" if bootramfs > 0 else "initrd"

        name="Image Factory EC2 boot - kernel: " + kernel_version

        if (distro == "rhel") and (major_version == 5):
            g.sh("/sbin/mkinitrd -f -v --preload xenblk --preload xennet /boot/initrd-%s.img %s" % (kernel_version))

        tmpl = self.menu_lst
        tmpl = string.replace(tmpl, "#KERNEL_VERSION#", kernel_version)
        tmpl = string.replace(tmpl, "#KERNEL_IMAGE_NAME#", ramfs_prefix)
        tmpl = string.replace(tmpl, "#TITLE#", name)

        g.write("/boot/grub/menu.lst", tmpl)

        # F14 bug fix
        # This fixes issues with Fedora 14 on EC2: https://bugzilla.redhat.com/show_bug.cgi?id=651861#c39
        if (distro == "fedora") and (major_version == 14):
            self.log.info("Fixing F14 EC2 bug")
            g.sh("echo \"hwcap 1 nosegneg\" > /etc/ld.so.conf.d/libc6-xen.conf")
            g.sh("/sbin/ldconfig")
            self.log.info("Done with EC2 filesystem modifications")

        g.sync ()
        g.umount_all ()

        # TODO: Based on architecture associate one of two XML blocks that contain the correct
        # regional AKIs for pvgrub

    def push_image(self, target_image_id, provider, credentials):
        try:
            if  self.target in self.upload_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "upload"):
                #No need to have an image object here
                #self.init_guest("local")
                self.push_image_upload(target_image_id, provider, credentials)
            elif self.target in self.nonul_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "snapshot"):
                self.init_guest("remote")
                self.push_image_snapshot(target_image_id, provider, credentials)
            else:
                raise ImageFactoryException("Invalid build target (%s) passed to build_image()" % (self.target))
        except:
            self.log_exc()
            self.status="FAILED"


    def push_image_snapshot(self, target_image_id, provider, credentials):
        if provider == "rackspace":
            self.push_image_snapshot_rackspace(target_image_id, provider, credentials)
        else:
            self.push_image_snapshot_ec2(target_image_id, provider, credentials)

    def push_image_snapshot_rackspace(self, target_image_id, provider, credentials):

        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()

        rack_username = ctxt.xpathEval("//provider_credentials/rackspace_credentials/username")[0].content
        rack_access_key = ctxt.xpathEval("//provider_credentials/rackspace_credentials/access_key")[0].content

        cloudservers = CloudServers(rack_username, rack_access_key)
	cloudservers.authenticate()

        # TODO: Config file
        rack_jeos = {'Fedora': { '14' : { 'x86_64': 71},
                                 '13' : { 'x86_64': 53} } }

        jeos_id = None
        try:
            jeos_id = rack_jeos[self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]
        except KeyError:
            raise ImageFactoryException("Unable to find Rackspace JEOS for desired distro - ask Rackspace")


	jeos_image = cloudservers.images.get(jeos_id)
        # Hardcode to use a modest sized server
	onegig_flavor = cloudservers.flavors.get(3)

        # This is the Rackspace version of key injection
	mypub = open("/etc/oz/id_rsa-icicle-gen.pub")
	server_files = { "/root/.ssh/authorized_keys":mypub }

        instance_name = "factory-build-%s" % (self.new_image_id, )
	jeos_instance = cloudservers.servers.create(instance_name,jeos_image, onegig_flavor, files=server_files)

	for i in range(30):
	  if jeos_instance.status == "ACTIVE":
	    self.log.debug("JEOS instance now active - moving to customize")
	    break
          self.log.debug("Waiting for Rackspace instance to start access: %d/300" % (i*10))
	  sleep(10)
	  # There is no query or update method, we simply recreate
	  jeos_instance = cloudservers.servers.get(jeos_instance.id)

	#print "Public ip: " , jeos_instance.public_ip
	#print "ID: " , jeos_instance.id

        # As with EC2 put this all in a try block and then terminate at the end to avoid long running
        # instances which cost users money
        try:
            self.guest.sshprivkey = "/etc/oz/id_rsa-icicle-gen"
	    guestaddr = jeos_instance.public_ip

            # TODO: Make this loop so we can take advantage of early availability
            # Ugly ATM because failed access always triggers an exception
            self.log.debug("Waiting up to 300 seconds for ssh to become available on %s" % (guestaddr))
            retcode = 1
            for i in range(30):
                self.log.debug("Waiting for Rackspace ssh access: %d/300" % (i*10))

                access=1
                try:
                    stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, "/bin/true")
                except:
                    access=0

                if access:
                    break

                sleep(10)

            if retcode:
                raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 20 seconds for remaining boot tasks")
            sleep(20)

	    self.log.debug("Doing Rackspace Customize")
	    self.guest.mkdir_p(self.guest.icicle_tmp)
	    self.guest.do_customize(guestaddr)
	    self.log.debug("Done!")

            self.log.debug("Generating ICICLE for Rackspace image")
            self.output_descriptor = self.guest.do_icicle(guestaddr)
            self.log.debug("Done!")

            image_name = "factory-image-%s" % (self.new_image_id, )
	    snap_image = cloudservers.images.create(image_name, jeos_instance)

	    self.log.debug("New Rackspace image created with ID: %s" % (snap_image.id))

	    for i in range(30):
	        if snap_image.status == "ACTIVE":
                    self.log.debug("Snapshot Completed")
                    break
                self.log.debug("Image status: %s - Waiting for completion: %d/300" % (snap_image.status, i*10))
                sleep(10)
	        # There is no query or update method, we simply recreate
	        snap_image = cloudservers.images.get(snap_image.id)

            self.log.debug("Storing Rackspace image ID (%s) and details in Warehouse" % (snap_image.id))
            icicle_id = self.warehouse.store_icicle(self.output_descriptor)
	    metadata = dict(target_image=target_image_id, provider=provider, icicle=icicle_id, target_identifier=snap_image.id)
	    self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)

	finally:
            self.log.debug("Shutting down Rackspace server")
            cloudservers.servers.delete(jeos_instance.id)

        self.percent_complete=100
        self.status = "COMPLETED"

    def push_image_snapshot_ec2(self, target_image_id, provider, credentials):
        self.log.debug("Being asked to push for provider %s" % (provider))
        self.log.debug("distro: %s - update: %s - arch: %s" % (self.tdlobj.distro, self.tdlobj.update, self.tdlobj.arch))
        self.ec2_decode_credentials(credentials)
        self.log.debug("acting as EC2 user: %s" % (str(self.ec2_user_id)))

        self.status="PUSHING"
        self.percent_complete=0

        region=provider
        # These are the region details for the TARGET region for our new AMI
        region_conf=self.ec2_region_details[region]
        aki = region_conf[self.tdlobj.arch]
        boto_loc = region_conf['boto_loc']
        if region != "ec2-us-east-1":
            upload_url = "http://s3-%s.amazonaws.com/" % (region_conf['host'])
        else:
            # Note to Amazon - would it be that hard to have s3-us-east-1.amazonaws.com?
            upload_url = "http://s3.amazonaws.com/"

        register_url = "http://ec2.%s.amazonaws.com/" % (region_conf['host'])

        ami_id = "none"
        build_region = provider

        try:
            ami_id = self.ec2_jeos_amis[provider][self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]
        except KeyError:
            pass

        if ami_id == "none":
	    try:
	        # Fallback to modification on us-east and upload cross-region
	        ami_id = self.ec2_jeos_amis['ec2-us-east-1'][self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]
	        build_region = 'ec2-us-east-1'
	        self.log.info("WARNING: Building in ec2-us-east-1 for upload to %s" % (provider))
	        self.log.info(" This may be a bit slow - ask the Factory team to create a region-local JEOS")
	    except KeyError:
	        pass

        if ami_id == "none":
            self.status="FAILED"
            raise ImageFactoryException("No available JEOS for desired OS, verison combination")

        instance_type='m1.large'
        if self.tdlobj.arch == "i386":
            instance_type='m1.small'

        # These are the region details for the region we are building in (which may be different from the target)
        build_region_conf = self.ec2_region_details[build_region]

        self.log.debug("Starting ami %s with instance_type %s" % (ami_id, instance_type))

        # Note that this connection may be to a region other than the target
        ec2region = boto.ec2.get_region(build_region_conf['host'], aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)

        # Create a use-once SSH-able security group
        factory_security_group_name = "imagefactory-%s" % (self.new_image_id, )
        factory_security_group_desc = "Temporary ImageFactory generated security group with SSH access"
	self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
	factory_security_group = conn.create_security_group(factory_security_group_name, factory_security_group_desc)
	factory_security_group.authorize('tcp', 22, 22, '0.0.0.0/0')

        # Construct the shell script that will inject our public key
        user_data = self.gen_ssh_userdata("/etc/oz/id_rsa-icicle-gen.pub")

        # Now launch it
        reservation = conn.run_instances(ami_id,instance_type=instance_type,user_data=user_data, security_groups = [ factory_security_group_name ])

        if len(reservation.instances) != 1:
            self.status="FAILED"
            raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

        instance = reservation.instances[0]

        # We have occasionally seen issues when you immediately query an instance
        # Give it 10 seconds to settle
        sleep(10)

        for i in range(30):
            self.log.debug("Waiting for EC2 instance to start: %d/300" % (i*10))
            instance.update()
            if instance.state == u'running':
                break
            sleep(10)

        if instance.state != u'running':
            self.status="FAILED"
            raise ImageFactoryException("Instance failed to start after 300 seconds - stopping")

        # From this point on we must be sure to terminate the instance when we are done
        # so wrap in a try/finally
        # Accidentally running a 64 bit instance doing nothing costs 56 USD week
        try:
            guestaddr = instance.public_dns_name

            self.guest.sshprivkey = "/etc/oz/id_rsa-icicle-gen"

            # TODO: Make this loop so we can take advantage of early availability
            # Ugly ATM because failed access always triggers an exception
            self.log.debug("Waiting up to 300 seconds for ssh to become available on %s" % (guestaddr))
            retcode = 1
            for i in range(30):
                self.log.debug("Waiting for EC2 ssh access: %d/300" % (i*10))

                access=1
                try:
                    stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, "/bin/true")
                except:
                    access=0

                if access:
                    break

                sleep(10)

            if retcode:
                raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 20 seconds for remaining boot tasks")
            sleep(20)

            # remove utility package and repo so that it isn't in the final image
            # and does not screw up our customize step
            # Our temporary SSH access key remains in place after this
            self.log.debug("Removing utility package and repo")
            # Removing the util package adds back the mlocate cron job - it cannot be allowed to run
            # so stop cron if it is running
            self.guest.guest_execute_command(guestaddr, "/sbin/service crond stop")
            self.guest.guest_execute_command(guestaddr, "rpm -e imgfacsnapinit")
            self.guest.guest_execute_command(guestaddr, "rm -f /etc/yum.repos.d/imgfacsnap.repo")
            self.log.debug("Removal complete")

            self.log.debug("Customizing guest: %s" % (guestaddr))
            self.guest.mkdir_p(self.guest.icicle_tmp)
            self.guest.do_customize(guestaddr)
            self.log.debug("Customization step complete")

            self.log.debug("Generating ICICLE from customized guest")
            self.output_descriptor = self.guest.do_icicle(guestaddr)
            self.log.debug("ICICLE generation complete")

            self.log.debug("Re-de-activate firstboot just in case it has been revived during customize")
            self.guest.guest_execute_command(guestaddr, "[ -f /etc/init.d/firstboot ] && /sbin/chkconfig firstboot off || /bin/true")
            self.log.debug("De-activation complete")

            cert = self.ec2_cert_file
            key = self.ec2_key_file
            ec2cert =  "/etc/pki/imagefactory/cert-ec2.pem"

            # This is needed for uploading and registration
            # Note that it is excluded from the final image
            self.log.debug("Uploading cert material")
            self.guest.guest_live_upload(guestaddr, cert, "/tmp")
            self.guest.guest_live_upload(guestaddr, key, "/tmp")
            self.guest.guest_live_upload(guestaddr, ec2cert, "/tmp")
            self.log.debug("Cert upload complete")

            # Some local variables to make the calls below look a little cleaner
            ec2_uid = self.ec2_user_id
            arch = self.tdlobj.arch
            # AKI is set above
            uuid = self.new_image_id

            # We exclude /mnt /tmp and /root/.ssh to avoid embedding our utility key into the image
            command = "euca-bundle-vol -c /tmp/%s -k /tmp/%s -u %s -e /mnt,/tmp,/root/.ssh --arch %s -d /mnt/bundles --kernel %s -p %s -s 10240 --ec2cert /tmp/cert-ec2.pem --fstab /etc/fstab -v /" % (os.path.basename(cert), os.path.basename(key), ec2_uid, arch, aki, uuid)
            self.log.debug("Executing bundle vol command: %s" % (command))
            stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, command)
            self.log.debug("Bundle output: %s" % (stdout))

            # Now, ensure we have an appropriate bucket to receive this image
            # TODO: This is another copy - make it a function soon please
            bucket= "imagefactory-" + region + "-" + self.ec2_user_id

            sconn = S3Connection(self.ec2_access_key, self.ec2_secret_key)
            try:
                sconn.create_bucket(bucket, location=boto_loc)
            except S3CreateError as buckerr:
                if buckerr.error_code == "BucketAlreadyOwnedByYou":
                    # Expected behavior after first push - not an error
                    pass
                else:
                    raise
            # TODO: End of copy

            # TODO: We cannot timeout on any of the three commands below - can we fix that?
            manifest = "/mnt/bundles/%s.manifest.xml" % (uuid)
            command = 'euca-upload-bundle -b %s -m %s --ec2cert /tmp/cert-ec2.pem -a "%s" -s "%s" -U %s' % (bucket, manifest, self.ec2_access_key, self.ec2_secret_key, upload_url)
            command_log = 'euca-upload-bundle -b %s -m %s --ec2cert /tmp/cert-ec2.pem -a "%s" -s "%s" -U %s' % (bucket, manifest, "<access_key>", "<secret_key>", upload_url)
            self.log.debug("Executing upload bundle command: %s" % (command_log))
            stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, command)
            self.log.debug("Upload output: %s" % (stdout))

            manifest_s3_loc = "%s/%s.manifest.xml" % (bucket, uuid)

            command = 'euca-register -U %s -A "%s" -S "%s" %s' % (register_url, self.ec2_access_key, self.ec2_secret_key, manifest_s3_loc)
            command_log = 'euca-register -U %s -A "%s" -S "%s" %s' % (register_url, "access_key", "secret_key", manifest_s3_loc)
            self.log.debug("Executing register command: %s" % (command_log))
            stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, command)
            self.log.debug("Register output: %s" % (stdout))

            m = re.match(".*(ami-[a-fA-F0-9]+)", stdout)
            ami_id = m.group(1)
            self.log.debug("Extracted AMI ID: %s " % (ami_id))

            icicle_id = self.warehouse.store_icicle(self.output_descriptor)
            metadata = dict(target_image=target_image_id, provider=provider, icicle=icicle_id, target_identifier=ami_id)
            self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        finally:
            self.log.debug("Stopping EC2 instance and deleting temp security group")
            instance.stop()
            factory_security_group.delete()

        self.log.debug("FedoraBuilder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
        self.percent_complete=100
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
        if subprocess.call(["cp", "-f", input_image, staging_image]):
            raise ImageFactoryException("Copy of condorcloud image to staging location (%s) failed" % (staging_image))

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
        if subprocess.call(["mv", "-f", staging_image, final_image]):
            raise ImageFactoryException("Move of condorcloud image to final location (%s) failed" % (final_image))

        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=self.new_image_id)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        self.percent_complete = 100

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


    def rhevm_push_image_upload(self, target_image_id, provider, credentials):
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

        # ATM the return is expected to be an empty string
        # The RHEV-M UUID is stored as a new piece of metadata with a key of "ami-id"
        # This is not thread-safe
        # TODO: Coordinate with Pete when he changes this to return the AMI ID as the body
        response = self.warehouse.post_on_object_with_id_of_type(target_image_id, "target_image", post_data)

        # TODO: Remove this when the change mentioned above has been made
        image_metadata = self.warehouse.metadata_for_id_of_type(("ami-id",), target_image_id, "target_image")
        self.log.debug("Got metadata output of: %s", repr(image_metadata))
	m = re.match("OK ([a-fA-F0-9-]+)", image_metadata["ami-id"])
	rhevm_uuid = m.group(1)
	self.log.debug("Extracted RHEVM UUID: %s " % (rhevm_uuid))

        # Create the provdier image
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=rhevm_uuid)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        self.percent_complete = 100


    def push_image_upload(self, target_image_id, provider, credentials):
        # TODO: RHEV-M and VMWare
        self.status="PUSHING"
        self.percent_complete=0
        try:
            if self.target == "ec2":
                if self.app_config["ec2_ami_type"] == "s3":
                    self.ec2_push_image_upload(target_image_id, provider, credentials)
                elif self.app_config["ec2_ami_type"] == "ebs":
                    self.ec2_push_image_upload_ebs(target_image_id, provider, credentials)
                else:
                    raise ImageFactoryException("Invalid or unspecified EC2 AMI type in config file")
            elif self.target == "condorcloud":
                self.condorcloud_push_image_upload(target_image_id, provider, credentials)
            elif self.target == "rhevm":
                self.rhevm_push_image_upload(target_image_id, provider, credentials)
            elif self.target == "vsphere":
                self.vmware_push_image_upload(target_image_id, provider, credentials)
            else:
                raise ImageFactoryException("Invalid upload push requested for target (%s) and provider (%s)" % (self.target, provider))
        except:
            self.log_exc()
            self.status="FAILED"
            raise
        self.status="COMPLETED"

    def generic_decode_credentials(self, credentials, provider_data):
        # convenience function for simple creds (rhev-m and vmware currently)
        # TODO: This is just silly-long - surely there's a better, cleaner, faster alternative
        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()

        self.username = None
        _usernodes = ctxt.xpathEval("//provider_credentials/%s_credentials/username" % (self.target))
        if len(_usernodes) > 0:
            self.username = _usernodes[0].content
        
        self.password = None
        _passnodes = ctxt.xpathEval("//provider_credentials/%s_credentials/password" % (self.target))
        if len(_passnodes) > 0:
            self.password = _passnodes[0].content

        doc.freeDoc()
        ctxt.xpathFreeContext()

        if not self.username:
            try:
                self.username = provider_data['username']
            except KeyError:
                raise ImageFactoryException("No username specified in config file or in push call")

        if not self.password:
            try:
                self.password = provider_data['password']
            except KeyError:
                raise ImageFactoryException("No password specified in config file or in push call")


    def ec2_decode_credentials(self, credentials):
        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()

        self.ec2_user_id = ctxt.xpathEval("//provider_credentials/ec2_credentials/account_number")[0].content
        self.ec2_access_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/access_key")[0].content
        self.ec2_secret_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/secret_access_key")[0].content

        # Support both "key" and "x509_private" as element names
        ec2_key_node = None
        ec2_key_node = ctxt.xpathEval("//provider_credentials/ec2_credentials/key")
        if not ec2_key_node:
            ec2_key_node = ctxt.xpathEval("//provider_credentials/ec2_credentials/x509_private")
        if not ec2_key_node:
            raise ImageFactoryException("No x509 private key found in ec2 credentials")
        ec2_key=ec2_key_node[0].content

        # Support both "certificate" and "x509_public" as element names
        ec2_cert_node = None
        ec2_cert_node = ctxt.xpathEval("//provider_credentials/ec2_credentials/certificate")
        if not ec2_cert_node:
            ec2_cert_node = ctxt.xpathEval("//provider_credentials/ec2_credentials/x509_public")
        if not ec2_cert_node:
            raise ImageFactoryException("No x509 public certificate found in ec2 credentials")
        ec2_cert = ec2_cert_node[0].content

        doc.freeDoc()
        ctxt.xpathFreeContext()

        # Shove certs into  named temporary files
        self.ec2_cert_file_object = NamedTemporaryFile()
        self.ec2_cert_file_object.write(ec2_cert)
        self.ec2_cert_file_object.flush()
        self.ec2_cert_file=self.ec2_cert_file_object.name

        self.ec2_key_file_object = NamedTemporaryFile()
        self.ec2_key_file_object.write(ec2_key)
        self.ec2_key_file_object.flush()
        self.ec2_key_file=self.ec2_key_file_object.name


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


    def gen_ssh_userdata(self, pubkey_filename):
        # Used in both snapshots and EBS building so it is a function
        pubkey_file=open(pubkey_filename, "r")
        pubkey = pubkey_file.read()
        pubkey_file.close()

        user_data_start='''#!/bin/bash

if [ ! -d /root/.ssh ] ; then
  mkdir /root/.ssh
  chmod 700 /root/.ssh
fi

cat << "EOF" >> /root/.ssh/authorized_keys
'''

        user_data_finish='''EOF
chmod 600 /root/.ssh/authorized_keys
'''

        user_data = "%s%s%s" % (user_data_start, pubkey, user_data_finish)
        return user_data


    def ec2_push_image_upload_ebs(self, target_image_id, provider, credentials):
        # TODO: Merge with ec2_push_image_upload and/or factor out duplication
        # In this case we actually do need an Oz object to manipulate a remote guest
        self.init_guest("remote")

        self.ec2_decode_credentials(credentials)
        # We don't need the x509 material here so close the temp files right away
        # TODO: Mod the decode to selectively create the files in the first place
        #   This is silly and messy
        self.ec2_cert_file_object.close()
        self.ec2_key_file_object.close()


        # if the image is already here, great, otherwise grab it from the warehouse
        input_image_path=self.app_config['imgdir'] + "/"
        input_image_name="ec2-image-" + target_image_id + ".dsk"
        input_image=input_image_path + input_image_name

        self.retrieve_image(target_image_id, input_image)

        input_image_compressed_name = input_image_name + ".gz"
        input_image_compressed=input_image + ".gz"
       
        if not os.path.isfile(input_image_compressed):
            self.log.debug("No compressed version of image file found - compressing now")
            f_out = open(input_image_compressed, 'wb')
            retcode = subprocess.call(['gzip', '-c', input_image], stdout=f_out)
            f_out.close()
            if retcode:
                raise ImageFactoryException("Error while compressing image prior to scp")
            self.log.debug("Compression complete")

        region=provider
        region_conf=self.ec2_region_details[region]
        aki = region_conf[self.tdlobj.arch]

        # For now, use our F14 - 32 bit JEOS image as the utility image for uploading to the EBS volume
        try:
            ami_id = self.ec2_jeos_amis[provider]['Fedora']['14']['i386']
        except KeyError:
            raise ImageFactoryException("Can only build EBS in us-east and us-west for now - aborting")

        # i386
        instance_type='m1.small'

        self.log.debug("Initializing connection to ec2 region (%s)" % region_conf['host'])
        ec2region = boto.ec2.get_region(region_conf['host'], aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)

        # Create a use-once SSH-able security group
        factory_security_group_name = "imagefactory-%s" % (str(self.new_image_id))
        factory_security_group_desc = "Temporary ImageFactory generated security group with SSH access"
        self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
        factory_security_group = conn.create_security_group(factory_security_group_name, factory_security_group_desc)
        factory_security_group.authorize('tcp', 22, 22, '0.0.0.0/0')

        # TODO: Ad-hoc key generation
        # Construct the shell script that will inject our public key
        user_data = self.gen_ssh_userdata("/etc/oz/id_rsa-icicle-gen.pub")

        # Now launch it
        reservation = conn.run_instances(ami_id,instance_type=instance_type,user_data=user_data, security_groups = [ factory_security_group_name ])

        if len(reservation.instances) != 1:
            self.status="FAILED"
            raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

        instance = reservation.instances[0]

        # We have occasionally seen issues when you immediately query an instance
        # Give it 10 seconds to settle
        sleep(10)

        for i in range(30):
            self.log.debug("Waiting for EC2 instance to start: %d/300" % (i*10))
            instance.update()
            if instance.state == u'running':
                break
            sleep(10)

        if instance.state != u'running':
            self.status="FAILED"
            raise ImageFactoryException("Instance failed to start after 300 seconds - stopping")

        # From this point on we must be sure to terminate the instance when we are done
        # so wrap in a try/finally
        # Accidentally running a 64 bit instance doing nothing costs 56 USD week
        volume = None
        try:
            guestaddr = instance.public_dns_name

            self.guest.sshprivkey = "/etc/oz/id_rsa-icicle-gen"

            # TODO: Make this loop so we can take advantage of early availability
            # Ugly ATM because failed access always triggers an exception
            self.log.debug("Waiting up to 300 seconds for ssh to become available on %s" % (guestaddr))
            retcode = 1
            for i in range(30):
                self.log.debug("Waiting for EC2 ssh access: %d/300" % (i*10))

                access=1
                try:
                    stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, "/bin/true")
                except:
                    access=0

                if access:
                    break

                sleep(10)

            if retcode:
                raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 20 seconds for remaining boot tasks")
            sleep(20)

            self.log.debug("Creating 10 GiB volume in (%s)" % (instance.placement))
            volume = conn.create_volume(10, instance.placement)

            # Do the upload before testing to see if the volume has completed
            # to get a bit of parallel work
            self.log.debug("Uploading compressed image file")
            self.guest.guest_live_upload(guestaddr, input_image_compressed, "/mnt")

            # Volumes can sometimes take a very long time to create
            # Wait up to 10 minutes for now (plus the time taken for the upload above)
            self.log.debug("Waiting up to 600 seconds for volume (%s) to become available" % (volume.id))
            retcode = 1
            for i in range(60):
                volume.update()
                if volume.status == "available":
                    retcode = 0
                    break
                self.log.debug("Volume status (%s) - waiting for 'available': %d/600" % (volume.status, i*10)) 
                sleep(10)

            if retcode:
                raise ImageFactoryException("Unable to create target volume for EBS AMI - aborting")

            # Volume is now available
            # Attach it
            conn.attach_volume(volume.id, instance.id, "/dev/sdh")

            self.log.debug("Waiting up to 120 seconds for volume (%s) to become in-use" % (volume.id))
            retcode = 1
            for i in range(12):
                volume.update()
                vs = volume.attachment_state()
                if vs == "attached":
                    retcode = 0
                    break
                self.log.debug("Volume status (%s) - waiting for 'attached': %d/120" % (vs, i*10))
                sleep(10)

            if retcode:
                raise ImageFactoryException("Unable to attach volume (%s) to instance (%s) aborting" % (volume.id, instance.id))

            # TODO: This may not be necessary but it helped with some funnies observed during testing
            #         At some point run a bunch of builds without the delay to see if it breaks anything
            self.log.debug("Waiting 20 seconds for EBS attachment to stabilize")
            sleep(20)

            # Decompress image into new EBS volume
            command = "gzip -dc /mnt/%s | dd of=/dev/xvdh bs=4k\n" % (input_image_compressed_name)
            self.log.debug("Decompressing image file into EBS device via command:")
            self.log.debug("  %s" % (command))
            self.guest.guest_execute_command(guestaddr, command)

            # Sync before snapshot
            self.guest.guest_execute_command(guestaddr, "sync")

            # Snapshot EBS volume
            self.log.debug("Taking snapshot of volume (%s)" % (volume.id))
            snapshot = conn.create_snapshot(volume.id, 'Image Factory Snapshot for provider image %s' % self.new_image_id)

            # This can take a _long_ time - wait up to 20 minutes
            self.log.debug("Waiting up to 1200 seconds for snapshot (%s) to become completed" % (snapshot.id))
            retcode = 1
            for i in range(120):
                snapshot.update()
                if snapshot.status == "completed":
                    retcode = 0
                    break
                self.log.debug("Snapshot progress(%s) -  status (%s) - waiting for 'completed': %d/1200" % (str(snapshot.progress), snapshot.status, i*10))
                sleep(10)

            if retcode:
                raise ImageFactoryException("Unable to snapshot volume (%s) - aborting" % (volume.id))

            # register against snapshot
            self.log.debug("Registering snapshot (%s) as new EBS AMI" % (snapshot.id))
            ebs = EBSBlockDeviceType()
            ebs.snapshot_id = snapshot.id
            block_map = BlockDeviceMapping() 
            block_map['/dev/sda1'] = ebs 
            result = conn.register_image(name='ImageFactory created AMI - %s' % (self.new_image_id), 
                            description='ImageFactory created AMI - %s' % (self.new_image_id),
                            architecture=self.tdlobj.arch,  kernel_id=aki, 
                            root_device_name='/dev/sda1', block_device_map=block_map)

            ami_id = str(result)
            self.log.debug("Extracted AMI ID: %s " % (ami_id))
        finally:
            self.log.debug("Stopping EC2 instance and deleting temp security group and volume")
            instance.stop()
            factory_security_group.delete()
            
            if volume:
                self.log.debug("Waiting up to 240 seconds for instance (%s) to shut down" % (instance.id))
                retcode = 1
                for i in range(24):
                    instance.update()
                    if instance.state == "terminated":
                        retcode = 0
                        break
                    self.log.debug("Instance status (%s) - waiting for 'terminated': %d/240" % (instance.state, i*10))
                    sleep(10)

                if retcode:
                    self.log.debug("WARNING: Unable to delete volume (%s)" % (volume.id))
                else:
                    self.log.debug("Deleting EBS volume (%s)" % (volume.id))
                    volume.delete()

        # TODO: Add back-reference to ICICLE from base image object
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=ami_id)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)

        self.log.debug("FedoraBuilder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
        self.percent_complete=100

    def ec2_push_image_upload(self, target_image_id, provider, credentials):
        self.ec2_decode_credentials(credentials)

        # if the image is already here, great, otherwise grab it from the warehouse
        input_image_path=self.app_config['imgdir'] + "/"
        input_image_name="ec2-image-" + target_image_id + ".dsk"
        input_image=input_image_path + input_image_name

        self.retrieve_image(target_image_id, input_image)

        bundle_destination=self.app_config['imgdir']

        # TODO: Cross check against template XML and warn if they do not match
        g = guestfs.GuestFS ()
        g.add_drive(input_image)
        g.launch ()
        inspection = g.inspect_os()
        if len(inspection) >  0:
            # This should always be /dev/vda or /dev/sda but we do it anyway to be safe
            osroot = inspection[0]
            arch = g.inspect_get_arch(osroot)
        else:
            self.log.debug("Warning - unable to inspect EC2 image file - assuming x86_64 arch")
            arch = "x86_64"
        g.umount_all()

        self.percent_complete=10

        region=provider
        region_conf=self.ec2_region_details[region]
        aki = region_conf[arch]
        boto_loc = region_conf['boto_loc']
        if region != "ec2-us-east-1":
            upload_url = "http://s3-%s.amazonaws.com/" % (region_conf['host'])
        else:
            # Note to Amazon - would it be that hard to have s3-us-east-1.amazonaws.com?
            upload_url = "http://s3.amazonaws.com/"

        register_url = "http://ec2.%s.amazonaws.com/" % (region_conf['host'])

        bucket= "imagefactory-" + region + "-" + self.ec2_user_id

        # Euca does not support specifying region for bucket
        # (Region URL is not sufficient)
        # See: https://bugs.launchpad.net/euca2ools/+bug/704658
        # What we end up having to do is manually create a bucket in the right region
        # then explicitly point to that region URL when doing the image upload
        # We CANNOT let euca create the bucket when uploading or it will end up in us-east-1

        conn = S3Connection(self.ec2_access_key, self.ec2_secret_key)
        try:
            conn.create_bucket(bucket, location=boto_loc)
        except S3CreateError as buckerr:
            if buckerr.error_code == "BucketAlreadyOwnedByYou":
                # Expected behavior after first push - not an error
                pass
            else:
                raise

        # TODO: Make configurable?
        ec2_service_cert = "/etc/pki/imagefactory/cert-ec2.pem"

        bundle_command = [ "euca-bundle-image", "-i", input_image, "--kernel", aki, "-d", bundle_destination, "-a", self.ec2_access_key, "-s", self.ec2_secret_key ]
        bundle_command.extend( [ "-c", self.ec2_cert_file, "-k", self.ec2_key_file, "-u", self.ec2_user_id, "-r", arch, "--ec2cert", ec2_service_cert ] )

        bundle_command_log = [ "euca-bundle-image", "-i", input_image, "--kernel", aki, "-d", bundle_destination, "-a", "<access_key>", "-s", "<secret_key>" ]
        bundle_command_log.extend( [ "-c", self.ec2_cert_file, "-k", self.ec2_key_file, "-u", self.ec2_user_id, "-r", arch, "--ec2cert", ec2_service_cert ] )

        self.log.debug("Executing bundle command: %s " % (bundle_command_log))

        bundle_output = subprocess_check_output(bundle_command)

        self.log.debug("Bundle command complete")
        self.log.debug("Bundle command output: %s " % (str(bundle_output)))
        self.percent_complete=40

        manifest = bundle_destination + "/" + input_image_name + ".manifest.xml"

        upload_command = [ "euca-upload-bundle", "-b", bucket, "-m", manifest, "--ec2cert", ec2_service_cert, "-a", self.ec2_access_key, "-s", self.ec2_secret_key, "-U" , upload_url ]
        upload_command_log = [ "euca-upload-bundle", "-b", bucket, "-m", manifest, "--ec2cert", ec2_service_cert, "-a", "<access_key>", "-s", "<secret_key>", "-U" , upload_url ]
        self.log.debug("Executing upload command: %s " % (upload_command_log))
        upload_output = subprocess_check_output(upload_command)
        self.log.debug("Upload command output: %s " % (str(upload_output)))
        self.percent_complete=90

        s3_path = bucket + "/" + input_image_name + ".manifest.xml"

        register_env = { 'EC2_URL':register_url }
        register_command = [ "euca-register" , "-A", self.ec2_access_key, "-S", self.ec2_secret_key, s3_path ]
        register_command_log = [ "euca-register" , "-A", "<access_key>", "-S", "<secret_key>", s3_path ]
        self.log.debug("Executing register command: %s with environment %s " % (register_command_log, repr(register_env)))
        register_output = subprocess_check_output(register_command, env=register_env)
        self.log.debug("Register command output: %s " % (str(register_output)))
        m = re.match(".*(ami-[a-fA-F0-9]+)", register_output[0])
        ami_id = m.group(1)
        self.log.debug("Extracted AMI ID: %s " % (ami_id))

        # TODO: This should be in a finally statement that rethrows exceptions
        self.ec2_cert_file_object.close()
        self.ec2_key_file_object.close()

        # Use new warehouse wrapper to do everything
        # TODO: Generate and store ICICLE
        self.status = "PUSHING"
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=ami_id)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)

        #self.output_descriptor="unknown"
        #metadata = dict(uuid=self.new_image_id, type="provider_image", template=self.template, target=self.target, icicle=self.output_descriptor, target_image=target_image_id, provider=provider, target_identifier=ami_id)
        self.log.debug("FedoraBuilder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
        self.percent_complete=100

    def abort(self):
        pass

    # This file content is tightly bound up with our mod code above
    # I've inserted it as class variables for convenience
    rc_local="""# We have seen timing issues with curl commands - try several times
for t in 1 2 3 4 5 6 7 8 9 10; do
  echo "Try number $t" >> /tmp/ec2-keypull.stderr
  curl -o /tmp/my-key http://169.254.169.254/2009-04-04/meta-data/public-keys/0/openssh-key 2>> /tmp/ec2-keypull.stderr
  [ -f /tmp/my-key ] && break
  sleep 10
done

if ! [ -f /tmp/my-key ]; then
  echo "Failed to retrieve SSH key after 10 tries and 100 seconds" > /dev/hvc0
  exit 1
fi

dd if=/dev/urandom count=50 2>/dev/null|md5sum|awk '{ print $1 }'|passwd --stdin root >/dev/null

if [ ! -d /root/.ssh ] ; then
mkdir /root/.ssh
chmod 700 /root/.ssh
fi

cat /tmp/my-key >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

for home in `find /home/* -maxdepth 0 -type d 2>/dev/null | tr '\\n' ' '`; do
user=`echo $home | awk -F '/' '{ print $3 }'`

if [ ! -d $home/.ssh ] ; then
mkdir -p $home/.ssh
chmod 700 $home/.ssh
chown $user $home/.ssh
fi

cat /tmp/my-key >> $home/.ssh/authorized_keys
chmod 600 $home/.ssh/authorized_keys
chown $user $home/.ssh/authorized_keys

done
rm /tmp/my-key

# This conditionally runs Audrey if it exists
[ -f /usr/bin/audrey ] && /usr/bin/audrey
"""

    rc_local_all="""
# This conditionally runs Audrey if it exists
[ -f /usr/bin/audrey ] && /usr/bin/audrey
"""

    ifcfg_eth0="""DEVICE=eth0
BOOTPROTO=dhcp
ONBOOT=yes
TYPE=Ethernet
USERCTL=yes
PEERDNS=yes
IPV6INIT=no
"""

    menu_lst="""default=0
timeout=0
title #TITLE#
    root (hd0)
    kernel /boot/vmlinuz-#KERNEL_VERSION# ro root=LABEL=/ rd_NO_PLYMOUTH
    initrd /boot/#KERNEL_IMAGE_NAME#-#KERNEL_VERSION#.img
"""

    fstab_32bit="""LABEL=/    /         #FILESYSTEM_TYPE#    defaults         1 1
/dev/#DISK_DEVICE_PREFIX#da2  /mnt      ext3    defaults         1 2
/dev/#DISK_DEVICE_PREFIX#da3  swap      swap    defaults         0 0
none       /dev/pts  devpts  gid=5,mode=620   0 0
none       /dev/shm  tmpfs   defaults         0 0
none       /proc     proc    defaults         0 0
none       /sys      sysfs   defaults         0 0
"""

    fstab_64bit="""LABEL=/    /         #FILESYSTEM_TYPE#    defaults         1 1
/dev/#DISK_DEVICE_PREFIX#db   /mnt      ext3    defaults         0 0
/dev/#DISK_DEVICE_PREFIX#dc   /data     ext3    defaults         0 0
none       /dev/pts  devpts  gid=5,mode=620   0 0
none       /dev/shm  tmpfs   defaults         0 0
none       /proc     proc    defaults         0 0
none       /sys      sysfs   defaults         0 0
"""

    # Dont attempt to be clever with ephemeral devices - leave it to users
    fstab_generic="""LABEL=/    /         #FILESYSTEM_TYPE#    defaults         1 1
none       /dev/pts  devpts  gid=5,mode=620   0 0
none       /dev/shm  tmpfs   defaults         0 0
none       /proc     proc    defaults         0 0
none       /sys      sysfs   defaults         0 0
"""

    ############ BEGIN CONFIG-LIKE class variables ###########################
    ##########################################################################
    # Perhaps there is a better way to do this but this works for now

    # TODO: Ideally we should use boto "Location" references when possible - 1.9 contains only DEFAULT and EU
    #       The rest are hard coded strings for now.
    ec2_region_details={
         'ec2-us-east-1':      { 'boto_loc': Location.DEFAULT,     'host':'us-east-1',      'i386': 'aki-407d9529', 'x86_64': 'aki-427d952b' },
         'ec2-us-west-1':      { 'boto_loc': 'us-west-1',          'host':'us-west-1',      'i386': 'aki-99a0f1dc', 'x86_64': 'aki-9ba0f1de' },
         'ec2-ap-southeast-1': { 'boto_loc': 'ap-southeast-1',     'host':'ap-southeast-1', 'i386': 'aki-13d5aa41', 'x86_64': 'aki-11d5aa43' },
         'ec2-ap-northeast-1': { 'boto_loc': 'ap-northeast-1',     'host':'ap-northeast-1', 'i386': 'aki-d209a2d3', 'x86_64': 'aki-d409a2d5' },
         'ec2-eu-west-1':      { 'boto_loc': Location.EU,          'host':'eu-west-1',      'i386': 'aki-4deec439', 'x86_64': 'aki-4feec43b' } }


        # v0.2 of these AMIs - created week of April 4, 2011
        # v0.3 for F13 64 bit only - created April 12, 2011
    ec2_jeos_amis={
         'ec2-us-east-1': {'Fedora': { '14' : { 'x86_64': 'ami-d6b946bf', 'i386': 'ami-6ab94603' },
                                       '13' : { 'x86_64': 'ami-10bc4379', 'i386': 'ami-06ba456f' } } } ,
         'ec2-us-west-1': {'Fedora': { '14' : { 'x86_64': 'ami-c9693a8c', 'i386': 'ami-c7693a82' },
                                       '13' : { 'x86_64': 'ami-33693a76', 'i386': 'ami-23693a66' } } } }
