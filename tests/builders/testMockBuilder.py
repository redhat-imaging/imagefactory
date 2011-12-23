#
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
import zope
import os.path
from imgfac.builders.IBuilder import IBuilder
from imgfac.builders.Mock_Builder import Mock_Builder
from imgfac.Template import Template


class TestMockBuilder(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        self.template = Template("<template></template>")
        self.target = "mock"
        self.builder = Mock_Builder(self.template, self.target)

    def tearDown(self):
        del self.builder
        del self.template
        del self.target

    def testImplementsIBuilder(self):
        self.assert_(IBuilder.implementedBy(Mock_Builder), 'Mock_Builder does not implement the ImageBuilder interface...')

    def testInit(self):
        self.assertEqual(self.builder.template, self.template)
        self.assertEqual(self.builder.target, self.target)

    def testBuildImage(self):
        self.builder.build_image()
        self.assertEqual(self.builder.status, "COMPLETED")
        self.assert_(os.path.exists(self.builder.image))



if __name__ == '__main__':
    unittest.main()
