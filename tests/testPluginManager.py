# encoding: utf-8

#   Copyright 2012 Red Hat, Inc.
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
from imgfac.PluginManager import PluginManager
import tempfile
import json
import os.path
import os
import shutil
import sys

INFO1 = {
            "type":"os",
            "targets":[["osfoo", "osbar", "osbaz"]],
            "description":"blah",
            "maintainer": {
                "name":"foo1",
                "email":"bar1",
                "url":"baz1"
            },
            "version":"1.0",
            "license":"NA"
        }
INFO2 = {
            "type":"cloud",
            "targets":[["cloudfoo", "cloudbar", "cloudbaz"]],
            "description":"whatever",
            "maintainer": {
                "name":"foo2",
                "email":"bar2",
                "url":"baz2"
            },
            "version":"1.0",
            "license":"NA"
        }


class testPluginManager(unittest.TestCase):
    """ TODO: Docstring for testPluginManager  """

    def __init__(self, methodName='runTest'):
        super(testPluginManager, self).__init__(methodName)
        logging.basicConfig(level=logging.NOTSET,
                            format='%(asctime)s \
                                    %(levelname)s \
                                    %(name)s \
                                    pid(%(process)d) \
                                    Message: %(message)s', 
                            filename='/tmp/testPluginManager.log')

    def setUp(self):
        # create the info file for an OS plugin
        self.os_info_file = tempfile.NamedTemporaryFile(mode='w', suffix='.info', prefix='ifut-')
        json.dump(INFO1, self.os_info_file)
        self.os_info_file.flush()
        os.fsync(self.os_info_file)
        self.os_plugin_name = os.path.basename(self.os_info_file.name).partition('.')[0]
        # create a module for this plugin
        os.mkdir(os.path.join(tempfile.gettempdir(), self.os_plugin_name), 0744)
        osclass = open(os.path.join(tempfile.gettempdir(), self.os_plugin_name, self.os_plugin_name + '.py'), 'w')
        osclass.write('class %s(object):\n    pass' % self.os_plugin_name)
        osclass.close()
        osinit = open(os.path.join(tempfile.gettempdir(), self.os_plugin_name, '__init__.py'), 'w')
        osinit.write('from %s import %s as delegate_class' % (self.os_plugin_name, self.os_plugin_name))
        osinit.close()
        # create the info file for a CLOUD plugin
        self.cloud_info_file = tempfile.NamedTemporaryFile(mode='w', suffix='.info', prefix='ifut-')
        json.dump(INFO2, self.cloud_info_file)
        self.cloud_info_file.flush()
        os.fsync(self.cloud_info_file)
        self.cloud_plugin_name = os.path.basename(self.cloud_info_file.name).partition('.')[0]
        # create a module for this plugin
        os.mkdir(os.path.join(tempfile.gettempdir(), self.cloud_plugin_name), 0744)
        cloudclass = open(os.path.join(tempfile.gettempdir(), self.cloud_plugin_name, self.cloud_plugin_name + '.py'), 'w')
        cloudclass.write('class %s(object):\n    pass' % self.cloud_plugin_name)
        cloudclass.close()
        cloudinit = open(os.path.join(tempfile.gettempdir(), self.cloud_plugin_name, '__init__.py'), 'w')
        cloudinit.write('from %s import %s as delegate_class' % (self.cloud_plugin_name, self.cloud_plugin_name))
        cloudinit.close()
        # get a PluginManager instance and load plugin .info files
        self.plugin_mgr = PluginManager(plugin_path=tempfile.gettempdir())
        self.plugin_mgr.load()

    def tearDown(self):
        self.plugin_mgr = None
        shutil.rmtree(path=os.path.join(tempfile.gettempdir(), self.os_plugin_name), ignore_errors=True)
        shutil.rmtree(path=os.path.join(tempfile.gettempdir(), self.cloud_plugin_name), ignore_errors=True)
        self.os_info_file.close()
        self.cloud_info_file.close()

    def testMetadataForPlugin(self):
        os_metadata = self.plugin_mgr.metadata_for_plugin(self.os_plugin_name)
        self.assertDictEqual(os_metadata, INFO1)
        cloud_metadata = self.plugin_mgr.metadata_for_plugin(self.cloud_plugin_name)
        self.assertDictEqual(cloud_metadata, INFO2)

    @unittest.skip('See comments in code.')
    def testPluginForTarget(self):
        # This code is flawed...
        os_plugin = self.plugin_mgr.plugin_for_target(('osfoo', 'osbar', 'osbaz'))
        self.assertEqual(os_plugin.__class__.__name__, self.os_plugin_name)
        cloud_plugin = self.plugin_mgr.plugin_for_target(('cloudfoo', 'cloudbar', 'cloudbaz'))
        self.assertEqual(cloud_plugin.__class__.__name__, self.cloud_plugin_name)


if __name__ == '__main__':
    unittest.main()
