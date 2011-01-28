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

import unittest
import time
import cqpid
from qmf2 import *
from qmfagent.ImageFactoryAgent import ImageFactoryAgent


class TestImageFactoryAgent(unittest.TestCase):
    def setUp(self):
        # self.factory_agent = ImageFactoryAgent("localhost")
        # self.factory_agent.run()
        self.connection = cqpid.Connection("localhost")
        self.session = ConsoleSession(self.connection)
        self.connection.open()
        self.session.open()
        self.agents = self.session.getAgents()
    
    def tearDown(self):
        self.agents = None
        self.session.close()
        self.connection.close()
        self.session = None
        self.connection = None
        # self.factory_agent.shutdown()
        # self.factory_agent = None
    
    def testQueries(self):
        for agent in self.agents:
            if agent.getName().startswith("redhat.com:imagefactory:"):
                # test to see that we can get an ImageFactory
                factories = agent.query("{class:ImageFactory, package:'com.redhat.imagefactory'}")
                factory_count = len(factories)
                self.assertEqual(1, factory_count, "Expected to get one(1) factory from the agent, recieved %d..." % (factory_count, ))
                # test to see that we can get a BuildAdaptor for the mock target
                response = factories[0].build_image("<template></template>", "mock", "foo", "bar")
                build_adaptor_addr = DataAddr(response["build_adaptor"])
                self.assertIsNotNone(build_adaptor_addr)
                query = Query(build_adaptor_addr)
                builds = agent.query(query)
                self.assertEqual(1, len(builds))
                self.assertIsNotNone(builds[0].status)
    

if __name__ == '__main__':
    unittest.main()