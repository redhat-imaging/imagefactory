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

import libxml2
import logging
import cqpid
from qmf2 import *
from threading import Thread, Lock
import zope
import builders
from builders import *

class BuildAdaptor(object):
    # QMF schema for BuildAdaptor
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "BuildAdaptor")
    qmf_schema.addProperty(SchemaProperty("status", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT))
    qmf_schema.addProperty(SchemaProperty("image", SCHEMA_DATA_STRING))
    qmf_schema.addMethod(SchemaMethod("abort", desc = "If possible, abort running build."))
    # TODO: (redmine 256) - build_states needs to be implemented...
    # _states_method = SchemaMethod("build_states", desc = "Returns a representation of the build state transitions.")
    # _states_method.addArgument(SchemaProperty("states", SCHEMA_DATA_MAP, direction=DIR_IN_OUT))
    # qmf_schema.addMethod(_states_method)
    
    #QMF schema for status change event
    qmf_event_schema_status = Schema(SCHEMA_TYPE_EVENT, "com.redhat.imagefactory", "BuildAdaptorStatusEvent")
    qmf_event_schema_status.addProperty(SchemaProperty("addr", SCHEMA_DATA_MAP))
    qmf_event_schema_status.addProperty(SchemaProperty("event", SCHEMA_DATA_STRING))
    qmf_event_schema_status.addProperty(SchemaProperty("new_status", SCHEMA_DATA_STRING))
    qmf_event_schema_status.addProperty(SchemaProperty("old_status", SCHEMA_DATA_STRING))
    #QMF schema for change to percent_complete event
    qmf_event_schema_percentage = Schema(SCHEMA_TYPE_EVENT, "com.redhat.imagefactory", "BuildAdaptorPercentCompleteEvent")
    qmf_event_schema_percentage.addProperty(SchemaProperty("addr", SCHEMA_DATA_MAP))
    qmf_event_schema_percentage.addProperty(SchemaProperty("event", SCHEMA_DATA_STRING))
    qmf_event_schema_percentage.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT))
    
    ### Properties
    def template():
        doc = "The template property."
        def fget(self):
            return self._template
        def fset(self, value):
            self._template = value
        def fdel(self):
            del self._template
        return locals()
    template = property(**template())
    
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
    
    def image():
        doc = "The image property."
        def fget(self):
            return self._image
        def fset(self, value):
            self._image = value
            self.qmf_object.image = value
        def fdel(self):
            del self._image
        return locals()
    image = property(**image())
    
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
    
    def __init__(self, template, target):
        super(BuildAdaptor, self).__init__()
        
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.qmf_object = Data(BuildAdaptor.qmf_schema)
        # FIXME: sloranz - I should be able to get the agent from the qmf_object this is a workaround...
        self.agent = None 
        
        self.template = template
        self.target = target
        self.status = "None"
        self.percent_complete = 0
        self.image = "None"
        self.builder = None
        
        builder_class = builders.MockBuilder.MockBuilder
        if (self.target != "mock"): # If target is mock always run mock builder regardless of template
            parsed_doc = libxml2.parseDoc(template)
            node = parsed_doc.xpathEval('/template/os/name')
            os_name = node[0].content
            class_name = "%sBuilder" % (os_name, )
            try:
                builder_module = getattr(builders, class_name)
                builder_class = getattr(builder_module, class_name)
            except AttributeError, e:
                self.log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e, os_name)
		
        self.builder = builder_class(template, target)
        # Register as a delegate to the builder
        self.builder.delegate = self
        self.image = str(self.builder.image_id)
    
    def build_image(self):
        thread_name = "%s.build_image()" % (self.builder.image_id, )
        # using args to pass the method we want to call on the target object.
        self._builder_thread = Thread(target = self.builder, name=thread_name, args=('build_image'))
        self._builder_thread.start()
    
    def push_image(self, image_id, provider, credentials):
        thread_name = "%s.push_image()" % (image_id, )
        # using args to pass the method we want to call on the target object.
        kwargs = dict(image_id=image_id, provider=provider, credentials=credentials)
        self._builder_thread = Thread(target = self.builder, name=thread_name, args=('push_image'), kwargs=kwargs)
        self._builder_thread.start()
    
    def abort(self):
        self.builder.abort()
    
    # Builder delegate methods
    def builder_did_update_status(self, builder, old_status, new_status):
        self.status = new_status
        # FIXME: sloranz - I should be able to get the agent from the qmf_object this is a workaround...
        agent = self.agent
        # agent = self.qmf_object.getAgent()
        self.log.debug("Raising event with agent (%s), changed status from %s to %s" % (agent, old_status, new_status))
        event = Data(BuildAdaptor.qmf_event_schema_status)
        event.addr = self.qmf_object.getAddr().asMap()
        event.event = "STATUS"
        event.new_status = str(new_status)
        event.old_status = str(old_status)
        agent.session.raiseEvent(data=event, severity=4)
        
        if(new_status == "COMPLETED"):
            agent.deregister(self.qmf_object)
        
    
    def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
        self.percent_complete = new_percentage
        # FIXME: sloranz - I should be able to get the agent from the qmf_object this is a workaround...
        agent = self.agent
        # agent = self.qmf_object.getAgent()
        self.log.debug("Raising event with agent (%s), changed percent complete from %s to %s" % (agent, original_percentage, new_percentage))
        event = Data(BuildAdaptor.qmf_event_schema_percentage)
        event.addr = self.qmf_object.getAddr().asMap()
        event.event = "PERCENTAGE"
        event.percent_complete = new_percentage
        agent.session.raiseEvent(data=event, severity=4)
    

# if __name__ == '__main__':
# 	unittest.main()