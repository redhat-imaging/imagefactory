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
import os
import json
from imagefactory.ApplicationConfiguration import ApplicationConfiguration


class TestApplicationConfiguration(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        
        self.defaults = dict(verbose=False, debug=False, foreground=False, config="/etc/imagefactory.conf", imgdir="/tmp", qmf=False, qpidd="localhost", warehouse=None, template=None)
        
        config_file_path = self.defaults["config"]
        if (os.path.isfile(config_file_path)):
            try:
                config_file = open(config_file_path)
                self.defaults.update(json.load(config_file))
                config_file.close()
            except IOError, e:
                pass
        
    
    def tearDown(self):
        del self.defaults
    
    def testSingleton(self):
        self.assertIs(ApplicationConfiguration(), ApplicationConfiguration())
    
    # def testConfigurationDictionaryDefaults(self):
    #     self.assertIsNotNone(ApplicationConfiguration().configuration)
    #     self.assertDictContainsSubset(self.defaults, ApplicationConfiguration().configuration)
    # 

if __name__ == '__main__':
    unittest.main()