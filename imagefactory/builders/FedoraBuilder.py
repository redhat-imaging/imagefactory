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
import ConfigParser
import boto.ec2
from time import *
from tempfile import *
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageFactoryException import ImageFactoryException
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from boto.s3.connection import S3Connection
from boto.s3.connection import Location
from boto.exception import *

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
    upload_clouds = [ "rhev-m", "vmware", "condorcloud" ]
    nonul_clouds = [ "rackspace", "gogrid" ]     

    def __init__(self, template, target):
        super(FedoraBuilder, self).__init__(template, target)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        # TODO: Should this be in base?  Does image_id ever need to be an actual UUID object?
        self.image_id = str(self.image_id)	
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
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + str(self.image_id)

    def build_image(self):
        if  self.target in self.upload_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "upload"):
            self.init_guest("local")
            self.build_upload()
        elif self.target in self.nonul_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "snapshot"):
            # No actual need to have a guest object here so don't bother
            self.build_snapshot()
        else:
            raise ImageFactoryException("Invalid build target (%s) passed to build_image()" % (self.target))

    def build_snapshot(self):
        # All we need do here is store the relevant bits in the Warehouse
        self.log.debug("Building Linux for a non-upload cloud")
        self.image = "%s/placeholder-linux-image-%s" % (self.app_config['imgdir'], self.image_id)
        image_file = open(self.image, 'w')
        image_file.write("Placeholder for non upload cloud Linux image")
        image_file.close()
        self.store_image()
        self.percent_complete = 100
        self.status = "COMPLETED"
        self.log.debug("Completed placeholder warehouse object for linux non-upload image...")
        image_file.close()

    def build_upload(self):
        self.log.debug("build_upload() called on FedoraBuilder...")
        self.log.debug("Building for target %s with warehouse config %s" % (self.target, self.app_config['warehouse']))
        self.status="BUILDING"
        try:
            self.guest.cleanup_old_guest()
            self.guest.generate_install_media(force_download=False)
            self.percent_complete=10
        except:
            self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
            self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
            self.log.debug("         traceback: %s" % (repr(traceback.format_tb(sys.exc_info()[2]))))
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
            except:
                self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
                self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
                self.log.debug("         traceback:")
                for tbline in traceback.format_tb(sys.exc_info()[2]):
                    self.log.debug("   %s" %  (tbline))
                self.guest.cleanup_old_guest()
                self.status="FAILED"
                raise
        finally:
            self.guest.cleanup_install()
        
        self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
        # OK great, we now have a customized KVM image
        # Now we do some target specific transformation
        if self.target == "ec2":
            self.log.info("Transforming image for use on EC2")
            self.ec2_transform_image()
        
        if (self.app_config['warehouse']):
            self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
            # TODO: Revisit target_parameters for different providers
            
            if self.target in [ "condorcloud", "rhev-m" ]:
                # TODO: Prune any unneeded elements
                target_parameters=libvirt_xml
            else:
                target_parameters="No target parameters for cloud type %s" % (self.target)

            self.store_image(target_parameters)
            self.log.debug("Image warehouse storage complete")
        self.percent_complete=100
        self.status="COMPLETED"
    
    def ec2_transform_image(self):
        # On entry the image points to our generic KVM image - we transform image
        #  and then update the image property to point to our new image and update
        #  the metadata
        try:
            output_dir=self.app_config['imgdir']
            self.ec2_copy_filesystem(output_dir)
            self.ec2_modify_filesystem()
        except:
            self.log.debug("Exception during ec2_transform_image")
            self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
            self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
            self.log.debug("         traceback: %s" % (repr(traceback.format_tb(sys.exc_info()[2]))))
            self.status="FAILED"
            raise
    
    def ec2_copy_filesystem(self, output_dir):
        target_image=output_dir + "/ec2-image-" + self.image_id + ".dsk"
        
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
        tmp_image_file = "/tmp/tmp-img-" + self.image_id
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
        
        self.log.info("Creating cloud-info file for EC2")
        tmpl = 'CLOUD_TYPE="ec2"\n'
        g.write("/etc/sysconfig/cloud-info", tmpl)
        
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
    
    def push_image(self, image_id, provider, credentials):
        try:
            if  self.target in self.upload_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "upload"):
                #No need to have an image object here
                #self.init_guest("local")
                self.push_image_upload(image_id, provider, credentials)
            elif self.target in self.nonul_clouds or (self.target == "ec2" and self.app_config["ec2_build_style"] == "snapshot"):
                self.init_guest("remote")
                self.push_image_snapshot(image_id, provider, credentials)
            else:
                raise ImageFactoryException("Invalid build target (%s) passed to build_image()" % (self.target))
        except:
            self.log.debug("Exception during push_image")
            self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
            self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
            self.log.debug("         traceback: %s" % (repr(traceback.format_tb(sys.exc_info()[2]))))
            self.status="FAILED"


    def push_image_snapshot(self, image_id, provider, credentials):
        # TODO: Rackspace and other snapshot builds - for now this is always EC2
        self.push_image_snapshot_ec2(image_id, provider, credentials)

    def push_image_snapshot_ec2(self, image_id, provider, credentials):
        self.log.debug("Being asked to push for provider %s" % (provider))
        self.log.debug("distro: %s - update: %s - arch: %s" % (self.tdlobj.distro, self.tdlobj.update, self.tdlobj.arch))
        self.ec2_decode_credentials(credentials)
        self.log.debug("acting as EC2 user: %s" % (str(self.ec2_user_id)))

        self.status="PUSHING"
        self.percent_complete=0
        # TODO: This is a cut and paste - should really be a function
        # TODO: Ideally we should use boto "Location" references when possible - 1.9 contains only DEFAULT and EU
        #       The rest are hard coded strings for now.
        ec2_region_details=\
        {'ec2-us-east-1':      { 'boto_loc': Location.DEFAULT,     'host':'us-east-1',      'i386': 'aki-407d9529', 'x86_64': 'aki-427d952b' },
         'ec2-us-west-1':      { 'boto_loc': 'us-west-1',          'host':'us-west-1',      'i386': 'aki-99a0f1dc', 'x86_64': 'aki-9ba0f1de' },
         'ec2-ap-southeast-1': { 'boto_loc': 'ap-southeast-1',     'host':'ap-southeast-1', 'i386': 'aki-13d5aa41', 'x86_64': 'aki-11d5aa43' },
         'ec2-ap-northeast-1': { 'boto_loc': 'ap-northeast-1',     'host':'ap-northeast-1', 'i386': 'aki-d209a2d3', 'x86_64': 'aki-d409a2d5' },
         'ec2-eu-west-1':      { 'boto_loc': Location.EU,          'host':'eu-west-1',      'i386': 'aki-4deec439', 'x86_64': 'aki-4feec43b' } }

        region=provider
        # These are the region details for the TARGET region for our new AMI
        region_conf=ec2_region_details[region]
        aki = region_conf[self.tdlobj.arch]
        boto_loc = region_conf['boto_loc']
        if region != "ec2-us-east-1":
            upload_url = "http://s3-%s.amazonaws.com/" % (region_conf['host'])
        else:
            # Note to Amazon - would it be that hard to have s3-us-east-1.amazonaws.com?
            upload_url = "http://s3.amazonaws.com/"

        register_url = "http://ec2.%s.amazonaws.com/" % (region_conf['host'])

        # Construct the shell script that will inject our public key
        pubkey_file=open("/etc/oz/id_rsa-icicle-gen.pub", "r")
        pubkey = pubkey_file.read()

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

        user_data="%s%s%s" % (user_data_start, pubkey, user_data_finish)

        # v0.2 of these AMIs - created week of April 4, 2011
        # v0.3 for F13 64 bit only - created April 12, 2011
        ec2_jeos_amis=\
        {'ec2-us-east-1': {'Fedora': { '14' : { 'x86_64': 'ami-289b6741', 'i386': 'ami-909a66f9' },
                                       '13' : { 'x86_64': 'ami-a49a66cd', 'i386': 'ami-109a6679' } } } ,
         'ec2-us-west-1': {'Fedora': { '14' : { 'x86_64': 'ami-b34a19f6', 'i386': 'ami-b74a19f2' },
                                       '13' : { 'x86_64': 'ami-ad4a19e8', 'i386': 'ami-a14a19e4' } } } }

        ami_id = "none"
        build_region = provider

        try:
            ami_id = ec2_jeos_amis[provider][self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]
        except KeyError:
            pass

        if ami_id == "none":
	    try:
	        # Fallback to modification on us-east and upload cross-region
	        ami_id = ec2_jeos_amis['ec2-us-east-1'][self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]
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
        build_region_conf = ec2_region_details[build_region]

        self.log.debug("Starting ami %s with instance_type %s" % (ami_id, instance_type))

        # Note that this connection may be to a region other than the target
        ec2region = boto.ec2.get_region(build_region_conf['host'], aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        reservation = conn.run_instances(ami_id,instance_type=instance_type,user_data=user_data)
        
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
            uuid = self.image_id

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
            self.log.debug("Executing upload bundle command: %s" % (command))
            stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, command)
            self.log.debug("Upload output: %s" % (stdout))

            manifest_s3_loc = "%s/%s.manifest.xml" % (bucket, uuid)

            command = 'euca-register -U %s -A "%s" -S "%s" %s' % (register_url, self.ec2_access_key, self.ec2_secret_key, manifest_s3_loc)
            self.log.debug("Executing register command: %s" % (command))
            stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, command)
            self.log.debug("Register output: %s" % (stdout))

            m = re.match(".*(ami-[a-fA-F0-9]+)", stdout)
            ami_id = m.group(1)
            self.log.debug("Extracted AMI ID: %s " % (ami_id))

            metadata = dict(image=image_id, provider=provider, icicle="none", target_identifier=ami_id)
            self.warehouse.create_provider_image(self.image_id, metadata=metadata)
        finally:
            self.log.debug("Stopping EC2 instance")
            instance.stop()

        self.log.debug("FedoraBuilder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), str(image_id), str(self.image_id), str(metadata)))
        self.percent_complete=100
        self.status="COMPLETED"

    def condorcloud_push_image_upload(self, image_id, provider, credentials):
        # condorcloud is a simple local cloud instance using Condor
        # The push action in this case simply requires that we copy the image to a known
        # location and then move it to another known loacation

        # This is where the image should be after a local build
        input_image = self.app_config["imgdir"] + "/base-image-" + image_id + ".dsk"
        # Grab from Warehouse if it isn't here
        self.retrieve_image(image_id, input_image)
        
        storage = "/home/cloud/images"
        if not os.path.isdir(storage):
            raise ImageFactoryException("Storage dir (%s) for condorcloud is not present" % (storage))

        staging = storage + "/staging"
        if not os.path.isdir(staging):
            raise ImageFactoryException("Staging dir (%s) for condorcloud is not present" % (staging))
               
        image_base = "/condorimage-" + str(self.image_id) + ".img"
        staging_image = staging + image_base

        # Copy to staging location
        # The os-native cp command in Fedora and RHEL does sparse file detection which is good
        self.log.debug("Copying (%s) to (%s)" % (input_image, staging_image))
        if subprocess.call(["cp", "-f", input_image, staging_image]):
            raise ImageFactoryException("Copy of condorcloud image to staging location (%s) failed" % (staging_image))

        # Retrieve original XML and write it out to the final dir
        image_xml_base="/condorimage-" + str(self.image_id) + ".xml"
        image_xml_file= storage + image_xml_base

        image_metadata = self.warehouse.metadata_for_id_of_type(("target_parameters",), image_id, "image")
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

        metadata = dict(image=image_id, provider=provider, icicle="none", target_identifier=self.image_id)
        self.warehouse.create_provider_image(self.image_id, metadata=metadata)
        self.percent_complete = 100

    def rhevm_push_image_upload(self, image_id, provider, credentials):
        pass
        # Decode the config file, verify that the provider is in it - err out if not
        # Execute the POST against our warehouse URL and collect the results
        # NOW: Pull back the ami-id
        # FUTURE: Read the actual output of the post
        # Then use that information to create the provider_image object


    def push_image_upload(self, image_id, provider, credentials):
        # TODO: RHEV-M and VMWare
        self.status="PUSHING"
        self.percent_complete=0
        try:
            if self.target == "ec2":
                self.ec2_push_image_upload(image_id, provider, credentials)
            elif self.target == "condorcloud":
                self.condorcloud_push_image_upload(image_id, provider, credentials)
            elif self.target == "rhev-m":
                self.rhevm_push_image_upload(image_id, provider, credentials)
            else:
                raise ImageFactoryException("Invalid upload push requested for target (%s) and provider (%s)" % (self.target, provider))
        except:
            self.log.debug("Exception during push_image_upload")
            self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
            self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
            self.log.debug("         traceback: %s" % (repr(traceback.format_tb(sys.exc_info()[2]))))
            self.status="FAILED"
            raise
        self.status="COMPLETED"

    def ec2_decode_credentials(self, credentials): 
        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()
        
        self.ec2_user_id = ctxt.xpathEval("//provider_credentials/ec2_credentials/account_number")[0].content
        self.ec2_access_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/access_key")[0].content
        self.ec2_secret_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/secret_access_key")[0].content
        ec2_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/key")[0].content
        ec2_cert = ctxt.xpathEval("//provider_credentials/ec2_credentials/certificate")[0].content
        
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

    def retrieve_image(self, image_id, local_image_file):
        # Grab image_id from warehouse unless it is already present as local_image_file
        # TODO: Use Warehouse class instead
        if not os.path.isfile(local_image_file):
            if not (self.app_config['warehouse']):
                raise ImageFactoryException("No warehouse configured - cannot retrieve image")
            url = "%simages/%s" % (self.app_config['warehouse'], image_id)
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
 

    def ec2_push_image_upload(self, image_id, provider, credentials):
        self.ec2_decode_credentials(credentials)      

        # if the image is already here, great, otherwise grab it from the warehouse
        input_image_path=self.app_config['imgdir'] + "/"
        input_image_name="ec2-image-" + image_id + ".dsk"
        input_image=input_image_path + input_image_name
        
        self.retrieve_image(image_id, input_image)

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
        
        # TODO: Ideally we should use boto "Location" references when possible - 1.9 contains only DEFAULT and EU
        #       The rest are hard coded strings for now.
        ec2_region_details=\
        {'ec2-us-east-1':      { 'boto_loc': Location.DEFAULT,     'host':'us-east-1',      'i386': 'aki-407d9529', 'x86_64': 'aki-427d952b' },
         'ec2-us-west-1':      { 'boto_loc': 'us-west-1',          'host':'us-west-1',      'i386': 'aki-99a0f1dc', 'x86_64': 'aki-9ba0f1de' },
         'ec2-ap-southeast-1': { 'boto_loc': 'ap-southeast-1',     'host':'ap-southeast-1', 'i386': 'aki-13d5aa41', 'x86_64': 'aki-11d5aa43' },
         'ec2-ap-northeast-1': { 'boto_loc': 'ap-northeast-1',     'host':'ap-northeast-1', 'i386': 'aki-d209a2d3', 'x86_64': 'aki-d409a2d5' },
         'ec2-eu-west-1':      { 'boto_loc': Location.EU,          'host':'eu-west-1',      'i386': 'aki-4deec439', 'x86_64': 'aki-4feec43b' } }
        
        region=provider
        region_conf=ec2_region_details[region]
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
        bundle_command.extend( [ "-c", self.ec2_cert_file ] )
        bundle_command.extend( [ "-k", self.ec2_key_file ] )
        bundle_command.extend( [ "-u", self.ec2_user_id ] )
        bundle_command.extend( [ "-r", arch ] )
        bundle_command.extend( [ "--ec2cert", ec2_service_cert ] )
        
        self.log.debug("Executing bundle command: %s " % (bundle_command))
        
        bundle_output = subprocess_check_output(bundle_command)
        
        self.log.debug("Bundle command complete")
        self.log.debug("Bundle command output: %s " % (str(bundle_output)))
        self.percent_complete=40
        
        manifest = bundle_destination + "/" + input_image_name + ".manifest.xml"
        
        upload_command = [ "euca-upload-bundle", "-b", bucket, "-m", manifest, "--ec2cert", ec2_service_cert, "-a", self.ec2_access_key, "-s", self.ec2_secret_key, "-U" , upload_url ]
        self.log.debug("Executing upload command: %s " % (upload_command))
        upload_output = subprocess_check_output(upload_command)
        self.log.debug("Upload command output: %s " % (str(upload_output)))
        self.percent_complete=90
        
        s3_path = bucket + "/" + input_image_name + ".manifest.xml"

        register_env = { 'EC2_URL':register_url }
        register_command = [ "euca-register" , "-A", self.ec2_access_key, "-S", self.ec2_secret_key, s3_path ]
        self.log.debug("Executing register command: %s with environment %s " % (register_command, repr(register_env)))
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
        metadata = dict(image=image_id, provider=provider, icicle="none", target_identifier=ami_id)
        self.warehouse.create_provider_image(self.image_id, metadata=metadata)
        
        #self.output_descriptor="unknown"
        #metadata = dict(uuid=self.image_id, type="provider_image", template=self.template, target=self.target, icicle=self.output_descriptor, image=image_id, provider=provider, target_identifier=ami_id)
        self.log.debug("FedoraBuilder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), str(image_id), str(self.image_id), str(metadata)))
        self.percent_complete=100
    
    def abort(self):
        pass
    
    # This file content is tightly bound up with our mod code above
    # I've inserted it as class variables for convenience
    rc_local="""curl http://169.254.169.254/2009-04-04/meta-data/public-keys/0/openssh-key 2>/dev/null >/tmp/my-key

if [ $? -eq 0 ] ; then
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
fi

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
