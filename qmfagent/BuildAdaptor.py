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
import libxml2
from builder import *
import logging

class BuildAdaptor(object):
    instances = []
    
    # QMF schema for BuildAdaptor
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "BuildAdaptor")
    qmf_schema.addProperty(SchemaProperty("descriptor", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("target", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("status", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT))
    qmf_schema.addProperty(SchemaProperty("finished_image", SCHEMA_DATA_STRING))
    qmf_schema.addMethod(SchemaMethod("abort_build", desc = "If possible, abort running build."))
    _states_method = SchemaMethod("build_states", desc = "Returns a representation of the build state transitions.")
    _states_method.addArgument(SchemaProperty("states", SCHEMA_DATA_MAP, direction=DIR_IN_OUT))
    qmf_schema.addMethod(_states_method)
    
    ### Properties
    def descriptor():
        doc = "The descriptor property."
        def fget(self):
            return self._descriptor
        def fset(self, value):
            self._descriptor = value
        def fdel(self):
            del self._descriptor
        return locals()
    descriptor = property(**descriptor())
    
    def target():
        doc = "The target property."
        def fget(self):
            return self._target
        def fset(self, value):
            self._target = value
        def fdel(self):
            del self._target
        return locals()
    target = property(**target())
    
    def status():
        doc = "The status property."
        def fget(self):
            return self._status
        def fset(self, value):
            self._status = value
        def fdel(self):
            del self._status
        return locals()
    status = property(**status())
    
    def percent_complete():
        doc = "The percent_complete property."
        def fget(self):
            return self._percent_complete
        def fset(self, value):
            self._percent_complete = value
        def fdel(self):
            del self._percent_complete
        return locals()
    percent_complete = property(**percent_complete())
    
    def finished_image():
        doc = "The finished_image property."
        def fget(self):
            return self._finished_image
        def fset(self, value):
            self._finished_image = value
        def fdel(self):
            del self._finished_image
        return locals()
    finished_image = property(**finished_image())
    
    
    def __init__(self, descriptor, target, image_uuid, sec_credentials):
        super(BuildAdaptor, self).__init__()
        
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        
        self.descriptor = descriptor
        self.target = target
        self.status = "created"
        self.percent_complete = 0
        self.finished_image = ""
        self.image_uuid = image_uuid
        self.sec_credentials = sec_credentials
        self.builder = None
        
        self.qmf_object = Data(BuildAdaptor.qmf_schema)
        self.qmf_object.descriptor = self.descriptor
        self.qmf_object.target = self.target
        self.qmf_object.status = self.status
        self.qmf_object.percent_complete = self.percent_complete
        self.qmf_object.finished_image = self.finished_image
        
        builder_class = None
        if self.target == "mock": # If target is mock always run mock builder regardless of descriptor
            builder_class = MockBuilder.MockBuilder
        else: # otherwise, use the node value found in <os><name>ExampleOS</name></os> of the tdl
            parsed_doc = libxml2.parseDoc(descriptor)
            os_name_node = parsed_doc.xpathEval('/template/os/name')
            os_name = os_name_node[0].getContent()
			class_name = os_name + "Builder"
			try:
				builder_class = getattr(os_name, os_name)
			except Exception, e:
				self.log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e.message, os_name)
				builder_class = MockBuilder.MockBuilder
		
        self.builder = self._builder_class(descriptor, target, image_uuid, sec_credentials)
        # Register as a delegate to the builder
        self.builder.delegate = self
        
        # Create instance lock to protect during status updates
        self._builder_thread_lock = Lock()
        # Run build() in a new thread
        self._builder_thread = Thread(target = self.builder)
        self._builder_thread.start()
        
        # Add to list of instances
        BuildAdaptor.instances.append(self)
    
    # Builder delegat methods
    def builder_did_update_status(self, builder, old_status, new_status):
        # Currently the lone delegate function
        # This indicates that the underlying builder has had a status change
        # For now we just copy back the status
        self.status = self._builder.status
        self.percent_complete = self._builder.percent_complete
        self.completed_image = self._builder.image
        # TODO: Fire events if the status change is significant
    


# if __name__ == '__main__':
# 	unittest.main()