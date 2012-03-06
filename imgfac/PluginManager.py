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

import logging
import os
import os.path
import json
from Singleton import Singleton

PLUGIN_TYPES = ('os', 'cloud')
INFO_FILE_EXTENSION = '.info'

class PluginManager(Singleton):
    """ Registers and manages ImageFactory plugins. """
    @property
    def plugins(self):
        """The property plugins"""
        return self._plugins

    def _singleton_init(self, plugin_path):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.path = plugin_path
        self._plugins = dict()
        self._targets = dict()

    def load(self):
        """
        Enumerates through installed plugins and registers each according to
        the features provided. Only one plugin may be registered per feature.
        When more than one plugin is found, the first will be registered and
        all others listed as inactive.
        """

        info_files = list()
        directory_listing = os.listdir(self.path)
        for _file in directory_listing:
            if _file.endswith(INFO_FILE_EXTENSION):
                info_files.append(_file)

        for _type in PLUGIN_TYPES:
            for filename in info_files:
                plugin_name = filename.rstrip(INFO_FILE_EXTENSION)
                md = self.metadata_for_plugin(plugin_name)
                self._plugins[plugin_name] = md
                if(md['type'] is _type.lower()):
                    for target in md['targets']:
                        self._targets[target] = plugin_name

    def metadata_for_plugin(self, plugin):
        """
        Returns the metadata dictionary for the plugin.

        @param plugin name of the plugin or the plugin's info file

        @return dictionary containing the plugin's metadata
        """
        if(plugin in self._plugins):
            return self._plugins[plugin]
        else:
            info_file = plugin + INFO_FILE_EXTENSION
            fp = open(os.path.join(self.path, info_file), 'r')
            metadata = json.load(fp)
            fp.close()
            return metadata
