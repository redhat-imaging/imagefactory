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
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from boto.s3.connection import S3Connection
from boto.s3.connection import Location
from boto.exception import *
from boto.ec2.blockdevicemapping import EBSBlockDeviceType, BlockDeviceMapping

# Boto is very verbose - shut it up
logging.getLogger('boto').setLevel(logging.INFO)

def ssh_execute_command(guestaddr, sshprivkey, command, timeout=10,
                        user='root', prefix=None):
    """
    Function to execute a command on the guest using SSH and return the output.
    Modified version of function from ozutil to allow us to deal with non-root
    authorized users on ec2
    """
    # ServerAliveInterval protects against NAT firewall timeouts
    # on long-running commands with no output
    #
    # PasswordAuthentication=no prevents us from falling back to
    # keyboard-interactive password prompting
    #
    # -F /dev/null makes sure that we don't use the global or per-user
    # configuration files
    #
    # -t -t ensures we have a pseudo tty for sudo

    cmd = ["ssh", "-i", sshprivkey,
           "-F", "/dev/null",
           "-o", "ServerAliveInterval=30",
           "-o", "StrictHostKeyChecking=no",
           "-o", "ConnectTimeout=" + str(timeout),
           "-o", "UserKnownHostsFile=/dev/null",
           "-t", "-t",
           "-o", "PasswordAuthentication=no"]

    if prefix:
        command = prefix + " " + command

    cmd.extend( ["%s@%s" % (user, guestaddr), command ] )

    return subprocess_check_output(cmd)


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

    def guest_execute_command(self, guestaddr, command, timeout=30,
                              tunnels=None):
        return super(FedoraRemoteGuest, self).guest_execute_command(guestaddr, command, timeout, tunnels)

    def guest_live_upload(self, guestaddr, file_to_upload, destination,
                          timeout=30):
        return super(FedoraRemoteGuest, self).guest_live_upload(guestaddr, file_to_upload, destination, timeout)



class Fedora_ec2_Builder(BaseBuilder):
    """docstring for Fedora_ec2_Builder"""
    zope.interface.implements(IBuilder)

    def __init__(self, template, target, config_block = None):
        super(Fedora_ec2_Builder, self).__init__(template, target, config_block)
        config_obj = ApplicationConfiguration()
        self.app_config = config_obj.configuration
        if "ec2" in config_obj.jeos_images:
            self.ec2_jeos_amis = config_obj.jeos_images['ec2']
        else:
            self.log.warning("No JEOS amis defined for ec2.  Snapshot builds will not be possible.")
            self.ec2_jeos_amis = {}
        
        self.warehouse_url = self.app_config['warehouse']
        # May not be necessary to do both of these
        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml, rootpw_required=True)
        # Add in target specific content
        self.add_target_content()

        # Create a name combining the TDL name and the UUID for use when tagging EC2 AMIs
        self.longname = self.tdlobj.name + "-" + self.new_image_id
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        # 18-Jul-2011 - Moved to constructor and modified to change TDL object name itself
        #   Oz now uses the tdlobject name property directly in several places so we must change it
        self.tdlobj.name = "factory-build-" + self.new_image_id

        # populate a config object to pass to OZ; this allows us to specify our
        # own output dir but inherit other Oz behavior
        self.oz_config = ConfigParser.SafeConfigParser()
        self.oz_config.read("/etc/oz/oz.cfg")
        self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])
        # make this a property to enable quick cleanup on abort
        self.instance = None

    def init_guest(self, guesttype):
        if guesttype == "local":
            self.guest = oz.Fedora.get_class(self.tdlobj, self.oz_config, None)
        else:
            self.guest = FedoraRemoteGuest(self.tdlobj, self.oz_config, None,
                                           "virtio", True, "virtio", True)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())

    def build_image(self, build_id=None):
        try:
            if self.app_config["ec2_build_style"] == "upload":
                self.init_guest("local")
                self.build_upload(build_id)
            elif self.app_config["ec2_build_style"] == "snapshot":
                # No actual need to have a guest object here so don't bother
                self.build_snapshot(build_id)
            else:
                raise ImageFactoryException("Invalid ec2_build_style (%s) passed to build_image()" % (self.app_config["ec2_build_style"]))
        except:
            self.log_exc()
            self.status="FAILED"
            raise

    def build_snapshot(self, build_id):
        # All we need do here is store the relevant bits in the Warehouse
        self.status = "BUILDING"
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
        self.log.debug("Fedora_ec2_Builder: build_upload() called for target %s with warehouse config %s" % (self.target, self.app_config['warehouse']))
        self.status="BUILDING"
        try:
            self.guest.cleanup_old_guest()
            self.threadsafe_generate_install_media(self.guest)
            self.percent_complete=10

            # We want to save this later for use by RHEV-M and Condor clouds
            libvirt_xml=""

            try:
                self.guest.generate_diskimage()
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
            finally:
                self.guest.cleanup_install()

            self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
            # OK great, we now have a customized KVM image
            # Now we do some target specific transformation

            # Add the cloud-info file
            self.modify_oz_filesystem()

            self.log.info("Transforming image for use on EC2")
            self.ec2_copy_filesystem(self.app_config['imgdir'])
            self.ec2_modify_filesystem()

            if (self.app_config['warehouse']):
                self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
                target_parameters="No target parameters for cloud type %s" % (self.target)

                self.store_image(build_id, target_parameters)
                self.log.debug("Image warehouse storage complete")
        except:
            self.log_exc()
            self.status="FAILED"
            raise

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

        # TODO: We lost the original filename here; delete the original image?
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

        # BG - Upload rc.local extra content
        # Again, this uses a static copy - this bit is where the ssh key is downloaded
        # TODO: Is this where we inject puppet?
        # TODO - Possibly modify the key injection from rc_local to be only non-root
        #  and add a special user to sudoers - this is what BG has evolved to do
        self.log.info("Updating rc.local for key injection")
        g.write("/tmp/rc.local", self.rc_local)
        g.sh("cat /tmp/rc.local >> /etc/rc.local")
        # It's possible the above line actually creates rc.local
        # Make sure it is executable
        g.sh("chmod a+x /etc/rc.local")
        g.rm("/tmp/rc.local")

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
            if self.app_config["ec2_build_style"] == "upload":
                self.push_image_upload(target_image_id, provider, credentials)
            elif self.app_config["ec2_build_style"] == "snapshot":
                self.init_guest("remote")
                self.push_image_snapshot_ec2(target_image_id, provider,
                                             credentials)
            else:
                raise ImageFactoryException("Invalid build target (%s) passed to build_image()" % (self.target))
        except:
            self.log_exc()
            self.status="FAILED"

    def install_euca_tools(self, guestaddr):
        # For F13-F15 we now have a working euca2ools in the default repos
        self.guest.guest_execute_command(guestaddr, "yum -y install euca2ools")

    def wait_for_ec2_ssh_access(self, guestaddr):
        # We have added an isolated change here to deal with a switch to using a non-root user
        # as the destination for key injection - this allows the remaining code to be run unaltered
        # by allowing direct root ssh access during customization - this is undone before the snapshot
        if self.tdlobj.distro == "RHEL-6" and int(self.tdlobj.update) >= 4:
            user = 'ec2-user'
            prefix = 'sudo'
        else:
            user = 'root'
            prefix = None

        self.log.debug("User user (%s) and command prefix (%s) for initial ssh access testing" % (user, prefix))

        for i in range(300):
            if i % 10 == 0:
                self.log.debug("Waiting for EC2 ssh access: %d/300" % (i))

            try:

                stdout, stderr, retcode = ssh_execute_command(guestaddr, self.guest.sshprivkey, "/bin/true", 
                                                              timeout = 10, user = user, prefix=prefix) 
                break
            except:
                pass

            sleep(1)

        if i == 299:
            raise ImageFactoryException("Unable to gain ssh access as user (%s) after 300 seconds - aborting" % (user))

        
        if user != "root":
            # We need to copy the authorized key from wherever it currently lives to root

            def execute_regular_noex(command):
                try:
                    ignored = ssh_execute_command(guestaddr, self.guest.sshprivkey, command, 
                                                  timeout = 10, user = user, prefix=prefix)
                except:
                    pass

            self.log.debug("AMI uses non-root key injection to user (%s) - enabling temporary root access" % (user))
            # These may fail if .ssh is already present - ignore those failures and test below
            execute_regular_noex("mkdir /root/.ssh")
            execute_regular_noex("chmod 600 /root/.ssh")
            execute_regular_noex("cp /home/%s/.ssh/authorized_keys /root/.ssh/authorized_keys")
            execute_regular_noex("chmod 600 /root/.ssh/authorized_keys")

            # At this point we should be able to do a regular guest_execute_command as root
            # if we cannot - fail
            try:
                self.guest.guest_execute_command(guestaddr, "/bin/true")
            except:
                raise ImageFactoryException("Transfer of authorized key to root failed - Aborting")
                



    def wait_for_ec2_instance_start(self, instance):
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

    def correct_remote_manifest(self, guestaddr, manifest):
        # not needed in fedora but unfortunately needed elsewhere
        pass

    def ebs_pre_shapshot_tasks(self, guestaddr):
        # not needed in Fedora but needed in current RHEL AMIs to make key injection work
        pass

    def terminate_instance(self, instance):
        # boto 1.9 claims a terminate() method but does not implement it
        # boto 2.0 throws an exception if you attempt to stop() an S3 backed instance
        # introspect here and do the best we can
        if "terminate" in dir(instance):
            instance.terminate()
        else:
            instance.stop()

    def push_image_snapshot_ec2(self, target_image_id, provider, credentials):
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
        factory_security_group_name = "imagefactory-%s" % (self.new_image_id, )
        factory_security_group_desc = "Temporary ImageFactory generated security group with SSH access"
        self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
        factory_security_group = conn.create_security_group(factory_security_group_name, factory_security_group_desc)
        factory_security_group.authorize('tcp', 22, 22, '0.0.0.0/0')

        # Create a use-once SSH key
        key_name = "fac-tmp-key-%s" % (self.new_image_id)
        key = conn.create_key_pair(key_name)
        # Shove into a named temp file
        key_file_object = NamedTemporaryFile()
        key_file_object.write(key.material)
        key_file_object.flush()
        key_file=key_file_object.name

        # Now launch it
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
                self.log.debug("Uploading cert material")
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

                # Unfortunately, for some OS versions we need to correct the manifest
                self.correct_remote_manifest(guestaddr, manifest)

                command = ['euca-upload-bundle', '-b', bucket, '-m', manifest,
                           '--ec2cert', '/tmp/cert-ec2.pem',
                           '-a', self.ec2_access_key, '-s', self.ec2_secret_key,
                           '-U', upload_url]
                command_log = map(replace, command)
                self.log.debug("Executing upload bundle command: %s" % (command_log))
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, ' '.join(command))
                self.log.debug("Upload output: %s" % (stdout))

                manifest_s3_loc = "%s/%s.manifest.xml" % (bucket, uuid)

                command = ['euca-register', '-U', register_url,
                           '-A', self.ec2_access_key, '-S', self.ec2_secret_key,
                           #'-n', image_name, '-d', image_desc,
                           manifest_s3_loc]
                command_log = map(replace, command)
                self.log.debug("Executing register command: %s" % (command_log))
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr,
                                                                           ' '.join(command))
                self.log.debug("Register output: %s" % (stdout))

                m = re.match(".*(ami-[a-fA-F0-9]+)", stdout)
                new_ami_id = m.group(1)
                self.log.debug("Extracted AMI ID: %s " % (new_ami_id))
                ### End S3 snapshot code
            else:
                self.log.debug("Performing image prep tasks for EBS backed images")
                self.ebs_pre_shapshot_tasks(guestaddr)
                self.log.debug("Creating a new EBS backed image from our running EBS instance")
                new_ami_id = conn.create_image(self.instance.id, image_name, image_desc)
                self.log.debug("EUCA creat_image call returned AMI ID: %s" % (new_ami_id))
                self.log.debug("Now waiting for AMI to become available")
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

            icicle_id = self.warehouse.store_icicle(self.output_descriptor)
            metadata = dict(target_image=target_image_id, provider=provider, icicle=icicle_id, target_identifier=new_ami_id, provider_account_identifier=self.ec2_access_key)
            self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)
        finally:
            self.log.debug("Terminating EC2 instance and deleting temp security group")
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

        self.log.debug("Fedora_ec2_Builder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
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
        input_image_name = "ec2-image-" + target_image_id + ".dsk"
        input_image = self.app_config['imgdir'] + "/" + input_image_name

        self.retrieve_image(target_image_id, input_image)

        input_image_compressed_name = input_image_name + ".gz"
        input_image_compressed = input_image + ".gz"

        if not os.path.isfile(input_image_compressed):
            self.log.debug("No compressed version of image file found - compressing now")
            f_in = open(input_image, 'rb')
            f_out = gzip.open(input_image_compressed, 'wb')
            f_out.writelines(f_in)
            f_out.close()
            f_in.close()
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
        instance_type=self.app_config.get('ec2-32bit-util','m1.small')

        self.log.debug("Initializing connection to ec2 region (%s)" % region_conf['host'])
        ec2region = boto.ec2.get_region(region_conf['host'], aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)
        conn = ec2region.connect(aws_access_key_id=self.ec2_access_key, aws_secret_access_key=self.ec2_secret_key)

        # Create a use-once SSH-able security group
        factory_security_group_name = "imagefactory-%s" % (str(self.new_image_id))
        factory_security_group_desc = "Temporary ImageFactory generated security group with SSH access"
        self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
        factory_security_group = conn.create_security_group(factory_security_group_name, factory_security_group_desc)
        factory_security_group.authorize('tcp', 22, 22, '0.0.0.0/0')

        # Create a use-once SSH key
        key_name = "fac-tmp-key-%s" % (self.new_image_id)
        key = conn.create_key_pair(key_name)
        # Shove into a named temp file
        key_file_object = NamedTemporaryFile()
        key_file_object.write(key.material)
        key_file_object.flush()
        key_file=key_file_object.name

        # Now launch it
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

            self.log.debug("Creating 10 GiB volume in (%s)" % (self.instance.placement))
            volume = conn.create_volume(10, self.instance.placement)

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
            command = "gzip -dc /mnt/%s | dd of=/dev/xvdh bs=4k\n" % (input_image_compressed_name)
            self.log.debug("Decompressing image file into EBS device via command: %s" % (command))
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
            self.log.debug("Terminating EC2 instance and deleting temp security group and volume")
            self.terminate_instance(self.instance)
            factory_security_group.delete()
            key_file_object.close()
            conn.delete_key_pair(key_name)

            if volume:
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
                    self.log.debug("WARNING: Unable to delete volume (%s)" % (volume.id))
                else:
                    self.log.debug("Deleting EBS volume (%s)" % (volume.id))
                    volume.delete()

        # TODO: Add back-reference to ICICLE from base image object
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=ami_id, provider_account_identifier=self.ec2_access_key)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)

        self.log.debug("Fedora_ec2_Builder instance %s pushed image with uuid %s to provider_image UUID (%s) and set metadata: %s" % (id(self), target_image_id, self.new_image_id, str(metadata)))
        self.percent_complete=100

    def ec2_push_image_upload(self, target_image_id, provider, credentials):
        def replace(item):
            if item in [self.ec2_access_key, self.ec2_secret_key]:
                return "REDACTED"
            return item

        self.ec2_decode_credentials(credentials)

        # if the image is already here, great, otherwise grab it from the warehouse
        input_image_name="ec2-image-" + target_image_id + ".dsk"
        input_image=self.app_config['imgdir'] + "/" + input_image_name

        self.retrieve_image(target_image_id, input_image)

        bundle_destination=self.app_config['imgdir']

        self.percent_complete=10

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

        self.log.debug("Executing upload command: %s " % (upload_command_log))
        upload_output = subprocess_check_output(upload_command)
        self.log.debug("Upload command output: %s " % (str(upload_output)))
        self.percent_complete=90

        s3_path = bucket + "/" + input_image_name + ".manifest.xml"

        register_env = { 'EC2_URL':register_url }
        register_command = [ "euca-register" , "-A", self.ec2_access_key,
                             "-S", self.ec2_secret_key, s3_path ]
        register_command_log = map(replace, register_command)
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
        metadata = dict(target_image=target_image_id, provider=provider, icicle="none", target_identifier=ami_id, provider_account_identifier=self.ec2_access_key)
        self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)

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
    kernel /boot/vmlinuz-#KERNEL_VERSION# ro root=LABEL=/ rd_NO_PLYMOUTH
    initrd /boot/#KERNEL_IMAGE_NAME#-#KERNEL_VERSION#.img
"""

    fstab_32bit="""LABEL=/    /         ext3    defaults         1 1
/dev/xvda2  /mnt      ext3    defaults         1 2
/dev/xvda3  swap      swap    defaults         0 0
none       /dev/pts  devpts  gid=5,mode=620   0 0
none       /dev/shm  tmpfs   defaults         0 0
none       /proc     proc    defaults         0 0
none       /sys      sysfs   defaults         0 0
"""

    fstab_64bit="""LABEL=/    /         ext3    defaults         1 1
/dev/xvdb   /mnt      ext3    defaults         0 0
/dev/xvdc   /data     ext3    defaults         0 0
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
         'ec2-us-west-2':      { 'boto_loc': 'us-west-2',          'host':'us-west-2',      'i386': 'aki-dce26fec', 'x86_64': 'aki-98e26fa8' },
         'ec2-ap-southeast-1': { 'boto_loc': 'ap-southeast-1',     'host':'ap-southeast-1', 'i386': 'aki-13d5aa41', 'x86_64': 'aki-11d5aa43' },
         'ec2-ap-southeast-2': { 'boto_loc': 'ap-southeast-2',     'host':'ap-southeast-2', 'i386': 'aki-33990e09', 'x86_64': 'aki-31990e0b' },
         'ec2-ap-northeast-1': { 'boto_loc': 'ap-northeast-1',     'host':'ap-northeast-1', 'i386': 'aki-d209a2d3', 'x86_64': 'aki-d409a2d5' },
         'ec2-sa-east-1':      { 'boto_loc': 'sa-east-1',          'host':'sa-east-1',      'i386': 'aki-bc3ce3a1', 'x86_64': 'aki-cc3ce3d1' },
         'ec2-eu-west-1':      { 'boto_loc': Location.EU,          'host':'eu-west-1',      'i386': 'aki-4deec439', 'x86_64': 'aki-4feec43b' } }

        # July 13 - new approach - generic JEOS AMIs for Fedora - no userdata and no euca-tools
        #           ad-hoc ssh keys replace userdata - runtime install of euca tools for bundling
        # v0.6 of F14 and F15 - dropped F13 for now - also include official public RHEL hourly AMIs for RHEL6
        # Sept 1 - 2011 - updated us-west Fedora JEOSes to 0.6
        # Sept 30 - 2011 - Moved out of here entirely to ApplicationConfiguration
        # ec2_jeos_amis = <not here anymore>
