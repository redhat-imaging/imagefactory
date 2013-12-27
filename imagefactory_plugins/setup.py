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

from distutils.core import setup
from distutils.command.sdist import sdist as _sdist
from distutils.sysconfig import get_python_lib
import os
import os.path
import subprocess
import time

# ****** IF ADDING A NEW PLUGIN ******
# If your plugin follows the standard format, all you should need to do is add the name
# here.  If this doesn't work, you'll have to dig into the details below

plugins = ['EC2', 'TinMan','MockCloud','MockOS', 'OpenStack',
           'RHEVM', 'vSphere', 'Rackspace', 'IndirectionCloud',
           'OVA', 'Docker']

VERSION = '1.1.4'
RELEASE = '0'

class sdist(_sdist):
    """ custom sdist command, to prep imagefactory-plugins.spec file """

    def run(self):
        global VERSION
        global RELEASE

        # Create a development release string for later use
        git_head = subprocess.Popen("git log -1 --pretty=format:%h",
                                    shell=True,
                                    stdout=subprocess.PIPE).communicate()[0].strip()
        date = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        git_release = "%sgit%s" % (date, git_head)

        # Expand macros in imagefactory-plugins.spec.in
        spec_in = open('imagefactory-plugins.spec.in', 'r')
        spec = open('imagefactory-plugins.spec', 'w')
        for line in spec_in.xreadlines():
            if "@VERSION@" in line:
                line = line.replace("@VERSION@", VERSION)
            elif "@RELEASE@" in line:
                # If development release, include date+githash in %{release}
                if RELEASE.startswith('0'):
                    RELEASE += '.' + git_release
                line = line.replace("@RELEASE@", RELEASE)
            spec.write(line)
        spec_in.close()
        spec.close()

        # Run parent constructor
        _sdist.run(self)


site_pkgs = get_python_lib()
datafiles = [('/etc/imagefactory/jeos_images', ['conf/ec2_fedora_jeos.conf', 'conf/ec2_rhel_jeos.conf', 'conf/rackspace_fedora_jeos.conf', 'conf/rackspace_rhel_jeos.conf'])]
packages = [ 'imagefactory_plugins' ]

for plugin in plugins:
    datafiles.append( (site_pkgs + '/imagefactory_plugins/' + plugin, [ plugin + '/' + plugin + '.info' ]) )
    packages.append( "imagefactory_plugins." + plugin )

# ovfcommon is not a proper plugin, so add it separately
packages.append( "imagefactory_plugins.ovfcommon" )

setup(name='imagefactory-plugins',
      version=VERSION,
      description='Default plugins for the Image Factory system image generation tool',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='Apache License, Version 2.0',
      url='http://www.aeolusproject.org/imagefactory.html',
      package_dir = {'imagefactory_plugins': ''},
      scripts = [ 'EC2/create-ec2-factory-credentials' ],
      packages=packages,
      cmdclass = {'sdist': sdist},
      data_files = datafiles
      )
