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
import logging
from threading import Thread
from props import prop
from NotificationCenter import NotificationCenter
from Template import Template
from PluginManager import PluginManager
from ApplicationConfiguration import ApplicationConfiguration
from PersistentImageManager import PersistentImageManager
from BaseImage import BaseImage
from TargetImage import TargetImage
from ProviderImage import ProviderImage
from ImageFactoryException import ImageFactoryException

class Builder(object):
    """ TODO: Docstring for Builder  """

##### PROPERTIES
    os_plugin = prop("_os_plugin")
    cloud_plugin = prop("_cloud_plugin")
    base_image = prop("_base_image")
    target_image = prop("_target_image")
    provider_image = prop("_provider_image")
    image_metadata = prop("_image_metadata")

##### INITIALIZER
    def __init__(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.app_config = ApplicationConfiguration().configuration
        self.notification_center = NotificationCenter()
        self.pim = PersistentImageManager.default_manager()
        self._os_plugin = None
        self._cloud_plugin = None
        self._base_image = None
        self._target_image = None
        self._provider_image = None
        self.base_thread = None
        self.target_thread = None
        self.push_thread = None
        self.snapshot_thread = None

#####  BUILD IMAGE
    def build_image_from_template(self, template, parameters=None):
        """
        TODO: Docstring for build_image_from_template

        @param template TODO 

        @return TODO
        """
        # Create what is essentially an empty BaseImage here
        self.base_image = BaseImage()
        self.base_image.template = template
        self.base_image.parameters = parameters
        self.pim.add_image(self.base_image)

        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'template':template, 'parameters':parameters}
        self.base_thread = Thread(target=self._build_image_from_template, name=thread_name, args=(), kwargs=thread_kwargs)
        self.base_thread.start()

    def _build_image_from_template(self, template, parameters=None):
        try:
	    template = template if(isinstance(template, Template)) else Template(template)
	    plugin_mgr = PluginManager(self.app_config['plugins'])
	    self.os_plugin = plugin_mgr.plugin_for_target((template.os_name, template.os_version, template.os_arch))
	    self.os_plugin.create_base_image(self, template, parameters)
            # This implies a convention where the plugin can never dictate completion and must indicate failure
            # via an exception
            self.base_image.status="COMPLETE"
            self.pim.save_image(self.base_image)
        except Exception, e:
            self.base_image.status="FAILED"
            self.pim.save_image(self.base_image)
            self.log.error("Exception encountered in _build_image_from_template thread")
            self.log.exception(e)

##### CUSTOMIZE IMAGE FOR TARGET
    def customize_image_for_target(self, target, image_id=None, template=None, parameters=None):
        """
        TODO: Docstring for customize_image_for_target

        @param factory_image TODO
        @param target TODO 
        @param target_params TODO

        @return TODO
        """

        self.target_image = TargetImage()
        self.target_image.target = target
        self.target_image.base_image_id = image_id
        self.target_image.template = template
        self.target_image.parameters = parameters
        self.pim.add_image(self.target_image)        

        if(image_id and (not template)):
            self.base_image = self.pim.image_with_id(image_id)
            template = self.base_image.template
            self.target_image.template = template
        elif template:
            self.build_image_from_template(template, parameters)
            # Populate the base_image property of our target image correctly
            # (The ID value is always available immediately after the call above)
            image_id = self.base_image.identifier
            self.target_image.base_image_id = self.base_image.identifier
        elif template and image_id:
            raise ImageFactoryException("Must specify either a template or a BaseImage ID, not both")
        else:
            raise ImageFactoryException("Asked to create a TargetImage without a BaseImage or a template")

        # Both base_image and target_image exist at this point and have IDs and status
        # We can now launch our thread and return to the caller
        
        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'target':target, 'image_id':image_id, 'template':template, 'parameters':parameters}
        self.target_thread = Thread(target=self._customize_image_for_target, name=thread_name, args=(), kwargs=thread_kwargs)
        self.target_thread.start()

    def _customize_image_for_target(self, target, image_id=None, template=None, parameters=None):
        try:
            # If there is an ongoing base build, wait for it to finish
            if self.base_thread:
                threadname=self.base_thread.getName()
                self.log.debug("Waiting for our BaseImage builder thread (%s) to finish" % (threadname))
                self.base_thread.join()
                self.log.debug("BaseImage builder thread (%s) finished - continuing with TargetImage tasks" % (threadname))

            if self.base_image.status == "FAILED":
                raise ImageFactoryException("The BaseImage (%s) for our TargetImage has failed its build.  Cannot continue." % (self.base_image.identifier))

            if self.base_image.status != "COMPLETE":
                raise ImageFactoryException("Got to TargetImage build step with a BaseImage status of (%s).  This should never happen.  Aborting." % (self.base_image.status))

            template = template if(isinstance(template, Template)) else Template(template)

            plugin_mgr = PluginManager(self.app_config['plugins'])

            # It's possible this has already been set by the base_image creation above
            if not self.os_plugin:
                self.os_plugin = plugin_mgr.plugin_for_target((template.os_name, template.os_version, template.os_arch))

            self.cloud_plugin = plugin_mgr.plugin_for_target(target)
            if not self.cloud_plugin:
                self.log.warn("Unable to find cloud plugin for target (%s)" % (target))

            try:
                _should_create = self.cloud_plugin.builder_should_create_target_image(self, target, image_id, template, parameters)
            except AttributeError as e:
                _should_create = True
            try:
                if _should_create : self.cloud_plugin.builder_will_create_target_image(self, target, image_id, template, parameters)
            except AttributeError as e:
                pass
            if(_should_create):
                try:
                    self.os_plugin.create_target_image(self, target, image_id, parameters)
                    self.cloud_plugin.builder_did_create_target_image(self, target, image_id, template, parameters)
                except AttributeError as e:
                    pass
            self.target_image.status = "COMPLETE"
            self.pim.save_image(self.target_image)
        except Exception, e:
            self.target_image.status = "FAILED"
            self.pim.save_image(self.target_image)
            self.log.error("Exception encountered in _customize_image_for_target thread")
            self.log.exception(e)

##### CREATE PROVIDER IMAGE
    def create_image_on_provider(self, provider, credentials, target, image_id=None, template=None, parameters=None):
        if(parameters and parameters.get('snapshot', False)):
            self.snapshot_image_on_provider(provider, credentials, target, image_id, template, parameters)
        else:
            self.push_image_to_provider(provider, credentials, target, image_id, template, parameters)

##### PUSH IMAGE TO PROVIDER
    def push_image_to_provider(self, provider, credentials, target, image_id, template, parameters):
        """
        TODO: Docstring for push_image_to_provider

        @param image TODO
        @param provider TODO
        @param credentials TODO
        @param provider_params TODO 

        @return TODO
        """

        self.provider_image = ProviderImage() 
        self.provider_image.provider = provider
        self.provider_image.credentials = credentials
        self.provider_image.target_image_id = image_id
        self.provider_image.template = template
        self.pim.add_image(self.provider_image)

        if(image_id and (not template)):
            self.target_image = self.pim.image_with_id(image_id)
            if not self.target_image:
                raise ImageFactoryException("Unable to retrieve target image with id (%s) from storage" % (image_id))
            self.base_image = self.pim.image_with_id(self.target_image.base_image_id)
            if not self.base_image:
                raise ImageFactoryException("Unable to retrieve base image with id (%s) from storage" % (image_id))
            template = self.target_image.template
            self.provider_image.template = template
        elif template and image_id:
            raise ImageFactoryException("Must specify either a template or a TargetImage ID, not both")
        elif template:
            self.customize_image_for_target(target=target , image_id=None, template=template, parameters=parameters)
            # Populate the target_image value of our provider image properly
            # (The ID value is always available immediately after the call above)
            # self.base_image is created in cascading fashion from the above call
            image_id = self.target_image.identifier
            self.provider_image.target_image_id = self.target_image.identifier
        else:
            raise ImageFactoryException("Asked to create a ProviderImage without a TargetImage or a template")

        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'provider':provider, 'credentials':credentials, 'target':target, 'image_id':image_id, 'template':template, 'parameters':parameters}
        self.push_thread = Thread(target=self._push_image_to_provider, name=thread_name, args=(), kwargs=thread_kwargs)
        self.push_thread.start()

    def _push_image_to_provider(self, provider, credentials, target, image_id, template, parameters):
        try:
            # If there is an ongoing target_image build, wait for it to finish
            if self.target_thread:
                threadname=self.target_thread.getName()
                self.log.debug("Waiting for our TargetImage builder thread (%s) to finish" % (threadname))
                self.target_thread.join()
                self.log.debug("TargetImage builder thread (%s) finished - continuing with ProviderImage tasks" % (threadname))

            if self.target_image.status == "FAILED":
                raise ImageFactoryException("The TargetImage (%s) for our ProviderImage has failed its build.  Cannot continue." % (self.target_image.identifier))

            if self.target_image.status != "COMPLETE":
                raise ImageFactoryException("Got to ProviderImage build step with a TargetImage status of (%s).  This should never happen.  Aborting." % (self.target_image.status))

            template = template if(isinstance(template, Template)) else Template(template)

            plugin_mgr = PluginManager(self.app_config['plugins'])
            if not self.cloud_plugin:
                self.cloud_plugin = plugin_mgr.plugin_for_target(target)
                self.cloud_plugin.push_image_to_provider(self, provider, credentials, target, image_id, parameters)
            self.provider_image.status="COMPLETE"
            self.pim.save_image(self.provider_image)
        except Exception, e:
            self.provider_image.status="FAILED"
            self.pim.save_image(self.provider_image)
            self.log.error("Exception encountered in _push_image_to_provider thread")
            self.log.exception(e)

##### SNAPSHOT IMAGE
    def snapshot_image(self, provider, credentials, target, image_id, template, parameters):
        """
        TODO: Docstring for snapshot_image
        
        @param template TODO
        @param target TODO
        @param provider TODO
        @param credentials TODO
        @param snapshot_params TODO

        @return TODO
        """

        self.provider_image = ProviderImage()
        self.provider_image.provider = provider
        self.provider_image.credentials = credentials
        self.provider_image.target_image_id = image_id
        self.provider_image.template = template
        self.pim.add_image(self.provider_image)

        if not template:
            raise ImageFactoryException("Must specify a template when requesting a snapshot-style build")

        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'provider':provider, 'credentials':credentials, 'target':target, 'image_id':image_id, 'template':template, 'parameters':parameters}
        self.snapshot_thread = Thread(target=self._snapshot_image, name=thread_name, args=(), kwargs=thread_kwargs)
        self.snapshot_thread.start()

    def _snapshot_image(self, provider, credentials, target, image_id, template, parameters):
        try:
            plugin_mgr = PluginManager(self.app_config['plugins'])
            self.cloud_plugin = plugin_mgr.plugin_for_target(target)
            self.cloud_plugin.snapshot_image_on_provider(self, provider, credentials, target, image_id, template, parameters)
            self.provider_image.status="COMPLETE"
            self.pim.save_image(self.provider_image)
        except Exception, e:
            self.provider_image.status="FAILED"
            self.pim.save_image(self.provider_image)
            self.log.error("Exception encountered in _snapshot_image thread")
            self.log.exception(e)

##### DELETE IMAGE
    def delete_image_on_provider(self, provider, credentials, target, image_object, parameters):
        """
        Delete an image on the given provider - We only need plugin-specific methods to delete ProviderImages
        Both TargetImages and BaseImages can be deleted directly at the PersistentImageManager layer.
        
        @param provider - XML or JSON provider definition
        @param credentials - Credentials for the given provider
        @param target - Target type for this provider
        @param image_object - Already-retrieved and populated ProviderImage object
        @param parameters TODO

        @return TODO
        """

        thread_name = str(uuid.uuid4())[0:8]
        thread_kwargs = {'provider':provider, 'credentials':credentials, 'target':target, 'image_object':image_object, 'parameters':parameters}
        self.delete_thread = Thread(target=self._delete_image_on_provider, name=thread_name, args=(), kwargs=thread_kwargs)
        self.delete_thread.start()


    def _delete_image_on_provider(self, provider, credentials, target, image_object, parameters):
        try:
            plugin_mgr = PluginManager(self.app_config['plugins'])
            self.cloud_plugin = plugin_mgr.plugin_for_target(target)
            self.cloud_plugin.delete_from_provider(self, provider, credentials, target, parameters)
            self.provider_image.status="DELETED"
            self.pim.save_image(image_object)
            # TODO: Perhaps wait a modest amount of time (a few minutes) before actually deleting the object
        except Exception, e:
            self.provider_image.status="DELETEFAILED"
            self.pim.save_image(image_object)
            self.log.error("Exception encountered in _delete_image_on_provider thread")
            self.log.exception(e)
