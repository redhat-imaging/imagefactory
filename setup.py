from distutils.core import setup, Extension
import os

VERSION = '0.1.5'

datafiles=[('/etc', ['imagefactory.conf']), ('/etc/rc.d/init.d', ['imagefactory/scripts/imagefactory'])]

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
