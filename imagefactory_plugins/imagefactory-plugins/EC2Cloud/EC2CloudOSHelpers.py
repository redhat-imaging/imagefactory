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
import oz.RHEL_6
import oz.Fedora
from tempfile import *


class Base_ec2_Helper(object):

    def __init__(self, plugin):
        self.plugin = plugin

    def init_guest(self):
        raise ImageFactoryException("init_guest() not implemented in this helper")

    def ebs_pre_snapshot_tasks(self, guestaddr):
        pass

    def correct_remote_manifest(self, guestaddr, manifest):
        pass

    def install_euca_tools(self, guestaddr):
        pass

    def _init_guest_common(self):
        self.guest.diskimage = self.plugin.app_config["imgdir"] + "/base-image-" + self.plugin.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + self.plugin.new_image_id
        # Allow both us and the plugin to reference self.guest
        self.plugin.guest = self.guest



class RHEL5_ec2_Helper(Base_ec2_Helper):

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
            return super(RHEL5_ec2_Helper.RHEL5RemoteGuest, self).guest_execute_command(guestaddr, command, timeout, tunnels)

        def guest_live_upload(self, guestaddr, file_to_upload, destination,
                              timeout=30):
            return super(RHEL5_ec2_Helper.RHEL5RemoteGuest, self).guest_live_upload(guestaddr, file_to_upload, destination, timeout)

    def init_guest(self):
        self.guest = self.RHEL5RemoteGuest(self.plugin.tdlobj, self.plugin.oz_config, None)
        self._init_guest_common()

    def ebs_pre_shapshot_tasks(self, guestaddr):
        # The RHEL JEOS AMIs will refuse to inject the dynamic EC2 key if authorized_keys already exists
        # We have to remove it here.
        # NOTE: This means it is not possible for users to add a static authorized key during the build via a file or RPM
        self.log.debug("Removing existing authorized_keys file to allow key injection on RHEL reboot")
        self.guest.guest_execute_command(guestaddr, "[ -f /root/.ssh/authorized_keys ] && rm -f /root/.ssh/authorized_keys")

    def correct_remote_manifest(self, guestaddr, manifest):
        # We end up with a bogus block device mapping due to our EBS to S3 switch
        # cannot get euca-bundle-vol in RHEL5 EPEL to correct this so fix it manually - sigh
        # Remove entirely - we end up with the default root map to sda1 which is acceptable
        # TODO: Switch to a euca version that can produce sensible maps
        self.log.debug("Removing bogus block device mapping from remote manifest")
        self.guest.guest_execute_command(guestaddr, 'perl -p -i -e "s/<block_device_mapping\>.*<\/block_device_mapping>//" %s' % (manifest))

    def install_euca_tools(self, guestaddr):
        # For RHEL5 S3 snapshots we need to enable EPEL, install, then disable EPEL
        # TODO: This depends on external infra which is bad, and trusts external SW, which may be bad
        # For now we also mount up /mnt
        self.guest.guest_execute_command(guestaddr, "mount /dev/sdf /mnt")
        self.guest.guest_execute_command(guestaddr, "rpm -ivh http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-4.noarch.rpm")
        self.guest.guest_execute_command(guestaddr, "yum -y install euca2ools")
        self.guest.guest_execute_command(guestaddr, "rpm -e epel-release")



class RHEL6_ec2_Helper(Base_ec2_Helper):

    class RHEL6RemoteGuest(oz.RHEL_6.RHEL6Guest):
        def __init__(self, tdl, config, auto):
            # The debug output in the Guest parent class needs this property to exist
            self.host_bridge_ip = "0.0.0.0"
            oz.RHEL_6.RHEL6Guest.__init__(self, tdl, config, auto)

        def connect_to_libvirt(self):
            pass

        def guest_execute_command(self, guestaddr, command, timeout=30,
                                  tunnels=None):
            return super(RHEL6_ec2_Helper.RHEL6RemoteGuest, self).guest_execute_command(guestaddr, command, timeout, tunnels)

        def guest_live_upload(self, guestaddr, file_to_upload, destination,
                              timeout=30):
            return super(RHEL6_ec2_Helper.RHEL6RemoteGuest, self).guest_live_upload(guestaddr, file_to_upload, destination, timeout)

    def init_guest(self):
        self.guest = self.RHEL6RemoteGuest(self.plugin.tdlobj, self.plugin.oz_config, None)
        self._init_guest_common()

    def ebs_pre_shapshot_tasks(self, guestaddr):
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



class Fedora_ec2_Helper(Base_ec2_Helper):

    class FedoraRemoteGuest(oz.Fedora.FedoraGuest):
        def __init__(self, tdl, config, auto, nicmodel, haverepo, diskbus,
                     brokenisomethod):
            # The debug output in the Guest parent class needs this property to exist
            self.host_bridge_ip = "0.0.0.0"
            oz.Fedora.FedoraGuest.__init__(self, tdl, config, auto, nicmodel, haverepo, diskbus,
                     brokenisomethod)

        def connect_to_libvirt(self):
            pass

        def guest_execute_command(self, guestaddr, command, timeout=30,
                                  tunnels=None):
            return super(Fedora_ec2_Helper.FedoraRemoteGuest, self).guest_execute_command(guestaddr, command, timeout, tunnels)

        def guest_live_upload(self, guestaddr, file_to_upload, destination,
                              timeout=30):
            return super(Fedora_ec2_Helper.FedoraRemoteGuest, self).guest_live_upload(guestaddr, file_to_upload, destination, timeout)

    def init_guest(self):
        self.guest = self.FedoraRemoteGuest(self.plugin.tdlobj, self.plugin.oz_config, None,
                                           "virtio", True, "virtio", True)
        self._init_guest_common()

    def install_euca_tools(self, guestaddr):
        # For F13-F15 we now have a working euca2ools in the default repos
        self.guest.guest_execute_command(guestaddr, "yum -y install euca2ools")

    # correct_remote_manifest() and ebs_pre_snapshot_tasks() not needed - blanks versions inherited above

