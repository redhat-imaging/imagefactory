#!/usr/bin/env python
# Copyright 2011 Jonathan Kinred
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at:
# 
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import re
import sys
import time
import os
import pycurl
import logging
import urllib2
from psphere import config, template
from psphere.client import Client
from psphere.errors import TemplateNotFoundError
from psphere.soap import VimFault
from time import sleep, time

logging.getLogger('suds').setLevel(logging.INFO)

class VSphereHelper:
    def __init__(self, url, username, password):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        if(url.startswith('http://') or url.startswith('https://')):
            server = urllib2.Request(url).get_host()
        else:
            server = url
        self.client = Client(server=server, username=username, password=password)

    def curl_progress(self, download_t, download_d, upload_t, upload_d):
        curtime=time()
        # TODO: Make poke frequency variable
        # 5 seconds isn't too much and it makes the status bar in the vSphere GUI look nice :-)
        if  (curtime - self.time_at_last_poke) >= 5:
            self.lease.HttpNfcLeaseProgress(percent = int(upload_d*100/upload_t))
            self.time_at_last_poke = time()

    def create_vm(self, imagefilename, name, compute_resource, datastore, disksize, nics,
                  memory, num_cpus, guest_id, host=None):
        """Create a virtual machine using the specified values.

        :param name: The name of the VM to create.
        :type name: str
        :param compute_resource: The name of a ComputeResource in which to \
                create the VM.
        :type compute_resource: str
        :param datastore: The name of the datastore on which to create the VM.
        :type datastore: str
        :param disksize: The size of the disk, specified in KB, MB or GB. e.g. \
                20971520KB, 20480MB, 20GB.
        :type disksize: str
        :param nics: The NICs to create, specified in a list of dict's which \
                contain a "network_name" and "type" key. e.g. \
                {"network_name": "VM Network", "type": "VirtualE1000"}
        :type nics: list of dict's
        :param memory: The amount of memory for the VM. Specified in KB, MB or \
                GB. e.g. 2097152KB, 2048MB, 2GB.
        :type memory: str
        :param num_cpus: The number of CPUs the VM will have.
        :type num_cpus: int
        :param guest_id: The vSphere string of the VM guest you are creating. \
                The list of VMs can be found at \
            http://www.vmware.com/support/developer/vc-sdk/visdk41pubs/ApiReference/index.html
        :type guest_id: str
        :param host: The name of the host (default: None), if you want to \
                provision the VM on a \ specific host.
        :type host: str

        """
        # Convenience variable
        client = self.client

        self.log.debug("Creating VM %s" % name)
        # If the host is not set, use the ComputeResource as the target
        if host is None:
            target = client.find_entity_view("ComputeResource",
                                          filter={"name": compute_resource})
            resource_pool = target.resourcePool
        else:
            target = client.find_entity_view("HostSystem", filter={"name": host})
            resource_pool = target.parent.resourcePool

        disksize_pattern = re.compile("^\d+[KMG]B")
        if disksize_pattern.match(disksize) is None:
            raise Exception("Disk size %s is invalid. Try \"12G\" or similar" % disksize)

        if disksize.endswith("GB"):
            disksize_kb = int(disksize[:-2]) * 1024 * 1024
        elif disksize.endswith("MB"):
            disksize_kb = int(disksize[:-2]) * 1024
        elif disksize.endswith("KB"):
            disksize_kb = int(disksize[:-2])
        else:
            raise Exception("Disk size %s is invalid. Try \"12G\" or similar" % disksize)

        memory_pattern = re.compile("^\d+[KMG]B")
        if memory_pattern.match(memory) is None:
            raise Exception("Memory size %s is invalid. Try \"12G\" or similar" % memory)

        if memory.endswith("GB"):
            memory_mb = int(memory[:-2]) * 1024
        elif memory.endswith("MB"):
            memory_mb = int(memory[:-2])
        elif memory.endswith("KB"):
            memory_mb = int(memory[:-2]) / 1024
        else:
            raise Exception("Memory size %s is invalid. Try \"12G\" or similar" % memory)

        # A list of devices to be assigned to the VM
        vm_devices = []

        # Create a disk controller
        controller = self.create_controller("VirtualLsiLogicController")
        vm_devices.append(controller)

        ds_to_use = None
        for ds in target.datastore:
            if ds.name == datastore:
                ds_to_use = ds
                break

        if ds_to_use is None:
            raise Exception("Could not find datastore on %s with name %s" %
                  (target.name, datastore))

        # Ensure the datastore is accessible and has enough space
        if ds_to_use.summary.accessible is not True:
            raise Exception("Datastore (%s) exists, but is not accessible" %
                  ds_to_use.summary.name)
        if ds_to_use.summary.freeSpace < disksize_kb * 1024:
            raise Exception("Datastore (%s) exists, but does not have sufficient"
                  " free space." % ds_to_use.summary.name)

        disk = self.create_disk(datastore=ds_to_use, disksize_kb=disksize_kb)
        vm_devices.append(disk)

        cdrom = self.create_cdrom(datastore=ds_to_use)
        vm_devices.append(cdrom)
        
        for nic in nics:
            nic_spec = self.create_nic(target, nic)
            if nic_spec is None:
                raise Exception("Could not create spec for NIC")

            # Append the nic spec to the vm_devices list
            vm_devices.append(nic_spec)

        vmfi = client.create("VirtualMachineFileInfo")
        vmfi.vmPathName = "[%s]" % ds_to_use.summary.name
        vm_config_spec = client.create("VirtualMachineConfigSpec")
        vm_config_spec.name = name
        vm_config_spec.memoryMB = memory_mb
        vm_config_spec.files = vmfi
        vm_config_spec.annotation = "Auto-provisioned by psphere"
        vm_config_spec.numCPUs = num_cpus
        vm_config_spec.guestId = guest_id
        vm_config_spec.deviceChange = vm_devices

        # Find the datacenter of the target
        if target.__class__.__name__ == "HostSystem":
            datacenter = target.parent.parent.parent
        else:
            datacenter = target.parent.parent

        importspec = client.create('VirtualMachineImportSpec')

        importspec.configSpec = vm_config_spec
        importspec.resPoolEntity = None

        lease = resource_pool.ImportVApp(spec = importspec, folder = datacenter.vmFolder)
        self.lease = lease

        # Lease takes a bit of time to initialize
        for i in range(1000):
            #print lease.error
            if lease.state == "ready":
                break
            if lease.state == "error":
                raise Exception("Our HttpNFCLease failed to initialize")
            sleep(5)
            lease.update_view_data(properties=["state"])

        #print "For debug and general info, here is the lease info"
        #pprint(lease.info)

        url = None
        for url in lease.info.deviceUrl:
            if url['disk']:
                url = url['url']

        if not url:
            raise Exception("Unable to extract disk upload URL from HttpNfcLease")

        self.log.debug("Extracted image upload URL (%s) from lease" % (url))

        lease_timeout = lease.info.leaseTimeout
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

        lease.HttpNfcLeaseComplete()

        vm = lease.info.entity

        vm.MarkAsTemplate()

    def create_nic(self, target, nic):
        # Convenience variable
        client = self.client
        """Return a NIC spec"""
        # Iterate through the networks and look for one matching
        # the requested name
        for network in target.network:
            if network.name == nic["network_name"]:
                net = network
                break
        else:
            return None

        # Success! Create a nic attached to this network
        backing = client.create("VirtualEthernetCardNetworkBackingInfo")
        backing.deviceName = nic["network_name"]
        backing.network = net

        connect_info = client.create("VirtualDeviceConnectInfo")
        connect_info.allowGuestControl = True
        connect_info.connected = False
        connect_info.startConnected = True

        new_nic = client.create(nic["type"]) 
        new_nic.backing = backing
        new_nic.key = 2
        # TODO: Work out a way to automatically increment this
        new_nic.unitNumber = 1
        new_nic.addressType = "generated"
        new_nic.connectable = connect_info

        nic_spec = client.create("VirtualDeviceConfigSpec")
        nic_spec.device = new_nic
        nic_spec.fileOperation = None
        operation = client.create("VirtualDeviceConfigSpecOperation")
        nic_spec.operation = (operation.add)

        return nic_spec

    def create_controller(self, controller_type):
        # Convenience variable
        client = self.client
        controller = client.create(controller_type)
        controller.key = 0
        controller.device = [0]
        controller.busNumber = 0,
        controller.sharedBus = client.create("VirtualSCSISharing").noSharing
        spec = client.create("VirtualDeviceConfigSpec")
        spec.device = controller
        spec.fileOperation = None
        spec.operation = client.create("VirtualDeviceConfigSpecOperation").add
        return spec

    def create_disk(self, datastore, disksize_kb):
        # Convenience variable
        client = self.client
        backing = client.create("VirtualDiskFlatVer2BackingInfo")
        backing.datastore = None
        backing.diskMode = "persistent"
        backing.fileName = "[%s]" % datastore.summary.name
        backing.thinProvisioned = True

        disk = client.create("VirtualDisk")
        disk.backing = backing
        disk.controllerKey = 0
        disk.key = 0
        disk.unitNumber = 0
        disk.capacityInKB = disksize_kb

        disk_spec = client.create("VirtualDeviceConfigSpec")
        disk_spec.device = disk
        file_op = client.create("VirtualDeviceConfigSpecFileOperation")
        disk_spec.fileOperation = file_op.create
        operation = client.create("VirtualDeviceConfigSpecOperation")
        disk_spec.operation = operation.add

        return disk_spec

    def create_cdrom(self, datastore):
        # Convenience variable
        client = self.client
        # This creates what is essentially a virtual CDROM drive with no disk in it
        # Adding this greatly simplifies the process of adding a custom ISO via deltacloud
        connectable = client.create('VirtualDeviceConnectInfo')
        connectable.allowGuestControl = True
        connectable.connected = True
        connectable.startConnected = True
        #connectable.status = None

        backing = client.create('VirtualCdromIsoBackingInfo')
        backing.datastore = None
        backing.fileName = '[%s]' % datastore.summary.name

        cdrom = client.create('VirtualCdrom')
        cdrom.connectable = connectable
        cdrom.backing = backing
        # 201 is the second built in IDE controller
        cdrom.controllerKey = 201
        cdrom.key = 10
        cdrom.unitNumber = 0

        cdrom_spec = client.create('VirtualDeviceConfigSpec')
        cdrom_spec.fileOperation = None
        cdrom_spec.device = cdrom
        operation = client.create('VirtualDeviceConfigSpecOperation')
        cdrom_spec.operation = operation.add

        return cdrom_spec

    def delete_vm(self, name):
        vm = self.client.find_entity_view("VirtualMachine", filter={"name":name})
        if not vm:
            raise Exception("Cannot find VM with name (%s)" % (name))

        vmdestroy = vm.Destroy_Task()
        for i in range(300):
            if not (vmdestroy.info.state in ["queued", "running"]):
                break
            sleep(1)
            vmdestroy.update_view_data(properties=["info"])

        if vmdestroy.info.state != "success":
            # TODO: Return the reason - this is part of the rather complex Task object
            raise Exception("Failed to delete VM (%s) in timeout period" % (name))
