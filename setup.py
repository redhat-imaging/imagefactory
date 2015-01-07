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
import subprocess
import time

VERSION = '1.1.7'
RELEASE = '1'

class sdist(_sdist):
    """ custom sdist command, to prep imagefactory.spec file """

    def run(self):
        global VERSION
        global RELEASE

        # Create a development release string for later use
        git_head = subprocess.Popen("git log -1 --pretty=format:%h",
                                    shell=True,
                                    stdout=subprocess.PIPE).communicate()[0].strip()
        date = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        git_release = "%sgit%s" % (date, git_head)

        # Expand macros in imagefactory.spec.in
        spec_in = open('imagefactory.spec.in', 'r')
        spec = open('imagefactory.spec', 'w')
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

        # Create Version.py to allow internal version repording via the API
        version_out = open("imgfac/Version.py", 'w')
        version_out.write('VERSION = "%s-%s"\n' % (VERSION, RELEASE))
        version_out.close()

        # Run parent constructor
        _sdist.run(self)

datafiles=[('/etc/imagefactory', ['imagefactory.conf']),
           ('/etc/pki/imagefactory', ['cert-ec2.pem']),
           ('/etc/sysconfig', ['conf/sysconfig/imagefactoryd']),
           ('/etc/logrotate.d', ['conf/logrotate.d/imagefactoryd']),
           ('/etc/rc.d/init.d', ['scripts/imagefactoryd'])]

setup(name='imagefactory',
      version=VERSION,
      description='Image Factory system image generation tool',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='Apache License, Version 2.0',
      url='http://www.aeolusproject.org/imagefactory.html',
      packages=['imgfac', 'imgfac.rest', 'imgfac.picklingtools'],
      scripts=['imagefactory', 'imagefactoryd'],
      data_files = datafiles,
      cmdclass = {'sdist': sdist}
      )
