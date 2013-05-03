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

from PersistentImage import PersistentImage
from props import prop


METADATA = ('target_image_id', 'provider', 'identifier_on_provider', 'provider_account_identifier', 'parameters')

class ProviderImage(PersistentImage):
    """ TODO: Docstring for ProviderImage  """

    target_image_id = prop("_target_image_id")
    provider = prop("_provider")
    identifier_on_provider = prop("_identifier_on_provider")
    provider_account_identifier = prop("_provider_account_identifier")
    credentials = prop("_credentials")
    parameters = prop("_parameters")

    def __init__(self, image_id=None):
        """ TODO: Fill me in
        
        @param template TODO
        @param target_img_id TODO
        """
        super(ProviderImage, self).__init__(image_id)
        self.target_image_id = None
        self.provider = None
        self.identifier_on_provider = None
        self.provider_account_identifier = None
        self.credentials = None
        self.parameters = None

    def metadata(self):
        self.log.debug("Executing metadata in class (%s) my metadata is (%s)" % (self.__class__, METADATA))
        return frozenset(METADATA + super(self.__class__, self).metadata())
