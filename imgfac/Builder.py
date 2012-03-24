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

import uuid
import Provider
from threading import Thread
from props import prop
from NotificationCenter import NotificationCenter
from Template import Template
from PluginManager import PluginManager
from ApplicationConfiguration import ApplicationConfiguration


class Builder(object):
    """ TODO: Docstring for Builder  """

##### PROPERTIES
    os_plugin = prop("_os_plugin")
    cloud_plugin = prop("_cloud_plugin")
    base_image = prop("_base_image")
    target_image = prop("_target_image")
    provider_image = prop("_provider_image")

##### INITIALIZER
    def __init__(self):
        self.app_config = ApplicationConfiguration().configuration
        self.notification_center = NotificationCenter()
        self._os_plugin = None
        self._cloud_plugin = None
        self._base_image = None
        self._target_image = None
        self._provider_image = None

#####  BUILD IMAGE
    def build_image_from_template(self, template, parameters=None):
        """
        TODO: Docstring for build_image_from_template

        @param template TODO 

        @return TODO
        """
        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'template':template, 'parameters':parameters}
        self.base_thread = Thread(target=self._build_image_from_template, name=thread_name, args=(), kwargs=thread_kwargs)
        self.base_thread.start()

    def _build_image_from_template(self, template, parameters=None):
        template = template if(isinstance(template, Template)) else Template(template)
        plugin_mgr = PluginManager(self.app_config['plugins'])
        self.os_plugin = plugin_mgr.plugin_for_target((template.os_name, template.os_version, template.os_arch))
        self.base_image = self.os_plugin.create_base_image(self, template, parameters)

##### CUSTOMIZE IMAGE FOR TARGET
    def customize_image_for_target(self, target, image_id=None, template=None, parameters=None):
        """
        TODO: Docstring for customize_image_for_target

        @param factory_image TODO
        @param target TODO 
        @param target_params TODO

        @return TODO
        """
        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'target':target, 'image_id':image_id, 'template':template, 'parameters':parameters}
        self.target_thread = Thread(target=self._customize_image_for_target, name=thread_name, args=(), kwargs=thread_kwargs)
        self.target_thread.start()

    def _customize_image_for_target(self, target, image_id=None, template=None, parameters=None):
        if(image_id and (not template)):
            # TODO get the template from the base_image
            pass
        # TODO: if there is no base_image, we need to wait while one is built.
        # we can probably use NotificationCenter and threading.Event to wait.
        
        template = template if(isinstance(template, Template)) else Template(template)
        plugin_mgr = PluginManager(self.app_config['plugins'])
        self.os_plugin = plugin_mgr.plugin_for_target((template.os_name, template.os_version, template.os_arch))
        self.cloud_plugin = plugin_mgr.plugin_for_target(target)

        try:
            _should_create = self.cloud_plugin.builder_should_create_target_image(self, target, image_id, template, parameters)
        except AttributeError:
            _should_create = True
        try:
            if _should_create : self.cloud_plugin.builder_will_create_target_image(self, target, image_id, template, parameters)
        except AttributeError:
            pass
        if(_should_create):
            try:
                self.target_image = self.os_plugin.create_target_image(self, target, image, parameters)
                self.cloud_plugin.builder_did_create_target_image(self, target, image, template, parameters)
            except AttributeError:
                pass

##### CREATE PROVIDER IMAGE
    def create_image_on_provider(self, provider, credentials, image_id=None, template=None, parameters=None):
        if(parameters.get('snapshot', False)):
            self.snapshot_image_on_provider(provider, credentials, template, parameters)
        else:
            self.push_image_to_provider(provider, credentials, image_id, template, parameters)

##### PUSH IMAGE TO PROVIDER
    def push_image_to_provider(self, provider, credentials, image_id, template, parameters):
        """
        TODO: Docstring for push_image_to_provider

        @param image TODO
        @param provider TODO
        @param credentials TODO
        @param provider_params TODO 

        @return TODO
        """
        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'provider':provider, 'credentials':credentials, 'image_id':image_id, 'template':template, 'parameters':parameters}
        self.push_thread = Thread(target=self._push_image_to_provider, name=thread_name, args=(), kwargs=thread_kwargs)
        self.push_thread.start()

    def _push_image_to_provider(self, provider, credentials, image_id, template, parameters):
        # TODO: if there is no target_image, we need to wait while one is built.
        # we can probably use NotificationCenter and threading.Event to wait.
        plugin_mgr = PluginManager(self.app_config['plugins'])
        self.cloud_plugin = plugin_mgr.plugin_for_target(Provider.map_provider_to_target(provider))
        target_image = None # TODO: either retrieve the image or build one.
        self.provider_image = self.cloud_plugin.push_image_to_provider(self, provider, credentials, target_image, parameters)

##### SNAPSHOT IMAGE
    def snapshot_image(self, provider, credentials, template, parameters):
        """
        TODO: Docstring for snapshot_image
        
        @param template TODO
        @param target TODO
        @param provider TODO
        @param credentials TODO
        @param snapshot_params TODO
    
        @return TODO
        """
        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'provider':provider, 'credentials':credentials, 'template':template, 'parameters':parameters}
        self.snapshot_thread = Thread(target=self._snapshot_image, name=thread_name, args=(), kwargs=thread_kwargs)
        self.snapshot_thread.start()

    def _snapshot_image(self, provider, credentials, template, parameters):
        plugin_mgr = PluginManager(self.app_config['plugins'])
        self.cloud_plugin = plugin_mgr.plugin_for_target(Provider.map_provider_to_target(provider))
        self.provider_image = self.cloud_plugin.snapshot_image_on_provider(self, provider, credentials, template, parameters)
