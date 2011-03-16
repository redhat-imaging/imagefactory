from distutils.core import setup, Extension
import os

version_file = open("version.txt", "r")
VERSION = version_file.read()[0:-1]
version_file.close()

datafiles=[('/etc', ['imagefactory.conf']), ('', ['version.txt'])]

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
