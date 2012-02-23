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

    def create_image(self, builder):
        """
        Create a JEOS image to be used as the basis for customization.

        @param builder The builder object.
        """

    def install_packages(self, builder):
        """
        Installs any packages specified beyond the JEOS and generates an ICICLE
        document for the image.

        @param builder The builder object.
        """

    def customize_image_for_builder(self, builder):
        """
        Performs cloud agnostic customizaion of the image.

        @param builder The builder object.
        """
