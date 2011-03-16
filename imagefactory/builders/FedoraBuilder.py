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
import ConfigParser
from tempfile import *
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
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
    # if retcode:
    #     cmd = ' '.join(*popenargs)
    #     raise OzException("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)

class FedoraBuilder(BaseBuilder):
    """docstring for FedoraBuilder"""
    zope.interface.implements(IBuilder)
    
    # Initializer
    def __init__(self, template, target):
        super(FedoraBuilder, self).__init__(template, target)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        # populate a config object to pass to OZ
        # This allows us to specify working directories
        self.config = ConfigParser.ConfigParser()
        self.config.add_section('paths')
        self.config.set('paths', 'output_dir', self.app_config["output_dir"])
        # self.config.set('paths', 'data_dir', self.app_config["output_dir"])
        self.guest = oz.Fedora.get_class(oz.TDL.TDL(xmlstring=template.xml), self.config, None)
        # TODO: Should this be global?
        self.image_id = str(self.image_id)	
        # May not be necessary to do both of these
        self.guest.diskimage = self.app_config["output_dir"] + "/base-image-" + self.image_id + ".dsk"
    
    # Image actions
    def build_image(self):
        self.build()
    
    def build(self):
        self.log.debug("build() called on FedoraBuilder...")
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
                # if customize:
                #     guest.customize(libvirt_xml)
                # if generate_cdl:
                #     print guest.generate_cdl(libvirt_xml)
                # else:
                #     print libvirt_xml
            except:
                self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
                self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
                self.log.debug("         traceback: (%s)" % (sys.exc_info()[2]))
                self.guest.cleanup_old_guest()
                raise
        finally:
            self.guest.cleanup_install()
        # TODO: Catch exceptions here and err out if we don't end up with an image
        
        self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
        # OK great, we now have a customized KVM image
        # Now we do some target specific transformation
        if self.target == "ec2":
            self.log.info("Transforming image for use on EC2")
            self.ec2_transform_image()
        
        if (self.app_config['warehouse']):
            self.log.debug("Storing Fedora image at %s..." % (self.app_config['warehouse'], ))
            # TODO: Revisit target_parameters for different providers
            self.store_image("No Target Paremeters Yet")
            self.log.debug("Image warehouse storage complete")
        self.percent_complete=100
        self.status="COMPLETED"
    
    def ec2_transform_image(self):
        # On entry the image points to our generic KVM image - we transform image
        #  and then update the image property to point to our new image and update
        #  the metadata
        try:
            output_dir=self.app_config['output_dir']
            self.ec2_copy_filesystem(output_dir)
            self.ec2_modify_filesystem()
        except:
            self.log.debug("Exception during ec2_transform_image")
            self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
            self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
            self.log.debug("         traceback: %s" % (repr(traceback.format_tb(sys.exc_info()[2]))))
    
    def ec2_copy_filesystem(self, output_dir):
        target_image=output_dir + "/ec2-image-" + self.image_id + ".dsk"
        
        # TODO: Whole thing should be in a try/excep block
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
        # TODO: Use the temp file module instead of creating one by hand
        tmp_image_file = "/tmp/tmp-img-" + self.image_id
        f = open (tmp_image_file, "w")
        f.truncate (10 * 1024 * 1024)
        f.close
        g.add_drive(tmp_image_file)
        
        self.log.debug("launch guestfs")
        g.launch ()
        
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
        # These are more or less directly ported from BoxGrinder
        # Should include a full ACK and links to BG
        # TODO: This would be safer and more robust if done within the running modified
        # guest - in this would require tighter Oz integration
        
        # TODO: Can we recycle the guestfs object?
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
        
        # Do this if we wish to try to use networking for further action
        # self.log.info("Updating resolve.conf")
        # g.upload("/etc/resolv.conf", "/etc/resolv.conf")
        
        # TODO: If we are dealing with RHEL Remove kernel, install kernel-xen via sh
        # recreate initrd using scheme described below
        # g.sh("yum -y remove kernel")
        # g.sh("yum -y install kernel-xen")
        # recreate INITRD 
        # BG - create_devices
        # TODO: Why?
        # TODO: MAKEDEV is no longer even a standard part of F14 - force it in ks.cfg?
        #   It isn't even on the ISO so we'd really have to fiddle
        #print "Making device files"
        #g.sh("/sbin/MAKEDEV -d /dev -x console")
        #g.sh("/sbin/MAKEDEV -d /dev -x null")
        #g.sh("/sbin/MAKEDEV -d /dev -x zero")
        
        # BG - Make a /data directory for 64 bit hosts
        # Epemeral devs come pre-formatted from AWS - weird
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
        
        #f = NamedTemporaryFile()
        #f.write(tmpl)
        #f.flush()
        #g.upload(f.name, "/etc/fstab")
        #f.close()
        g.write("/etc/fstab", tmpl)
        
        
        # BG - Enable networking
        # Upload a known good ifcfg-eth0 and then chkconfig on networking
        self.log.info("Enabling networking and uploading ifcfg-eth0")
        g.sh("/sbin/chkconfig network on")
        f = NamedTemporaryFile()
        f.write(self.ifcfg_eth0)
        f.flush()
        g.upload(f.name, "/etc/sysconfig/network-scripts/ifcfg-eth0")
        f.close()
        
        # Disable first boot - this slows things down otherwise
        if g.is_file("/etc/init.d/firstboot"):
            g.sh("/sbin/chkconfig firstboot off")
        
        # BG - Upload rc.local extra content
        # Again, this uses a static copy - this bit is where the ssh key is downloaded
        # TODO: Is this where we inject puppet?
        # TODO - Possibly modify the key injection from rc_local to be only non-root
        #  and add a special user to sudoers - this is what BG has evolved to do
        self.log.info("Updating rc.local for key injection")
        f = NamedTemporaryFile()
        f.write(self.rc_local)
        f.flush()
        g.upload(f.name, "/tmp/rc.local")
        g.sh("cat /tmp/rc.local >> /etc/rc.local")
        f.close()
        
        # Install menu list
        # Derive the kernel version from the last element of ls /lib/modules and some
        # other magic - look at linux_helper for details
        
        # Look at /lib/modules and assume that the last kernel listed is the version we use
        # TODO: In 32 bit we can end up with PAE versions which we must select
        
        self.log.info("Modifying and updating menu.lst")
        kernel_versions = g.ls("/lib/modules")
        kernel_version = None
        if (len(kernel_versions) > 1) and (arch == "i386"):
            paere = re.compile("PAE$")
            for kern in kernel_versions:
                if paere.search(kern):
                    kernel_version = kern
        else:
            kernel_version = kernel_versions[len(kernel_versions)-1]
        
        self.log.debug("Using kernel version: %s" % (kernel_version))
        
        # We could deduce this from version but it's easy to inspect
        bootramfs = int(g.sh("ls -1 /boot | grep initramfs | wc -l"))
        ramfs_prefix = "initramfs" if bootramfs > 0 else "initrd"
        
        name="Image Factory EC2 boot - kernel: " + kernel_version
        
        tmpl = self.menu_lst
        tmpl = string.replace(tmpl, "#KERNEL_VERSION#", kernel_version)
        tmpl = string.replace(tmpl, "#KERNEL_IMAGE_NAME#", ramfs_prefix)
        tmpl = string.replace(tmpl, "#TITLE#", name)
        
        f = NamedTemporaryFile()
        f.write(tmpl)
        f.flush()
        g.upload(f.name, "/boot/grub/menu.lst")
        f.close()
        
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
        # TODO: Conditional on provider type
        # TODO: Providers other than EC2
        self.status="PUSHING"
        self.percent_complete=0
        try:
            self.ec2_push_image(image_id, provider, credentials)
        except:
            self.log.debug("Exception during ec2_push_image")
            self.log.debug("Unexpected error: (%s)" % (sys.exc_info()[0]))
            self.log.debug("             value: (%s)" % (sys.exc_info()[1]))
            self.log.debug("         traceback: %s" % (repr(traceback.format_tb(sys.exc_info()[2]))))
        self.status="COMPLETED"
    
    def ec2_push_image(self, image_id, provider, credentials):
        # Decode credentials
        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()
        
        ec2_user_id = ctxt.xpathEval("//provider_credentials/ec2_credentials/account_number")[0].content
        ec2_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/key")[0].content
        ec2_cert = ctxt.xpathEval("//provider_credentials/ec2_credentials/certificate")[0].content
        ec2_access_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/access_key")[0].content
        ec2_secret_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/secret_access_key")[0].content
        
        doc.freeDoc()
        ctxt.xpathFreeContext()		
        
        # Shove certs into  named temporary files
        ec2_cert_file_object = NamedTemporaryFile()
        ec2_cert_file_object.write(ec2_cert)
        ec2_cert_file_object.flush()
        ec2_cert_file=ec2_cert_file_object.name
        
        ec2_key_file_object = NamedTemporaryFile()
        ec2_key_file_object.write(ec2_key)
        ec2_key_file_object.flush()
        ec2_key_file=ec2_key_file_object.name
        
        # if the image is already here, great, otherwise grab it from the warehouse
        input_image_path=self.app_config['output_dir'] + "/"
        input_image_name="ec2-image-" + image_id + ".dsk"
        input_image=input_image_path + input_image_name
        
        # TODO: Conditionally grab from warehouse
        
        bundle_destination=self.app_config['output_dir']
        
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
        
        bucket= "imagefactory-" + region + "-" + ec2_user_id
        
        # Euca does not support specifying region for bucket
        # (Region URL is not sufficient)
        # See: https://bugs.launchpad.net/euca2ools/+bug/704658
        # What we end up having to do is manually create a bucket in the right region
        # then explicitly point to that region URL when doing the image upload
        # We CANNOT let euca create the bucket when uploading or it will end up in us-east-1

        conn = S3Connection(ec2_access_key, ec2_secret_key)
        try:
            conn.create_bucket(bucket, location=boto_loc)
        except S3CreateError as buckerr:
            if buckerr.error_code == "BucketAlreadyOwnedByYou":
                # Expected behavior after first push - not an error
                pass
            else:
                raise
        
        # TODO: Make configurable?  - Bundle with our RPM?
        ec2_service_cert = "/etc/ec2/amitools/cert-ec2.pem"
        
        bundle_command = [ "euca-bundle-image", "-i", input_image, "--kernel", aki, "-d", bundle_destination, "-a", ec2_access_key, "-s", ec2_secret_key ]
        bundle_command.extend( [ "-c", ec2_cert_file ] )
        bundle_command.extend( [ "-k", ec2_key_file ] )
        bundle_command.extend( [ "-u", ec2_user_id ] )
        bundle_command.extend( [ "-r", arch ] )
        bundle_command.extend( [ "--ec2cert", ec2_service_cert ] )
        
        self.log.debug("Executing bundle command: %s " % (bundle_command))
        
        bundle_output = subprocess_check_output(bundle_command)
        
        self.log.debug("Bundle command complete")
        self.log.debug("Bundle command output: %s " % (str(bundle_output)))
        self.percent_complete=40
        
        manifest = bundle_destination + "/" + input_image_name + ".manifest.xml"
        
        upload_command = [ "euca-upload-bundle", "-b", bucket, "-m", manifest, "--ec2cert", ec2_service_cert, "-a", ec2_access_key, "-s", ec2_secret_key, "-U" , upload_url ]
        self.log.debug("Executing upload command: %s " % (upload_command))
        upload_output = subprocess_check_output(upload_command)
        self.log.debug("Upload command output: %s " % (str(upload_output)))
        self.percent_complete=90
        
        s3_path = bucket + "/" + input_image_name + ".manifest.xml"

        register_env = { 'EC2_URL':register_url }
        register_command = [ "euca-register" , "-A", ec2_access_key, "-S", ec2_secret_key, s3_path ]
        self.log.debug("Executing register command: %s with environment %s " % (register_command, repr(register_env)))
        register_output = subprocess_check_output(register_command, env=register_env)
        self.log.debug("Register command output: %s " % (str(register_output)))
        m = re.match(".*(ami-[a-fA-F0-9]+)", register_output[0])
        ami_id = m.group(1)
        self.log.debug("Extracted AMI ID: %s " % (ami_id))
        
        # TODO: This should be in a finally statement that rethrows exceptions
        ec2_cert_file_object.close()
        ec2_key_file_object.close()
        
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
