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

# Build - QMF Class representing a build that is being built, has finished building
# or has failed to build
#
# BuildAdaptor - Internal class that keeps the QMF build class status up to date
#  while executing the actual build using a Builder worker class

import qmf
from threading import Thread, Lock
from basebuilder import *
from mockbuilder import *

class BuildAdaptor(object):

    # Array containing all instances of this class
    class_instances = []

    # Schema that is registerable with the QMF agent
    # Note that the exported class is simply called Build
    qmf_schema = qmf.SchemaObjectClass("com.redhat.imagefactory", "Build")
    qmf_schema.add_property(qmf.SchemaProperty("descriptor", qmf.TYPE_SSTR))
    qmf_schema.add_property(qmf.SchemaProperty("target", qmf.TYPE_SSTR))
    qmf_schema.add_property(qmf.SchemaProperty("status", qmf.TYPE_SSTR))
    qmf_schema.add_property(qmf.SchemaProperty("percent_complete", qmf.TYPE_UINT32))
    qmf_schema.add_property(qmf.SchemaProperty("finished_image", qmf.TYPE_SSTR))

    _method = qmf.SchemaMethod("abort_build", {"desc":"if possible abort running build"})
    qmf_schema.add_method(_method)

    _method = qmf.SchemaMethod("build_states", {"desc":"return a representation of the build state transitions"})
    _method.add_argument(qmf.SchemaArgument("states", qmf.TYPE_MAP, {"dir":qmf.DIR_OUT}))
    qmf_schema.add_method(_method)

    qmf_agent = None

    def __init__(self, descriptor, target, image_uuid, sec_credentials):

        # Create our QMF object
        _oid = self.qmf_agent.alloc_object_id()
        self.qmf_object = qmf.AgentObject(self.qmf_schema)
        self.qmf_object.set_object_id(_oid)

        # Set attributes from constructor args
        self._descriptor = descriptor
        self.qmf_object.set_attr("descriptor", descriptor)
        self._target = target
        self.qmf_object.set_attr("target", target)
 
          
        # Set attributes representing initial status
        self._status = "created"
        self.qmf_object.set_attr("status", self._status)
 
        self._percent_complete = 0
        self.qmf_object.set_attr("percent_complete", self._percent_complete)
 
        self._finished_image = ""
        self.qmf_object.set_attr("finished_image", self._finished_image)

        # Set semi-private attributes from constructor
        # These are not visible via QMF and thus not described below
        self._image_uuid = image_uuid
        self._sec_credentials = sec_credentials

        # Instantiate the appropriate builder based on input descriptor and target
        self._builder_class = None

        # If target is mock always run mock builder regardless of descriptor
        if target == "mock":
            self._builder_class = MockBuilder

        # TODO: Else lookup in our dictionary
        
        # Instantiate builder if it exists
        if self._builder_class:
            self._builder = self._builder_class(descriptor, target, image_uuid, sec_credentials)
        # TODO: Else set status to failed and pass along a no_builder_found error

        # Register as a delegate 
        self._builder.delegate = self

        # Create instance lock to protect during status updates
        self._builder_thread_lock = Lock()

        # Run build() in a new thread
        self._builder_thread = Thread(target = self._builder)
        self._builder_thread.start()

        # Add to list of instances
        BuildAdaptor.class_instances.append(self)


    @classmethod
    def find_by_qmf_id(cls, qmf_oid): 
        # Loop through object array - if OID matches, return QMF AgentObject
        for _instance in BuildAdaptor.class_instances:
            if _instance.qmf_object.object_id() == qmf_oid:
                return _instance 

    def builder_did_update_status(self, builder, old_status, new_status):
        # Currently the lone delegate function
        # This indicates that the underlying builder has had a status change
        # For now we just copy back the status
        self.status = self._builder.status
        self.percent_complete = self._builder.percent_complete
        self.completed_image = self._builder.image
        # TODO: Fire events if the status change is significant

    #def abort_build(self): pass
    #def build_states(self): pass

    ### Whole bunch of properties
    @property
    def descriptor(self):
        """Descriptor for the image being built - aka TDL"""
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value):
        self._descriptor = value
        self.qmf_object.set_attr("descriptor", value)

    @property
    def target(self):
        """Target back end for image being built"""
        return self._target

    @target.setter
    def target(self, value):
        self._target = value
        self.qmf_object.set_attr("target", value)


    def status():
        doc = "status of build"  # use doc rather than fdoc
        def fget(self):
            return self._status
        def fset(self, value):
            self._status = value
            self.qmf_object.set_attr("status", value)
        return locals()  # returns a dictionary
    status = property(**status())  # pass in as keyword args

    def percent_complete():
        doc = "perecent of build complete"  # use doc rather than fdoc
        def fget(self):
            return self._percent_complete
        def fset(self, value):
            self._percent_complete = value
            self.qmf_object.set_attr("percent_complete", value)
        return locals()  # returns a dictionary
    percent_complete = property(**percent_complete())  # pass in as keyword args

    @property
    def finished_image(self):
        """URL representing location of finished image"""
        return self._finished_image

    @finished_image.setter
    def finished_image(self, value):
        self._finished_image = value
        self.qmf_object.set_attr("finished_image", value)


