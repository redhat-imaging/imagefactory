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

import cqpid
from qmf2 import *
import BuildAdaptor
import httplib2
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.Template import Template
import logging

# Singleton representing the Factory itself

class ImageFactory(object):
    instance = None
    
    # QMF schema for ImageFactory
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "ImageFactory")
    _build_image_method = SchemaMethod("image", desc="Build a new image")
    _build_image_method.addArgument(SchemaProperty("template", SCHEMA_DATA_STRING, direction=DIR_IN))
    _build_image_method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN))
    _build_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT))
    qmf_schema.addMethod(_build_image_method)
    _push_image_method = SchemaMethod("provider_image", desc="Push an image to a provider.")
    _push_image_method.addArgument(SchemaProperty("image_id", SCHEMA_DATA_STRING, direction=DIR_IN))
    _push_image_method.addArgument(SchemaProperty("provider", SCHEMA_DATA_STRING, direction=DIR_IN))
    _push_image_method.addArgument(SchemaProperty("credentials", SCHEMA_DATA_STRING, direction=DIR_IN))
    _push_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT))
    qmf_schema.addMethod(_push_image_method)
    
    ## Properties
    def qmf_object():
        doc = "The qmf_object property."
        def fget(self):
            return self._qmf_object
        def fset(self, value):
            self._qmf_object = value
        def fdel(self):
            del self._qmf_object
        return locals()
    qmf_object = property(**qmf_object())
    
    
    def __new__(cls, *p, **k):
    	if cls.instance is None:
    		cls.instance = object.__new__(cls, *p, **k)
    	return cls.instance
    
    def __init__(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
    	self.qmf_object = Data(ImageFactory.qmf_schema)
    	self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
    
    def image(self,template,target):
        template_object = Template(template)
        build_adaptor = BuildAdaptor.BuildAdaptor(template_object,target)
        build_adaptor.build_image()
        return build_adaptor
    
    def provider_image(self,image_id, provider, credentials):
        template_id, template = self.warehouse.template_for_image_id(image_id)
	self.log.debug("Got template id: %s and template: %s" % (repr(template_id), repr(template)))
        image_metadata = self.warehouse.metadata_for_id([ "target" ], image_id, "images")
        target = image_metadata["target"]

        if (template and target):
            build_adaptor = BuildAdaptor.BuildAdaptor(Template(template),target)
            build_adaptor.push_image(image_id, provider, credentials)
            return build_adaptor
        else:
            raise RuntimeError("Could not return build_adaptor!\nimage: %s\nimage_metadata: %s\ntemplate_id: %s\ntemplate: %s\n" % (image, image_metadata, template_id, template))
    
