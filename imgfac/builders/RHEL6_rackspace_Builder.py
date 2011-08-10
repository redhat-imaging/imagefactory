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

import oz.RHEL_6
import ConfigParser
from Fedora_rackspace_Builder import Fedora_rackspace_Builder

class RHEL6RemoteGuest(oz.RHEL_6.RHEL6Guest):
    def __init__(self, tdl, config, auto):
        # The debug output in the Guest parent class needs this property to exist
        self.host_bridge_ip = "0.0.0.0"
        oz.RHEL_6.RHEL6Guest.__init__(self, tdl, config, auto)

    def connect_to_libvirt(self):
        pass

class RHEL6_rackspace_Builder(Fedora_rackspace_Builder):
    def init_guest(self):
        self.guest = RHEL6RemoteGuest(self.tdlobj, self.oz_config, None)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + self.new_image_id
