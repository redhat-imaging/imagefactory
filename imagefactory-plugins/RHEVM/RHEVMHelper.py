#!/usr/bin/python
import pdb
import logging
import stat
import os
import sys
import struct
import time
import uuid
import subprocess
from tempfile import NamedTemporaryFile, TemporaryFile
from ovirtsdk.api import API
from ovirtsdk.xml import params
from xml.etree import ElementTree
from time import sleep

# Large portions derived from dc-rhev-img from iwhd written by
# Pete Zaitcev <zaitcev@redhat.com>

NFSUID = 36
NFSGID = 36

# Borrowed from Oz by Chris Lalancette 
def subprocess_check_output(*popenargs, **kwargs):
    """
Function to call a subprocess and gather the output.
"""
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    if 'stderr' in kwargs:
        raise ValueError('stderr argument not allowed, it will be overridden.')

    #executable_exists(popenargs[0][0])

    # NOTE: it is very, very important that we use temporary files for
    # collecting stdout and stderr here. There is a nasty bug in python
    # subprocess; if your process produces more than 64k of data on an fd that
    # is using subprocess.PIPE, the whole thing will hang. To avoid this, we
    # use temporary fds to capture the data
    stdouttmp = TemporaryFile()
    stderrtmp = TemporaryFile()

    process = subprocess.Popen(stdout=stdouttmp, stderr=stderrtmp, *popenargs,
                               **kwargs)
    process.communicate()
    retcode = process.poll()

    stdouttmp.seek(0, 0)
    stdout = stdouttmp.read()
    stdouttmp.close()

    stderrtmp.seek(0, 0)
    stderr = stderrtmp.read()
    stderrtmp.close()

    if retcode:
        cmd = ' '.join(*popenargs)
        raise SubprocessException("'%s' failed(%d): %s" % (cmd, retcode, stderr), retcode)
    return (stdout, stderr, retcode)


class RHEVMHelper(object):

    def __init__(self, url, username, password):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.api = API(url=url, username=username, password=password)

    # These are the only two genuinley public methods
    # What we create is a VM template

    def import_template(self, image_filename, nfs_host, nfs_path, nfs_dir, cluster):
        self.log.debug("Preparing for RHEVM template import of image file (%s)" % (image_filename))
        self.init_vm_import(image_filename, nfs_host, nfs_path, nfs_dir, cluster)
        self.log.debug("Staging files")
        self.stage_files()
        self.log.debug("Moving files to final export domain location")
        self.move_files()
        self.log.debug("Executing import")
        self.execute_import()
        return str(self.tpl_uuid)

    def delete_template(self, template_uuid):
        template = self.api.templates.get(id=template_uuid)
        if template:
            template.delete()
            return True
        else:
            return False

    # Begin Nuts and Bolts

    # We don't want to run seteuid() in our main process as it will globally change the UID/GID for everything
    # OTOH, we need to be root to access our image files and temp files
    # We use stdin and Popen's preexec_fn via the helper functions below to deal with this
    def become_nfs_user(self):
        os.setegid(NFSGID)
        os.seteuid(NFSUID)

    def copy_as_nfs_user(self, sourcefile, destfile):
        self.log.debug("Copying (%s) to (%s) as nfsuser" % (sourcefile, destfile))
        f = open(sourcefile,"r")
        (stdout, stderr, retcode) = subprocess_check_output([ 'dd', 'of=%s' % (destfile), 'bs=4k' ], stdin=f, preexec_fn=self.become_nfs_user)
        f.close()

    def move_as_nfs_user(self, sourcefile, destfile):
        self.log.debug("Moving (%s) to (%s) as nfsuser" % (sourcefile, destfile))
        (stdout, stderr, retcode) = subprocess_check_output([ 'mv', '%s' % (sourcefile), '%s' % (destfile)], preexec_fn=self.become_nfs_user)

    def mkdir_as_nfs_user(self, directory):
        self.log.debug("Making directory (%s) as nfsuser" % (directory))
        (stdout, stderr, retcode) = subprocess_check_output([ 'mkdir', '%s' % (directory)], preexec_fn=self.become_nfs_user)

    def rm_rf_as_nfs_user(self, directory):
        self.log.debug("Recursive remove of dir (%s) as nfsuser" % (directory))
        (stdout, stderr, retcode) = subprocess_check_output([ 'rm', '-rf', '%s' % (directory)], preexec_fn=self.become_nfs_user)

    def get_storage_domain(self, nfs_host, nfs_path):
	# Find the storage domain that matches the nfs details given
	sds = self.api.storagedomains.list()
	for sd in sds:
	    if sd.get_type() == "export":
		self.log.debug("Export domain: (%s)" % (sd.get_name()))
		stor = sd.get_storage()
		if (stor.get_address() == nfs_host) and (stor.get_path() == nfs_path):
		    self.log.debug("This is the right domain (%s)" % (sd.get_id()))
		    return sd
	return None

    def get_pool_id(self, sd_uuid):
        # Get datacenter for a given storage domain UUID
        # This is the UUID that becomes the "StoragePoolID" in our OVF XML
        # TODO: The storagedomain object has a get_data_center() method that doesn't seem to work
        #       Find out why
        dcs =  self.api.datacenters.list()
        for dc in dcs:
            self.log.debug("Looking for our storage domain (%s) in data center (%s)" % (sd_uuid, dc.get_id()))
	    sd = dc.storagedomains.get(id=sd_uuid)
            if sd: 
		self.log.debug("This is the right datacenter (%s)" % (dc.get_id()))
		return dc
        return None

    def get_cluster_by_dc(self, poolid):
        # If we have been passed "_any_" as the cluster name, we pick the first cluster that
        # matches our datacenter/pool ID
	clusters = self.api.clusters.list()

	for cluster in clusters:
	    dc_id = None
	    if cluster.get_data_center():
		dc_id = cluster.get_data_center().get_id()
	    self.log.debug("Checking cluster (%s) with name (%s) with data center (%s)" % (cluster.get_id(), cluster.get_name(), dc_id))
	    if dc_id == poolid:
		return cluster
        self.log.debug("Cannot find cluster for dc (%s)" % (poolid))
        return None

    def get_cluster_by_name(self, name):
        # If we have been passed a specific cluster name, we need to find that specific cluster
	clusters = self.api.clusters.list()
	for cluster in clusters:
	    self.log.debug("Checking cluster (%s) with name (%s)" % (cluster.get_id(), cluster.get_name()))
	    if cluster.get_name() == name:
		return cluster
        self.log.debug("Cannot find cluster named (%s)" % (name))
	return None


    def check_qcow_size(self, filename):
        # Detect if an image is in qcow format
        # If it is, return the size of the underlying disk image
        # If it isn't, return none

	# For interested parties, this is the QCOW header struct in C
	# struct qcow_header {
	#    uint32_t magic; 
	#    uint32_t version;
	#    uint64_t backing_file_offset;
	#    uint32_t backing_file_size;
	#    uint32_t cluster_bits;
	#    uint64_t size; /* in bytes */
	#    uint32_t crypt_method;
	#    uint32_t l1_size;
	#    uint64_t l1_table_offset;
	#    uint64_t refcount_table_offset;
	#    uint32_t refcount_table_clusters;
	#    uint32_t nb_snapshots;
	#    uint64_t snapshots_offset;
	# };

	# And in Python struct format string-ese
	qcow_struct=">IIQIIQIIQQIIQ" # > means big-endian
	qcow_magic = 0x514649FB # 'Q' 'F' 'I' 0xFB

	f = open(filename,"r")
	pack = f.read(struct.calcsize(qcow_struct))
	f.close()

	unpack = struct.unpack(qcow_struct, pack)

	if unpack[0] == qcow_magic:
	    return unpack[5]
	else:
            return None

    def init_vm_import(self, image_filename, nfs_host, nfs_path, nfs_dir, cluster):
        # Prepare for the import of a VM
        self.image_filename = image_filename
        self.nfs_host = nfs_host
        self.nfs_path = nfs_path
        self.nfs_dir = nfs_dir

        # Sets some values used when creating XML and meta files
        self.storage_domain_object = self.get_storage_domain(nfs_host, nfs_path)
        if self.storage_domain_object:
            self.storage_domain = self.storage_domain_object.get_id()
        else:
            raise Exception("Cannot find storage domain matching NFS details given")

        self.dc_object = self.get_pool_id(self.storage_domain)
        if self.dc_object:
            # Our StoragePoolID is the UUID of the DC containing our storage domain
            self.pool_id=self.dc_object.get_id()
        else:
            raise Exception("Cannot find datacenter for our storage domain")

        if cluster == '_any_':
            self.cluster_object = self.get_cluster_by_dc(self.pool_id)
        else:
            self.cluster_object = self.get_cluster_by_name(cluster)
        if self.cluster_object:
            self.cluster = self.cluster_object.get_id()
        else:
            raise Exception("Cannot find cluster (%s)" % (cluster))

        # Volume size is the qcow_size if the image is qcow
        # or the raw disk image size if not
        self.qcow_size = self.check_qcow_size(image_filename)
        if self.qcow_size:
            self.vol_size=self.qcow_size
        else:
            statb = os.stat(imgdst)
            self.vol_size = statb[stat.ST_SIZE]

        # We need these three unique identifiers when generating XML and the meta file
        self.img_uuid = uuid.uuid4()
        self.vol_uuid = uuid.uuid4()
        self.tpl_uuid = uuid.uuid4()

        # Set this once to use in both the OVF XML and the meta file
        self.raw_create_time = time.time()
        self.create_time = time.gmtime(self.raw_create_time)

    def stage_files(self):
        # Called after init to copy files to staging location

        # This is the base dir of the export domain
        self.export_domain_dir = self.nfs_dir + "/" + self.storage_domain
        if not os.path.isdir(self.export_domain_dir):
            raise Exception("Cannot find expected export domain directory (%s) at local mount point (%s)" % (self.nfs_dir, self.storage_domain))

        # Make distinct tempdir for OVF stuff
        self.ovftmpdir=self.export_domain_dir + "/" + "imgfac." + str(self.tpl_uuid)
        self.mkdir_as_nfs_user(self.ovftmpdir)

        # Add the OVF file
        self.ovfdest = self.ovftmpdir + "/" + str(self.tpl_uuid) + ".ovf"
        ovf_file_object = NamedTemporaryFile()
        et = self.generate_ovf_xml()
        et.write(ovf_file_object)
        ovf_file_object.flush()
        self.copy_as_nfs_user(ovf_file_object.name, self.ovfdest)
        ovf_file_object.close()

        # Make our own temporary subdir for the image file itself
        self.imgtmpdir=self.export_domain_dir + "/" + "imgfac." + str(self.img_uuid)
        self.mkdir_as_nfs_user(self.imgtmpdir)
        
        # Add the meta file for the image
        self.imgdest = self.imgtmpdir + "/" + str(self.vol_uuid)
        self.imgmetadest = self.imgdest + ".meta"
        meta_file_object = NamedTemporaryFile()
        meta_file_object.write(self.generate_meta_file())
        meta_file_object.flush()
        self.copy_as_nfs_user(meta_file_object.name, self.imgmetadest)
        meta_file_object.close()

        # Copy the big image file last 
        self.copy_as_nfs_user(self.image_filename, self.imgdest)

    def move_files(self):
        self.final_image_dir = "%s/images/%s" % (self.export_domain_dir, str(self.img_uuid))
        self.final_ovf_dir = "%s/master/vms/%s" % (self.export_domain_dir, str(self.tpl_uuid))

        self.move_as_nfs_user(self.imgtmpdir, self.final_image_dir)
        self.move_as_nfs_user(self.ovftmpdir, self.final_ovf_dir)

    def remove_export_template(self):
        self.rm_rf_as_nfs_user(self.final_image_dir)
        self.rm_rf_as_nfs_user(self.final_ovf_dir)       

    def execute_import(self):
        # We import to the master storage domain of the datacenter of which our export domain is a member
        # Got it?
        action = params.Action()
        sds = self.dc_object.storagedomains.list()
        for sd in sds:
            if sd.get_master():
                action.storage_domain=sd
        if not action.storage_domain:
            raise Exception("Could not find master storage domain for datacenter ID (%s)" % (self.dc_object.get_id()))
        action.cluster = self.cluster_object

        # At this point our freshly copied in files are discoverable via the tpl_uuid in our export domain
        template = self.storage_domain_object.templates.get(id=str(self.tpl_uuid))
        if template:
            template.import_template(action=action)
            real_template = self.api.templates.get(id=str(self.tpl_uuid))
            # Wait 5 minutes for an import to finish
            self.log.debug("Waiting for template import to complete")
            for i in range(30):
                self.log.debug("Waited %d - state (%s)" % (i*10, real_template.get_status().get_state()))
                if real_template.get_status().get_state() != 'locked':
                    break
                real_template = real_template.update()
                sleep(10)
            self.log.debug("Deleting export domain files")
            self.remove_export_template() 
            final_state = real_template.get_status().get_state()
            if final_state == 'ok':
                self.log.debug("Template import completed successfully")
                return
            elif final_state == 'locked':
                raise Exception("Timed out waiting for template import to finish")
            else:
                raise Exception("Template import ended in unknown state (%s)" % (final_state))

    def generate_meta_file(self):
        metafile=""

	metafile += "DOMAIN=" + self.storage_domain + "\n"
	# saved template has VOLTYPE=SHARED
	metafile += "VOLTYPE=LEAF\n"
	metafile += "CTIME=" + str(int(self.raw_create_time)) + "\n"
	# saved template has FORMAT=COW
        if self.qcow_size:
	    metafile += "FORMAT=COW\n"
        else:
	    metafile += "FORMAT=RAW\n"
	metafile += "IMAGE=" + str(self.img_uuid) + "\n"
	metafile += "DISKTYPE=1\n"
	metafile += "PUUID=00000000-0000-0000-0000-000000000000\n"
	metafile += "LEGALITY=LEGAL\n"
	metafile += "MTIME=" + str(int(self.raw_create_time)) + "\n"
	metafile += "POOL_UUID=" + self.pool_id + "\n"
	# assuming 1KB alignment
	metafile += "SIZE=" + str(self.vol_size/512) + "\n"
	metafile += "TYPE=SPARSE\n"
	metafile += "DESCRIPTION=Uploaded by Image Factory\n"
        metafile += "EOF\n"

        return metafile
 
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
	etfile.set('ovf:size', str(self.vol_size))
        # TODO: Bulk this up a bit
	etfile.set('ovf:description', os.path.basename(self.image_filename))
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
	vol_size_str = str((self.vol_size + (1024*1024*1024) - 1) / (1024*1024*1024))
	etdisk.set('ovf:size', vol_size_str)
	etdisk.set('ovf:actual_size', vol_size_str)
	# XXX ovf:vm_snapshot_id
	etdisk.set('ovf:fileRef', str(self.img_uuid)+'/'+str(self.vol_uuid))
	# XXX ovf:format ("usually url to the specification")
        if self.qcow_size:
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
	ete.text = str(self.img_uuid)
	etcon.append(ete)

	ete = ElementTree.Element('TemplateId')
	ete.text = str(self.tpl_uuid)
	etcon.append(ete)

	# spec also has 'TemplateName'

	ete = ElementTree.Element('Description')
	ete.text = "Template imported by Image Factory"
	etcon.append(ete)

	ete = ElementTree.Element('Domain')
	# AD domain, not in use right now
	# ete.text = 
	etcon.append(ete)

	ete = ElementTree.Element('CreationDate')
	ete.text = time.strftime("%Y/%m/%d %H:%M:%S", self.create_time)
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
	ete.text = "0"
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
	ete.text = "OtherLinux"
	etsec.append(ete)

	etcon.append(etsec)

	etsec = ElementTree.Element('Section')
	etsec.set('xsi:type', "ovf:VirtualHardwareSection_Type")

	ete = ElementTree.Element('Info')
	ete.text = "1 CPU, 512 Memory"
	etsec.append(ete)

	etsys = ElementTree.Element('System')
	# This is probably wrong, needs actual type.
	ete = ElementTree.Element('vssd:VirtualSystemType')
	ete.text = "RHEVM 4.6.0.163"
	etsys.append(ete)
	etsec.append(etsys)

	etitem = ElementTree.Element('Item')

	ete = ElementTree.Element('rasd:Caption')
	ete.text = "1 virtual CPU"
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
	ete.text = "1"
	etitem.append(ete)

	etsec.append(etitem)

	etitem = ElementTree.Element('Item')

	ete = ElementTree.Element('rasd:Caption')
	ete.text = "512 MB of memory"
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
	ete.text = "512"
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
	ete.text = time.strftime("%Y/%m/%d %H:%M:%S", self.create_time)
	etitem.append(ete)

	ete = ElementTree.Element('rasd:LastModified')
	ete.text = time.strftime("%Y/%m/%d %H:%M:%S", self.create_time)
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
