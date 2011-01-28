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
import zope
from builders.ImageBuilderDelegate import ImageBuilderDelegate
from builders.ImageBuilderInterface import ImageBuilderInterface
from builders.MockBuilder import MockBuilder


class TestMockBuilder(unittest.TestCase):
	def setUp(self):
		self.mock_builder = MockBuilder("IDL")
		self.delegate = MockBuilderDelegate()
		# self.mock_builder.delegate = self.delegate
		self.new_builder_status = "NEW_STATUS"
	
	def tearDown(self):
		self.mock_builder = None
		self.delegate = None
		self.new_builder_status = None
	
	def testImplementsImageBuilderInterface(self):
		self.assert_(ImageBuilderInterface.implementedBy(MockBuilder), 'MockBuilder does not implement the ImageBuilder interface...')
	
	def testInit(self):
		self.assertEqual("IDL", self.mock_builder.template)
		self.assert_(self.mock_builder.image_id, 'Initilizer failed to set \'image_id\'...')
	
	def testIsCallable(self):
		self.assert_(callable(self))
	
	def testBuild(self):
		# TODO: sloranz@redhat.com - test more here... make sure we're getting the file we think.
		# known_uuid = uuid.uuid4()
		# self.mock_builder.image_id = known_uuid
		self.mock_builder.build()
	
	def testDelegateAssignment(self):
		self.mock_builder.delegate = self.delegate
		self.assertIs(self.mock_builder.delegate, self.delegate)
	
	def testShouldUpdateStatus(self):
		self.mock_builder.status = "UPDATE_ME"
		self.mock_builder.delegate = self.delegate
		self.mock_builder.status = self.new_builder_status
		self.assertEqual(self.new_builder_status, self.mock_builder.status)
		self.mock_builder.delegate = None
	
	def testShouldNotUpdateStatus(self):
		self.mock_builder.status = "NO_UPDATE"
		self.mock_builder.delegate = self.delegate
		self.mock_builder.status = self.new_builder_status
		self.assertEqual("NO_UPDATE", self.mock_builder.status)
		self.mock_builder.delegate = None
	
	def testModifyStatusUpdate(self):
		self.mock_builder.status = "INSERT_CHANGE"
		self.mock_builder.delegate = self.delegate
		self.mock_builder.status = self.new_builder_status
		self.assertEqual("MODIFIED_STATUS_UPDATE", self.mock_builder.status)
		self.mock_builder.delegate = None
	
	def testModifyPercentageUpdate(self):
		self.mock_builder.percent_complete = None
		self.mock_builder.delegate = self.delegate
		self.mock_builder.percent_complete = 50
		self.assertEqual(0, self.mock_builder.percent_complete)
		self.mock_builder.delegate = None
	
	def testShouldUpdatePercentage(self):
		self.mock_builder.percent_complete = 50
		self.mock_builder.delegate = self.delegate
		self.mock_builder.percent_complete = 95
		self.assertEqual(95, self.mock_builder.percent_complete)
		self.mock_builder.delegate = None
	
	def testShouldNotUpdatePercentage(self):
		self.mock_builder.percent_complete = 100
		self.mock_builder.delegate = self.delegate
		self.mock_builder.percent_complete = 52
		self.assertEqual(100, self.mock_builder.percent_complete)
		self.mock_builder.delegate = None
	


class MockBuilderDelegate(object):
	zope.interface.implements(ImageBuilderDelegate)
	
	def builder_should_update_status(self, builder, original_status, new_status):
		if(original_status == "NO_UPDATE"):
			return False
		else:
			return True
	
	def builder_will_update_status(self, builder, original_status, new_status):
		if(original_status == "INSERT_CHANGE"):
			return "MODIFIED_STATUS_UPDATE"
		else:
			return new_status
	
	def builder_will_update_percentage(self, builder, original_percentage, new_percentage):
		if(original_percentage >= 0):
			return new_percentage
		else:
			return 0
	
	def builder_should_update_percentage(self, builder, original_percentage, new_percentage):
		if(original_percentage == 100):
			return False
		else:
			return True
	
	


if __name__ == '__main__':
	unittest.main()