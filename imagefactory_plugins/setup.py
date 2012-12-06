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

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
from setuptools.command.easy_install import easy_install as _easy_install
from distutils.sysconfig import get_python_lib
from distutils.spawn import find_executable
import subprocess
import sys


# ****** IF ADDING A NEW PLUGIN ******
# If your plugin follows the standard format, all you should need to do is add the name
# here.  If this doesn't work, you'll have to dig into the details below

plugins = ['EC2Cloud', 'FedoraOS','MockSphere','MockRPMBasedOS', 'OpenStackCloud',
           'RHEVM', 'vSphere']

depflag = "--install-no-deps"
if depflag in sys.argv:
    sys.argv.pop(sys.argv.index(depflag))
    NO_DEPENDENCIES = True
else:
    NO_DEPENDENCIES = False

class easy_install(_easy_install):
    def check_preinstall_deps(self):
        # There are some things we cannot install via setuptools. Until we take on
        # providing pre/post install magic to install these things, we need to let
        # the user know what we need and how to get it installed in order to proceed.
        # Note: this check should be made more generic if we end up with more than a few
        # things to check. For now, this will suffice.
        missing_dependencies = []
        try:
            required_module = 'oz'
            __import__(required_module)
        except:
            missing_dependencies.append(required_module)
        # check for one of the commands we use from euca2ools
        if(not find_executable('euca-bundle-image')):
            missing_dependencies.append('euca2ools')

        if(len(missing_dependencies) > 0):
            info_url = 'http://imgfac.org/documentation/dependencies'
            print('###############################\nSetup cannot continue due to missing dependencies that are not installed by this script: %s\nPlease see %s for more information regarding pre-install dependencies.' % (missing_dependencies, info_url))
            exit(1)
    
    def easy_install(self, spec, deps=False):
        # This allows us to use "setup.py install" in our SPEC file without getting auto deps
        if NO_DEPENDENCIES:
            _easy_install.easy_install(self, spec, False)
        else:
            self.check_preinstall_deps()
            _easy_install.easy_install(self, spec, True)

# Required for Python 2.6 backwards compat
def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    stdout, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = ' '.join(*popenargs)
        raise Exception("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)

# Generate the version string from git
try:
    # see http://peak.telecommunity.com/DevCenter/setuptools#specifying-your-project-s-version
    cmd = 'git describe'
    (pkg_version, ignore, ignore) = subprocess_check_output(cmd, shell=True)
    version_parts = pkg_version.rstrip('\n').split('-')
    if(len(version_parts) > 1):
        version_parts[1] = 'dev' + version_parts[1]
    pkg_version = '.'.join(version_parts)
except:
    unknown_version = '0.0.unknown.version'
    print('%s not found! Unable to set version string, using "%s"' % (cmd, unknown_version))
    pkg_version = unknown_version

site_pkgs = get_python_lib()
datafiles = [('/etc/imagefactory/jeos_images', ['conf/ec2_fedora_jeos.conf', 'conf/ec2_rhel_jeos.conf'])]
packages = [ 'imagefactory_plugins' ]
dependencies = ['glance', 'boto', 'pshere', 'ovirt-engine-sdk>=3.1.0']

for plugin in plugins:
    # TODO: This really needs to set the version in each plugin's .info file as well.
    datafiles.append( (site_pkgs + '/imagefactory_plugins/' + plugin, [ plugin + '/' + plugin + '.info' ]) )
    packages.append( "imagefactory_plugins." + plugin )

setup(name='imagefactory-plugins',
      version=pkg_version,
      description='Default plugins for the Image Factory system image generation tool',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='Apache License, Version 2.0',
      url='http://www.aeolusproject.org/imagefactory.html',
      package_dir = {'imagefactory_plugins': ''},
      scripts = [ 'EC2Cloud/create-ec2-factory-credentials' ],
      packages=packages,
      data_files = datafiles,
      install_requires = dependencies,
      cmdclass={'easy_install': easy_install}
      )
