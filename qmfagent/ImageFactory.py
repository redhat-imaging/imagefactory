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
from BuildAdaptor import BuildAdaptor

# Singleton representing the Factory itself

class ImageFactory(object):
	instance = None
    
    # QMF schema for ImageFactory
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "ImageFactory")
	_method = SchemaMethod("build_image", {"desc":"Build a new image"})
	_method.addArgument(SchemaProperty("descriptor", SCHEMA_DATA_STRING, direction=DIR_IN))
	_method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN))
	_method.addArgument(SchemaProperty("image_uuid", SCHEMA_DATA_STRING, direction=DIR_IN))
	_method.addArgument(SchemaProperty("sec_credentials", SCHEMA_DATA_STRING, direction=DIR_IN))
	_method.addArgument(SchemaProperty("build", SCHEMA_DATA_MAP, direction=DIR_OUT))
	qmf_schema.addMethod(_method)
	
	def __new__(cls):
		if cls.instance is None:
			cls.instance = cls.__new__(cls)
		return cls.instance
    
	def __init__(self): # TODO: sloranz@redhat.com - make sure this is compatible with qmfv2 api
		self.qmf_object = Data(ImageFactory.qmf_schema)
		_oid = self.qmf_agent.alloc_object_id()
		self.qmf_object.set_object_id(_oid)
	
	def build_image(self,descriptor,target,image_uuid,sec_credentials,qmf_agent):
		return BuildAdaptor(descriptor,target,image_uuid,sec_credentials,qmf_agent)
	
