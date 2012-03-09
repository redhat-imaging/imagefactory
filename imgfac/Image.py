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

from BaseImage import BaseImage
from props import prop

class Image(BaseImage):
    """ TODO: Docstring for Image  """

    target_image = prop("_target_image")
    provider = prop("_provider")
    credentials = prop("_credentials")
    parameters = prop("_parameters")

    def __init__(self, target_image, provider, credentials, parameters):
        """ TODO: Fill me in
        
        @param template TODO
        @param target_img_id TODO
        """
        super(Image, self).init()
        self.target_image = target_image
        self.provider = provider
        self.credentials = credentials
        self.parameters = parameters
