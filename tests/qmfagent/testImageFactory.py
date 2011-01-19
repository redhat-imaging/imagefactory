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

class testImageFactory(unittest.TestCase):
    def setUp(self):
        self.expected_schema_methods = {"build_image" : ("descriptor", "target", "image_uuid", "sec_credentials", "build_adaptor")}
    
    def testQMFSchemaDefinition(self):
        method_iterator = ImageFactory.qmf_schema.getMethods().__iter__()
        try:
            next_method = method_iterator.next()
            arguments = self.expected_schema_methods[next_method.getName()]
            property_iterator = next_method.getArguments().__iter__()
            try:
                next_property = property_iterator.next()
                self.assert_(next_property.getName() in arguments)
            except StopIteration:
                pass
        except StopIteration:
            pass
    
    def testSingleton(self):
        image_factory_one = ImageFactory()
        image_factory_two = ImageFactory()
        self.assertEqual(id(image_factory_one), id(image_factory_two))
    
    def testClassDefinition(self):
        pass
    

if __name__ == '__main__':
	unittest.main()