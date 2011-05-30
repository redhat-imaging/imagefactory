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
from imagefactory import BuildDispatcher
from imagefactory.builders import MockBuilder

class testBuildDispatcher(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')

    def tearDown(self):
        pass

    def testInstantiateMockBuilder(self):
        template_xml = "<template><name>f14jeos</name><os><name>Fedora</name></os></template>"
        dispatcher = BuildDispatcher.BuildDispatcher(template_xml, "mock")
        self.assertIsInstance(dispatcher._builder, MockBuilder.MockBuilder)
        self.assertEqual(dispatcher.template.xml, template_xml)
        self.assertEqual(dispatcher.target, "mock")

if __name__ == '__main__':
    unittest.main()
