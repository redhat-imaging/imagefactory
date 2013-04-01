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

# ****** IF ADDING A NEW PLUGIN ******
# If your plugin follows the standard format, all you should need to do is add the name
# here.  If this doesn't work, you'll have to dig into the details below

plugins = ['EC2', 'TinMan','MockCloud','MockOS', 'OpenStack',
           'RHEVM', 'vSphere']


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

#version_file_path = "imgfac/Version.py"
#version_file = open(version_file_path, 'w')
(pkg_version, ignore, ignore) = subprocess_check_output('/usr/bin/git describe | tr - _', shell=True)
pkg_version = pkg_version.rstrip('\n')
#version_file.write('VERSION = "%s"' % pkg_version)
#version_file.close()

site_pkgs = get_python_lib()
datafiles = [('/etc/imagefactory/jeos_images', ['conf/ec2_fedora_jeos.conf', 'conf/ec2_rhel_jeos.conf'])]
packages = [ 'imagefactory_plugins' ]

for plugin in plugins:
    datafiles.append( (site_pkgs + '/imagefactory_plugins/' + plugin, [ plugin + '/' + plugin + '.info' ]) )
    packages.append( "imagefactory_plugins." + plugin )

class sdist(_sdist):
    """ custom sdist command to prepare imagefactory-plugins.spec file """
    def run(self):
        cmd = (""" sed -e "s/@VERSION@/%s/g" < imagefactory-plugins.spec.in """ % pkg_version) + " > imagefactory-plugins.spec"
        os.system(cmd)
        _sdist.run(self)

setup(name='imagefactory-plugins',
      version=pkg_version,
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
