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

import re
import os
from Fedora_vsphere_Builder import Fedora_vsphere_Builder
from tempfile import NamedTemporaryFile

class RHEL5_vsphere_Builder(Fedora_vsphere_Builder):
    def __init__(self, template, target, config_block = None):
        super(RHEL5_vsphere_Builder, self).__init__(template, target, config_block)

    def modify_guest(self):
        # We swap out the default kickstart for one that forces mptspi
        # This results in a bootable guest both during KVM customize and when
        # run on vsphere
        # By adding this at JEOS install time we leave open the possibility
        # of modifying the module/boot environment during customization,
        # for example, via the install of vmware tools.
        
        # Use this just to get a known unique temp file name
        new_kickstart = NamedTemporaryFile(delete = False)
        new_kickstart_name = new_kickstart.name
        new_kickstart.close()

        # This step does the rootpw substitution for us
        # modified file ends up in new_kickstart_name
        # This is slightly naughty since we use an internal Oz function
        self.guest._copy_kickstart(new_kickstart_name)

        # read the now root-pw-substituted kickstart
        new_kickstart = open(new_kickstart_name, "r")        
        ks_lines = new_kickstart.readlines()
        new_kickstart.close()

        # Add our device line
        new_kickstart = open(new_kickstart_name, "w")
        for ks_line in ks_lines:
            new_kickstart.write(ks_line)
            if re.match("install", ks_line):
                new_kickstart.write("device scsi mptspi\n")
        new_kickstart.close()

        # Tell Oz that we want it to use this ks.cfg rather than the built in one
        self.guest.auto = new_kickstart_name

    def builder_cleanup(self):
        if os.path.isfile(self.guest.auto):
            os.unlink(self.guest.auto)
