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
from imagefactory.Template import Template
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.ApplicationConfiguration import ApplicationConfiguration


class testTemplate(unittest.TestCase):
    def setUp(self):
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
        self.template_xml = "<template>This is a test template.  There is not much to it.</template>"
        self.template_bucket = "unittests_templates"
    
    def tearDown(self):
        del self.warehouse
        del self.template_xml
    
    def testTemplateFromUUID(self):
        template_id = self.warehouse.store_template(self.template_xml, bucket=self.template_bucket)
        template = Template(template_id, bucket=self.template_bucket)
        self.assertEqual(template_id, template.identifier)
        self.assertEqual(self.template_xml, template.xml)
        self.assertIsNone(template.url)
    
    def testTemplateFromXML(self):
        template = Template(self.template_xml)
        self.assertEqual(self.template_xml, template.xml)
        self.assertIsNone(template.identifier)
        self.assertIsNone(template.url)
    
    def testTemplateFromURL(self):
        template_id = self.warehouse.store_template(self.template_xml, bucket=self.template_bucket)
        template_url = "%s/%s/%s" % (self.warehouse.url, self.template_bucket, template_id)
        template = Template(template_url)
        self.assertEqual(template_url, template.url)
        self.assertEqual(template_id, template.identifier)
        self.assertEqual(self.template_xml, template.xml)
    

if __name__ == '__main__':
    unittest.main()