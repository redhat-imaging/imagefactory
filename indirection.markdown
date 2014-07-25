Indirection plugin is the most versatile plugin for ImageFactory.  Indirection
allows the user to automate image customization of any tool.  Such flexibility 
is achieved by breaking up the image building process into three steps.

Step 1: Create utility image

Utility image is the image that contains any special tools needed to customize 
an image.  In the example here, the utility image will contain 
diskimage-builder and instack-undercloud packages.  The following kickstart
file will be passed in to imagefactory:

```
install
text
keyboard us
lang en_US.UTF-8

skipx

network --device eth0 --bootproto dhcp
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
kernel-headers
kernel-devel
%end
```

The above kickstart script does not contain rootpw property.  ImageFactory will
complain unless /etc/imagefactory/imagefactory.conf has root password
enforcement disabled in following manner:

```
{
  ...
  "tdl_require_root_pw": 0,
  ...
}
```
