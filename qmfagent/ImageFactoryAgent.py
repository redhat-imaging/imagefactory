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
import ImageFactory
import BuildAdaptor

class ImageFactoryAgent(AgentHandler):
    
    # Declare a schema for a structured exception that can be used in failed method invocations.
    qmf_exception_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "exception")
    qmf_exception_schema.addProperty(SchemaProperty("exception", SCHEMA_DATA_STRING))
    qmf_exception_schema.addProperty(SchemaProperty("severity", SCHEMA_DATA_INT))
    qmf_exception_schema.addProperty(SchemaProperty("details", SCHEMA_DATA_MAP))
    
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
        self._managedObjects = {}
        self.session = None
        # Create and open a messaging connection to a broker.
        self.connection = cqpid.Connection(url)
        self.connection.open()
        # Create, configure, and open a QMFv2 agent session using the connection.
        self.session = AgentSession(self.connection)
        self.session.setDomain("com.redhat.imagefactory")
        self.session.setVendor("Red Hat, Inc.")
        self.session.setProduct("Image Factory")
        self.session.open()
        # Initialize the parent class with the session.
        AgentHandler.__init__(self, self.session)
        # Register our schemata with the agent session.
        self.session.registerSchema(ImageFactoryAgent.qmf_exception_schema)
        self.session.registerSchema(BuildAdaptor.qmf_schema)
    
    def shutdown(self):
        """
        Clean up the session and connection.
        """
        if self.session:
            self.session.close()
        self.connection.close()
    
    def method(self, handle, methodName, args, subtypes, addr, userId):
        """
        Handle incoming method calls.
        """
        if (methodName == "build_image"):
            #build_adaptor = 
            pass
    

# if __name__ == '__main__':
#     unittest.main()