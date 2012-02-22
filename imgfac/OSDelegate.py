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

    def builder_should_create_image(self, builder):
        """
        Allow or prohibit a JEOS image to be created and customized with additional packages.
        
        @param builder The builder object creating the image.
    
        @return bool
        """

    def builder_will_create_image(self, builder):
        """
        Invoked just before the installation of a JEOS image.
        
        @param builder The builder object creating the image.
        """

    def builder_did_create_image(self, builder):
        """
        Invoked after the builder has completed the custom package installation.
        
        @param builder The builder object creating the image.
        """

    def builder_should_generate_icicle(self, builder):
        """
        Allow or prohibit generation of an ICICLE document for an image.
        
        @param builder The builder creating the ICICLE.
    
        @return bool
        """
        pass

    def builder_will_generate_icicle(self, builder):
        """
        Invoked just before an ICICLE document is generated for an image.
        
        @param builder The builder creating the ICICLE.
        """

    def builder_did_generate_icicle(self, builder):
        """
        Invoked after the builder has generated an ICICLE document for an image.
        
        @param builder The builder creating the ICICLE.
        """
