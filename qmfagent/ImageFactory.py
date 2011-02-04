#
# Copyright (C) 2010 Red Hat, Inc.
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
from ApplicationConfiguration import ApplicationConfiguration

# Singleton representing the Factory itself

class ImageFactory(object):
    instance = None
    
    # QMF schema for ImageFactory
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "ImageFactory")
    _build_image_method = SchemaMethod("build_image", desc="Build a new image")
    _build_image_method.addArgument(SchemaProperty("template", SCHEMA_DATA_STRING, direction=DIR_IN))
    _build_image_method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN))
    _build_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT))
    qmf_schema.addMethod(_build_image_method)
    _push_image_method = SchemaMethod("push_image", desc="Push an image to a provider.")
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
    	self.qmf_object = Data(ImageFactory.qmf_schema)
    
    def build_image(self,template,target):
        build_adaptor = BuildAdaptor.BuildAdaptor(template,target)
        build_adaptor.build_image()
        return build_adaptor
    
    def push_image(self,image_id, provider, credentials):
        base_url = ApplicationConfiguration().configuration['warehouse']
        if (base_url):
            http = httplib2.Http()
            headers_response_template, template = http.request("%s/%s/template" % (base_url, image_id), "GET")
            headers_response_target, target = http.request("%s/%s/target" % (base_url, image_id), "GET")
            if (template and target):
                build_adaptor = BuildAdaptor.BuildAdaptor(template,target)
                build_adaptor.push_image(image_id, provider, credentials)
                return build_adaptor
            else:
                raise RuntimeError("Could not retrieve template (%s) or target (%s) from %s/%s" % (template, target, base_url, image_id))
        else:
            raise RuntimeError("No image warehouse found!")
    
