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

import logging
import uuid
import zope
import inspect
from imgfac.CloudDelegate import CloudDelegate
from imgfac.PersistentImageManager import PersistentImageManager
from imgfac.TargetImage import TargetImage
from imagefactory_plugins.ovfcommon.ovfcommon import RHEVOVFPackage, VsphereOVFPackage
from imagefactory_plugins.ovfcommon.ovfcommon import VirtualBoxOVFPackage
from imagefactory_plugins.ovfcommon.ovfcommon import LibvirtVagrantOVFPackage
from imagefactory_plugins.ovfcommon.ovfcommon import VMWareFusionVagrantOVFPackage
from imagefactory_plugins.ovfcommon.ovfcommon import HyperVOVFPackage

from imgfac.ImageFactoryException import ImageFactoryException
from oz.ozutil import copyfile_sparse
from oz.TDL import TDL

class OVA(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        retval = False

        if isinstance(builder.base_image, TargetImage):
            if builder.base_image.target in ('vsphere', 'rhevm', 'hyperv'):
                retval = True

        self.log.info('builder_should_create_target_image() called on OVA plugin - returning %s' % retval)

        return retval

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in OVA plugin')
        self.status="BUILDING"

        # NOTE: This is unique to the OVA plugin at the moment
        # The ID passed in as the "base" image is actually a target image for the cloud
        # type that will be the ultimate target of the OVA.  This allows us to reuse the
        # existing target plugin code for disk format transformation and focus on the OVF
        # specific work in this plugin

        # The target image containing the disk in the correct format
        # Again, the builder things this is a base image but it is actually a target image
        self.target_image = builder.base_image

        # The base image that this origin target image was created from
        self.base_image = PersistentImageManager.default_manager().image_with_id(self.target_image.base_image_id)

        # A convenience variable pointing at the target image we are creating
        # Take note - self.target_image is the image we are sourcing from
        #             self.image is us, another target image
        self.image = builder.target_image
        self.parameters = parameters

        # This lets our logging helper know what image is being operated on
        self.active_image = self.image

        self.generate_ova()

        self.percent_complete=100
        self.status="COMPLETED"

    def generate_ova(self):
        if self.target_image.target == 'rhevm':
            ova_format = self.parameters.get('rhevm_ova_format', 'rhevm')
            if ova_format == 'rhevm':
                klass = RHEVOVFPackage
            elif ova_format == 'vagrant-libvirt':
                klass = LibvirtVagrantOVFPackage
            else:
                raise ImageFactoryException("Unknown rhevm ova_format (%s) requested - must be 'rhevm' or 'libvirt-vagrant'" % (ova_format) )
        elif self.target_image.target == 'vsphere':
            ova_format = self.parameters.get('vsphere_ova_format', 'vsphere')
            if ova_format == 'vsphere':
                klass = VsphereOVFPackage
            elif ova_format == 'vagrant-virtualbox':
                klass = VirtualBoxOVFPackage
            elif ova_format == 'vagrant-vmware-fusion':
                klass = VMWareFusionVagrantOVFPackage
            else:
                raise ImageFactoryException("Unknown vsphere ova_format (%s) requested - must be 'vsphere', 'vagrant-virtualbox' or 'vagrant-vmware-fusion'" % (ova_format) )
        elif self.target_image.target == 'hyperv':
            ova_format = self.parameters.get('hyperv_ova_format', 'hyperv-vagrant')
            if ova_format == 'hyperv-vagrant':
                klass = HyperVOVFPackage
            elif ova_format == 'hyperv':
                klass = HyperVOVFPackage
                self.parameters['hyperv_vagrant'] = False
            else:
                raise ImageFactoryException("Unknown hyperv ova_format (%s) requested - must be 'hyperv-vagrant' or 'hyperv'" % (ova_format) )
        else:
            raise ImageFactoryException("OVA plugin only supports rhevm and vsphere target images")

        tdl = TDL(xmlstring=self.image.template, rootpw_required=False)
        if not 'ovf_name' in self.parameters:
            self.parameters['ovf_name'] = tdl.name

        klass_parameters = dict()

        if self.parameters:
            params = ['ovf_cpu_count','ovf_memory_mb','ovf_name',
                      'rhevm_default_display_type','rhevm_description','rhevm_os_descriptor',
                      'vsphere_product_name','vsphere_product_vendor_name','vsphere_product_version',
                      'vsphere_virtual_system_type', 'vsphere_scsi_controller_type',
                      'vsphere_network_controller_type', 'vsphere_nested_virt', 'vsphere_cdrom',
                      'fusion_scsi_controller_type', 'fusion_network_controller_type', 'fusion_nested_virt',
                      'hyperv_vagrant',
                      'vagrant_sync_directory']

            for param in params:
                if (self.parameters.get(param) and 
                    klass.__init__.func_code.co_varnames.__contains__(param)):
                    klass_parameters[param] = self.parameters.get(param)

        pkg = klass(disk=self.image.data, base_image=self.base_image,
                    **klass_parameters)
        ova = pkg.make_ova_package()
        copyfile_sparse(ova, self.image.data)
        pkg.delete()
