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

from props import prop
from NotificationCenter import NotificationCenter


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
        super(Builder, self).init()
        self.notification_center = NotificationCenter()

#####  BUILD IMAGE
    def build_image_from_template(self, template, parameters=None):
        """
        TODO: Docstring for build_image_from_template

        @param template TODO 

        @return TODO
        """
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
            self.push_image_to_provider(provider, credentials, image, template, parameters)

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
        self.provider_image = self.cloud_plugin.snapshot_image_on_provider(self, provider, credentials, template, parameters)
