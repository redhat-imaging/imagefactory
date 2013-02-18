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

import logging
import zope
from imgfac.OSDelegate import OSDelegate
from imgfac.BaseImage import BaseImage
from imgfac.TargetImage import TargetImage

class MockRPMBasedOS(object):
    zope.interface.implements(OSDelegate)

    def __init__(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def create_base_image(self, builder, template, parameters):
        self.log.info('create_base_image() called in MockRPMBasedOS')
        mock_image_file = open(builder.base_image.data, "w")
        mock_image_file.write("MockRPMBasedOS base_image file for id (%s)" % builder.base_image.identifier)
        mock_image_file.close()
        #return BaseImage(template)

    def create_target_image(self, builder, target, base_image, parameters):
        self.log.info('create_target_image() called in MockRPMBasedOS')
        mock_image_file = open(builder.target_image.data, "w")
        mock_image_file.write("MockRPMBasedOS target_image file for id (%s)" % builder.target_image.identifier)
        mock_image_file.close()
        #return TargetImage(base_image, target, parameters)
