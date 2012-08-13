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

import logging
import zope
import oz.Fedora
import oz.TDL
import subprocess
import os
import shutil
import re
import guestfs
import string
import libxml2
import httplib2
import traceback
import pycurl
import gzip
import ConfigParser
import boto.ec2
from time import *
from tempfile import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.ReservationManager import ReservationManager
from boto.s3.connection import S3Connection
from boto.s3.connection import Location
from boto.exception import *
from boto.ec2.blockdevicemapping import EBSBlockDeviceType, BlockDeviceMapping
from imgfac.CloudDelegate import CloudDelegate

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


class EC2Cloud(object):
    zope.interface.implements(CloudDelegate)

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def __init__(self):
        # Note that we are now missing ( template, target, config_block = None):
        super(EC2Cloud, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        config_obj = ApplicationConfiguration()
        self.app_config = config_obj.configuration
        self.oz_config = ConfigParser.SafeConfigParser()
        self.oz_config.read("/etc/oz/oz.cfg")
        self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])
        
        if "ec2" in config_obj.jeos_images:
            self.ec2_jeos_amis = config_obj.jeos_images['ec2']
        else:
            self.log.warning("No JEOS amis defined for ec2.  Snapshot builds will not be possible.")
            self.ec2_jeos_amis = {}


    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_should_create_target_image() called on EC2Cloud plugin - returning True')
        return True


    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        # Nothing really to do here
        pass


    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in EC2Cloud plugin')
        # The bulk of what is done here is EC2 specific
        # There are OS conditionals thrown in at the moment
        # For now we are putting everything into the EC2 Cloud plugin
        # TODO: Revisit this, and the plugin interface, to see if there are ways to
        #       make the separation cleaner

        try:
            # TODO: More convenience vars - revisit
            self.template = template
            self.target = target
            self.builder = builder
            self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml, rootpw_required=True)
            self._get_os_helper()
            # Add in target specific content
            self.add_target_content()

            # TODO: This is a convenience variable for refactoring - rename
            self.new_image_id = builder.target_image.identifier

            # This lets our logging helper know what image is being operated on
            self.active_image = self.builder.target_image
                    
            self.activity("Initializing Oz environment")
            # Create a name combining the TDL name and the UUID for use when tagging EC2 AMIs
            self.longname = self.tdlobj.name + "-" + self.new_image_id

            # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
            # We don't really care about the name so just force uniqueness
            self.tdlobj.name = "factory-build-" + self.new_image_id

            # populate a config object to pass to OZ; this allows us to specify our
            # own output dir but inherit other Oz behavior
            self.oz_config = ConfigParser.SafeConfigParser()
            self.oz_config.read("/etc/oz/oz.cfg")
            self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])

            # make this a property to enable quick cleanup on abort
            self.instance = None

            # OK great, we now have a customized KVM image
            # Now we do some target specific transformation
            # None of these things actually require anything other than the TDL object
            # and the original disk image
            
            # At this point our builder has a target_image and a base_image
            # OS plugin has already provided the initial file for us to work with
            # which we can currently assume is a raw KVM compatible image

            self.modify_oz_filesystem()

            self.ec2_copy_filesystem()
            self.ec2_modify_filesystem()

        except:
            self.log_exc()
            self.status="FAILED"
            raise

        self.percent_complete=100
        self.status="COMPLETED"

    def _get_os_helper(self):
        # For now we are adopting a 'mini-plugin' approach to OS specific code within the EC2 plugin
        # In theory, this could live in the OS plugin - however, the code in question is very tightly
        # related to the EC2 plugin, so it probably should stay here
        try:
            # Change RHEL-6 to RHEL6, etc.
            os_name = self.tdlobj.distro.translate(None, '-')
            class_name = "%s_ec2_Helper" % (os_name)
            module_name = "imgfactory-plugins.EC2Cloud.EC2CloudOSHelpers.%s" % (class_name)
            __import__(module_name)
            os_helper_class = getattr(sys.modules[module_name], class_name)
            self.os_helper = os_helper_class(self)
        except:
            self.log_exc()
            raise ImageFactoryException("Unable to create EC2 OS helper object for distro (%s) in TDL" % (self.tdlobj.distro) )

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        self.log.info('push_image_to_provider() called in EC2Cloud')

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier

        self.tdlobj = oz.TDL.TDL(xmlstring=builder.target_image.template, rootpw_required=True)
        self._get_os_helper()
        self.builder = builder
        self.active_image = self.builder.provider_image
        self.push_image_upload(target_image, provider, credentials)


    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        self.log.debug("Deleting AMI (%s)" % (self.builder.provider_image.identifier_on_provider))
        self.activity("Preparing EC2 region details")
        region=provider
        region_conf=self.ec2_region_details[region]
        boto_loc = region_conf['boto_loc']
        if region != "ec2-us-east-1":
            s3_url = "http://s3-%s.amazonaws.com/" % (region_conf['host'])
        else:
            # Note to Amazon - would it be that hard to have s3-us-east-1.amazonaws.com?
            s3_url = "http://s3.amazonaws.com/"

        self.ec2_decode_credentials(credentials)
        
        ec2region = boto.ec2.get_region(boto_loc, aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)

        amis = conn.get_all_images([ self.builder.provider_image.identifier_on_provider ])
        if len(amis) == 0:
            raise ImageFactoryException("Unable to find AMI (%s) - cannot delete it" % (self.builder.provider_image.identifier_on_provider))

        if len(amis) > 1:
            raise ImageFactoryException("AMI lookup during delete returned more than one result - this should never happen - aborting")

        if ami.root_device_type == "ebs":
            self.log.debug("This is an EBS AMI")
            # Disect the block device mapping to identify the snapshots
            bd_map = ami.block_device_mapping
            self.log.debug("De-registering AMI")
            ami.deregister()
            self.log.debug("Deleting EBS snapshots associated with AMI")
            for bd in bd_map:
                self.log.debug("Deleting bd snapshot (%s) for bd (%s)" % (bd_map[bd].snapshot_id, bd))
                conn.delete_snapshot(bd_map[bd].snapshot_id)
        else:
            self.log.debug("This is an S3 AMI")
            s3_conn = boto.s3.connection.S3Connection(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key, host=s3_url)
            # Disect the location to get the bucket and key for the manifest
            (bucket, key) = split(ami.location, '/', 1)
            self.log.debug("Retrieving S3 AMI manifest from bucket (%s) at key (%s)" % (bucket, key))
            bucket = s3_conn.get_bucket(bucket)
            key_obj = bucket.get_key(key)
            manifest = key_obj.get_contents_as_string()
            # It is possible that the key has a path-like structure"
            # The XML contains only filenames - not path components
            # so extract any "directory" type stuff here
            keyprefix = ""
            keysplit = rsplit(key,"/",1)
            if len(keysplit) == 2:
                keyprefix="%s/" % (keysplit[0])

            self.log.debug("Deleting S3 image disk chunks")
            man_etree = ElementTree.fromstring(manifest)
            for part in man_etree.find("image").find("parts").findall("part"):
                filename = part.find("filename").text
                fullname = "%s%s" % (keyprefix, filename)
                part_key_obj = bucket.get_key(fullname)
                self.log.debug("Deleting %s" % (fullname))
                part_key_obj.delete()
            self.log.debug("Deleting manifest object %s" % (key))
            key_obj.delete()
            
            self.log.debug("de-registering the AMI itself")
            ami.deregister()

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())
        self.active_image.status_detail['error'] = traceback.format_exc()

    def modify_oz_filesystem(self):
        self.activity("Removing unique identifiers from image - Adding cloud information")

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
        # Second argument is 0 - means don't save a backup - this confuses network init
        g.aug_init("/", 0)
        if g.aug_rm("/files/etc/sysconfig/network-scripts/ifcfg-eth0/HWADDR"):
            self.log.debug("Removed HWADDR from image's /etc/sysconfig/network-scripts/ifcfg-eth0")
            g.aug_save()
        else:
            self.log.debug("Failed to remove HWADDR from image's /etc/sysconfig/network-scripts/ifcfg-eth0")
        g.aug_close()

        g.sync ()
        g.umount_all ()


    def ec2_copy_filesystem(self):
        self.activity("Copying image contents to single flat partition for EC2")
        target_image=self.image + ".tmp"

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
        # F16 and upwards end up with boot on sda2 due to GRUB changes
        if (self.tdlobj.distro == 'Fedora') and (int(self.tdlobj.update) >= 16):
            g.mount_ro ("/dev/sda2", "/in/boot")
        else:
            g.mount_ro ("/dev/sda1", "/in/boot")
        g.mount_options ("", "/dev/sdb", "/out/in")

        self.log.info("Copying image contents to EC2 flat filesystem")
        g.cp_a("/in/", "/out")
        self.log.info("Done")

        g.sync ()
        g.umount_all ()
        os.unlink(tmp_image_file)
        self.log.debug("Copy complete - removing old image and replacing with new flat filesystem image")
        os.unlink(self.image)
        os.rename(target_image, self.image)


    def ec2_modify_filesystem(self):
        # Modifications
        # Many of these are more or less directly ported from BoxGrinder
        # Boxgrinder is written and maintained by Marek Goldmann and can be found at:
        # http://boxgrinder.org/

        # TODO: This would be safer and more robust if done within the running modified
        # guest - in this would require tighter Oz integration

        self.activity("Modifying flat filesystem with EC2 specific changes")
        g = guestfs.GuestFS ()

        g.add_drive(self.image)
        g.launch ()

        # Do inspection here, as libguestfs prefers we do it before mounting anything
        # This should always be /dev/vda or /dev/sda but we do it anyway to be safe
        osroot = g.inspect_os()[0]

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
        # TODO: Match OS default behavior and/or what is found in the existing image

        self.log.info("Modifying and uploading fstab")
        # Make arch conditional
        if arch == "x86_64":
            tmpl=self.fstab_64bit
        else:
            tmpl=self.fstab_32bit

        g.write("/etc/fstab", tmpl)

        # BG - Enable networking
        # Upload a known good ifcfg-eth0 and then chkconfig on networking
        self.log.info("Enabling networking and uploading ifcfg-eth0")
        g.sh("/sbin/chkconfig network on")
        g.write("/etc/sysconfig/network-scripts/ifcfg-eth0", self.ifcfg_eth0)

        # Disable first boot - this slows things down otherwise
        if g.is_file("/etc/init.d/firstboot"):
            g.sh("/sbin/chkconfig firstboot off")

        # Ensure a sensible runlevel on systemd systems (>=F15)
        # Oz/Anaconda hand us a graphical runlevel
        if g.is_symlink("/etc/systemd/system/default.target"):
            g.rm("/etc/systemd/system/default.target")
            g.ln_s("/lib/systemd/system/multi-user.target","/etc/systemd/system/default.target")

        # BG - Upload rc.local extra content
        # Again, this uses a static copy - this bit is where the ssh key is downloaded
        # TODO: Is this where we inject puppet?
        # TODO - Possibly modify the key injection from rc_local to be only non-root
        #  and add a special user to sudoers - this is what BG has evolved to do
        self.log.info("Updating rc.local for key injection")
        g.write("/tmp/rc.local", self.rc_local)
        # Starting with F16, rc.local doesn't exist by default
        if not g.exists("/etc/rc.d/rc.local"):
            g.sh("echo \#\!/bin/bash > /etc/rc.d/rc.local")
            g.sh("chmod a+x /etc/rc.d/rc.local")
        g.sh("cat /tmp/rc.local >> /etc/rc.d/rc.local")
        g.rm("/tmp/rc.local")

        # Don't ever allow password logins to EC2 sshd
        g.aug_init("/", 0)
        g.aug_set("/files/etc/ssh/sshd_config/PermitRootLogin", "without-password")
        g.aug_save()
        g.aug_close()
        self.log.debug("Disabled root loging with password in /etc/ssh/sshd_config")

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
        elif (len(kernel_versions) > 1) and (arch == "i386") and (distro == "fedora") and (int(major_version) <=13):
            paere = re.compile("PAE$")
            for kern in kernel_versions:
                if paere.search(kern):
                    kernel_version = kern
        else:
            kernel_version = kernel_versions[len(kernel_versions)-1]
        if not kernel_version:
            self.log.debug("Unable to extract correct kernel version from: %s" % (str(kernel_versions)))
            raise ImageFactoryException("Unable to extract kernel version")

        self.log.debug("Using kernel version: %s" % (kernel_version))


        # We could deduce this from version but it's easy to inspect
        bootramfs = int(g.sh("ls -1 /boot | grep initramfs | wc -l"))
        ramfs_prefix = "initramfs" if bootramfs > 0 else "initrd"

        name="Image Factory EC2 boot - kernel: " + kernel_version

        if (distro == "rhel") and (major_version == 5):
            g.sh("/sbin/mkinitrd -f -v --preload xenblk --preload xennet /boot/initrd-%s.img %s" % (kernel_version))

        kernel_options = ""
        if (distro == "fedora") and (str(major_version) == "16"):
            self.log.debug("Adding idle=halt option for Fedora 16 on EC2")
            kernel_options += "idle=halt " 

        tmpl = self.menu_lst
        tmpl = string.replace(tmpl, "#KERNEL_OPTIONS#", kernel_options)
        tmpl = string.replace(tmpl, "#KERNEL_VERSION#", kernel_version)
        tmpl = string.replace(tmpl, "#KERNEL_IMAGE_NAME#", ramfs_prefix)
        tmpl = string.replace(tmpl, "#TITLE#", name)

        g.write("/boot/grub/menu.lst", tmpl)

        # EC2 Xen nosegneg bug
        # This fixes issues with Fedora >=14 on EC2: https://bugzilla.redhat.com/show_bug.cgi?id=651861#c39
        if (arch == "i386") and (distro == "fedora") and (int(major_version) >= 14):
            self.log.info("Fixing Xen EC2 bug")
            g.sh("echo \"hwcap 1 nosegneg\" > /etc/ld.so.conf.d/libc6-xen.conf")
            g.sh("/sbin/ldconfig")

        self.log.info("Done with EC2 filesystem modifications")

        g.sync ()
        g.umount_all ()

        # TODO: Based on architecture associate one of two XML blocks that contain the correct
        # regional AKIs for pvgrub

    def wait_for_ec2_ssh_access(self, guestaddr):
        self.activity("Waiting for SSH access to EC2 instance")
        for i in range(300):
            if i % 10 == 0:
                self.log.debug("Waiting for EC2 ssh access: %d/300" % (i))

            try:
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, "/bin/true", timeout = 10)
                break
            except:
                pass

            sleep(1)

        if i == 299:
            raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

    def wait_for_ec2_instance_start(self, instance):
        self.activity("Waiting for EC2 instance to become active")
        for i in range(300):
            if i % 10 == 0:
                self.log.debug("Waiting for EC2 instance to start: %d/300" % (i))
            try:
                instance.update()
            except EC2ResponseError, e:
                # We occasionally get errors when querying an instance that has just started - ignore them and hope for the best
                self.log.warning("EC2ResponseError encountered when querying EC2 instance (%s) - trying to continue" % (instance.id), exc_info = True)
            except:
                self.log.error("Exception encountered when updating status of instance (%s)" % (instance.id), exc_info = True)
                self.status="FAILED"
                try:
                    self.terminate_instance(instance)
                except:
                    log.warning("WARNING: Instance (%s) failed to start and will not terminate - it may still be running" % (instance.id), exc_info = True)
                    raise ImageFactoryException("Instance (%s) failed to fully start or terminate - it may still be running" % (instance.id))
                raise ImageFactoryException("Exception encountered when waiting for instance (%s) to start" % (instance.id))
            if instance.state == u'running':
                break
            sleep(1)

        if instance.state != u'running':
            self.status="FAILED"
            try:
                self.terminate_instance(instance)
            except:
                log.warning("WARNING: Instance (%s) failed to start and will not terminate - it may still be running" % (instance.id), exc_info = True)
                raise ImageFactoryException("Instance (%s) failed to fully start or terminate - it may still be running" % (instance.id))
            raise ImageFactoryException("Instance failed to start after 300 seconds - stopping")

    def terminate_instance(self, instance):
        # boto 1.9 claims a terminate() method but does not implement it
        # boto 2.0 throws an exception if you attempt to stop() an S3 backed instance
        # introspect here and do the best we can
        if "terminate" in dir(instance):
            instance.terminate()
        else:
            instance.stop()

    def snapshot_image_on_provider(self, builder, provider, credentials, target, template, parameters):
        self.log.info('snapshot_image_on_provider() called in EC2Cloud')

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier

        # Template must be defined for snapshots
        self.tdlobj = oz.TDL.TDL(xmlstring=str(template), rootpw_required=True)
        self._get_os_helper()
        self.os_helper.init_guest()

        self.builder = builder
        self.active_image = self.builder.provider_image

        def replace(item):
            if item in [self.ec2_access_key, self.ec2_secret_key]:
                return "REDACTED"
            return item

        self.log.debug("Being asked to push for provider %s" % (provider))
        self.log.debug("distro: %s - update: %s - arch: %s" % (self.tdlobj.distro, self.tdlobj.update, self.tdlobj.arch))
        self.ec2_decode_credentials(credentials)
        self.log.debug("acting as EC2 user: %s" % (str(self.ec2_user_id)))

        self.status="PUSHING"
        self.percent_complete=0

        self.activity("Preparing EC2 region details")
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

        # These are the region details for the region we are building in (which may be different from the target)
        build_region_conf = self.ec2_region_details[build_region]


        # Note that this connection may be to a region other than the target
        self.activity("Preparing EC2 JEOS AMI details")
        ec2region = boto.ec2.get_region(build_region_conf['host'], aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)

        # Verify that AMI actually exists - err out if not
        # Extract AMI type - "ebs" or "instance-store" (S3)
        # If build_region != provider (meaning we are not building in our target region)
        #  if type == ebs throw an error - EBS builds must be in the target region/provider
        amis = conn.get_all_images([ ami_id ])
        ami = amis[0]
        if (build_region != provider) and (ami.root_device_type == "ebs"):
            self.log.error("EBS JEOS image exists in us-east-1 but not in target region (%s)" % (provider))
            raise ImageFactoryException("No EBS JEOS image for region (%s) - aborting" % (provider))

        instance_type=self.app_config.get('ec2-64bit-util','m1.large')
        if self.tdlobj.arch == "i386":
            instance_type=self.app_config.get('ec2-32bit-util','m1.small')

        # Create a use-once SSH-able security group
        self.activity("Creating EC2 security group for SSH access to utility image")
        factory_security_group_name = "imagefactory-%s" % (self.new_image_id, )
        factory_security_group_desc = "Temporary ImageFactory generated security group with SSH access"
        self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
        factory_security_group = conn.create_security_group(factory_security_group_name, factory_security_group_desc)
        factory_security_group.authorize('tcp', 22, 22, '0.0.0.0/0')

        # Create a use-once SSH key
        self.activity("Creating EC2 SSH key pair")
        key_name = "fac-tmp-key-%s" % (self.new_image_id)
        key = conn.create_key_pair(key_name)
        # Shove into a named temp file
        key_file_object = NamedTemporaryFile()
        key_file_object.write(key.material)
        key_file_object.flush()
        key_file=key_file_object.name

        # Now launch it
        self.activity("Launching EC2 JEOS image")
        self.log.debug("Starting ami %s with instance_type %s" % (ami_id, instance_type))
        reservation = conn.run_instances(ami_id, instance_type=instance_type, key_name=key_name, security_groups = [ factory_security_group_name ])

        if len(reservation.instances) != 1:
            self.status="FAILED"
            raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

        self.instance = reservation.instances[0]

        self.wait_for_ec2_instance_start(self.instance)

        # From this point on we must be sure to terminate the instance when we are done
        # so wrap in a try/finally
        # Accidentally running a 64 bit instance doing nothing costs 56 USD week
        try:
            guestaddr = self.instance.public_dns_name

            self.guest.sshprivkey = key_file

            # Ugly ATM because failed access always triggers an exception
            self.wait_for_ec2_ssh_access(guestaddr)

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 20 seconds for remaining boot tasks")
            sleep(20)

            self.activity("Customizing running EC2 JEOS instance")
            self.log.debug("Stopping cron and killing any updatedb process that may be running")
            # updatedb interacts poorly with the bundle step - make sure it isn't running
            self.guest.guest_execute_command(guestaddr, "/sbin/service crond stop")
            self.guest.guest_execute_command(guestaddr, "killall -9 updatedb || /bin/true")
            self.log.debug("Done")

            if ami.root_device_type == "instance-store":
                # Different OSes need different steps here
                # Only needed for S3 images
                self.install_euca_tools(guestaddr)

            # Not all JEOS images contain this - redoing it if already present is harmless
            self.log.info("Creating cloud-info file indicating target (%s)" % (self.target))
            self.guest.guest_execute_command(guestaddr, 'echo CLOUD_TYPE=\\\"%s\\\" > /etc/sysconfig/cloud-info' % (self.target))

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

            new_ami_id = None
            image_name = str(self.longname)
            image_desc = "%s - %s" % (asctime(localtime()), self.tdlobj.description)

            if ami.root_device_type == "instance-store":
                # This is an S3 image so we snapshot to another S3 image using euca-bundle-vol and
                # associated tools
                ec2cert =  "/etc/pki/imagefactory/cert-ec2.pem"

                # This is needed for uploading and registration
                # Note that it is excluded from the final image
                self.activity("Uploading certificate material for bundling of instance")
                self.guest.guest_live_upload(guestaddr, self.ec2_cert_file, "/tmp")
                self.guest.guest_live_upload(guestaddr, self.ec2_key_file, "/tmp")
                self.guest.guest_live_upload(guestaddr, ec2cert, "/tmp")
                self.log.debug("Cert upload complete")

                # Some local variables to make the calls below look a little cleaner
                ec2_uid = self.ec2_user_id
                arch = self.tdlobj.arch
                # AKI is set above
                uuid = self.new_image_id

                # We exclude /mnt /tmp and /root/.ssh to avoid embedding our utility key into the image
                command = "euca-bundle-vol -c /tmp/%s -k /tmp/%s -u %s -e /mnt,/tmp,/root/.ssh --arch %s -d /mnt/bundles --kernel %s -p %s -s 10240 --ec2cert /tmp/cert-ec2.pem --fstab /etc/fstab -v /" % (os.path.basename(self.ec2_cert_file), os.path.basename(self.ec2_key_file), ec2_uid, arch, aki, uuid)
                self.activity("Bundling remote instance in-place")
                self.log.debug("Executing bundle vol command: %s" % (command))
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, command)
                self.log.debug("Bundle output: %s" % (stdout))

                # Now, ensure we have an appropriate bucket to receive this image
                # TODO: This is another copy - make it a function soon please
                bucket= "imagefactory-" + region + "-" + self.ec2_user_id

                self.activity("Preparing S3 destination for image bundle")
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

                # Unfortunately, for some OS versions we need to correct the manifest
                self.correct_remote_manifest(guestaddr, manifest)

                command = ['euca-upload-bundle', '-b', bucket, '-m', manifest,
                           '--ec2cert', '/tmp/cert-ec2.pem',
                           '-a', self.ec2_access_key, '-s', self.ec2_secret_key,
                           '-U', upload_url]
                command_log = map(replace, command)
                self.activity("Uploading bundle to S3")
                self.log.debug("Executing upload bundle command: %s" % (command_log))
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, ' '.join(command))
                self.log.debug("Upload output: %s" % (stdout))

                manifest_s3_loc = "%s/%s.manifest.xml" % (bucket, uuid)

                command = ['euca-register', '-U', register_url,
                           '-A', self.ec2_access_key, '-S', self.ec2_secret_key, '-a', self.tdlobj.arch,
                           #'-n', image_name, '-d', image_desc,
                           manifest_s3_loc]
                command_log = map(replace, command)
                self.activity("Registering bundle as a new AMI")
                self.log.debug("Executing register command: %s" % (command_log))
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr,
                                                                           ' '.join(command))
                self.log.debug("Register output: %s" % (stdout))

                m = re.match(".*(ami-[a-fA-F0-9]+)", stdout)
                new_ami_id = m.group(1)
                self.log.debug("Extracted AMI ID: %s " % (new_ami_id))
                ### End S3 snapshot code
            else:
                self.activity("Preparing image for an EBS snapshot")
                self.log.debug("Performing image prep tasks for EBS backed images")
                self.ebs_pre_shapshot_tasks(guestaddr)
                self.activity("Requesting EBS snapshot creation by EC2")
                self.log.debug("Creating a new EBS backed image from our running EBS instance")
                new_ami_id = conn.create_image(self.instance.id, image_name, image_desc)
                self.log.debug("EUCA creat_image call returned AMI ID: %s" % (new_ami_id))
                self.activity("Waiting for newly generated AMI to become available")
                # As with launching an instance we have seen occasional issues when trying to query this AMI right
                # away - give it a moment to settle
                sleep(10)
                new_amis = conn.get_all_images([ new_ami_id ])
                new_ami = new_amis[0]
                timeout = 120
                interval = 10
                for i in range(timeout):
                    new_ami.update()
                    if new_ami.state == "available":
                        break
                    elif new_ami.state == "failed":
                        raise ImageFactoryException("Amazon reports EBS image creation failed")
                    self.log.debug("AMI status (%s) - waiting for 'available' - [%d of %d seconds elapsed]" % (new_ami.state, i * interval, timeout * interval))
                    sleep(interval)

            if not new_ami_id:
                raise ImageFactoryException("Failed to produce an AMI ID")

            # This replaces our Warehouse calls
            self.builder.provider_image.icicle = self.output_descriptor
            self.builder.provider_image.identifier_on_provider = new_ami_id
            self.builder.provider_account_identifier = self.ec2_access_key
        finally:
            self.activity("Terminating EC2 instance and deleting security group and SSH key")
            self.terminate_instance(self.instance)
            key_file_object.close()
            conn.delete_key_pair(key_name)
            try:
                timeout = 60
                interval = 5
                for i in range(timeout):
                    self.instance.update()
                    if(self.instance.state == "terminated"):
                        factory_security_group.delete()
                        self.log.debug("Removed temporary security group (%s)" % (factory_security_group_name))
                        break
                    elif(i < timeout):
                        self.log.debug("Instance status (%s) - waiting for 'terminated'. [%d of %d seconds elapsed]" % (self.instance.state, i * interval, timeout * interval))
                        sleep(interval)
                    else:
                        raise Exception("Timeout waiting for instance to terminate.")
            except Exception, e:
                self.log.debug("Unable to delete temporary security group (%s) due to exception: %s" % (factory_security_group_name, e))

        self.log.debug("Fedora_ec2_Builder instance %s pushed image with uuid %s to provider_image UUID (%s)" % (id(self), target_image_id, self.new_image_id))
        self.percent_complete=100
        self.status="COMPLETED"

    def push_image_upload(self, target_image_id, provider, credentials):
        self.status="PUSHING"
        self.percent_complete=0
        try:
            if self.app_config["ec2_ami_type"] == "s3":
                self.ec2_push_image_upload(target_image_id, provider,
                                           credentials)
            elif self.app_config["ec2_ami_type"] == "ebs":
                self.ec2_push_image_upload_ebs(target_image_id, provider,
                                               credentials)
            else:
                raise ImageFactoryException("Invalid or unspecified EC2 AMI type in config file")
        except:
            self.log_exc()
            self.status="FAILED"
            raise
        self.status="COMPLETED"

    def _ec2_get_xml_node(self, doc, credtype):
        nodes = doc.xpathEval("//provider_credentials/ec2_credentials/%s" % (credtype))
        if len(nodes) < 1:
            raise ImageFactoryException("No EC2 %s available" % (credtype))

        return nodes[0].content

    def ec2_decode_credentials(self, credentials):
        self.activity("Preparing EC2 credentials")
        doc = libxml2.parseDoc(credentials)

        self.ec2_user_id = self._ec2_get_xml_node(doc, "account_number")
        self.ec2_access_key = self._ec2_get_xml_node(doc, "access_key")
        self.provider_account_identifier = self.ec2_access_key
        self.ec2_secret_key = self._ec2_get_xml_node(doc, "secret_access_key")

        # Support both "key" and "x509_private" as element names
        ec2_key_node = doc.xpathEval("//provider_credentials/ec2_credentials/key")
        if not ec2_key_node:
            ec2_key_node = doc.xpathEval("//provider_credentials/ec2_credentials/x509_private")
        if not ec2_key_node:
            raise ImageFactoryException("No x509 private key found in ec2 credentials")
        ec2_key=ec2_key_node[0].content

        # Support both "certificate" and "x509_public" as element names
        ec2_cert_node = doc.xpathEval("//provider_credentials/ec2_credentials/certificate")
        if not ec2_cert_node:
            ec2_cert_node = doc.xpathEval("//provider_credentials/ec2_credentials/x509_public")
        if not ec2_cert_node:
            raise ImageFactoryException("No x509 public certificate found in ec2 credentials")
        ec2_cert = ec2_cert_node[0].content

        doc.freeDoc()

        # Shove certs into  named temporary files
        self.ec2_cert_file_object = NamedTemporaryFile()
        self.ec2_cert_file_object.write(ec2_cert)
        self.ec2_cert_file_object.flush()
        self.ec2_cert_file=self.ec2_cert_file_object.name

        self.ec2_key_file_object = NamedTemporaryFile()
        self.ec2_key_file_object.write(ec2_key)
        self.ec2_key_file_object.flush()
        self.ec2_key_file=self.ec2_key_file_object.name

    def ec2_push_image_upload_ebs(self, target_image_id, provider, credentials):
        # TODO: Merge with ec2_push_image_upload and/or factor out duplication
        # In this case we actually do need an Oz object to manipulate a remote guest
        self.os_helper.init_guest()

        self.ec2_decode_credentials(credentials)
        # We don't need the x509 material here so close the temp files right away
        # TODO: Mod the decode to selectively create the files in the first place
        #   This is silly and messy
        self.ec2_cert_file_object.close()
        self.ec2_key_file_object.close()

        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.data
        input_image_name = os.path.basename(input_image)

        input_image_compressed = input_image + ".gz"
        input_image_compressed_name = os.path.basename(input_image_compressed)
        compress_complete_marker = input_image_compressed + "-factory-compressed"

        # We are guaranteed to hit this from multiple builders looking at the same image
        # Grab a named lock based on the file name
        # If the file is not present this guarantees that only one thread will compress
        # NOTE: It is important to grab the lock before we even look for the file
        # TODO: Switched this to use shell callouts because of a 64 bit bug - fix that
        res_mgr = ReservationManager()
        res_mgr.get_named_lock(input_image_compressed)
        try:
            if not os.path.isfile(input_image_compressed) or not os.path.isfile(compress_complete_marker):
                self.activity("Compressing image file for upload to EC2")
                self.log.debug("No compressed version of image file found - compressing now")
                compress_command = 'gzip -c %s > %s' % (input_image, input_image_compressed)
                self.log.debug("Compressing image file with external gzip cmd: %s" % (compress_command))
                result = subprocess.call(compress_command, shell = True)
                if result:
                    raise ImageFactoryException("Compression of image failed")
                self.log.debug("Compression complete")
                # Mark completion with an empty file
                # Without this we might use a partially compressed file that resulted from a crash or termination
                subprocess.call("touch %s" % (compress_complete_marker), shell = True)
        finally:
            res_mgr.release_named_lock(input_image_compressed)

        self.activity("Preparing EC2 region details")
        region=provider
        region_conf=self.ec2_region_details[region]
        aki = region_conf[self.tdlobj.arch]

        # Use our F16 - 32 bit JEOS image as the utility image for uploading to the EBS volume
        try:
            ami_id = self.ec2_jeos_amis[provider]['Fedora']['16']['i386']
        except KeyError:
            raise ImageFactoryException("No Fedora 16 i386 JEOS/utility image in region (%s) - aborting", (provider))

        # i386
        instance_type=self.app_config.get('ec2-32bit-util','m1.small')

        self.activity("Initializing connection to ec2 region (%s)" % region_conf['host'])
        ec2region = boto.ec2.get_region(region_conf['host'], aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)

        # Create security group
        self.activity("Creating EC2 security group for SSH access to utility image")
        factory_security_group_name = "imagefactory-%s" % (str(self.new_image_id))
        factory_security_group_desc = "Temporary ImageFactory generated security group with SSH access"
        self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
        factory_security_group = conn.create_security_group(factory_security_group_name, factory_security_group_desc)
        factory_security_group.authorize('tcp', 22, 22, '0.0.0.0/0')

        # Create a use-once SSH key
        self.activity("Creating SSH key pair for image upload")
        key_name = "fac-tmp-key-%s" % (self.new_image_id)
        key = conn.create_key_pair(key_name)
        # Shove into a named temp file
        key_file_object = NamedTemporaryFile()
        key_file_object.write(key.material)
        key_file_object.flush()
        key_file=key_file_object.name

        # Now launch it
        self.activity("Launching EC2 utility image")
        reservation = conn.run_instances(ami_id, instance_type=instance_type, key_name=key_name, security_groups = [ factory_security_group_name ])

        if len(reservation.instances) != 1:
            self.status="FAILED"
            raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

        self.instance = reservation.instances[0]

        self.wait_for_ec2_instance_start(self.instance)

        # From this point on we must be sure to terminate the instance when we are done
        # so wrap in a try/finally
        # Accidentally running a 64 bit instance doing nothing costs 56 USD week
        volume = None
        try:
            guestaddr = self.instance.public_dns_name

            self.guest.sshprivkey = key_file

            # Ugly ATM because failed access always triggers an exception
            self.wait_for_ec2_ssh_access(guestaddr)

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 20 seconds for remaining boot tasks")
            sleep(20)

            self.activity("Creating 10 GiB volume in (%s) to hold new image" % (self.instance.placement))
            volume = conn.create_volume(10, self.instance.placement)

            # Do the upload before testing to see if the volume has completed
            # to get a bit of parallel work
            self.activity("Uploading compressed image file")
            self.guest.guest_live_upload(guestaddr, input_image_compressed, "/mnt")

            # Don't burden API users with the step-by-step details here
            self.activity("Preparing EC2 volume to receive new image")

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
            conn.attach_volume(volume.id, self.instance.id, "/dev/sdh")

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
                raise ImageFactoryException("Unable to attach volume (%s) to instance (%s) aborting" % (volume.id, self.instance.id))

            # TODO: This may not be necessary but it helped with some funnies observed during testing
            #         At some point run a bunch of builds without the delay to see if it breaks anything
            self.log.debug("Waiting 20 seconds for EBS attachment to stabilize")
            sleep(20)

            # Decompress image into new EBS volume
            self.activity("Decompressing image into new volume")
            command = "gzip -dc /mnt/%s | dd of=/dev/xvdh bs=4k\n" % (input_image_compressed_name)
            self.log.debug("Decompressing image file into EBS device via command: %s" % (command))
            self.guest.guest_execute_command(guestaddr, command)

            # Sync before snapshot
            self.guest.guest_execute_command(guestaddr, "sync")

            # Snapshot EBS volume
            self.activity("Taking EC2 snapshot of new volume")
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
            self.activity("Registering snapshot as a new AMI")
            self.log.debug("Registering snapshot (%s) as new EBS AMI" % (snapshot.id))
            ebs = EBSBlockDeviceType()
            ebs.snapshot_id = snapshot.id
            ebs.delete_on_termination = True
            block_map = BlockDeviceMapping()
            block_map['/dev/sda1'] = ebs
            # The ephemeral mappings are automatic with S3 images
            # For EBS images we need to make them explicit
            # These settings are required to make the same fstab work on both S3 and EBS images
            e0 = EBSBlockDeviceType()
            e0.ephemeral_name = 'ephemeral0'
            e1 = EBSBlockDeviceType()
            e1.ephemeral_name = 'ephemeral1'
            if self.tdlobj.arch == "i386":
                block_map['/dev/sda2'] = e0
                block_map['/dev/sda3'] = e1
            else:
                block_map['/dev/sdb'] = e0
                block_map['/dev/sdc'] = e1
            result = conn.register_image(name='ImageFactory created AMI - %s' % (self.new_image_id),
                            description='ImageFactory created AMI - %s' % (self.new_image_id),
                            architecture=self.tdlobj.arch,  kernel_id=aki,
                            root_device_name='/dev/sda1', block_device_map=block_map)

            ami_id = str(result)
            self.log.debug("Extracted AMI ID: %s " % (ami_id))
        except:
            self.log.debug("EBS image upload failed on exception")
            #DANGER!!! Uncomment at your own risk!
            #This is for deep debugging of the EBS utility instance - don't forget to shut it down manually
            #self.log.debug("EBS image upload failed on exception", exc_info = True)
            #self.log.debug("Waiting more or less forever to allow inspection of the instance")
            #self.log.debug("run this: ssh -i %s root@%s" % (key_file, self.instance.public_dns_name))
            #sleep(999999)
            raise
        finally:
            self.activity("Terminating EC2 instance and deleting temp security group and volume")
            self.terminate_instance(self.instance)
            key_file_object.close()
            conn.delete_key_pair(key_name)

            self.log.debug("Waiting up to 240 seconds for instance (%s) to shut down" % (self.instance.id))
            retcode = 1
            for i in range(24):
                self.instance.update()
                if self.instance.state == "terminated":
                    retcode = 0
                    break
                self.log.debug("Instance status (%s) - waiting for 'terminated': %d/240" % (self.instance.state, i*10))
                sleep(10)
            if retcode:
                self.log.warning("Instance (%s) failed to terminate - Unable to delete volume (%s) or delete factory temp security group" % (self.instance.id, volume.id))
            else:
                self.log.debug("Deleting temporary security group")
                factory_security_group.delete()
                if volume:
                    self.log.debug("Deleting EBS volume (%s)" % (volume.id))
                    volume.delete()

        # TODO: Add back-reference to ICICLE from base image object
        # This replaces our warehouse calls
        self.builder.provider_image.identifier_on_provider=ami_id
        self.builder.provider_image.provider_account_identifier=self.ec2_access_key

        self.log.debug("Fedora_ec2_Builder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
        self.percent_complete=100

    def ec2_push_image_upload(self, target_image_id, provider, credentials):
        def replace(item):
            if item in [self.ec2_access_key, self.ec2_secret_key]:
                return "REDACTED"
            return item

        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.data
        input_image_name = os.path.basename(input_image)

        self.ec2_decode_credentials(credentials)

        bundle_destination=self.app_config['imgdir']


        self.activity("Preparing EC2 region details and connection")
        region=provider
        region_conf=self.ec2_region_details[region]
        aki = region_conf[self.tdlobj.arch]
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
            # if the bucket already exists, it is not an error
            if buckerr.error_code != "BucketAlreadyOwnedByYou":
                raise

        # TODO: Make configurable?
        ec2_service_cert = "/etc/pki/imagefactory/cert-ec2.pem"

        bundle_command = [ "euca-bundle-image", "-i", input_image,
                           "--kernel", aki, "-d", bundle_destination,
                           "-a", self.ec2_access_key, "-s", self.ec2_secret_key,
                           "-c", self.ec2_cert_file, "-k", self.ec2_key_file,
                           "-u", self.ec2_user_id, "-r", self.tdlobj.arch,
                           "--ec2cert", ec2_service_cert ]

        bundle_command_log = map(replace, bundle_command)

        self.activity("Bundling image locally")
        self.log.debug("Executing bundle command: %s " % (bundle_command_log))

        bundle_output = subprocess_check_output(bundle_command)

        self.log.debug("Bundle command complete")
        self.log.debug("Bundle command output: %s " % (str(bundle_output)))
        self.percent_complete=40

        manifest = bundle_destination + "/" + input_image_name + ".manifest.xml"

        upload_command = [ "euca-upload-bundle", "-b", bucket, "-m", manifest,
                           "--ec2cert", ec2_service_cert,
                           "-a", self.ec2_access_key, "-s", self.ec2_secret_key,
                           "-U" , upload_url ]

        upload_command_log = map(replace, upload_command)

        self.activity("Uploading image to EC2")
        self.log.debug("Executing upload command: %s " % (upload_command_log))
        upload_output = subprocess_check_output(upload_command)
        self.log.debug("Upload command output: %s " % (str(upload_output)))
        self.percent_complete=90

        s3_path = bucket + "/" + input_image_name + ".manifest.xml"

        register_env = { 'EC2_URL':register_url }
        register_command = [ "euca-register" , "-A", self.ec2_access_key,
                             "-S", self.ec2_secret_key, "-a", self.tdlobj.arch, s3_path ]
        register_command_log = map(replace, register_command)
        self.activity("Registering image")
        self.log.debug("Executing register command: %s with environment %s " % (register_command_log, repr(register_env)))
        register_output = subprocess_check_output(register_command, env=register_env)
        self.log.debug("Register command output: %s " % (str(register_output)))
        m = re.match(".*(ami-[a-fA-F0-9]+)", register_output[0])
        ami_id = m.group(1)
        self.log.debug("Extracted AMI ID: %s " % (ami_id))

        # TODO: This should be in a finally statement that rethrows exceptions
        self.ec2_cert_file_object.close()
        self.ec2_key_file_object.close()

        self.status = "PUSHING"

        # TODO: Generate and store ICICLE
        # This replaces our warehouse calls
        self.builder.provider_image.identifier_on_provider = ami_id
        self.builder.provider_image.provider_account_identifier = self.ec2_access_key

        self.log.debug("Fedora_ec2_Builder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
        self.percent_complete=100

    def abort(self):
        # TODO: Make this progressively more robust

        # In the near term, the most important thing we can do is terminate any EC2 instance we may be using
        if self.instance:
            instance_id = self.instance.id
            try:
                self.terminate_instance(self.instance)
            except Exception, e:
                self.log.warning("Warning, encountered - Instance %s may not be terminated ******** " % (instance_id))
                self.log.exception(e)

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
    kernel /boot/vmlinuz-#KERNEL_VERSION# ro root=LABEL=/ rd_NO_PLYMOUTH #KERNEL_OPTIONS#
    initrd /boot/#KERNEL_IMAGE_NAME#-#KERNEL_VERSION#.img
"""

    fstab_32bit="""LABEL=/    /         ext3    defaults         1 1
/dev/xvda2  /mnt      ext3    defaults,nofail         1 2
/dev/xvda3  swap      swap    defaults,nofail         0 0
none       /dev/pts  devpts  gid=5,mode=620   0 0
none       /dev/shm  tmpfs   defaults         0 0
none       /proc     proc    defaults         0 0
none       /sys      sysfs   defaults         0 0
"""

    fstab_64bit="""LABEL=/    /         ext3    defaults         1 1
/dev/xvdb   /mnt      ext3    defaults,nofail         0 0
/dev/xvdc   /data     ext3    defaults,nofail         0 0
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
         'ec2-us-east-1':      { 'boto_loc': Location.DEFAULT,     'host':'us-east-1',      'i386': 'aki-805ea7e9', 'x86_64': 'aki-825ea7eb' },
         'ec2-us-west-1':      { 'boto_loc': 'us-west-1',          'host':'us-west-1',      'i386': 'aki-83396bc6', 'x86_64': 'aki-8d396bc8' },
         'ec2-us-west-2':      { 'boto_loc': 'us-west-2',          'host':'us-west-2',      'i386': 'aki-c2e26ff2', 'x86_64': 'aki-98e26fa8' },
         'ec2-ap-southeast-1': { 'boto_loc': 'ap-southeast-1',     'host':'ap-southeast-1', 'i386': 'aki-a4225af6', 'x86_64': 'aki-aa225af8' },
         'ec2-ap-northeast-1': { 'boto_loc': 'ap-northeast-1',     'host':'ap-northeast-1', 'i386': 'aki-ec5df7ed', 'x86_64': 'aki-ee5df7ef' },
         'ec2-sa-east-1':      { 'boto_loc': 'sa-east-1',          'host':'sa-east-1',      'i386': 'aki-bc3ce3a1', 'x86_64': 'aki-cc3ce3d1' },
         'ec2-eu-west-1':      { 'boto_loc': Location.EU,          'host':'eu-west-1',      'i386': 'aki-64695810', 'x86_64': 'aki-62695816' } }

        # July 13 - new approach - generic JEOS AMIs for Fedora - no userdata and no euca-tools
        #           ad-hoc ssh keys replace userdata - runtime install of euca tools for bundling
        # v0.6 of F14 and F15 - dropped F13 for now - also include official public RHEL hourly AMIs for RHEL6
        # Sept 1 - 2011 - updated us-west Fedora JEOSes to 0.6
        # Sept 30 - 2011 - Moved out of here entirely to ApplicationConfiguration
        # ec2_jeos_amis = <not here anymore>

    def add_target_content(self):
        """Merge in target specific package and repo content.
        TDL object must already exist as self.tdlobj"""
        doc = None
# TODONOW: Fix
#        if self.config_block:
        import os.path
        if None:
            doc = libxml2.parseDoc(self.config_block)
        elif os.path.isfile("/etc/imagefactory/target_content.xml"):
            doc = libxml2.parseFile("/etc/imagefactory/target_content.xml")
        else:
            self.log.debug("Found neither a call-time config nor a config file - doing nothing")
            return

        # Purely to make the xpath statements below a tiny bit shorter
        target = self.target
        os=self.tdlobj.distro
        version=self.tdlobj.update
        arch=self.tdlobj.arch

        # We go from most to least specific in this order:
        #   arch -> version -> os-> target
        # Note that at the moment we even allow an include statment that covers absolutely everything.
        # That is, one that doesn't even specify a target - this is to support a very simple call-time syntax
        include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and @arch='%s']" %
                                (target, os, version, arch))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and not(@arch)]" %
                                    (target, os, version))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and not(@version) and not(@arch)]" %
                                        (target, os))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and not(@os) and not(@version) and not(@arch)]" %
                                            (target))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[not(@target) and not(@os) and not(@version) and not(@arch)]")
        if len(include) == 0:
            self.log.debug("cannot find a config section that matches our build details - doing nothing")
            return

        # OK - We have at least one config block that matches our build - take the first one, merge it and be done
        # TODO: Merge all of them?  Err out if there is more than one?  Warn?
        include = include[0]

        packages = include.xpathEval("packages")
        if len(packages) > 0:
            self.tdlobj.merge_packages(str(packages[0]))

        repositories = include.xpathEval("repositories")
        if len(repositories) > 0:
            self.tdlobj.merge_repositories(str(repositories[0]))

