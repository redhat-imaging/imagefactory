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
from builders import *
from qmfagent.ImageFactory import ImageFactory

class TestImageFactory(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s')
        self.expected_schema_methods = {"build_image" : ("template", "target", "build_adaptor"), "push_image" : ("image_id", "provider", "credentials", "build_adaptor")}

    def tearDown(self):
        del self.expected_schema_methods
    
    def testQMFSchemaDefinition(self):
        for schema_method in ImageFactory.qmf_schema.getMethods():
            self.assertIn(schema_method.getName(), self.expected_schema_methods)
            arguments = self.expected_schema_methods[schema_method.getName()]
            for schema_property in schema_method.getArguments():
                self.assertIn(schema_property.getName(), arguments)
    
    def testSingleton(self):
        image_factory_one = ImageFactory()
        image_factory_two = ImageFactory()
        self.assertEqual(id(image_factory_one), id(image_factory_two))
    
    def testClassDefinition(self):
        pass
    

if __name__ == '__main__':
	unittest.main()