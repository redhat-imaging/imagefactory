Indirection plugin is the most versatile plugin for ImageFactory. Indirection
allows the user to automate image customization of any tool. Such flexibility 
is achieved by breaking up the image building process into three steps.

###Step 1: Create utility image

Utility image is the image that contains any special tools needed to customize 
an image. In the example here, the utility image will contain 
diskimage-builder, instack-undercloud, and git packages. The following
kickstart file will be passed in to imagefactory as utility_image.ks:

```
url --url=http://ftp.linux.ncsu.edu/pub/fedora/linux/releases/20/Fedora/x86_64/os/
# Without the Everything repo, we cannot install cloud-init
repo --name="fedora-everything" --baseurl=http://ftp.linux.ncsu.edu/pub/fedora/linux/releases/20/Everything/x86_64/os/
repo --name="testing" --baseurl=http://mirror.pnl.gov/fedora/linux/updates/20/x86_64/
# At moment this is where the working version of diskimage-builder lives
repo --name=updates-testing --baseurl=http://mirror.pnl.gov/fedora/linux/updates/testing/20/x86_64/
# instack-undercloud lives here for now
repo --name=openstack --baseurl=http://repos.fedorapeople.org/repos/openstack/openstack-icehouse/fedora-20/

install
text
keyboard us
lang en_US.UTF-8

skipx

network --device eth0 --bootproto dhcp
rootpw ROOTPW
firewall --disabled
authconfig --enableshadow --enablemd5
selinux --enforcing
timezone --utc America/New_York
bootloader --location=mbr --append="console=tty0 console=ttyS0,115200"
zerombr
clearpart --all --drives=vda

part biosboot --fstype=biosboot --size=1
part /boot --fstype ext4 --size=200 --ondisk=vda
part pv.2 --size=1 --grow --ondisk=vda
volgroup VolGroup00 --pesize=32768 pv.2
logvol swap --fstype swap --name=LogVol01 --vgname=VolGroup00 --size=768 --grow --maxsize=1536
logvol / --fstype ext4 --name=LogVol00 --vgname=VolGroup00 --size=1024 --grow
reboot

%packages
@core
diskimage-builder
instack-undercloud
git
%end
```

The above TDL does not contain administrative password property. ImageFactory will
complain unless /etc/imagefactory/imagefactory.conf has root password
enforcement disabled in following manner:

```
{
  ...
  "tdl_require_root_pw": 0,
  ...
}
```

In addition to the kickstart file, ImageFactory requires a TDL template
to build an image. Let's call this file utility_image.tdl:
```
<template>
  <name>f20-jeos</name>
  <os>
    <name>Fedora</name>
    <version>20</version>
    <arch>x86_64</arch>
    <install type='url'>
      <url>http://ftp.linux.ncsu.edu/pub/fedora/linux/releases/20/Fedora/x86_64/os/</url>
    </install>
  </os>
  <disk>
    <size>20</size>
  </disk>
  <description>Fedora 20 JEOS Image</description>
</template>
```

The following command should be run from the directory where utility_image.tdl
and utility_image.ks live:

```
imagefactory --debug base_image --file-parameter install_script utility_image.ks utility_image.tdl
```
Please take note of the image ID when ImageFactory finishes building the
utility image 
###Step 2: Create input image

After a utility image is built, another base image needs to be created to be
used as input image. Since both utility image and input image are base_image,
it is possible to use one image for both. Because diskimage-builder can only
modify images without logical volumes, the following kickstart file
(input_image.ks) will create a Fedora 20 image that fits this criteria:

```
url --url=http://ftp.linux.ncsu.edu/pub/fedora/linux/releases/20/Fedora/x86_64/os/
# Without the Everything repo, we cannot install cloud-init
repo --name="fedora-everything" --baseurl=http://ftp.linux.ncsu.edu/pub/fedora/linux/releases/20/Everything/x86_64/os/
install
text
keyboard us
lang en_US.UTF-8
skipx
network --device eth0 --bootproto dhcp
rootpw ROOTPW
firewall --disabled
authconfig --enableshadow --enablemd5
selinux --enforcing
timezone --utc America/New_York
bootloader --location=mbr --append="console=tty0 console=ttyS0,115200"
zerombr
clearpart --all --drives=vda
part / --fstype="ext4" --size=3000
reboot

%packages
@core
cloud-init
tar

%end
```

The following TDL template (input_image.tdl) is needed to build the input image:

```
<template>
  <name>f20-jeos</name>
  <os>
    <name>Fedora</name>
    <version>20</version>
    <arch>x86_64</arch>
    <install type='url'>
      <url>http://ftp.linux.ncsu.edu/pub/fedora/linux/releases/20/Fedora/x86_64/os/</url>
    </install>
  </os>
  <description>Fedora 20 JEOS Image</description>
</template>

```

The following command should be run from the directory where input_image.tdl
and input_image.ks live:

```
imagefactory --debug base_image --file-parameter install_script input_image.ks
input_image.tdl
```
Please take note of the image id when ImageFactory finishes building input
image.
###Step 3: Create target image 

The indirection plugin takes the following parameters. Some of the parameters
have default values and as a result will not be present in the command used to
build the target image. However, they are discussed here so one can modify this
example in all possible ways.

**--id** - The image id for the input image

**--parameter utility_image** - The image id for utility image

**--parameter input_image_device** - The name of the device where the base_image
is presented to the utility VM. Default is /dev/vdb1.

**--parameter input_image_file** - The path to the copy of input image on work
space. Default is /input_image.raw. Only input_image_device or
input_image_file can be provided.

**--file-parameter utility_customizations** - Partial TDL with commands to be
exectuted after the utility image is launched in run level 3

**--parameter results_location** - Full path to the customized image in the
filesystem presented as work space. Default is /results/images/boot.iso

The utility image is used to launch a VM in run level 3. This VM has an
unmounted filesystem attached as '/dev/vdb1' or input_image_device with the
following characteristics:

1. The input image is available as '/input_image.raw' or input_image_file

2. Once the customization TDL has finished running the plugin expects to find
the resulting image at '/results/images/boot.iso' or results_location. 

The TDL below does the following:

1. Mounts the workspace filesystem to /mnt 
2. Makes a copy of sudoers files
3. Modifies the sudoers file to disable requirement for tty when using sudo
4. Converts the input image from RAW to QCOW2 so diskimage-builder can consume
it
5. Runs all the commands needed to build the ovecloud-compute [1].
disk-image-create command takes -o argument which specifies the name of output
image. Since the work space was mounted as /mnt the full path should be
'/mnt/overloud-compute' in order for the indirection plugin to find it at
/overcloud-compute.qcow2

[1] https://github.com/agroup/instack-undercloud/blob/instack-undercloud-0.0.13-1/scripts/instack-build-images#L65


```
<template>
<commands>
   <command name='mount'>mount /dev/vdb1 /mnt</command>
   <command name='backup'>cp /etc/sudoers /etc/sudoers_backup</command>
   <command name='pty'>sed 's/.*requiretty//g' /etc/sudoers_backup > /etc/sudoers</command>
   <command name='convert'>qemu-img convert -f raw -O qcow2 /mnt/input_image.raw /mnt/input_image.qcow2</command>
   <command name="localimage">export DIB_LOCAL_IMAGE=/mnt/input_image.qcow2
set -eux
export TMP_DIR=${TMP_DIR:-/var/tmp}
export NODE_ARCH=${NODE_ARCH:-amd64}
export NODE_DIST=${NODE_DIST:-"fedora selinux-permissive"}
export DEPLOY_IMAGE_ELEMENT=${DEPLOY_IMAGE_ELEMENT:-deploy}
export DIB_INSTALLTYPE_nova=package
export DIB_INSTALLTYPE_heat=package
export DIB_INSTALLTYPE_keystone=package
export DIB_INSTALLTYPE_neutron=package
export DIB_INSTALLTYPE_glance=package
export DIB_INSTALLTYPE_swift=package
export DIB_INSTALLTYPE_cinder=package
export DIB_INSTALLTYPE_horizon=package
export DIB_INSTALLTYPE_python_cinderclient=package
export DIB_INSTALLTYPE_python_glanceclient=package
export DIB_INSTALLTYPE_python_heatclient=package
export DIB_INSTALLTYPE_python_keystoneclient=package
export DIB_INSTALLTYPE_python_neutronclient=package
export DIB_INSTALLTYPE_python_novaclient=package
export DIB_INSTALLTYPE_python_swiftclient=package
export DIB_INSTALLTYPE_python_ceilometerclient=package
export DIB_INSTALLTYPE_python_ironicclient=package
export DIB_INSTALLTYPE_os_collect_config=package
export DIB_INSTALLTYPE_os_refresh_config=package
export DIB_INSTALLTYPE_os_apply_config=package
export DIB_INSTALLTYPE_get_pip_py=package
export ELEMENTS_PATH=/usr/share/tripleo-image-elements:/usr/share/instack-undercloud
disk-image-create \
        --no-tmpfs \
        -a $NODE_ARCH \
        -o /mnt/overcloud-compute \
        $NODE_DIST pip-cache nova-compute nova-kvm neutron-openvswitch-agent os-collect-config \
        baremetal \
        dhcp-all-interfaces stackuser fedora-rdo-icehouse-repository \
        stable-interface-names</command>
</commands>
</template>
```

The command that will execute the target image build looks like the following:

```
imagefactory --debug target_image --id [input_image_id] --parameter utility_image [utility_image_id] --file-parameter utility_customizations dib_overcloud_compute.tdl --parameter results_location "/deploy-ramdisk.qcow2" indirection
```


