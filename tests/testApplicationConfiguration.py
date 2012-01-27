#!/usr/bin/env python
# encoding: utf-8

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
import os
import json
from imgfac.ApplicationConfiguration import ApplicationConfiguration


class TestApplicationConfiguration(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')

        self.defaults = dict(verbose=False, debug=False, foreground=False, config="/etc/imagefactory/imagefactory.conf", imgdir="/tmp", qmf=False, warehouse=None, template=None)

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
        self.assertTrue(id(ApplicationConfiguration()) == id(ApplicationConfiguration()))

    # def testConfigurationDictionaryDefaults(self):
    #     self.assertIsNotNone(ApplicationConfiguration().configuration)
    #     self.assertDictContainsSubset(self.defaults, ApplicationConfiguration().configuration)
    #

if __name__ == '__main__':
    unittest.main()
