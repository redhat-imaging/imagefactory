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

import oz.RHEL_5
import ConfigParser
from Fedora_ec2_Builder import Fedora_ec2_Builder

class RHEL5RemoteGuest(oz.RHEL_5.RHEL5Guest):
    def __init__(self, tdl, config, auto):
        # The debug output in the Guest parent class needs this property to exist
        self.host_bridge_ip = "0.0.0.0"
        # Add virtio as dummy arguments below - doesn't actually matter what we put
        oz.RHEL_5.RHEL5Guest.__init__(self, tdl, config, auto, "virtio",
                                      "virtio")

    def connect_to_libvirt(self):
        pass

    def guest_execute_command(self, guestaddr, command, timeout=30,
                              tunnels=None):
        return super(RHEL5RemoteGuest, self).guest_execute_command(guestaddr, command, timeout, tunnels)

    def guest_live_upload(self, guestaddr, file_to_upload, destination,
                          timeout=30):
        return super(RHEL5RemoteGuest, self).guest_live_upload(guestaddr, file_to_upload, destination, timeout)



class RHEL5_ec2_Builder(Fedora_ec2_Builder):
    def init_guest(self, guesttype):
        if guesttype == "local":
            self.guest = oz.RHEL_5.get_class(self.tdlobj, self.oz_config, None)
        else:
            self.guest = RHEL5RemoteGuest(self.tdlobj, self.oz_config, None)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + self.new_image_id

    def correct_remote_manifest(self, guestaddr, manifest):
        # We end up with a bogus block device mapping due to our EBS to S3 switch
        # cannot get euca-bundle-vol in RHEL5 EPEL to correct this so fix it manually - sigh
        # Remove entirely - we end up with the default root map to sda1 which is acceptable
        # TODO: Switch to a euca version that can produce sensible maps
        self.guest.guest_execute_command(guestaddr, 'perl -p -i -e "s/<block_device_mapping\>.*<\/block_device_mapping>//" %s' % (manifest))

    def install_euca_tools(self, guestaddr):
        # For RHEL5 we need to enable EPEL, install, then disable EPEL
        # TODO: This depends on external infra which is bad, and trusts external SW, which may be bad
        # For now we also mount up /mnt
        self.guest.guest_execute_command(guestaddr, "mount /dev/sdf /mnt")
        self.guest.guest_execute_command(guestaddr, "rpm -ivh http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-4.noarch.rpm")
        self.guest.guest_execute_command(guestaddr, "yum -y install euca2ools")
        self.guest.guest_execute_command(guestaddr, "rpm -e epel-release")
