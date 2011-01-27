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

import logging
import cqpid
from qmf2 import *
from ImageFactory import *
from BuildAdaptor import *
import uuid

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
        # Create and open a messaging connection to a broker.
        # FIXME: sloranz@redhat.com - Make this use actual amqp:// urls... currently, only host works
        self.connection = cqpid.Connection(url)
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
        # Now add the image factory object
        self.image_factory = ImageFactory()
        self.image_factory_addr = self.session.addData(self.image_factory.qmf_object, "image_factory")
        self.log.info("image_factory has qmf/qpid address: %s", self.image_factory_addr)
    
    ## AgentHandler override
    def method(self, handle, methodName, args, subtypes, addr, userId):
        """
        Handle incoming method calls.
        """
        self.log.debug("Method called: name = %s \n args = %s \n handle = %s \n addr = %s \n subtypes = %s \n userId = %s", methodName, args, handle, addr, subtypes, userId)
        if (methodName == "build_image"):
            try:
                build_adaptor = self.image_factory.build_image(args["descriptor"],args["target"],args["image_uuid"],args["sec_credentials"])
                build_adaptor_instance_name = "build_adaptor-%s" %  (uuid.uuid4(), )
                qmf_object_addr = self.session.addData(build_adaptor.qmf_object, build_adaptor_instance_name)
                # TODO: sloranz@redhat.com - This dictionary could get large over time, think about when to prune it...
                self.managedObjects[repr(qmf_object_addr)] = build_adaptor
                handle.addReturnArgument("build_adaptor", qmf_object_addr.asMap())
                self.session.methodSuccess(handle)
            except Exception, e:
                self.log.exception(e)
                self.session.raiseException(handle, e.message)
        else:
            errorMsg = "Method (%s) not implemented!!!" % (methodName, )
            self.log.warning(errorMsg)
            self.session.raiseException(handle, errorMsg)
    
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
    
    


# if __name__ == '__main__':
#     unittest.main()