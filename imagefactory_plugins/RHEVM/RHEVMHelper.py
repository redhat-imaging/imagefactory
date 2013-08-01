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
from threading import BoundedSemaphore
from imagefactory_plugins.ovfcommon.ovfcommon import RHEVOVFPackage

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
        raise Exception("'%s' failed(%d): %s" % (cmd, retcode, stderr), retcode)
    return (stdout, stderr, retcode)


class RHEVMHelper(object):

    api_connections_lock = BoundedSemaphore()

    def __init__(self, url, username, password):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        # The SDK allows only a single active connection object to be created, regardless of whether 
        # or not multiple RHEVM servers are being accessed.  For now we need to have a global lock,
        # create a connection object before each batch of API interactions and then disconnect it.
        self.api_details = { 'url':url, 'username':username, 'password':password }

    # TODO: When this limitation in the ovirt SDK is removed, get rid of these
    def _init_api(self):
        self.log.debug("Doing blocking acquire() on global RHEVM API connection lock")
        self.api_connections_lock.acquire()
        self.log.debug("Got global RHEVM API connection lock")
        url = self.api_details['url']
        username = self.api_details['username']
        password = self.api_details['password']
        self.api = API(url=url, username=username, password=password, insecure=True)

    def _disconnect_api(self):
        try:
            self.log.debug("Attempting API disconnect")
            if hasattr(self, 'api') and self.api is not None:
                self.api.disconnect()
            else:
                self.log.debug("API connection was not initialized.  Will not attempt to disconnect.")
        finally:
            # Must always do this
            self.log.debug("Releasing global RHEVM API connection lock")
            self.api_connections_lock.release()

    # These are the only two genuinley public methods
    # What we create is a VM template

    def import_template(self, image_filename, nfs_host, nfs_path, nfs_dir, cluster,
                        ovf_name = None, ovf_desc = None):
        if not ovf_desc:
            self.ovf_desc = "Imported by Image Factory"
        else:
            self.ovf_desc = ovf_desc
        self.log.debug("Preparing for RHEVM template import of image file (%s)" % (image_filename))

        # API lock protected action
        try: 
            self._init_api()
            self.init_vm_import(image_filename, nfs_host, nfs_path, nfs_dir, cluster)
        finally:
            self._disconnect_api()

        self.ovf_name = ovf_name
        self.log.debug("Staging files")
        self.stage_files()
        self.log.debug("Moving files to final export domain location")
        self.move_files()
        self.ovf_pkg.delete()
        self.log.debug("Executing import")

        # API lock protected action
        try:
            self._init_api()
            self.execute_import()
        finally:
            self._disconnect_api()

        return str(self.ovf_pkg.tpl_uuid)

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

    def copy_dir_as_nfs_user(self, sourcefile, destfile):
        self.log.debug("Copying directory (%s) to (%s) as nfsuser" % (sourcefile, destfile))
        (stdout, stderr, retcode) = subprocess_check_output([ 'cp', '-r', '%s' % (sourcefile), '%s' % (destfile)], preexec_fn=self.become_nfs_user)

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

    def stage_files(self):
        # Called after init to copy files to staging location

        # This is the base dir of the export domain
        self.export_domain_dir = self.nfs_dir + "/" + self.storage_domain
        if not os.path.isdir(self.export_domain_dir):
            raise Exception("Cannot find expected export domain directory (%s) at local mount point (%s)" % (self.nfs_dir, self.storage_domain))

        self.ovf_pkg = RHEVOVFPackage(disk=self.image_filename,
                                      ovf_name=self.ovf_name,
                                      ovf_desc=self.ovf_desc)
        self.ovf_pkg.sync()

    def move_files(self):
        self.final_image_dir = "%s/images/%s" % (self.export_domain_dir, str(self.ovf_pkg.img_uuid))
        self.final_ovf_dir = "%s/master/vms/%s" % (self.export_domain_dir, str(self.ovf_pkg.tpl_uuid))

        self.copy_dir_as_nfs_user(self.ovf_pkg.image_dir, self.final_image_dir)
        self.copy_dir_as_nfs_user(self.ovf_pkg.ovf_dir, self.final_ovf_dir)

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
        template = self.storage_domain_object.templates.get(id=str(self.ovf_pkg.tpl_uuid))
        if template:
            template.import_template(action=action)
            real_template = self.api.templates.get(id=str(self.ovf_pkg.tpl_uuid))
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
