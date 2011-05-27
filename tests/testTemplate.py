#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2010-2011 Red Hat, Inc.
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
from imagefactory.Template import Template
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.builders.MockBuilder import MockBuilder


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
        self.assertIsNone(template.url)

    def testTemplateFramImageID(self):
        template_id = self.warehouse.store_template(self.template_xml)
        template = Template(template_id)
        target = "mock"
        builder = MockBuilder(self.template_xml, target)
        builder.build_image()
        metadata = dict(template=template_id, target=target, icicle="None", target_parameters="None")
        self.warehouse.store_image(builder.image_id, builder.image, metadata=metadata)
        image_template = Template(builder.image_id)
        self.assertEqual(template_id, image_template.identifier)
        self.assertEqual(self.template_xml, image_template.xml)
        self.assertIsNone(template.url)

    def testTemplateFromXML(self):
        template = Template(self.template_xml)
        self.assertEqual(self.template_xml, template.xml)
        self.assertIsNone(template.identifier)
        self.assertIsNone(template.url)

    def testTemplateFromURL(self):
        template_id = self.warehouse.store_template(self.template_xml)
        template_url = "%s/%s/%s" % (self.warehouse.url, self.warehouse.template_bucket, template_id)
        template = Template(template_url)
        self.assertEqual(template_url, template.url)
        self.assertEqual(template_id, template.identifier)
        self.assertEqual(self.template_xml, template.xml)

    def testTemplateStringRepresentation(self):
        template = Template(self.template_xml)
        self.assertEqual(self.template_xml, repr(template))
        self.assertEqual(self.template_xml, str(template))
        self.assertEqual(self.template_xml, "%r" % (template, ))
        self.assertEqual(self.template_xml, "%s" % (template, ))


if __name__ == '__main__':
    unittest.main()
