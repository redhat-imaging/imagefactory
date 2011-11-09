#
# Copyright 2010 Jonathan Kinred <jonathan.kinred@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# This is initial and very rough support for VMWare machine imports
# The script below is based off of an example in Jonathan Kinred's
# psphere package, modified to do an import rather than creating a blank
# vm

# TODO: List all the TODOs :-)
#  There are a number of baked in assumptions here
#  Some are valid (like controller type) and others probably need to be
#  dynamic
import sys
import os
import math
import pycurl
from psphere.vim25 import ObjectNotFoundError
from psphere.vim25 import HttpNfcLease
from psphere.vim25 import Vim
from psphere.soap import VimFault
from psphere.scripting import BaseScript
from time import sleep
from time import time
from imgfac.ImageFactoryException import ImageFactoryException
import logging

logging.getLogger('suds').setLevel(logging.INFO)

class VMImport:
    def __init__(self, url, username, password):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.vim = Vim(url)
        self.vim.login(username, password)

    def curl_progress(self, download_t, download_d, upload_t, upload_d):
        curtime=time()
        # TODO: Make poke frequency variable
        # 5 seconds isn't too much and it makes the status bar in the vSphere GUI look nice :-)
        if  (curtime - self.time_at_last_poke) >= 5:
            self.vim.invoke('HttpNfcLeaseProgress', _this=self.lease_mo_ref, percent = int(upload_d*100/upload_t))
            self.time_at_last_poke = time()

    def import_vm(self, datastore, network_name, name, disksize_kb,
                  memory, num_cpus, guest_id, host=None, imagefilename=None):

        nic = {'network_name': network_name, 'type': 'VirtualE1000'}
        nics = [nic]
        # If the host is not set, use the ComputeResource as the target
        if not host:
            target = self.vim.find_entity_view(view_type='ComputeResource')
            target.update_view_data(['name', 'datastore', 'network', 'parent',
                                     'resourcePool'])
            resource_pool = target.resourcePool
        else:
            target = self.vim.find_entity_view(view_type='HostSystem',
                                                filter={'name': host})
            # Retrieve the properties we're going to use
            target.update_view_data(['name', 'datastore', 'network', 'parent'])
            host_cr = self.vim.get_view(mo_ref=target.parent, vim=self.vim)
            host_cr.update_view_data(properties=['resourcePool'])
            resource_pool = host_cr.resourcePool

        # A list of devices to be assigned to the VM
        vm_devices = []

        # Create a disk controller
        controller = self.create_controller('VirtualLsiLogicController')
        vm_devices.append(controller)

        # Find the given datastore and ensure it is suitable
        if host:
            ds_target = host_cr
        else:
            ds_target = target

        try:
            ds = ds_target.find_datastore(name=datastore)
        except ObjectNotFoundError, e:
            raise ImageFactoryException('Could not find datastore with name %s: %s' % (datastore,
                                                                 e.error))


        ds.update_view_data(properties=['summary'])
        # Ensure the datastore is accessible and has enough space
        if (not ds.summary.accessible or
            ds.summary.freeSpace < disksize_kb * 1024):
            raise ImageFactoryException('Datastore (%s) exists, but is not accessible or'
                  'does not have sufficient free space.' % ds.summary.name)

        disk = self.create_disk(datastore=ds, disksize_kb=disksize_kb)
        vm_devices.append(disk)

        cdrom = self.create_cdrom(datastore=ds)
        vm_devices.append(cdrom)

        for nic in nics:
            nic_spec = self.create_nic(target, nic)
            if not nic_spec:
                raise ImageFactoryException('Could not create spec for NIC')

            # Append the nic spec to the vm_devices list
            vm_devices.append(nic_spec)

        vmfi = self.vim.create_object('VirtualMachineFileInfo')
        vmfi.vmPathName = '[%s]' % ds.summary.name
        vm_config_spec = self.vim.create_object('VirtualMachineConfigSpec')
        vm_config_spec.name = name
        vm_config_spec.memoryMB = memory
        vm_config_spec.files = vmfi
        vm_config_spec.annotation = 'Auto-provisioned by pSphere'
        vm_config_spec.numCPUs = num_cpus
        vm_config_spec.guestId = guest_id
        vm_config_spec.deviceChange = vm_devices

        # Find the datacenter of the target
        try:
            dc = target.find_datacenter()
        except ObjectNotFoundError, e:
            raise ImageFactoryException('Error while trying to find datacenter for %s: %s' %
                  (target.name, e.error))

        dc.update_view_data(properties=['vmFolder'])

        importspec = self.vim.create_object('VirtualMachineImportSpec')

        importspec.configSpec = vm_config_spec
        importspec.resPoolEntity = None

        lease_mo_ref = self.vim.invoke('ImportVApp', _this=resource_pool, spec = importspec, folder = dc.vmFolder)

        lease = HttpNfcLease(mo_ref=lease_mo_ref, vim=self.vim)

        self.lease_mo_ref = lease_mo_ref

        for i in range(1000):
            lease.update_view_data()
            if lease.state == "ready":
                break
            sleep(5)

        # There's not a lot of logic to how these URLs are described
        # However, we can look to see if the upload URL defines a disk
        # We should only have one such URL, so use it and throw an error if 
        # we do not find it

        url = None
        for url in lease.info.deviceUrl:
            if url['disk']:
                url = url['url']

        if not url: 
            raise ImageFactoryException("Unable to extract disk upload URL from HttpNfcLease")

        self.lease_timeout = lease.info.leaseTimeout
        self.time_at_last_poke = time()

        image_file = open(imagefilename)

        # Upload the image itself
        image_size = os.path.getsize(imagefilename)
        curl = pycurl.Curl()
        curl.setopt(pycurl.URL, str(url))
        curl.setopt(pycurl.SSL_VERIFYPEER, 0)
        curl.setopt(pycurl.POST, 1)
        curl.setopt(pycurl.POSTFIELDSIZE, image_size)
        curl.setopt(pycurl.READFUNCTION, image_file.read)
        curl.setopt(pycurl.HTTPHEADER, ["User-Agent: Load Tool (PyCURL Load Tool)", "Content-Type: application/octet-stream"])
        curl.setopt(pycurl.NOPROGRESS, 0)
        curl.setopt(pycurl.PROGRESSFUNCTION, self.curl_progress)
        curl.perform()
        curl.close()

        image_file.close()

        self.vim.invoke('HttpNfcLeaseComplete', _this=lease.mo_ref)

        # Flip this vm to a template
        self.log.debug("Marking newly created VM as a template")
        self.vim.invoke('MarkAsTemplate', _this=lease.info.entity)


        self.vim.logout()

    def create_nic(self, target, nic):
        """Return a NIC spec"""
        # Get all the networks associated with the HostSystem/ComputeResource
        networks = self.vim.get_views(mo_refs=target.network, properties=['name'])

        # Iterate through the networks and look for one matching
        # the requested name
        for network in networks:
            if network.name == nic['network_name']:
                # Success! Create a nic attached to this network
                backing = (self.vim.
                       create_object('VirtualEthernetCardNetworkBackingInfo'))
                backing.deviceName = nic['network_name']
                backing.network = network.mo_ref

                connect_info = (self.vim.
                                create_object('VirtualDeviceConnectInfo'))
                connect_info.allowGuestControl = True
                connect_info.connected = False
                connect_info.startConnected = True

                new_nic = self.vim.create_object(nic['type'])
                new_nic.backing = backing
                new_nic.key = 2
                # TODO: Work out a way to automatically increment this
                new_nic.unitNumber = 1
                new_nic.addressType = 'generated'
                new_nic.connectable = connect_info

                nic_spec = self.vim.create_object('VirtualDeviceConfigSpec')
                nic_spec.device = new_nic
                nic_spec.fileOperation = None
                operation = (self.vim.
                             create_object('VirtualDeviceConfigSpecOperation'))
                nic_spec.operation = (operation.add)

                return nic_spec

    def create_controller(self, controller_type):
        controller = self.vim.create_object(controller_type)
        controller.key = 0
        controller.device = [0]
        controller.busNumber = 0,
        controller.sharedBus = (self.vim.
                                create_object('VirtualSCSISharing').noSharing)

        spec = self.vim.create_object('VirtualDeviceConfigSpec')
        spec.device = controller
        spec.fileOperation = None
        spec.operation = (self.vim.
                          create_object('VirtualDeviceConfigSpecOperation').add)

        return spec

    def create_disk(self, datastore, disksize_kb):
        backing = (self.vim.create_object('VirtualDiskFlatVer2BackingInfo'))
        backing.datastore = None
        backing.diskMode = 'persistent'
        backing.fileName = '[%s]' % datastore.summary.name
        backing.thinProvisioned = False

        disk = self.vim.create_object('VirtualDisk')
        disk.backing = backing
        disk.controllerKey = 0
        disk.key = 0
        disk.unitNumber = 0
        disk.capacityInKB = disksize_kb

        disk_spec = self.vim.create_object('VirtualDeviceConfigSpec')
        disk_spec.device = disk
        file_op = self.vim.create_object('VirtualDeviceConfigSpecFileOperation')
        disk_spec.fileOperation = file_op.create
        operation = self.vim.create_object('VirtualDeviceConfigSpecOperation')
        disk_spec.operation = operation.add

        return disk_spec

    def create_cdrom(self, datastore):
        # This creates what is essentially a virtual CDROM drive with no disk in it
        # Adding this greatly simplifies the process of adding a custom ISO via deltacloud
        connectable = self.vim.create_object('VirtualDeviceConnectInfo')
        connectable.allowGuestControl = True
        connectable.connected = True
        connectable.startConnected = True
        #connectable.status = None

        backing = self.vim.create_object('VirtualCdromIsoBackingInfo')
        backing.datastore = None
        backing.fileName = '[%s]' % datastore.summary.name

        cdrom = self.vim.create_object('VirtualCdrom')
        cdrom.connectable = connectable
        cdrom.backing = backing
        # 201 is the second built in IDE controller
        cdrom.controllerKey = 201
        cdrom.key = 10
        cdrom.unitNumber = 0

        cdrom_spec = self.vim.create_object('VirtualDeviceConfigSpec')
        cdrom_spec.fileOperation = None
        cdrom_spec.device = cdrom
        operation = self.vim.create_object('VirtualDeviceConfigSpecOperation')
        cdrom_spec.operation = operation.add

        return cdrom_spec
