#
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
import zope
import os.path
from builders.IBuilder import IBuilder
from builders.MockBuilder import MockBuilder


class TestMockBuilder(unittest.TestCase):
    def setUp(self):
        # logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s')
        self.template = "<template></template>"
        self.target = "mock"
        self.builder = MockBuilder(self.template, self.target)
    
    def tearDown(self):
        del self.builder
        del self.template
        del self.target
    
    def testImplementsIBuilder(self):
        self.assert_(IBuilder.implementedBy(MockBuilder), 'MockBuilder does not implement the ImageBuilder interface...')
    
    def testInit(self):
        self.assertEqual(self.builder.template, self.template)
        self.assertEqual(self.builder.target, self.target)
    
    def testBuildImage(self):
        self.builder.build_image()
        self.assertEqual(self.builder.status, "COMPLETED")
        self.assert_(os.path.exists(self.builder.image))
    


if __name__ == '__main__':
    unittest.main()
