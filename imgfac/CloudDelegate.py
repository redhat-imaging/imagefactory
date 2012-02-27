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

    def builder_should_create_image(self, builder):
        """
        Allow or prohibit a JEOS image to be created and customized with additional packages.

        @param builder The builder object.

        @return bool
        """

    def builder_will_create_image(self, builder):
        """
        Invoked just before the installation of a JEOS image.

        @param builder The builder object.
        """

    def builder_did_create_image(self, builder):
        """
        Invoked after the builder has completed the custom package installation.

        @param builder The builder object.
        """

    def builder_should_install_packages(self, builder):
        """
        Allow or prohibit installation of extra packages.

        @param builder The builder object.

        @return bool
        """

    def builder_will_install_packages(self, builder):
        """
        Invoked just before installing packages on the image.

        @param builder The builder object.
        """

    def builder_did_install_packages(self, builder):
        """
        Invoked after installing packages on the image.

        @param builder The builder object.
        """

    def builder_should_customize_image(self, builder):
        """
        Allow or prohibit cloud agnostic image customization.

        @param builder The builder object.

        @return bool
        """

    def builder_will_customize_image(self, builder):
        """
        Invoked just before cloud agnostic image customization.

        @param builder The builder object.
        """

    def builder_did_customize_image(self, builder):
        """
        Invoked after cloud agnostic image customization.

        @param builder The builder object.
        """
