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
from qmfagent.ImageFactory import ImageFactory
from builder import *

class TestImageFactory(unittest.TestCase):
    def setUp(self):
        self.expected_schema_methods = {"build_image" : ("descriptor", "target", "image_uuid", "sec_credentials", "build_adaptor")}

    def tearDown(self):
        self.expected_schema_methods = None
    
    def testQMFSchemaDefinition(self):
        for schema_method in ImageFactory.qmf_schema.getMethods():
            self.assert_(schema_method.getName() in self.expected_schema_methods)
            arguments = self.expected_schema_methods[schema_method.getName()]
            for schema_property in schema_method.getArguments():
                self.assert_(schema_property.getName() in arguments)
    
    def testSingleton(self):
        image_factory_one = ImageFactory()
        image_factory_two = ImageFactory()
        self.assertEqual(id(image_factory_one), id(image_factory_two))
    
    def testClassDefinition(self):
        pass
    

if __name__ == '__main__':
	unittest.main()