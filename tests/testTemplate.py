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

import os
import unittest
import logging
import tempfile
from imgfac.Template import Template
from imgfac.ImageWarehouse import ImageWarehouse
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.builders.Mock_Builder import Mock_Builder


class testTemplate(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
        self.template_xml = "<template>This is a test template.  There is not much to it.</template>"

    def tearDown(self):
        del self.warehouse
        del self.template_xml

    def testTemplateFromUUID(self):
        template_id = self.warehouse.store_template(self.template_xml)
        template = Template(template_id)
        self.assertEqual(template_id, template.identifier)
        self.assertEqual(self.template_xml, template.xml)
        self.assertFalse(template.url)

    def testTemplateFromImageID(self):
        template_id = self.warehouse.store_template(self.template_xml)
        template = Template(template_id)
        target = "mock"
        builder = Mock_Builder(self.template_xml, target)
        builder.build_image()
        metadata = dict(template=template_id, target=target, icicle="None", target_parameters="None")
        self.warehouse.store_target_image(builder.new_image_id, builder.image, metadata=metadata)
        image_template = Template(builder.new_image_id)
        self.assertEqual(template_id, image_template.identifier)
        self.assertEqual(self.template_xml, image_template.xml)
        self.assertFalse(template.url)

    def testTemplateFromXML(self):
        template = Template(self.template_xml)
        self.assertEqual(self.template_xml, template.xml)
        self.assertFalse(template.identifier)
        self.assertFalse(template.url)

    def testTemplateFromURL(self):
        template_id = self.warehouse.store_template(self.template_xml)
        template_url = "%s/%s/%s" % (self.warehouse.url, self.warehouse.template_bucket, template_id)
        template = Template(template_url)
        self.assertEqual(template_url, template.url)
        self.assertEqual(template_id, template.identifier)
        self.assertEqual(self.template_xml, template.xml)

    def testTemplateFromPath(self):
        (fd, template_path) = tempfile.mkstemp(prefix = "test_image_factory-")
        os.write(fd, self.template_xml)
        os.close(fd)

        template = Template(template_path)
        self.assertFalse(template.url)
        self.assertFalse(template.identifier)
        self.assertEqual(self.template_xml, template.xml)

        os.remove(template_path)

    def testTemplateStringRepresentation(self):
        template = Template(self.template_xml)
        self.assertEqual(self.template_xml, repr(template))
        self.assertEqual(self.template_xml, str(template))
        self.assertEqual(self.template_xml, "%r" % (template, ))
        self.assertEqual(self.template_xml, "%s" % (template, ))


if __name__ == '__main__':
    unittest.main()
