#
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
import zope
from zope.interface import Invalid
from imgfac.builders.IBuilder import IBuilder
from imgfac.builders.IBuilderDelegate import IBuilderDelegate
from imgfac.builders.BaseBuilder import BaseBuilder


class TestBaseBuilder(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        self.builder = BaseBuilder(template="<template></template>", target="mock")
        self.delegate = BuilderDelegate()
        self.new_builder_status = "NEW_STATUS"

    def tearDown(self):
        del self.builder
        del self.delegate
        del self.new_builder_status

    def testImplementsIBuilder(self):
        self.assert_(IBuilder.implementedBy(BaseBuilder), 'BaseBuilder does not implement the ImageBuilder interface.')
        try:
            IBuilder.validateInvariants(self.builder)
        except Invalid, e:
            self.fail(e)

    def testIsCallable(self):
        self.assert_(callable(self.builder))

    def testImageIdSet(self):
        self.assert_(self.builder.new_image_id, 'Initilizer failed to set \'image_id\'...')

    def testDelegateAssignment(self):
        self.builder.delegate = self.delegate
        self.assertEqual(id(self.builder.delegate), id(self.delegate))

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
