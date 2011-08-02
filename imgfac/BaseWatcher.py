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

class BaseWatcher(object):
    def __init__(self, image_id, build_id, remaining, warehouse):
        self.remaining = remaining
        self.warehouse = warehouse
        self.image_id = image_id
        self.build_id = build_id

    def completed(self):
        self.remaining -= 1
        if self.remaining == 0:
            self.all_completed()

    def all_completed(self):
        pass

    def _image_attr(self, attr):
        return self.warehouse.metadata_for_id_of_type([attr], self.image_id, 'image')[attr]

    def _set_image_attr(self, attr, value):
        self.warehouse.set_metadata_for_id_of_type({attr : value}, self.image_id, 'image')

    def _latest_build(self):
        return self._image_attr('latest_build')

    def _set_latest_build(self, build_id):
        self._set_image_attr('latest_build', build_id)

    def _latest_unpushed(self):
        return self._image_attr('latest_unpushed')

    def _set_latest_unpushed(self, build_id):
        self._set_image_attr('latest_unpushed', build_id)

    def _set_build_parent(self, parent_id):
        self.warehouse.set_metadata_for_id_of_type({'parent' : parent_id}, self.build_id, 'build')
