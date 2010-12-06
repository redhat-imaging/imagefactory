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

import qmf
import Build

# Singleton representing the Factory itself

class ImageFactory():
	_instance = None
	
    # ******* ImageFactory
    qmf_schema = qmf.SchemaObjectClass("com.redhat.imagefactory", "ImageFactory")
	
    _method = qmf.SchemaMethod("build_image", {"desc":"Build a new image"})
    _method.add_argument(qmf.SchemaArgument("descriptor", qmf.TYPE_LSTR, {"dir":qmf.DIR_IN}))
    _method.add_argument(qmf.SchemaArgument("target", qmf.TYPE_SSTR, {"dir":qmf.DIR_IN}))
    _method.add_argument(qmf.SchemaArgument("image_uuid", qmf.TYPE_SSTR, {"dir":qmf.DIR_IN}))
    _method.add_argument(qmf.SchemaArgument("sec_credentials", qmf.TYPE_LSTR, {"dir":qmf.DIR_IN}))
    _method.add_argument(qmf.SchemaArgument("build", qmf.TYPE_REF, {"dir":qmf.DIR_OUT}))
    qmf_schema.add_method(_method)
	
    qmf_agent = None
	
	def __new__(cls):
		if cls._instance is None:
			cls._instance = cls.__new__(cls)
		return cls._instance
	
    def __init__(self):
        self.qmf_object = qmf.AgentObject(self.qmf_schema)
        _oid = self.qmf_agent.alloc_object_id()
        self.qmf_object.set_object_id(_oid)
	
    def build_image(self,descriptor,target,image_uuid,sec_credentials):
        return Build.BuildAdaptor(descriptor,target,image_uuid,sec_credentials)
	
