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

PLUGIN_TYPES = ('OS', 'CLOUD')
INFO_FILE_EXTENSION = '.info'

class PluginManager(Singleton):
    """ Registers and manages ImageFactory plugins. """
    @property
    def plugins(self):
        """
        The property plugins
        """
        return self._plugins

    def _singleton_init(self, plugin_path):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        if(os.path.exists(plugin_path)):
            self.path = plugin_path
        else:
            self.log.exception("Plugin path (%s) does not exist! No plugins loaded." % plugin_path)
            raise Exception("Plugin path (%s) does not exist! No plugins loaded." % plugin_path)
        self._plugins = dict()
        self._targets = dict()
        self._types = dict().fromkeys(PLUGIN_TYPES, list())

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
            self._plugins[_type] = dict()
            for filename in info_files:
                plugin_name = filename.rstrip(INFO_FILE_EXTENSION)
                md = self.metadata_for_plugin(plugin_name)
                try:
                    if(md['type'].upper() == _type):
                        for target in md['targets']:
                            if(not target in self._targets):
                                self._targets[target] = plugin_name
                            else:
                                msg = 'Did not register %s for %s. Plugin %s already registered.' % (plugin_name, target, self._targets[target])
                                self._register_plugin_with_error(plugin_name, msg)
                                self.log.warn(msg)
                        self._plugins[plugin_name] = md
                        self._types[_type].append(plugin_name)
                        self.log.info('Plugin (%s) loaded...' % plugin_name)
                except KeyError as e:
                    msg = 'Invalid metadata for plugin (%s). Missing entry for %s.' % (plugin_name, e)
                    self._register_plugin_with_error(plugin_name, msg)
                    self.log.exception(msg)
                except Exception as e:
                    msg = 'Loading plugin (%s) failed with exception: %s' % (plugin_name, e)
                    self._register_plugin_with_error(plugin_name, msg)
                    self.log.exception(msg)
        print self._plugins

    def _register_plugin_with_error(self, plugin_name, error_msg):
        self._plugins[plugin_name] = dict(ERROR = error_msg)

    def metadata_for_plugin(self, plugin):
        """
        Returns the metadata dictionary for the plugin.

        @param plugin name of the plugin or the plugin's info file

        @return dictionary containing the plugin's metadata
        """
        if(plugin in self._plugins):
            return self._plugins[plugin]
        else:
            metadata = None
            info_file = plugin + INFO_FILE_EXTENSION
            try:
                fp = open(os.path.join(self.path, info_file), 'r')
                metadata = json.load(fp)
            except Exception as e:
                self.log.exception('Exception caught while loading plugin metadata: %s' % e)
            finally:
                fp.close()
                return metadata
