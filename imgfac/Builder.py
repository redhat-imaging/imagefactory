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

class Builder(object):
    """ TODO: Docstring for Builder  """

##### PROPERTIES
    delegate = prop("_delegate")
    os_plugin = prop("_os_plugin")
    cloud_plugin = prop("_cloud_plugin")
    base_image = prop("_base_image")
    target_image = prop("_target_image")
    provider_image = prop("_provider_image")

    def status():
        doc = "A string value."
        def fget(self):
            return self._status

        def fset(self, value):
            if(self.delegate):
                try: #check with the delegate if we should update
                    _shouldSet = self.delegate.builder_should_update_status(self, self._status, value)
                except AttributeError: #if the delegate doesn't respond to this method, we'll just go ahead with it
                    _shouldSet = True
                try: #give the delegate a chance to intervene on the update
                    if _shouldSet : value = self.delegate.builder_will_update_status(self, self._status, value)
                except AttributeError:
                    pass
                if(_shouldSet):
                    _original_status = self._status
                    self._status = value
                    try: #tell the delegate that the update occurred
                        self.delegate.builder_did_update_status(self, _original_status, self._status)
                    except AttributeError:
                        pass
            else:
                self._status = value
        return locals()
    status = property(**status())

    def percent_complete():
        doc = "The percentage through an operation."
        def fget(self):
            return self._percent_complete

        def fset(self, value):
            if(self.delegate):
                try: #check with the delegate if we should update
                    _shouldSet = self.delegate.builder_should_update_percentage(self, self._percent_complete, value)
                except AttributeError: #if the delegate doesn't respond to this method, we'll just go ahead with it
                    _shouldSet = True
                try: #give the delegate a chance to intervene on the update
                    if _shouldSet : value = self.delegate.builder_will_update_percentage(self, self._percent_complete, value)
                except AttributeError:
                    pass
                if(_shouldSet):
                    _original_percentage = self._percent_complete
                    self._percent_complete = value
                    try: #tell the delegate that the update occurred
                        self.delegate.builder_did_update_percentage(self, _original_percentage, self._percent_complete)
                    except AttributeError:
                        pass
            else:
                self._percent_complete = value

        return locals()
    percent_complete = property(**percent_complete())

##### INITIALIZER
    def __init__(self):
        """ TODO: Fill me in """
        super(Builder, self).init()

#####  BUILD IMAGE
    def build_image_from_template(self, template):
        """
        TODO: Docstring for build_image_from_template

        @param template TODO 

        @return TODO
        """
        self.base_image = self.os_plugin.create_base_image(self, template)

##### CUSTOMIZE IMAGE FOR TARGET
    def customize_image_for_target(self, base_image, target, parameters):
        """
        TODO: Docstring for customize_image_for_target

        @param factory_image TODO
        @param target TODO 
        @param target_params TODO

        @return TODO
        """
        try:
            _should_create = self.cloud_plugin.builder_should_create_target_image(self)
        except AttributeError:
            _should_create = True
        try:
            if _should_create : self.cloud_plugin.builder_will_create_target_image(self)
        except AttributeError:
            pass
        if(_should_create):
            try:
                self.target_image = self.os_plugin.create_target_image(self, base_image, target, parameters)
                self.cloud_plugin.builder_did_create_target_image(self)
            except AttributeError:
                pass


##### PUSH IMAGE TO PROVIDER
    def push_image_to_provider(self, image, target, provider, credentials, parameters):
        """
        TODO: Docstring for push_image_to_provider

        @param image TODO
        @param provider TODO
        @param credentials TODO
        @param provider_params TODO 

        @return TODO
        """
        self.provider_image = self.cloud_plugin.push_image_to_provider(self, image, target, provider, parameters)

##### SNAPSHOT IMAGE
    def snapshot_image(self, template, target, provider, credentials, parameters):
        """
        TODO: Docstring for snapshot_image
        
        @param template TODO
        @param target TODO
        @param provider TODO
        @param credentials TODO
        @param snapshot_params TODO
    
        @return TODO
        """
        self.provider_image = self.cloud_plugin.snapshot_image_on_provider(self, imag_id, target, provider, parameters)
