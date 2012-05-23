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
import os
import os.path
import subprocess

#version_file_path = "imgfac/Version.py"
#version_file = open(version_file_path, 'w')
pkg_version = subprocess.check_output('/usr/bin/git describe | tr - _', shell=True).rstrip('\n')
#version_file.write('VERSION = "%s"' % pkg_version)
#version_file.close()

#datafiles=[('share/man/man1', ['Documentation/man/imagefactory.1']),
#           ('/etc/imagefactory', ['imagefactory.conf']),
#           ('/etc/pki/imagefactory', ['cert-ec2.pem']),
#           ('/etc/sysconfig', ['imagefactory']),
#           ('/etc/logrotate.d', ['imagefactory']),
#           ('/etc/rc.d/init.d', ['scripts/imagefactory'])]

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
      package_dir = {'imagefactory-plugins': ''},
      packages=['imagefactory-plugins.EC2Cloud', 'imagefactory-plugins.FedoraOS'],
      cmdclass = {'sdist': sdist}
      )
