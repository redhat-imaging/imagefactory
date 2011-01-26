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
import builder
from builder import *
import logging
from threading import Thread, Lock

class BuildAdaptor(object):
    
    # QMF schema for BuildAdaptor
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "BuildAdaptor")
    qmf_schema.addProperty(SchemaProperty("descriptor", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("target", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("status", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT))
    qmf_schema.addProperty(SchemaProperty("finished_image", SCHEMA_DATA_STRING))
    # TODO: sloranz@redhat.com - these need to be implemented or removed!!!
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
            self.qmf_object.descriptor = value
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
            self.qmf_object.target = value
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
            self.qmf_object.status = value
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
            self.qmf_object.percent_complete = value
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
            self.qmf_object.finished_image = value
        def fdel(self):
            del self._finished_image
        return locals()
    finished_image = property(**finished_image())
    
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
    
    def __init__(self, descriptor, target, image_uuid, sec_credentials):
        super(BuildAdaptor, self).__init__()
        
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.qmf_object = Data(BuildAdaptor.qmf_schema)
        
        self.descriptor = descriptor
        self.target = target
        self.status = "created"
        self.percent_complete = 0
        self.finished_image = ""
        self.image_uuid = image_uuid
        self.sec_credentials = sec_credentials
        self.builder = None
        
        builder_class = builder.MockBuilder.MockBuilder
        if (self.target != "mock"): # If target is mock always run mock builder regardless of descriptor
            parsed_doc = libxml2.parseDoc(descriptor)
            node = parsed_doc.xpathEval('/template/os/name')
            os_name = node[0].content
            class_name = "%sBuilder" % (os_name, )
            try:
                builder_module = getattr(builder, class_name)
                builder_class = getattr(builder_module, class_name)
            except AttributeError, e:
                self.log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e, os_name)
		
        self.builder = builder_class(descriptor, target, image_uuid, sec_credentials)
        # Register as a delegate to the builder
        self.builder.delegate = self
        
        # Create instance lock to protect during status updates
        self._builder_thread_lock = Lock()
        # Run build() in a new thread
        self._builder_thread = Thread(target = self.builder)
        self._builder_thread.start()
    
    # Builder delegat methods
    def builder_did_update_status(self, builder, old_status, new_status):
        # Currently the lone delegate function
        # This indicates that the underlying builder has had a status change
        # For now we just copy back the status
        self.status = new_status
        self.percent_complete = builder.percent_complete
        # TODO: sloranz@redhat.com - check for 100% or COMPLETED status before setting this
        # self.completed_image = builder.image
        # TODO: Fire events if the status change is significant
    


# if __name__ == '__main__':
# 	unittest.main()