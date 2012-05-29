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
#from props import prop


METADATA = ( )

class BaseImage(PersistentImage):
    """ TODO: Docstring for BaseImage  """

    def __init__(self, image_id=None):
        """ TODO: Fill me in
        
        @param template TODO
        """
        super(BaseImage, self).__init__(image_id)
        self.template = None

    def metadata(self):
        self.log.debug("Getting metadata in class (%s) my metadata is (%s)" % (self.__class__, METADATA))
        return frozenset(METADATA + super(self.__class__, self).metadata())
