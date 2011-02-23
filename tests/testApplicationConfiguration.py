#!/usr/bin/env python
# encoding: utf-8

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
from imagefactory.ApplicationConfiguration import ApplicationConfiguration


class TestApplicationConfiguration(unittest.TestCase):
    def setUp(self):
        self.app_config = ApplicationConfiguration()
        self.arguments = self.app_config.arguments
        self.configuration = self.app_config.configuration
        self.defaults = dict(verbose=False, debug=False, foreground=False, config="/etc/imagefactory.conf", output="/tmp", qmf=False, broker="localhost", warehouse=None, template=None)
    
    def tearDown(self):
        del self.app_config
        del self.arguments
        del self.configuration
        del self.defaults
    
    def testSingleton(self):
        self.assertIs(ApplicationConfiguration(), self.app_config)
    
    def testArgumentDefaults(self):
        self.assertIsNotNone(self.arguments)
        for key in self.defaults:
            self.assertEqual(getattr(self.arguments, key), self.defaults[key])
    
    def testConfigurationDictionaryDefaults(self):
        self.assertIsNotNone(self.configuration)
        self.assertDictContainsSubset(self.defaults, self.configuration)

if __name__ == '__main__':
    unittest.main()