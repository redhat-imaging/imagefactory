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
from imgfac.ImageFactoryException import ImageFactoryException
from oz.ozutil import copyfile_sparse

class OVA(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        retval = False

        if isinstance(builder.base_image, TargetImage):
            if builder.base_image.target in ('vsphere', 'rhevm'):
                retval = True

        self.log.info('builder_should_create_target_image() called on OVA plugin - returning %s' % retval)

        return retval

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in OVA plugin')
        self.status="BUILDING"

        self.target_image = builder.base_image
        self.base_image = PersistentImageManager.default_manager().image_with_id(self.target_image.base_image_id)
        self.image = builder.target_image
        self.parameters = parameters

        # This lets our logging helper know what image is being operated on
        self.active_image = self.image

        self.generate_ova()

        self.percent_complete=100
        self.status="COMPLETED"

    def generate_ova(self):
        if self.target_image.target == 'rhevm':
            klass = RHEVOVFPackage
        elif self.target_image.target == 'vsphere':
            klass = VsphereOVFPackage
        else:
            raise ImageFactoryException("OVA plugin only support rhevm and vsphere images")

        klass_parameters = dict()

        if self.parameters:
            params = ['ovf_cpu_count','ovf_memory_mb',
                      'rhevm_default_display_type','rhevm_description','rhevm_os_descriptor',
                      'vsphere_product_name','vsphere_product_vendor_name','vsphere_product_version',
                      'vsphere_virtual_system_type']

            for param in params:
                if (self.parameters.get(param) and 
                    klass.__init__.func_code.co_varnames.__contains__(param)):
                    klass_parameters[param] = self.parameters.get(param)

        pkg = klass(disk=self.image.data, base_image=self.base_image.data,
                    **klass_parameters)
        ova = pkg.make_ova_package()
        copyfile_sparse(ova, self.image.data)
        pkg.delete()
