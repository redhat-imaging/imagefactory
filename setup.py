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

try:
    (pkg_version, ignore, ignore) = subprocess_check_output('/usr/bin/git describe | tr - _', shell=True)
    pkg_version = pkg_version.rstrip('\n')
except:
    pkg_version = 9999

def create_version_py():
    version_file_path = "imgfac/Version.py"
    version_file = open(version_file_path, 'w')
    version_file.write('VERSION = "%s"' % pkg_version)
    version_file.close()

def modify_specfile():
    cmd = (' sed -e "s/@VERSION@/%s/g" < imagefactory.spec.in ' % pkg_version) + " > imagefactory.spec"
    print cmd
    #cmd = (""" sed -e "s/@VERSION@/%s/g" < imagefactory.spec.in """ % pkg_version) + " > imagefactory.spec"
    os.system(cmd)

datafiles=[('share/man/man1', ['Documentation/man/imagefactory.1', 'Documentation/man/imagefactoryd.1']),
           ('/etc/imagefactory', ['imagefactory.conf']),
           ('/etc/pki/imagefactory', ['cert-ec2.pem']),
           ('/etc/sysconfig', ['imagefactoryd']),
           ('/etc/logrotate.d', ['imagefactoryd']),
           ('/etc/rc.d/init.d', ['scripts/imagefactoryd'])]

class sdist(_sdist):
    """ custom sdist command to prepare imagefactory.spec file """
    def run(self):
        create_version_py()
        modify_specfile()
        _sdist.run(self)

setup(name='imagefactory',
      version=pkg_version,
      description='Image Factory system image generation tool',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='Apache License, Version 2.0',
      url='http://www.aeolusproject.org/imagefactory.html',
      packages=['imgfac', 'imgfac.rest'],
      scripts=['imagefactory', 'imagefactoryd'],
      data_files = datafiles,
      cmdclass = {'sdist': sdist}
      )
