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
from imagefactory.builders import *
from imagefactory.qmfagent.ImageFactory import ImageFactory

class TestImageFactory(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        pass

    def tearDown(self):
        pass

    def testQMFSchemaDefinition(self):
        expected_schema_methods = dict(image=("template", "target", "build_adaptor"),
                                       build_image=("image", "build", "template", "targets", "build_adaptors"),
                                       provider_image=("image_id", "provider", "credentials", "build_adaptor"),
                                       push_image=("image", "build", "providers", "credentials", "build_adaptors"),
                                       import_image=("image", "build", "target_identifier", "image_desc", "target", "provider", "target_image", "provider_image"),
                                       instance_states=("class_name", "states"))
        for schema_method in ImageFactory.qmf_schema.getMethods():
            self.assertIn(schema_method.getName(), expected_schema_methods)
            arguments = expected_schema_methods[schema_method.getName()]
            for schema_property in schema_method.getArguments():
                self.assertIn(schema_property.getName(), arguments)

    def testSingleton(self):
        image_factory_one = ImageFactory()
        image_factory_two = ImageFactory()
        self.assertIs(image_factory_one, image_factory_two)
        del image_factory_one
        del image_factory_two

if __name__ == '__main__':
    unittest.main()
