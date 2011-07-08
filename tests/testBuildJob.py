#!/usr/bin/env python
# encoding: utf-8

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
from imagefactory import BuildJob
from imagefactory.builders import MockBuilder

class testBuildJob(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')

    def tearDown(self):
        pass

    def testInstantiateMockBuilder(self):
        template_xml = "<template><name>f14jeos</name><os><name>Fedora</name></os></template>"
        job = BuildJob.BuildJob(template_xml, "mock")
        self.assertIsInstance(job._builder, MockBuilder.MockBuilder)
        self.assertEqual(job.template.xml, template_xml)
        self.assertEqual(job.target, "mock")

if __name__ == '__main__':
    unittest.main()
