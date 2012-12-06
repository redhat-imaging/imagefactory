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
import subprocess
import sys

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
        try:
            required_module = 'guestfs'
            __import__(required_module)
        except:
            info_url = 'http://imgfac.org/documentation/dependencies'
            print('###################\nSetup cannot continue due to missing dependencies that are not installed by this script: %s\nPlease see %s for more information regarding pre-install dependencies.' % (required_module, info_url))
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

# Set the version in imgfac/Version.py
# used when returning version from the rest api or cli
version_file_path = "imgfac/Version.py"
version_file = open(version_file_path, 'w')
version_file.write('VERSION = "%s"' % pkg_version)
version_file.close()

datafiles=[('share/man/man1', ['documentation/man/imagefactory.1', 'documentation/man/imagefactoryd.1']),
           ('share/man/man5', ['documentation/man/imagefactory.conf.5']),
           ('share/man/man7', ['documentation/man/imagefactory.rest.7']),
           ('/etc/imagefactory', ['imagefactory.conf']),
           ('/etc/pki/imagefactory', ['cert-ec2.pem']),
           ('/etc/sysconfig', ['conf/sysconfig/imagefactoryd']),
           ('/etc/logrotate.d', ['conf/logrotate.d/imagefactoryd']),
           ('/etc/rc.d/init.d', ['scripts/imagefactoryd'])]

dependencies=['pycurl', 'zope.interface', 'libxml2.python', 'httplib2',
              'argparse', 'PasteDeploy', 'oauth2', 'bottle', 'pymongo',
              'requests', 'requests-oauth2']

setup(name='imagefactory',
      version=pkg_version,
      description='imagefactory system image generation tool',
      author='Red Hat, Inc. and Contributors',
      author_email='imcleod@redhat.com',
      license='Apache License, Version 2.0',
      url='http://imgfac.org',
      packages=['imgfac', 'imgfac.rest', 'imgfac.picklingtools', 'imgfac.secondary'],
      scripts=['imagefactory', 'imagefactoryd'],
      data_files = datafiles,
      install_requires = dependencies,
      cmdclass={'easy_install': easy_install}
      )
