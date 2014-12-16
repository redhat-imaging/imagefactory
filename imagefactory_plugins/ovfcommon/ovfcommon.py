# encoding: utf-8

#   Copyright 2013 Red Hat, Inc.
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

from xml.etree import ElementTree
from oz.ozutil import copyfile_sparse
import oz.TDL
import os
import tarfile
from shutil import rmtree
import uuid
import time
import glob
import tempfile
from stat import *
from imgfac.PersistentImageManager import PersistentImageManager
from imgfac.FactoryUtils import check_qcow_size
from imgfac.ImageFactoryException import ImageFactoryException
# Yes - again with two different XML libraries
# lxml.etree is required by Oz and is what I used to rebuild the
# Virtualbox XML format.
# TODO: Unify these
import lxml.etree
import datetime


class RHEVOVFDescriptor(object):
    def __init__(self, img_uuid, vol_uuid, tpl_uuid, disk,
                 ovf_name,
                 ovf_cpu_count,
                 ovf_memory_mb,
                 rhevm_description,
                 rhevm_default_display_type,
                 rhevm_os_descriptor,
                 pool_id="00000000-0000-0000-0000-000000000000"):
        self.img_uuid = img_uuid
        self.vol_uuid = vol_uuid
        self.tpl_uuid = tpl_uuid
        self.disk = disk

        if ovf_name is None:
            self.ovf_name = str(self.tpl_uuid)
        else:
            self.ovf_name = ovf_name

        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb
        self.rhevm_description = rhevm_description
        self.rhevm_default_display_type = rhevm_default_display_type
        self.rhevm_os_descriptor = rhevm_os_descriptor
        self.pool_id = pool_id

    def generate_ovf_xml(self):
        etroot = ElementTree.Element('ovf:Envelope')
        etroot.set('xmlns:ovf', "http://schemas.dmtf.org/ovf/envelope/1/")
        etroot.set('xmlns:rasd', "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData")
        etroot.set('xmlns:vssd', "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData")
        etroot.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        etroot.set('ovf:version', "0.9")

        etref = ElementTree.Element('References')

        etfile = ElementTree.Element('File')
        etfile.set('ovf:href', str(self.img_uuid)+'/'+str(self.vol_uuid))
        etfile.set('ovf:id', str(self.vol_uuid))
        etfile.set('ovf:size', str(self.disk.vol_size))
        # TODO: Bulk this up a bit
        etfile.set('ovf:description', self.ovf_name)
        etref.append(etfile)

        etroot.append(etref)

        etsec = ElementTree.Element('Section')
        etsec.set('xsi:type', "ovf:NetworkSection_Type")
        ete = ElementTree.Element('Info')
        ete.text = "List of Networks"
        etsec.append(ete)
        # dummy section, even though we have Ethernet defined below
        etroot.append(etsec)

        etsec = ElementTree.Element('Section')
        etsec.set('xsi:type', "ovf:DiskSection_Type")

        etdisk = ElementTree.Element('Disk')
        etdisk.set('ovf:diskId', str(self.vol_uuid))
        vol_size_str = str((self.disk.vol_size + (1024*1024*1024) - 1) / (1024*1024*1024))
        etdisk.set('ovf:size', vol_size_str)
        etdisk.set('ovf:vm_snapshot_id', str(uuid.uuid4()))
        etdisk.set('ovf:actual_size', vol_size_str)
        etdisk.set('ovf:format', 'http://www.vmware.com/specifications/vmdk.html#sparse')
        etdisk.set('ovf:parentRef', '')
        # XXX ovf:vm_snapshot_id
        etdisk.set('ovf:fileRef', str(self.img_uuid)+'/'+str(self.vol_uuid))
        # XXX ovf:format ("usually url to the specification")
        if self.disk.qcow_size:
            etdisk.set('ovf:volume-type', "Sparse")
            etdisk.set('ovf:volume-format', "COW")
        else:
            etdisk.set('ovf:volume-type', "Preallocated")
            etdisk.set('ovf:volume-format', "RAW")
        etdisk.set('ovf:disk-interface', "VirtIO")
        etdisk.set('ovf:disk-type', "System")
        etdisk.set('ovf:boot', "true")
        etdisk.set('ovf:wipe-after-delete', "false")
        etsec.append(etdisk)

        etroot.append(etsec)

        etcon = ElementTree.Element('Content')
        etcon.set('xsi:type', "ovf:VirtualSystem_Type")
        etcon.set('ovf:id', "out")

        ete = ElementTree.Element('Name')
        ete.text = self.ovf_name
        etcon.append(ete)

        ete = ElementTree.Element('TemplateId')
        ete.text = str(self.tpl_uuid)
        etcon.append(ete)

        # spec also has 'TemplateName'

        ete = ElementTree.Element('Description')
        ete.text = self.rhevm_description
        etcon.append(ete)

        ete = ElementTree.Element('Domain')
        # AD domain, not in use right now
        # ete.text =
        etcon.append(ete)

        ete = ElementTree.Element('CreationDate')
        ete.text = time.strftime("%Y/%m/%d %H:%M:%S", self.disk.create_time)
        etcon.append(ete)

        ete = ElementTree.Element('TimeZone')
        # ete.text =
        etcon.append(ete)

        ete = ElementTree.Element('IsAutoSuspend')
        ete.text = "false"
        etcon.append(ete)

        ete = ElementTree.Element('VmType')
        ete.text = "1"
        etcon.append(ete)

        ete = ElementTree.Element('default_display_type')
        # vnc = 0, gxl = 1
        ete.text = self.rhevm_default_display_type
        etcon.append(ete)

        ete = ElementTree.Element('default_boot_sequence')
        # C=0,   DC=1,  N=2, CDN=3, CND=4, DCN=5, DNC=6, NCD=7,
        # NDC=8, CD=9, D=10, CN=11, DN=12, NC=13, ND=14
        # (C - HardDisk, D - CDROM, N - Network)
        ete.text = "1"
        etcon.append(ete)

        etsec = ElementTree.Element('Section')
        etsec.set('xsi:type', "ovf:OperatingSystemSection_Type")
        etsec.set('ovf:id', str(self.tpl_uuid))
        etsec.set('ovf:required', "false")

        ete = ElementTree.Element('Info')
        ete.text = "Guest OS"
        etsec.append(ete)

        ete = ElementTree.Element('Description')
        # This is rigid, must be "Other", "OtherLinux", "RHEL6", or such
        ete.text = self.rhevm_os_descriptor
        etsec.append(ete)

        etcon.append(etsec)

        etsec = ElementTree.Element('Section')
        etsec.set('xsi:type', "ovf:VirtualHardwareSection_Type")

        ete = ElementTree.Element('Info')
        ete.text = "%s CPU, %s Memory" % (self.ovf_cpu_count, self.ovf_memory_mb)
        etsec.append(ete)

        etsys = ElementTree.Element('System')
        # This is probably wrong, needs actual type.
        ete = ElementTree.Element('vssd:VirtualSystemType')
        ete.text = "RHEVM 4.6.0.163"
        etsys.append(ete)
        etsec.append(etsys)

        etitem = ElementTree.Element('Item')

        ete = ElementTree.Element('rasd:Caption')
        ete.text = "%s virtual CPU" % self.ovf_cpu_count
        etitem.append(ete)

        ete = ElementTree.Element('rasd:Description')
        ete.text = "Number of virtual CPU"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:InstanceId')
        ete.text = "1"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ResourceType')
        ete.text = "3"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:num_of_sockets')
        ete.text = "1"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:cpu_per_socket')
        ete.text = self.ovf_cpu_count
        etitem.append(ete)

        etsec.append(etitem)

        etitem = ElementTree.Element('Item')

        ete = ElementTree.Element('rasd:Caption')
        ete.text = "%s MB of memory" % self.ovf_memory_mb
        etitem.append(ete)

        ete = ElementTree.Element('rasd:Description')
        ete.text = "Memory Size"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:InstanceId')
        ete.text = "2"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ResourceType')
        ete.text = "4"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:AllocationUnits')
        ete.text = "MegaBytes"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:VirtualQuantity')
        ete.text = self.ovf_memory_mb
        etitem.append(ete)

        etsec.append(etitem)

        etitem = ElementTree.Element('Item')

        ete = ElementTree.Element('rasd:Caption')
        ete.text = "Drive 1"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:InstanceId')
        ete.text = str(self.vol_uuid)
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ResourceType')
        ete.text = "17"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:HostResource')
        ete.text = str(self.img_uuid)+'/'+str(self.vol_uuid)
        etitem.append(ete)

        ete = ElementTree.Element('rasd:Parent')
        ete.text = "00000000-0000-0000-0000-000000000000"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:Template')
        ete.text = "00000000-0000-0000-0000-000000000000"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ApplicationList')
        # List of installed applications, separated by comma
        etitem.append(ete)

        # This corresponds to ID of volgroup in host where snapshot was taken.
        # Obviously we have nothing like it.
        ete = ElementTree.Element('rasd:StorageId')
        # "Storage Domain Id"
        ete.text = "00000000-0000-0000-0000-000000000000"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:StoragePoolId')
        ete.text = self.pool_id
        etitem.append(ete)

        ete = ElementTree.Element('rasd:CreationDate')
        ete.text = time.strftime("%Y/%m/%d %H:%M:%S", self.disk.create_time)
        etitem.append(ete)

        ete = ElementTree.Element('rasd:LastModified')
        ete.text = time.strftime("%Y/%m/%d %H:%M:%S", self.disk.create_time)
        etitem.append(ete)

        etsec.append(etitem)

        etitem = ElementTree.Element('Item')

        ete = ElementTree.Element('rasd:Caption')
        ete.text = "Ethernet 0 rhevm"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:InstanceId')
        ete.text = "3"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ResourceType')
        ete.text = "10"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ResourceSubType')
        # e1000 = 2, pv = 3
        ete.text = "3"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:Connection')
        ete.text = "rhevm"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:Name')
        ete.text = "eth0"
        etitem.append(ete)

        # also allowed is "MACAddress"

        ete = ElementTree.Element('rasd:speed')
        ete.text = "1000"
        etitem.append(ete)

        etsec.append(etitem)

        etitem = ElementTree.Element('Item')

        ete = ElementTree.Element('rasd:Caption')
        ete.text = "Graphics"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:InstanceId')
        # doc says "6", reality is "5"
        ete.text = "5"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:ResourceType')
        ete.text = "20"
        etitem.append(ete)

        ete = ElementTree.Element('rasd:VirtualQuantity')
        ete.text = "1"
        etitem.append(ete)

        etsec.append(etitem)

        etcon.append(etsec)

        etroot.append(etcon)

        et = ElementTree.ElementTree(etroot)
        return et


class VsphereOVFDescriptor(object):
    def __init__(self, disk,
                 ovf_cpu_count,
                 ovf_memory_mb,
                 vsphere_product_name,
                 vsphere_product_vendor_name,
                 vsphere_product_version,
                 vsphere_virtual_system_type):
        self.disk = disk
        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb
        self.vsphere_product_name = vsphere_product_name
        self.vsphere_product_vendor_name = vsphere_product_vendor_name
        self.vsphere_product_version = vsphere_product_version
        self.vsphere_virtual_system_type = vsphere_virtual_system_type

    def generate_ovf_xml(self):
        etroot = ElementTree.Element('Envelope')
        etroot.set("vmw:buildId", "build-880146")
        etroot.set("xmlns", "http://schemas.dmtf.org/ovf/envelope/1")
        etroot.set("xmlns:cim", "http://schemas.dmtf.org/wbem/wscim/1/common")
        etroot.set("xmlns:ovf", "http://schemas.dmtf.org/ovf/envelope/1")
        etroot.set("xmlns:rasd", "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData")
        etroot.set("xmlns:vmw", "http://www.vmware.com/schema/ovf")
        etroot.set("xmlns:vssd", "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData")
        etroot.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

        etref = ElementTree.Element('References')

        etfile = ElementTree.Element('File')
        etfile.set('ovf:href', 'disk.img')
        etfile.set('ovf:id', 'file1')
        etfile.set('ovf:size', str(self.disk.vol_size))

        etref.append(etfile)

        etroot.append(etref)

        etdisksec = ElementTree.Element('DiskSection')

        etinfo = ElementTree.Element('Info')
        etinfo.text = 'Virtual disk information'
        etdisksec.append(etinfo)

        etdisk = ElementTree.Element('Disk')
        etdisk.set("ovf:capacity", str(self.disk.vol_size))
        etdisk.set("ovf:capacityAllocationUnits", "byte")
        etdisk.set("ovf:diskId", "vmdisk1")
        etdisk.set("ovf:fileRef", "file1")
        etdisk.set("ovf:format", "http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized")
        etdisk.set("ovf:populatedSize", str(self.disk.sparse_size))
        etdisksec.append(etdisk)
        etroot.append(etdisksec)

        etnetsec = ElementTree.Element('NetworkSection')

        etinfo = ElementTree.Element('Info')
        etinfo.text = 'The list of logical networks'
        etnetsec.append(etinfo)

        etnet = ElementTree.Element('Network')
        etnet.set('ovf:name', 'VM Network')
        etdesc = ElementTree.Element('Description')
        etdesc.text = 'The VM Network network'
        etnet.append(etdesc)
        etnetsec.append(etnet)

        etroot.append(etnetsec)

        etvirtsys = ElementTree.Element('VirtualSystem')
        etvirtsys.set('ovf:id', self.disk.id)

        etinfo = ElementTree.Element('Info')
        etinfo.text = 'A virtual machine'
        etvirtsys.append(etinfo)

        etname = ElementTree.Element('Name')
        etname.text = self.disk.id
        etvirtsys.append(etname)

        # TODO this should be dynamic
        etossec = ElementTree.Element('OperatingSystemSection')
        etossec.set('ovf:id', '80')
        etossec.set('ovf:version', '6')
        etossec.set('vmw:osType', 'rhel6_64Guest')

        etinfo = ElementTree.Element('Info')
        etinfo.text = 'The kind of installed guest operating system'
        etossec.append(etinfo)

        etvirtsys.append(etossec)

        etvirthwsec = ElementTree.Element('VirtualHardwareSection')

        etinfo = ElementTree.Element('Info')
        etinfo.text = 'Virtual hardware requirements'
        etvirthwsec.append(etinfo)

        etsystem = ElementTree.Element('System')

        etelemname = ElementTree.Element('vssd:ElementName')
        etelemname.text = 'Virtual Hardware Family'
        etsystem.append(etelemname)

        etinstid = ElementTree.Element('vssd:InstanceID')
        etinstid.text = '0'
        etsystem.append(etinstid)

        etvirtsysid = ElementTree.Element('vssd:VirtualSystemIdentifier')
        etvirtsysid.text = self.disk.id
        etsystem.append(etvirtsysid)

        etvirtsystype = ElementTree.Element('vssd:VirtualSystemType')
        etvirtsystype.text = self.vsphere_virtual_system_type 
        etsystem.append(etvirtsystype)

        etvirthwsec.append(etsystem)

        etitem = ElementTree.Element('Item')
        etalloc = ElementTree.Element('rasd:AllocationUnits')
        etalloc.text = 'hertz * 10^6'
        etitem.append(etalloc)
        etdesc = ElementTree.Element('rasd:Description')
        etdesc.text = 'Number of Virtual CPUs'
        etitem.append(etdesc)
        etelemname = ElementTree.Element('rasd:ElementName')
        etelemname.text = "%s virtual CPU(s)" % self.ovf_cpu_count
        etitem.append(etelemname)
        etinstid = ElementTree.Element('rasd:InstanceID')
        etinstid.text = '1'
        etitem.append(etinstid)
        etrestype = ElementTree.Element('rasd:ResourceType')
        etrestype.text = '3'
        etitem.append(etrestype)
        etvirtqty = ElementTree.Element('rasd:VirtualQuantity')
        etvirtqty.text = self.ovf_cpu_count
        etitem.append(etvirtqty)
        etvirthwsec.append(etitem)

        etitem = ElementTree.Element('Item')
        etalloc = ElementTree.Element('rasd:AllocationUnits')
        etalloc.text = 'byte * 2^20'
        etitem.append(etalloc)
        etdesc = ElementTree.Element('rasd:Description')
        etdesc.text = 'Memory Size'
        etitem.append(etdesc)
        etelemname = ElementTree.Element('rasd:ElementName')
        etelemname.text = "%s MB of memory" % self.ovf_memory_mb
        etitem.append(etelemname)
        etinstid = ElementTree.Element('rasd:InstanceID')
        etinstid.text = '2'
        etitem.append(etinstid)
        etrestype = ElementTree.Element('rasd:ResourceType')
        etrestype.text = '4'
        etitem.append(etrestype)
        etvirtqty = ElementTree.Element('rasd:VirtualQuantity')
        etvirtqty.text = self.ovf_memory_mb
        etitem.append(etvirtqty)
        etvirthwsec.append(etitem)

        etitem = ElementTree.Element('Item')
        etaddr = ElementTree.Element('rasd:Address')
        etaddr.text = '0'
        etitem.append(etaddr)
        etdesc = ElementTree.Element('rasd:Description')
        etdesc.text = 'SCSI Controller'
        etitem.append(etdesc)
        etelemname = ElementTree.Element('rasd:ElementName')
        etelemname.text = 'SCSI Controller 0'
        etitem.append(etelemname)
        etinstid = ElementTree.Element('rasd:InstanceID')
        etinstid.text = '3'
        etitem.append(etinstid)
        etressubtype = ElementTree.Element('rasd:ResourceSubType')
        etressubtype.text = 'lsilogic'
        etitem.append(etressubtype)
        etrestype = ElementTree.Element('rasd:ResourceType')
        etrestype.text = '6'
        etitem.append(etrestype)
        etvirthwsec.append(etitem)

        etitem = ElementTree.Element('Item')
        etaddronparent = ElementTree.Element('rasd:AddressOnParent')
        etaddronparent.text = '0'
        etitem.append(etaddronparent)
        etelemname = ElementTree.Element('rasd:ElementName')
        etelemname.text = 'Hard disk 0'
        etitem.append(etelemname)
        ethostres = ElementTree.Element('rasd:HostResource')
        ethostres.text = 'ovf:/disk/vmdisk1'
        etitem.append(ethostres)
        etinstid = ElementTree.Element('rasd:InstanceID')
        etinstid.text = '4'
        etitem.append(etinstid)
        etparent = ElementTree.Element('rasd:Parent')
        etparent.text = '3'
        etitem.append(etparent)
        etrestype = ElementTree.Element('rasd:ResourceType')
        etrestype.text = '17'
        etitem.append(etrestype)
        etconfig = ElementTree.Element('vmw:Config')
        etconfig.set('ovf:required', 'false')
        etconfig.set('vmw:key', 'backing.writeThrough')
        etconfig.set('vmw:value', 'false')
        etitem.append(etconfig)
        etvirthwsec.append(etitem)

        etitem = ElementTree.Element('Item')
        etaddronparent = ElementTree.Element('rasd:AddressOnParent')
        etaddronparent.text = '7'
        etitem.append(etaddronparent)
        etautoalloc = ElementTree.Element('rasd:AutomaticAllocation')
        etautoalloc.text = 'true'
        etitem.append(etautoalloc)
        etconn = ElementTree.Element('rasd:Connection')
        etconn.text = 'VM Network'
        etitem.append(etconn)
        etdesc = ElementTree.Element('rasd:Description')
        etdesc.text = 'E1000 ethernet adapter on "VM Network"'
        etitem.append(etdesc)
        etelemname = ElementTree.Element('rasd:ElementName')
        etelemname.text = 'Network adapter 1'
        etitem.append(etelemname)
        etinstid = ElementTree.Element('rasd:InstanceID')
        etinstid.text = '5'
        etitem.append(etinstid)
        etressubtype = ElementTree.Element('rasd:ResourceSubType')
        etressubtype.text = 'E1000'
        etitem.append(etressubtype)
        etrestype = ElementTree.Element('rasd:ResourceType')
        etrestype.text = '10'
        etitem.append(etrestype)
        etconfig = ElementTree.Element('vmw:Config')
        etconfig.set('ovf:required', 'false')
        etconfig.set('vmw:key', 'connectable.allowGuestControl')
        etconfig.set('vmw:value', 'true')
        etitem.append(etconfig)
        etconfig = ElementTree.Element('vmw:Config')
        etconfig.set('ovf:required', 'false')
        etconfig.set('vmw:key', 'wakeOnLanEnabled')
        etconfig.set('vmw:value', 'false')
        etitem.append(etconfig)
        etvirthwsec.append(etitem)


        etvirtsys.append(etvirthwsec)

        etprodsec = ElementTree.Element('ProductSection')

        etinfo = ElementTree.Element('Info')
        etinfo.text = 'Information about the installed software'
        etprodsec.append(etinfo)

        etprod = ElementTree.Element('Product')
        etprod.text = self.vsphere_product_name
        etprodsec.append(etprod)

        etvendor = ElementTree.Element('Vendor')
        etvendor.text = self.vsphere_product_vendor_name
        etprodsec.append(etvendor)

        etversion = ElementTree.Element('Version')
        etversion.text = self.vsphere_product_version
        etprodsec.append(etversion)

        etvirtsys.append(etprodsec)

        etroot.append(etvirtsys)

        et = ElementTree.ElementTree(etroot)
        return et

class OVFPackage(object):
    '''A directory containing an OVF descriptor and related files such as disk images'''
    def __init__(self, disk, path=None):
        if path:
            self.path = path
        else:
            storage_path = PersistentImageManager.default_manager().storage_path
            self.path = tempfile.mkdtemp(dir=storage_path)
            # this needs to be readable by others, e.g. the nfs user
            # when used in the RHEVHelper
            os.chmod(self.path, S_IRUSR|S_IWUSR|S_IXUSR|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH)

        self.disk = disk

    def delete(self):
        rmtree(self.path, ignore_errors=True)

    def sync(self):
        '''Copy disk image to path, regenerate OVF descriptor'''
        self.copy_disk()
        self.ovf_descriptor = self.new_ovf_descriptor()

        ovf_xml = self.ovf_descriptor.generate_ovf_xml()

        try:
            os.makedirs(os.path.dirname(self.ovf_path))
        except OSError, e:
            if "File exists" not in e:
                raise

        ovf_xml.write(self.ovf_path)

    def make_ova_package(self, gzip=False):
        self.sync()

        mode = 'w' if not gzip else 'w|gz'
        ovapath = os.path.join(self.path, "ova")
        tar = tarfile.open(ovapath, mode)
        cwd = os.getcwd()
        os.chdir(self.path)
        files = glob.glob('*')
        files.remove(os.path.basename(ovapath))

        # per specification, the OVF descriptor must be first in
        # the archive, and the manifest if present must be second
        # in the archive
        for f in files:
            if f.endswith(".ovf"):
                tar.add(f)
                files.remove(f)
                break
        for f in files:
            if f.endswith(".MF"):
                tar.add(f)
                files.remove(f)
                break

        # everything else last
        for f in files:
            tar.add(f)

        os.chdir(cwd)
        tar.close()

        return ovapath


class RHEVOVFPackage(OVFPackage):
    def __init__(self, disk, path=None, base_image=None,
                 ovf_name=None,
                 ovf_cpu_count="1",
                 ovf_memory_mb="512",
                 rhevm_description="Created by Image Factory",
                 rhevm_default_display_type="0",
                 rhevm_os_descriptor="OtherLinux"):

        disk = RHEVDisk(disk)
        super(RHEVOVFPackage, self).__init__(disk, path)
        # We need these three unique identifiers when generating XML and the meta file
        self.img_uuid = str(uuid.uuid4())
        self.vol_uuid = str(uuid.uuid4())
        self.tpl_uuid = str(uuid.uuid4())
        self.image_dir = os.path.join(self.path, "images",
                                      self.img_uuid)
        self.disk_path = os.path.join(self.image_dir,
                                      self.vol_uuid)
        self.meta_path = self.disk_path + ".meta"
        self.ovf_dir  = os.path.join(self.path, "master", "vms",
                                     self.tpl_uuid)
        self.ovf_path = os.path.join(self.ovf_dir,
                                     self.tpl_uuid + '.ovf')

        self.ovf_name = ovf_name
        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb
        self.rhevm_description = rhevm_description
        self.rhevm_default_display_type = rhevm_default_display_type
        self.rhevm_os_descriptor = rhevm_os_descriptor

    def new_ovf_descriptor(self):
        return RHEVOVFDescriptor(self.img_uuid,
                                 self.vol_uuid,
                                 self.tpl_uuid,
                                 self.disk,
                                 self.ovf_name,
                                 self.ovf_cpu_count,
                                 self.ovf_memory_mb,
                                 self.rhevm_description,
                                 self.rhevm_default_display_type,
                                 self.rhevm_os_descriptor)

    def copy_disk(self):
        os.makedirs(os.path.dirname(self.disk_path))
        copyfile_sparse(self.disk.path, self.disk_path)

    def sync(self):
        super(RHEVOVFPackage, self).sync()
        self.meta_file = RHEVMetaFile(self.img_uuid, self.disk)
        meta = open(self.meta_path, 'w')
        meta.write(self.meta_file.generate_meta_file())
        meta.close()

    def make_ova_package(self):
        return super(RHEVOVFPackage, self).make_ova_package(gzip=True)


class VsphereOVFPackage(OVFPackage):
    def __init__(self, disk, base_image, path=None,
                 ovf_cpu_count="2",
                 ovf_memory_mb="4096",
                 vsphere_product_name="Product Name",
                 vsphere_product_vendor_name="Vendor Name",
                 vsphere_product_version="1.0",
                 vsphere_virtual_system_type="vmx-07 vmx-08"):
        disk = VsphereDisk(disk, base_image.data)
        super(VsphereOVFPackage, self).__init__(disk, path)
        self.disk_path = os.path.join(self.path, "disk.img")
        self.ovf_path  = os.path.join(self.path, "desc.ovf")

        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb
        self.vsphere_product_name = vsphere_product_name
        self.vsphere_product_vendor_name = vsphere_product_vendor_name
        self.vsphere_product_version = vsphere_product_version
        self.vsphere_virtual_system_type = vsphere_virtual_system_type

    def new_ovf_descriptor(self):
        return VsphereOVFDescriptor(self.disk,
                                    self.ovf_cpu_count,
                                    self.ovf_memory_mb,
                                    self.vsphere_product_name,
                                    self.vsphere_product_vendor_name,
                                    self.vsphere_product_version,
                                    self.vsphere_virtual_system_type)

    def copy_disk(self):
        copyfile_sparse(self.disk.path, self.disk_path)


class RHEVMetaFile(object):
    def __init__(self,
                 img_uuid,
                 disk,
                 storage_domain="00000000-0000-0000-0000-000000000000",
                 pool_id="00000000-0000-0000-0000-000000000000"):
        self.img_uuid = img_uuid
        self.disk = disk
        self.storage_domain = storage_domain
        self.pool_id = pool_id

    def generate_meta_file(self):
        metafile=""

        metafile += "DOMAIN=" + self.storage_domain + "\n"
        # saved template has VOLTYPE=SHARED
        metafile += "VOLTYPE=LEAF\n"
        metafile += "CTIME=" + str(int(self.disk.raw_create_time)) + "\n"
        # saved template has FORMAT=COW
        if self.disk.qcow_size:
            metafile += "FORMAT=COW\n"
        else:
            metafile += "FORMAT=RAW\n"
        metafile += "IMAGE=" + str(self.img_uuid) + "\n"
        metafile += "DISKTYPE=1\n"
        metafile += "PUUID=00000000-0000-0000-0000-000000000000\n"
        metafile += "LEGALITY=LEGAL\n"
        metafile += "MTIME=" + str(int(self.disk.raw_create_time)) + "\n"
        metafile += "POOL_UUID=" + self.pool_id + "\n"
        # assuming 1KB alignment
        metafile += "SIZE=" + str(self.disk.vol_size/512) + "\n"
        metafile += "TYPE=SPARSE\n"
        metafile += "DESCRIPTION=Uploaded by Image Factory\n"
        metafile += "EOF\n"

        return metafile

class RHEVDisk(object):
    def __init__(self, path):
        self.path = path
        self.qcow_size = check_qcow_size(self.path)
        if self.qcow_size:
            self.vol_size=self.qcow_size
        else:
            self.vol_size = os.stat(self.path).st_size

        self.raw_create_time = os.path.getctime(self.path)
        self.create_time = time.gmtime(self.raw_create_time)

class VsphereDisk(object):
    def __init__(self, path, base_image):
        self.path = path
        self.base_image = base_image
        self.id = os.path.basename(self.path).split('.')[0]

        self.vol_size = os.stat(self.base_image).st_size
        self.sparse_size = os.stat(self.path).st_blocks*512

        # self.raw_create_time = os.path.getctime(self.path)
        # self.create_time = time.gmtime(self.raw_create_time)

class LibvirtVagrantOVFPackage(OVFPackage):
    def __init__(self, disk, path=None, base_image=None, 
                 vagrant_sync_directory = "/vagrant"):
        super(LibvirtVagrantOVFPackage, self).__init__(disk,path)
        self.vagrant_sync_directory = vagrant_sync_directory
        # The base image can be either raw or qcow2 - determine size and save for later
        qcow_size = check_qcow_size(base_image.data)
        if qcow_size:
            self.disk_size=qcow_size
        else:
            self.disk_size = os.stat(base_image.data).st_size

    def make_ova_package(self):
        return super(LibvirtVagrantOVFPackage, self).make_ova_package(gzip=True)

    def copy_disk(self):
        copyfile_sparse(self.disk, os.path.join(self.path,"box.img"))

    def sync(self):
        self.copy_disk()

        vagrantfile = """Vagrant.configure('2') do |config|
        config.vm.synced_folder ".", "%s", type: "rsync"
        config.vm.provider :libvirt do |libvirt|
                libvirt.driver = 'kvm'
                libvirt.connect_via_ssh = false
                libvirt.username = 'root'
                libvirt.storage_pool_name = 'default'
        end
end
""" % (self.vagrant_sync_directory)

        vagrantfile_path = os.path.join(self.path, "Vagrantfile")
        vf = open(vagrantfile_path, 'w')
        vf.write(vagrantfile)
        vf.close()

        size_in_gb = int(self.disk_size / (1024 ** 3)) + 1
        metadata_json = '{"provider": "libvirt", "format": "qcow2", "virtual_size": %d}' % (size_in_gb)
        metadata_json_path = os.path.join(self.path, "metadata.json")
        mj = open(metadata_json_path, 'w')
        mj.write(metadata_json)
        mj.close()

class VirtualBoxOVFPackage(OVFPackage):
    def __init__(self, disk, path=None, base_image=None,
                 ovf_name=None,
                 ovf_cpu_count="1",
                 ovf_memory_mb="512",
                 vagrant_sync_directory="/vagrant"):
        super(VirtualBoxOVFPackage, self).__init__(disk, path)
        self.ovf_path  = os.path.join(self.path, "box.ovf")        

        if ovf_name:
            self.ovf_name = ovf_name.replace(' ','_')
        else:
            self.ovf_name = 'vagrant-virtualbox-box'
        self.disk_image_name = self.ovf_name + ".vmdk"
        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb
        self.vagrant_sync_directory = vagrant_sync_directory

        # We need the base image libvirt XML to obtain the MAC address originally used
        # when running the installer.  Virtualbox Vagrant seems to prefer guests that have
        # this explicitly defined
        libvirt_xml = base_image.parameters.get('libvirt_xml', None)
        if not libvirt_xml:
            raise ImageFactoryException("Passed a base image without libvirt XML - Need MAC address from this")

        doc = lxml.etree.fromstring(libvirt_xml)
        mac_addr = doc.xpath('/domain/devices/interface[@type="bridge"]/mac/@address')[0]
        # VirtualBox prefers this to be a flat string without the traditional colons
        self.mac_addr = mac_addr.replace(':','')

        # ARCH - used to select OS type
        self.arch = oz.TDL.TDL(base_image.template).arch
        self.base_image = base_image
        # The base image can be either raw or qcow2 - determine size and save for later
        qcow_size = check_qcow_size(base_image.data)
        if qcow_size:
            self.disk_size=qcow_size
        else:
            self.disk_size = os.stat(base_image.data).st_size


    def new_ovf_descriptor(self):
        return VirtualBoxOVFDescriptor(self.disk,
                                      self.disk_size,
                                      self.ovf_name,
                                      self.ovf_cpu_count,
                                      self.ovf_memory_mb,
                                      self.arch,
                                      self.disk_image_name,
                                      self.mac_addr)

    def copy_disk(self):
        copyfile_sparse(self.disk, os.path.join(self.path,self.disk_image_name))

    def sync(self):
        super(VirtualBoxOVFPackage, self).sync()

        vagrantfile = '''Vagrant.configure("2") do |config|
  config.vm.base_mac = "%s"
  config.vm.synced_folder ".", "%s", type: "rsync"
end
''' % (self.mac_addr, self.vagrant_sync_directory)
        vagrantfile_path = os.path.join(self.path, "Vagrantfile")
        vf = open(vagrantfile_path, 'w')
        vf.write(vagrantfile)
        vf.close()

        metadata_json = '{"provider":"virtualbox"}\n'
        metadata_json_path = os.path.join(self.path, "metadata.json")
        mj = open(metadata_json_path, 'w')
        mj.write(metadata_json)
        mj.close()

    def make_ova_package(self):
        # Stream optimized vmdk is already compressed at the sector level
        # no real benefit to further compression here
        return super(VirtualBoxOVFPackage, self).make_ova_package(gzip=False)

class VirtualBoxOVFDescriptor(object):
    def __init__(self, disk,
                 disk_size,
                 ovf_name,
                 ovf_cpu_count,
                 ovf_memory_mb,
                 arch,
                 disk_image_name,
                 mac_addr):
        self.disk = disk
        self.disk_size = disk_size

        self.ovf_name = ovf_name

        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb

        self.arch = arch
        self.disk_image_name = disk_image_name
        self.mac_addr = mac_addr

    def generate_ovf_xml(self):

	# lxml.etree favors use of the full namespace in constructors
	VSSD = '{http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData}'
	RASD = '{http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData}'
	VBOX = '{http://www.virtualbox.org/ovf/machine}'
	OVF = '{http://schemas.dmtf.org/ovf/envelope/1}'
	XSI = '{http://www.w3.org/2001/XMLSchema-instance}'
	nsmap = {'vssd': 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData', 'rasd': 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData', 'vbox': 'http://www.virtualbox.org/ovf/machine', None: 'http://schemas.dmtf.org/ovf/envelope/1', 'ovf': 'http://schemas.dmtf.org/ovf/envelope/1', 'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}

        # OS ID and description translation
        # VirtualBox uses a wide variety of these but they are so vague that it is
        # difficult to imagine them being genuinely useful to the hypervisor.
        # For example "Ubuntu" and "Red Hat Enterprise Linux" are IDs despite the fact
        # that they span a family of OSes that go as far back as the 2.6 kernel.
        # The only plausibly meaningful information in this field is whether or not
        # the OS in question is 32 bit or 64 bit.  So, we use RHEL and RHEL_64 bit as
        # the two possibilities.

        # TODO: If anyone encounters issues with this approach please let us know
        if self.arch == 'x86_64':
            os_id = '80'
            os_desc = 'RedHat_64'
        elif self.arch == 'i386':
            os_id = '79'
            os_desc = 'RedHat'
        else:
            raise ImageFactoryException("Virtualbox OVF architecture must be i386 or x86_64")

        # Variable items
	box_conf = { 'diskfile': self.disk_image_name,
		     'capacity': str(self.disk_size),
                     'cpu_count': str(self.ovf_cpu_count),
		     'machine_name': self.ovf_name,
		     'memory': str(self.ovf_memory_mb),
		     'os_id': os_id,
		     'os_desc': os_desc,
		     'mac_addr': self.mac_addr }

	# Time - used in multiple locations below - create once for consistent timestamp
	now = time.time()
	# Format preferred by virtualbox property timestamps
	nowvbstr = nowvbstr = '%d' % ( now * 10 ** 9 )
	# Format for other OVF timestamps
	nowstr = datetime.datetime.utcfromtimestamp(now).strftime('%Y-%m-%dT%H:%M:%SZ')

	# UUID for disk image
	disk_uuid = str(uuid.uuid4())

	# UUID for overall machine
	machine_uuid = str(uuid.uuid4())


	el_0 = lxml.etree.Element(OVF + 'Envelope', nsmap = nsmap)
	el_0.attrib[OVF + 'version'] = '1.0'
	el_0.attrib['{http://www.w3.org/XML/1998/namespace}lang'] = 'en-US'

	el_1 = lxml.etree.Element(OVF + 'References')

	el_2 = lxml.etree.Element(OVF + 'File')
	el_2.attrib[OVF + 'href'] = box_conf['diskfile']
	el_2.attrib[OVF + 'id'] = 'file1'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element(OVF + 'DiskSection')

	el_2 = lxml.etree.Element(OVF + 'Info')
	el_2.text = 'List of the virtual disks used in the package'
	el_1.append(el_2)

	el_2 = lxml.etree.Element(OVF + 'Disk')
	el_2.attrib[OVF + 'capacity'] = box_conf['capacity']
	el_2.attrib[OVF + 'diskId'] = 'vmdisk1'
	el_2.attrib[OVF + 'fileRef'] = 'file1'
	el_2.attrib[OVF + 'format'] = 'http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized'
	el_2.attrib[VBOX + 'uuid'] = disk_uuid
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element(OVF + 'NetworkSection')

	el_2 = lxml.etree.Element(OVF + 'Info')
	el_2.text = 'Logical networks used in the package'
	el_1.append(el_2)

	el_2 = lxml.etree.Element(OVF + 'Network')
	el_2.attrib[OVF + 'name'] = 'NAT'

	el_3 = lxml.etree.Element(OVF + 'Description')
	el_3.text = 'Logical network used by this appliance.'
	el_2.append(el_3)
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element(OVF + 'VirtualSystem')
	el_1.attrib[OVF + 'id'] = box_conf['machine_name']

	el_2 = lxml.etree.Element(OVF + 'Info')
	el_2.text = 'A virtual machine'
	el_1.append(el_2)

	el_2 = lxml.etree.Element(OVF + 'OperatingSystemSection')
	#el_2.attrib[OVF + 'id'] = '80'
	el_2.attrib[OVF + 'id'] = box_conf['os_id']

	el_3 = lxml.etree.Element(OVF + 'Info')
	el_3.text = 'The kind of installed guest operating system'
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Description')
	#el_3.text = 'RedHat_64'
	el_3.text = box_conf['os_desc']
	el_2.append(el_3)

	el_3 = lxml.etree.Element(VBOX + 'OSType')
	#el_3.text = 'RedHat_64'
	el_3.text = box_conf['os_desc']
	el_3.attrib[OVF + 'required'] = 'false'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element(OVF + 'VirtualHardwareSection')

	el_3 = lxml.etree.Element(OVF + 'Info')
	el_3.text = 'Virtual hardware requirements for a virtual machine'
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'System')

	el_4 = lxml.etree.Element(VSSD + 'ElementName')
	el_4.text = 'Virtual Hardware Family'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(VSSD + 'InstanceID')
	el_4.text = '0'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(VSSD + 'VirtualSystemIdentifier')
	#el_4.text = 'packer-centos-6.5-x86_64'
	el_4.text = box_conf['machine_name']
	el_3.append(el_4)

	el_4 = lxml.etree.Element(VSSD + 'VirtualSystemType')
	el_4.text = 'virtualbox-2.2'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Item')

	el_4 = lxml.etree.Element(RASD + 'Caption')
	el_4.text = '1 virtual CPU'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Description')
	el_4.text = 'Number of virtual CPUs'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ElementName')
	el_4.text = '%s virtual CPU' % (box_conf['cpu_count'])
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'InstanceID')
	el_4.text = '1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceType')
	el_4.text = '3'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'VirtualQuantity')
	el_4.text = box_conf['cpu_count']
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Item')

	el_4 = lxml.etree.Element(RASD + 'AllocationUnits')
	el_4.text = 'MegaBytes'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Caption')
	#el_4.text = '480 MB of memory'
	el_4.text = '%s MB of memory' % box_conf['memory']
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Description')
	el_4.text = 'Memory Size'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ElementName')
	#el_4.text = '480 MB of memory'
	el_4.text = '%s MB of memory' % box_conf['memory']
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'InstanceID')
	el_4.text = '2'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceType')
	el_4.text = '4'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'VirtualQuantity')
	el_4.text = '%s' % box_conf['memory']
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Item')

	el_4 = lxml.etree.Element(RASD + 'Address')
	el_4.text = '0'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Caption')
	el_4.text = 'ideController0'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Description')
	el_4.text = 'IDE Controller'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ElementName')
	el_4.text = 'ideController0'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'InstanceID')
	el_4.text = '3'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceSubType')
	el_4.text = 'PIIX4'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceType')
	el_4.text = '5'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Item')

	el_4 = lxml.etree.Element(RASD + 'Address')
	el_4.text = '1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Caption')
	el_4.text = 'ideController1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Description')
	el_4.text = 'IDE Controller'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ElementName')
	el_4.text = 'ideController1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'InstanceID')
	el_4.text = '4'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceSubType')
	el_4.text = 'PIIX4'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceType')
	el_4.text = '5'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Item')

	el_4 = lxml.etree.Element(RASD + 'AddressOnParent')
	el_4.text = '0'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Caption')
	el_4.text = 'disk1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Description')
	el_4.text = 'Disk Image'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ElementName')
	el_4.text = 'disk1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'HostResource')
	el_4.text = '/disk/vmdisk1'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'InstanceID')
	el_4.text = '5'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Parent')
	el_4.text = '3'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceType')
	el_4.text = '17'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Item')

	el_4 = lxml.etree.Element(RASD + 'AutomaticAllocation')
	el_4.text = 'true'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Caption')
	el_4.text = 'Ethernet adapter on \'NAT\''
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'Connection')
	el_4.text = 'NAT'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ElementName')
	el_4.text = 'Ethernet adapter on \'NAT\''
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'InstanceID')
	el_4.text = '6'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceSubType')
	el_4.text = 'E1000'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(RASD + 'ResourceType')
	el_4.text = '10'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element(VBOX + 'Machine')
	el_2.attrib[OVF + 'required'] = 'false'
	el_2.attrib['version'] = '1.12-macosx'
	#el_2.attrib['uuid'] = '{a22004b1-d5d7-48a4-a0f7-1547e77e66f4}'
	el_2.attrib['uuid'] = '{%s}' % ( machine_uuid )
	#el_2.attrib['name'] = 'packer-centos-6.5-x86_64'
	el_2.attrib['name'] = box_conf['machine_name']
	#el_2.attrib['OSType'] = 'RedHat_64'
	el_2.attrib['OSType'] = box_conf['os_desc']
	el_2.attrib['snapshotFolder'] = 'Snapshots'
	#el_2.attrib['lastStateChange'] = '2014-03-07T16:57:27Z'
	el_2.attrib['lastStateChange'] = nowstr

	el_3 = lxml.etree.Element(OVF + 'Info')
	el_3.text = 'Complete VirtualBox machine configuration in VirtualBox format'
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'ExtraData')

	el_4 = lxml.etree.Element(OVF + 'ExtraDataItem')
	el_4.attrib['name'] = 'GUI/LastGuestSizeHint'
	el_4.attrib['value'] = '720,400'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'ExtraDataItem')
	el_4.attrib['name'] = 'GUI/LastNormalWindowPosition'
	el_4.attrib['value'] = '400,183,720,421'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'Hardware')
	el_3.attrib['version'] = '2'
	el_4 = lxml.etree.Element(OVF + 'CPU')
	el_4.attrib['count'] = '1'
	el_4.attrib['hotplug'] = 'false'

	el_5 = lxml.etree.Element(OVF + 'HardwareVirtEx')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'HardwareVirtExNestedPaging')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'HardwareVirtExVPID')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'HardwareVirtExUX')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'PAE')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'HardwareVirtExLargePages')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'HardwareVirtForce')
	el_5.attrib['enabled'] = 'false'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Memory')
	el_4.attrib['RAMSize'] = box_conf['memory']
	el_4.attrib['PageFusion'] = 'false'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'HID')
	el_4.attrib['Pointing'] = 'PS2Mouse'
	el_4.attrib['Keyboard'] = 'PS2Keyboard'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'HPET')
	el_4.attrib['enabled'] = 'false'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Chipset')
	el_4.attrib['type'] = 'PIIX3'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Boot')

	el_5 = lxml.etree.Element(OVF + 'Order')
	el_5.attrib['position'] = '1'
	el_5.attrib['device'] = 'HardDisk'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Order')
	el_5.attrib['position'] = '2'
	el_5.attrib['device'] = 'DVD'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Order')
	el_5.attrib['position'] = '3'
	el_5.attrib['device'] = 'None'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Order')
	el_5.attrib['position'] = '4'
	el_5.attrib['device'] = 'None'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Display')
	el_4.attrib['VRAMSize'] = '8'
	el_4.attrib['monitorCount'] = '1'
	el_4.attrib['accelerate3D'] = 'false'
	el_4.attrib['accelerate2DVideo'] = 'false'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'VideoCapture')
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'RemoteDisplay')
	el_4.attrib['enabled'] = 'false'
	el_4.attrib['authType'] = 'Null'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'BIOS')

	el_5 = lxml.etree.Element(OVF + 'ACPI')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'IOAPIC')
	el_5.attrib['enabled'] = 'true'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Logo')
	el_5.attrib['fadeIn'] = 'true'
	el_5.attrib['fadeOut'] = 'true'
	el_5.attrib['displayTime'] = '0'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'BootMenu')
	el_5.attrib['mode'] = 'MessageAndMenu'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'TimeOffset')
	el_5.attrib['value'] = '0'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'PXEDebug')
	el_5.attrib['enabled'] = 'false'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'USBController')
	el_4.attrib['enabled'] = 'false'
	el_4.attrib['enabledEhci'] = 'false'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Network')

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '0'
	el_5.attrib['enabled'] = 'true'
	#el_5.attrib['MACAddress'] = '080027CE083D'
	el_5.attrib['MACAddress'] = box_conf['mac_addr']
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')
	el_5.append(el_6)

	el_6 = lxml.etree.Element(OVF + 'NAT')

	el_7 = lxml.etree.Element(OVF + 'DNS')
	el_7.attrib['pass-domain'] = 'true'
	el_7.attrib['use-proxy'] = 'false'
	el_7.attrib['use-host-resolver'] = 'false'
	el_6.append(el_7)

	el_7 = lxml.etree.Element(OVF + 'Alias')
	el_7.attrib['logging'] = 'false'
	el_7.attrib['proxy-only'] = 'false'
	el_7.attrib['use-same-ports'] = 'false'
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '1'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '080027D5C857'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '2'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '0800275B7551'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '3'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '0800272E32AD'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '4'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '080027A4CA2F'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '5'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '080027067B25'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '6'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '08002724BAEF'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Adapter')
	el_5.attrib['slot'] = '7'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['MACAddress'] = '080027693563'
	el_5.attrib['cable'] = 'true'
	el_5.attrib['speed'] = '0'
	el_5.attrib['type'] = '82540EM'

	el_6 = lxml.etree.Element(OVF + 'DisabledModes')

	el_7 = lxml.etree.Element(OVF + 'NAT')

	el_8 = lxml.etree.Element(OVF + 'DNS')
	el_8.attrib['pass-domain'] = 'true'
	el_8.attrib['use-proxy'] = 'false'
	el_8.attrib['use-host-resolver'] = 'false'
	el_7.append(el_8)

	el_8 = lxml.etree.Element(OVF + 'Alias')
	el_8.attrib['logging'] = 'false'
	el_8.attrib['proxy-only'] = 'false'
	el_8.attrib['use-same-ports'] = 'false'
	el_7.append(el_8)
	el_6.append(el_7)
	el_5.append(el_6)
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'UART')

	el_5 = lxml.etree.Element(OVF + 'Port')
	el_5.attrib['slot'] = '0'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['IOBase'] = '0x3f8'
	el_5.attrib['IRQ'] = '4'
	el_5.attrib['hostMode'] = 'Disconnected'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Port')
	el_5.attrib['slot'] = '1'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['IOBase'] = '0x2f8'
	el_5.attrib['IRQ'] = '3'
	el_5.attrib['hostMode'] = 'Disconnected'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'LPT')

	el_5 = lxml.etree.Element(OVF + 'Port')
	el_5.attrib['slot'] = '0'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['IOBase'] = '0x378'
	el_5.attrib['IRQ'] = '7'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'Port')
	el_5.attrib['slot'] = '1'
	el_5.attrib['enabled'] = 'false'
	el_5.attrib['IOBase'] = '0x378'
	el_5.attrib['IRQ'] = '7'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'AudioAdapter')
	el_4.attrib['controller'] = 'AC97'
	el_4.attrib['driver'] = 'CoreAudio'
	el_4.attrib['enabled'] = 'false'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'RTC')
	el_4.attrib['localOrUTC'] = 'local'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'SharedFolders')
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Clipboard')
	el_4.attrib['mode'] = 'Disabled'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'DragAndDrop')
	el_4.attrib['mode'] = 'Disabled'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'IO')

	el_5 = lxml.etree.Element(OVF + 'IoCache')
	el_5.attrib['enabled'] = 'true'
	el_5.attrib['size'] = '5'
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'BandwidthGroups')
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'HostPci')

	el_5 = lxml.etree.Element(OVF + 'Devices')
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'EmulatedUSB')

	el_5 = lxml.etree.Element(OVF + 'CardReader')
	el_5.attrib['enabled'] = 'false'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'Guest')
	el_4.attrib['memoryBalloonSize'] = '0'
	el_3.append(el_4)

	el_4 = lxml.etree.Element(OVF + 'GuestProperties')

	el_5 = lxml.etree.Element(OVF + 'GuestProperty')
	el_5.attrib['name'] = '/VirtualBox/GuestAdd/Revision'
	el_5.attrib['value'] = '92456'
	el_5.attrib['timestamp'] = nowvbstr
	el_5.attrib['flags'] = ''
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'GuestProperty')
	el_5.attrib['name'] = '/VirtualBox/GuestAdd/Version'
	el_5.attrib['value'] = '4.3.8'
	el_5.attrib['timestamp'] = nowvbstr
	el_5.attrib['flags'] = ''
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'GuestProperty')
	el_5.attrib['name'] = '/VirtualBox/GuestAdd/VersionExt'
	el_5.attrib['value'] = '4.3.8'
	el_5.attrib['timestamp'] = nowvbstr
	el_5.attrib['flags'] = ''
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'GuestProperty')
	el_5.attrib['name'] = '/VirtualBox/GuestInfo/OS/Product'
	el_5.attrib['value'] = 'Linux'
	el_5.attrib['timestamp'] = nowvbstr
	el_5.attrib['flags'] = ''
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'GuestProperty')
	el_5.attrib['name'] = '/VirtualBox/GuestInfo/OS/Release'
	el_5.attrib['value'] = '2.6.32-431.el6.x86_64'
	el_5.attrib['timestamp'] = nowvbstr
	el_5.attrib['flags'] = ''
	el_4.append(el_5)

	el_5 = lxml.etree.Element(OVF + 'GuestProperty')
	el_5.attrib['name'] = '/VirtualBox/GuestInfo/OS/Version'
	el_5.attrib['value'] = '#1 SMP Fri Nov 22 03:15:09 UTC 2013'
	el_5.attrib['timestamp'] = nowvbstr
	el_5.attrib['flags'] = ''
	el_4.append(el_5)
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element(OVF + 'StorageControllers')

	el_4 = lxml.etree.Element(OVF + 'StorageController')
	el_4.attrib['name'] = 'IDE Controller'
	el_4.attrib['type'] = 'PIIX4'
	el_4.attrib['PortCount'] = '2'
	el_4.attrib['useHostIOCache'] = 'true'
	el_4.attrib['Bootable'] = 'true'

	el_5 = lxml.etree.Element(OVF + 'AttachedDevice')
	el_5.attrib['type'] = 'HardDisk'
	el_5.attrib['port'] = '0'
	el_5.attrib['device'] = '0'

	el_6 = lxml.etree.Element(OVF + 'Image')
	el_6.attrib['uuid'] = '{%s}' % disk_uuid
	el_5.append(el_6)
	el_4.append(el_5)
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)
        el_0.append(el_1)

        et = ElementTree.ElementTree(el_0)
        return et
