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
from zope.interface import Invalid
from imagefactory.builders.IBuilder import IBuilder
from imagefactory.builders.IBuilderDelegate import IBuilderDelegate
from imagefactory.builders.BaseBuilder import BaseBuilder


class TestBaseBuilder(unittest.TestCase):
    def setUp(self):
        # logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s')
        self.builder = BaseBuilder()
        self.delegate = BuilderDelegate()
        self.new_builder_status = "NEW_STATUS"
    
    def tearDown(self):
        del self.builder
        del self.delegate
        del self.new_builder_status
    
    def testImplementsIBuilder(self):
        self.assert_(IBuilder.implementedBy(BaseBuilder), 'BaseBuilder does not implement the ImageBuilder interface.')
        try:
            IBuilder.validateInvariants(BaseBuilder())
        except Invalid, e:
            self.fail(e)
    
    def testIsCallable(self):
        self.assert_(callable(self.builder))
    
    def testImageIdSet(self):
        self.assert_(self.builder.image_id, 'Initilizer failed to set \'image_id\'...')
    
    def testDelegateAssignment(self):
        self.builder.delegate = self.delegate
        self.assertIs(self.builder.delegate, self.delegate)
    
    def testShouldUpdateStatus(self):
        self.builder.status = "UPDATE_ME"
        self.builder.delegate = self.delegate
        self.builder.status = self.new_builder_status
        self.assertEqual(self.new_builder_status, self.builder.status)
        self.builder.delegate = None
    
    def testShouldNotUpdateStatus(self):
        self.builder.status = "NO_UPDATE"
        self.builder.delegate = self.delegate
        self.builder.status = self.new_builder_status
        self.assertEqual("NO_UPDATE", self.builder.status)
        self.builder.delegate = None
    
    def testModifyStatusUpdate(self):
        self.builder.status = "INSERT_CHANGE"
        self.builder.delegate = self.delegate
        self.builder.status = self.new_builder_status
        self.assertEqual("MODIFIED_STATUS_UPDATE", self.builder.status)
        self.builder.delegate = None
    
    def testModifyPercentageUpdate(self):
        self.builder.percent_complete = None
        self.builder.delegate = self.delegate
        self.builder.percent_complete = 50
        self.assertEqual(self.builder.percent_complete, 0)
        self.builder.delegate = None
    
    def testShouldUpdatePercentage(self):
        self.builder.percent_complete = 50
        self.builder.delegate = self.delegate
        self.builder.percent_complete = 95
        self.assertEqual(95, self.builder.percent_complete)
        self.builder.delegate = None
    
    def testShouldNotUpdatePercentage(self):
        self.builder.percent_complete = 100
        self.builder.delegate = self.delegate
        self.builder.percent_complete = 52
        self.assertEqual(100, self.builder.percent_complete)
        self.builder.delegate = None
    

class BuilderDelegate(object):
    zope.interface.implements(IBuilderDelegate)
    
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