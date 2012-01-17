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
from tempfile import *
from Fedora_ec2_Builder import Fedora_ec2_Builder

class RHEL6RemoteGuest(oz.RHEL_6.RHEL6Guest):
    def __init__(self, tdl, config, auto):
        # The debug output in the Guest parent class needs this property to exist
        self.host_bridge_ip = "0.0.0.0"
        oz.RHEL_6.RHEL6Guest.__init__(self, tdl, config, auto)

    def connect_to_libvirt(self):
        pass

    def guest_execute_command(self, guestaddr, command, timeout=30,
                              tunnels=None):
        return super(RHEL6RemoteGuest, self).guest_execute_command(guestaddr, command, timeout, tunnels)

    def guest_live_upload(self, guestaddr, file_to_upload, destination,
                          timeout=30):
        return super(RHEL6RemoteGuest, self).guest_live_upload(guestaddr, file_to_upload, destination, timeout)



class RHEL6_ec2_Builder(Fedora_ec2_Builder):
    def init_guest(self, guesttype):
        if guesttype == "local":
            self.guest = oz.RHEL_6.get_class(self.tdlobj, self.oz_config, None)
        else:
            self.guest = RHEL6RemoteGuest(self.tdlobj, self.oz_config, None)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + self.new_image_id

    def ebs_pre_shapshot_tasks(self, guestaddr):
        # We have to add the audrey conditional
        self.log.info("Updating rc.local with Audrey conditional")
        audrey_file_object = NamedTemporaryFile()
        audrey_file_object.write(self.rc_local_all)
        audrey_file_object.flush()
        self.guest.guest_live_upload(guestaddr, audrey_file_object.name, "/tmp/rc.local.append")
        self.guest.guest_execute_command(guestaddr, "cat /tmp/rc.local.append >> /etc/rc.local")
        audrey_file_object.close()

        # The RHEL JEOS AMIs will refuse to inject the dynamic EC2 key if authorized_keys already exists
        # We have to remove it here.
        # NOTE: This means it is not possible for users to add a static authorized key during the build via a file or RPM
        self.log.debug("Removing existing authorized_keys file to allow key injection on RHEL reboot")
        self.guest.guest_execute_command(guestaddr, "[ -f /root/.ssh/authorized_keys ] && rm -f /root/.ssh/authorized_keys")

    def install_euca_tools(self, guestaddr):
        # For RHEL6 we need to enable EPEL, install, then disable EPEL
        # TODO: This depends on external infra which is bad, and trusts external SW, which may be bad
        # For now we also mount up /mnt
        self.guest.guest_execute_command(guestaddr, "mount /dev/xvdj /mnt")
        self.guest.guest_execute_command(guestaddr, "rpm -ivh http://download.fedora.redhat.com/pub/epel/6/i386/epel-release-6-5.noarch.rpm")
        self.guest.guest_execute_command(guestaddr, "yum -y install euca2ools")
        self.guest.guest_execute_command(guestaddr, "rpm -e epel-release")
