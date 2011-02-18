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
import logging
import time
import cqpid
from qmf2 import *
from qmfagent.ImageFactoryAgent import ImageFactoryAgent


class TestImageFactoryAgent(unittest.TestCase):
    def setUp(self):
        # logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s')
        # FIXME: sloranz - only state changes from building on will raise events until qmf_object.getAgent() works as expected
        # self.expected_state_transitions = (("NEW","INITIALIZING"),("INITIALIZING","BUILDING"),("BUILDING","FINISHING"),("FINISHING","COMPLETED"))
        self.expected_state_transitions = (("INITIALIZING","BUILDING"),("BUILDING","FINISHING"),("FINISHING","COMPLETED"))
        self.if_agent = ImageFactoryAgent("localhost")
        self.if_agent.start()
        self.connection = cqpid.Connection("localhost")
        self.connection.open()
        self.console_session = ConsoleSession(self.connection)
        self.console_session.setAgentFilter("[and, [eq, _vendor, [quote, 'redhat.com']], [eq, _product, [quote, 'imagefactory']]]")
        self.console_session.open()
        self.console = MockConsole(self.console_session)
        self.console.start()
        time.sleep(5) # Give the agent some time to show up. raise this value testQueries fails to find the agent.
    
    def tearDown(self):
        del self.expected_state_transitions
        self.console.cancel()
        del self.console
        self.console_session.close()
        self.connection.close()
        del self.console_session
        del self.connection
        self.if_agent.shutdown()
        del self.if_agent
    
    def testImageFactoryAgent(self):
        """Test agent registration, method calls, and events"""
        # test that the agent registered and consoles can see it.
        try:
            self.assertIsNotNone(self.console.agent)
        except AttributeError:
            self.fail("No imagefactory agent found...")
        
        # test that build_image returns what we expect
        try:
            self.assertIsNotNone(self.console.build_adaptor_addr_str)
        except AttributeError:
            self.fail("build_image did not return a DataAddr for build_adaptor...")
        
        # test that status changes in build adaptor create QMF events the consoles see.
        agent_name = self.console.agent.getName()
        self.assertGreater(self.console.event_count, 0)
        self.assertEqual(len(self.expected_state_transitions), len(self.console.status_events))
        for event in self.console.status_events:
            index = self.console.status_events.index(event)
            self.assertEqual(agent_name, event["agent"].getName())
            properties = event["data"].getProperties()
            self.assertIsNotNone(properties)
            self.assertEqual(self.console.build_adaptor_addr_str, properties["addr"])
            self.assertEqual(self.expected_state_transitions[index][0],properties["old_status"])
            self.assertEqual(self.expected_state_transitions[index][1],properties["new_status"])
    

class MockConsole(ConsoleHandler):
    def __init__(self, consoleSession):
        super(MockConsole, self).__init__(consoleSession)
        self.status_events = []
        self.event_count = 0
    
    def agentAdded(self, agent):
        self.agent = agent
        factories = agent.query("{class:ImageFactory, package:'com.redhat.imagefactory'}")
        response = factories[0].build_image("<template></template>", "mock")
        self.build_adaptor_addr_str = response["build_adaptor"]
    
    def agentDeleted(self, agent, reason):
        self.agent = None
        self.reason_for_missing_agent = reason
    
    def eventRaised(self, agent, data, timestamp, severity):
        if(data.getProperties()["event"] == "STATUS"):
            self.status_events.append(dict(agent=agent, data=data, timestamp=timestamp, severity=severity))
        self.event_count = self.event_count + 1
    


if __name__ == '__main__':
    unittest.main()