from distutils.core import setup, Extension
import os
import os.path
import subprocess

version_file_name = "version.txt"
try:
    if(not os.path.exists(version_file_name)):
        subprocess.call('/usr/bin/git describe > %s' % (version_file_name, ), shell=True)
    version_file = open(version_file_name, "r")
    VERSION = version_file.read()[0:-1]
    version_file.close()
except Exception, e:
    raise RuntimeError("ERROR: version.txt could not be found.  Run 'git describe > version.txt' to get the correct version info.")

datafiles=[('/etc', ['imagefactory.conf']), ('/etc/pki/imagefactory', ['cert-ec2.pem']),    ('/etc/rc.d/init.d', ['imagefactory/scripts/imagefactory']), ('', ['version.txt'])]

setup(name='imagefactory',
      version=VERSION,
      description='Image Factory system image generation tool',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='GPLv2',
      url='http://www.aeolusproject.org/imagefactory.html',
      packages=['imagefactory', 'imagefactory.builders', 'imagefactory.qmfagent'],
      scripts=['imgfac.py'],
      data_files = datafiles,
      )
