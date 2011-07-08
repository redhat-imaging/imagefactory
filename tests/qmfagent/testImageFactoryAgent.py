#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import unittest
import logging
import time
import cqpid
from qmf2 import *
from imagefactory.qmfagent.ImageFactoryAgent import ImageFactoryAgent


class TestImageFactoryAgent(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        self.expected_state_transitions = (("NEW","INITIALIZING"),("INITIALIZING","PENDING"),("PENDING","FINISHING"),("FINISHING","COMPLETED"))
        self.if_agent = ImageFactoryAgent("localhost")
        self.if_agent.start()
        self.connection = cqpid.Connection("localhost")
        self.connection.open()
        self.console_session = ConsoleSession(self.connection)
        self.console_session.setAgentFilter("[and, [eq, _vendor, [quote, 'redhat.com']], [eq, _product, [quote, 'imagefactory']]]")
        self.console_session.open()
        self.console = MockConsole(self.console_session, self.if_agent.image_factory_addr)
        self.console.start()
        time.sleep(5) # Give the agent some time to show up.

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
        # test for the correct version of the qmf2 bindings
        self.assertTrue(hasattr(AgentSession(self.connection), "raiseEvent"))

        # test the build failure qmf event raised by BuildAdaptor
        self.assertEqual(len(self.console.test_failure_events), 1)
        self.assertEqual(len(self.console.real_failure_events), 0, "Unexpected failure events raised!\n%s" % (self.console.real_failure_events, ))
        self.assertEqual(self.console.build_adaptor_addr_fail, self.console.test_failure_events[0]["data"]["addr"])
        # test that exceptions are passed properly by the agent handler
        self.assertIsInstance(self.console.image_exception, Exception)
        self.assertEqual(str(self.console.image_exception), "Wrong number of arguments: expected 2, got 0")

        # test that the agent registered and consoles can see it.
        try:
            self.assertIsNotNone(self.console.agent)
        except AttributeError:
            self.fail("No imagefactory agent found...")

        # test that image returns what we expect
        try:
            self.assertIsNotNone(self.console.build_adaptor_addr_success)
        except AttributeError:
            self.fail("image did not return a DataAddr for build_adaptor...")

        # test that status changes in build adaptor create QMF events the consoles see.
        agent_name = self.console.agent.getName()
        self.assertEqual(len(self.expected_state_transitions), len(self.console.build_status_events))
        for event in self.console.build_status_events:
            index = self.console.build_status_events.index(event)
            self.assertEqual(agent_name, event["agent"].getName())
            properties = event["data"]
            self.assertIsNotNone(properties)
            self.assertEqual(self.console.build_adaptor_addr_success, properties["addr"])
            self.assertEqual(self.expected_state_transitions[index][0],properties["old_status"])
            self.assertEqual(self.expected_state_transitions[index][1],properties["new_status"])

        # test that provider_image returns what we expect
        try:
            self.assertIsNotNone(self.console.build_adaptor_addr_push)
        except AttributeError:
            self.fail("provider_image did not return a DataAddr for build_adaptor...")

        # test that status changes in build adaptor create QMF events the consoles see.
        self.assertGreater(len(self.console.push_status_events), 0)
        # self.assertEqual(len(self.expected_state_transitions), len(self.console.push_status_events))
        # for event in self.console.push_status_events:
        #     index = self.console.push_status_events.index(event)
        #     self.assertEqual(agent_name, event["agent"].getName())
        #     properties = event["data"].getProperties()
        #     self.assertIsNotNone(properties)
        #     self.assertEqual(self.console.build_adaptor_addr_push, properties["addr"])
        #     self.assertEqual(self.expected_state_transitions[index][0],properties["old_status"])
        #     self.assertEqual(self.expected_state_transitions[index][1],properties["new_status"])

        self.assertIsNotNone(self.console.import_image_ids)
        self.assertEqual(len(self.console.import_image_ids), 4)
        self.assertTrue('image' in self.console.import_image_ids)
        self.assertTrue('build' in self.console.import_image_ids)
        self.assertTrue('target_image' in self.console.import_image_ids)
        self.assertTrue('provider_image' in self.console.import_image_ids)

        # test instance_states method
        self.assertIsNotNone(self.console.image_factory_states)
        self.assertIsNotNone(self.console.build_adaptor_states)


class MockConsole(ConsoleHandler):
    def __init__(self, consoleSession, agent_addr):
        super(MockConsole, self).__init__(consoleSession)
        self.agent_addr = agent_addr
        self.build_adaptor_addr_success = ""
        self.build_adaptor_addr_fail = ""
        self.build_adaptor_addr_push = ""
        self.build_status_events = []
        self.push_status_events =[]
        self.import_image_ids = None
        self.test_failure_events = []
        self.real_failure_events = []
        self.event_count = 0

    def agentAdded(self, agent):
        if(str(self.agent_addr).startswith(agent.getName())):
            self.agent = agent
            self.factory = agent.query("{class:ImageFactory, package:'com.redhat.imagefactory'}")[0]
            self.build_adaptor_addr_success = self.factory.build_image("", "", "<template></template>", ["mock"])["build_adaptors"][0]
            self.build_adaptor_addr_fail = self.factory.build_image("", "", "<template>FAIL</template>", ["mock"])["build_adaptors"][0]

            self.image_factory_states = self.factory.instance_states("ImageFactory")
            self.build_adaptor_states = self.factory.instance_states("BuildAdaptor")

            try:
                self.image_exception = self.factory.image()
            except Exception, e:
                self.image_exception = e

    def agentDeleted(self, agent, reason):
        self.agent = None
        self.reason_for_missing_agent = reason
        print("Uh... the agent was delete because: %s" % (reason, ))

    def eventRaised(self, agent, data, timestamp, severity):
        if(data.getProperties()["event"] == "STATUS"):
            if(data.getProperties()["addr"] == self.build_adaptor_addr_success):
                self.build_status_events.append(dict(agent=agent, data=data.getProperties(), timestamp=timestamp, severity=severity))
                if(data.getProperties()["new_status"] == "COMPLETED"):
                    time.sleep(2)
                    ba = self.agent.query(Query(DataAddr(self.build_adaptor_addr_success)))[0]
                    self.build_adaptor_addr_push = self.factory.push_image(ba.image, ba.build, ["mock-provider1"], "None")["build_adaptors"][0]
            elif(data.getProperties()["addr"] == self.build_adaptor_addr_push):
                self.push_status_events.append(dict(agent=agent, data=data.getProperties(), timestamp=timestamp, severity=severity))
                if(data.getProperties()["new_status"] == "COMPLETED"):
                    time.sleep(1)
                    ba = self.agent.query(Query(DataAddr(self.build_adaptor_addr_push)))[0]
                    self.import_image_ids = self.factory.import_image(ba.image, ba.build, "mock-img-id", "<image><name>Mock Image</name></image>", "mock", "mock-provider2")
        elif(data.getProperties()["event"] == "FAILURE"):
            if(data.getProperties()["addr"] == self.build_adaptor_addr_fail):
                self.test_failure_events.append(dict(agent=agent, data=data.getProperties(), timestamp=timestamp, severity=severity))
            else:
                self.real_failure_events.append(dict(agent=agent, data=data.getProperties(), timestamp=timestamp, severity=severity))

        self.event_count = self.event_count + 1


if __name__ == '__main__':
    unittest.main()
