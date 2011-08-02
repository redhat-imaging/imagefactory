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
from imgfac.qmfagent.BuildAdaptor import BuildAdaptor

class TestBuildAdaptor(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')

    def tearDown(self):
        pass

    def testQMFSchemaDefinition(self):
        expected_schema_properties = ("image", "build", "status", "percent_complete", "image_id")
        expected_schema_methods = dict(abort=(), instance_states=("class_name", "states"))
        for schema_property in BuildAdaptor.qmf_schema.getProperties():
            self.assertIn(schema_property.getName(), expected_schema_properties)
        for schema_method in BuildAdaptor.qmf_schema.getMethods():
            self.assertIn(schema_method.getName(), expected_schema_methods)
            arguments = expected_schema_methods[schema_method.getName()]
            for schema_property in schema_method.getArguments():
                self.assertIn(schema_property.getName(), arguments)

if __name__ == '__main__':
	unittest.main()
