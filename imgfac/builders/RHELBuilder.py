#
#   Copyright 2011 Red Hat, Inc.
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

import zope
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder

class RHELBuilder(BaseBuilder):
    """docstring for RHELBuilder"""
    zope.interface.implements(IBuilder)

# Initializer
    def __init__(self, template=None, target=None):
        super(RHELBuilder, self).__init__(template, target)

# Image actions
    def build_image(self, build_id=None):
        pass

    def abort(self):
        pass
