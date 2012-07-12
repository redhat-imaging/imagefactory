#
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

from zope.interface import Interface

class CloudDelegate(Interface):
    """ Delegate interface for OS installation and customization. OS plugins
    use provide the builder with a delegate. Not all methods defined in this
    interface need to be implemented by the delegate, just the ones that
    the plugin cares about. Delegation provides a way for the plugin to
    customize the behavior of the builder. """

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        """
        Prepare the image for use on and upload to a specified provider.

        @param builder The Builder object coordinating image creation.
        @param image The TargetImage to be pushed.
        @param target The cloud target to which the provider belongs.
        @param provider The cloud provider to which the image will be pushed.
        @param parameters The cloud provider specific parameters for pushing.

        @return A ProviderImage object.
        """

    def snapshot_image_on_provider(self, builder, provider, credentials, target, template, parameters):
        """
        Create a ProviderImage by taking a snapshot of an existing image on the provider.

        @param builder The Builder object coordinating image creation.
        @param image_id The provider identifier of the image to snapshot.
        @param target The cloud target to which the provider belongs.
        @param provider The cloud provider to which the image will be pushed.
        @param parameters The cloud provider specific parameters for pushing.

        @return A ProviderImage object.
        """

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        """
        Delete the image from the provider.

        @param builder The Builder object with the provider image to delete.
        @param target The cloud target to which the provider belongs.
        @param provider The cloud provider from which the image will be deleted.
        @param parameters The cloud provider specific parameters for deletion.
        """

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        """
        Allows the delegate to decide if a TargetImage should be created.

        @param builder The Builder object coordinating image creation.

        @return bool
        """

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        """
        Called just before a TargetImage is created.

        @param builder The Builder object coordinating image creation.
        """
    
    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        """
        Called just after a TargetImage has been created.

        @param builder The Builder object coordinating image creation.
        """

