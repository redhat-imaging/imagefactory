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

class OSDelegate(Interface):
    """ Delegate interface for OS installation and customization. OS plugins
    use provide the builder with a delegate. Not all methods defined in this
    interface need to be implemented by the delegate, just the ones that
    the plugin cares about. Delegation provides a way for the plugin to
    customize the behavior of the builder. """

    def create_base_image(self, builder, template, parameters):
        """
        Create a JEOS image and install any packages specified in the template.

        @param builder The Builder object coordinating image creation.
        @param template A Template object.
        @param parameters Dictionary of target specific parameters.

        @return A BaseImage object.
        """

    def create_target_image(self, builder, target, base_image, parameters):
        """
        Performs cloud specific customization on the base image.

        @param builder The builder object.
        @param base_image The BaseImage to customize.
        @param target The cloud type to customize for.
        @param parameters Dictionary of target specific parameters.

        @return A TargetImage object.
        """

    def add_cloud_plugin_content(self, content):
        """
        This is a method that cloud plugins can call to deposit content/commands to
        be run during the OS-specific first stage of the Target Image creation.

        There is no support for repos at the moment as these introduce external
        dependencies that we may not be able to resolve.

        @param content dict containing commands and file.
        """
