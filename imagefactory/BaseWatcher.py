# Copyright (C) 2010-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

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
