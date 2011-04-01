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

import logging
import uuid
import cqpid
from qmf2 import *
from ImageFactory import ImageFactory
from BuildAdaptor import BuildAdaptor

class ImageFactoryAgent(AgentHandler):
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
    
    def managedObjects():
        doc = "The managedObjects property."
        def fget(self):
            return self._managedObjects
        # def fset(self, value):
        #     self._managedObjects = value
        # def fdel(self):
        #     del self._managedObjects
        return locals()
    managedObjects = property(**managedObjects())
    
    
    def __init__(self, url):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self._managedObjects = {}
        self.session = None
        # create a connection and connect to qpidd
        # TODO: (redmine 277) - Make this use actual amqp:// urls... currently, only host works
        self.connection = cqpid.Connection(url, "{reconnect:True}")
        self.connection.open()
        # Create, configure, and open a QMFv2 agent session using the connection.
        self.session = AgentSession(self.connection)
        self.session.setVendor("redhat.com")
        self.session.setProduct("imagefactory")
        self.session.open()
        # Initialize the parent class with the session.
        AgentHandler.__init__(self, self.session)
        # Register our schemata with the agent session.
        self.session.registerSchema(ImageFactory.qmf_schema)
        self.session.registerSchema(BuildAdaptor.qmf_schema)
        self.session.registerSchema(BuildAdaptor.qmf_event_schema_status)
        self.session.registerSchema(BuildAdaptor.qmf_event_schema_percentage)
        self.session.registerSchema(BuildAdaptor.qmf_event_schema_build_failed)
        # Now add the image factory object
        self.image_factory = ImageFactory(agent=self)
        self.image_factory_addr = self.session.addData(self.image_factory.qmf_object, "image_factory")
        self.log.info("image_factory has qmf/qpid address: %s", self.image_factory_addr)
    
    ## AgentHandler override
    def method(self, handle, methodName, args, subtypes, addr, userId):
        """
        Handle incoming method calls.
        """
        self.log.debug("Method called: name = %s \n args = %s \n handle = %s \n addr = %s \n subtypes = %s \n userId = %s", methodName, args, handle, addr, subtypes, userId)
        
        try:
            
            if (addr == self.image_factory_addr):
                target_obj = self.image_factory
            elif (repr(addr) in self.managedObjects):
                target_obj = self.managedObjects[repr(addr)]
            else:
                raise RuntimeError("%s does not match an object managed by ImageFactoryAgent!  Unable to respond to %s." % (repr(addr), methodName))
            
            result = getattr(target_obj, methodName)(**args)
            
            if ((addr == self.image_factory_addr) and (methodName in ("image", "provider_image"))):
                build_adaptor_instance_name = "build_adaptor:%s:%s" %  (methodName, result.builder.image_id)
                qmf_object_addr = self.session.addData(result.qmf_object, build_adaptor_instance_name, persistent=True)
                self.managedObjects[repr(qmf_object_addr)] = result
                handle.addReturnArgument("build_adaptor", qmf_object_addr.asMap())
                self.session.methodSuccess(handle)
            elif(result and isinstance(result, dict)):
                for key in result:
                    handle.addReturnArgument(key, result[key])
                self.session.methodSuccess(handle)
            else:
                returned_dictionary = {}
                for method in type(target_obj).qmf_schema.getMethods():
                    if (method.getName() == methodName):
                        for method_arg in method.getArguments():
                            if (method_arg.getDirection() == DIR_OUT):
                                returned_dictionary.update({method_arg.getName() : method_arg.getDesc()})
                raise RuntimeError("Method '%s' on objects of class %s must return a dictionary of %s" % (methodName, target_obj.__class__.__name__, returned_dictionary))
        except Exception, e:
            self.log.exception(str(e))
            self.session.raiseException(handle, str(e))
    
    def shutdown(self):
        """
        Clean up the session and connection. Cancel the running thread.
        """
        try:
            self.session.close()
            self.connection.close()
            self.cancel()
            return True
        except Exception, e:
            self.log.exception(e)
            return False
    
    def deregister(self, managed_object):
        """
        Remove an item from the agents collection of managed objects.
        """
        managed_object_key = None
        if(managed_object.__class__ == Data):
            managed_object_key = repr(managed_object.getAddr())
        elif(managed_object.__class__ == DataAddr):
            managed_object_key = repr(managed_object)
        elif(managed_object.__class__ == str):
            managed_object_key = managed_object
        
        try:
            del self.managedObjects[managed_object_key]
        except KeyError:
            self.log.error("Trying to remove object (%s) from managedObjects that does not exist..." % (managed_object_key, ))
    
