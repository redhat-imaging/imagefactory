from distutils.core import setup, Extension
import os

VERSION = '0.0.1'

datafiles=[('/etc', ['imagefactory.conf'])]

setup(name='image_factory',
      version=VERSION,
      description='Image Factory system image generation tool',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='GPLv2',
      url='http://aeolusproject.et3.redhat.com/',
      package_dir={'image_factory': ''},
      #package_data={'image': ['auto/*', 'guesttools/*']},
      packages=['image_factory.builders', 'image_factory.qmfagent'],
      py_modules=['image_factory.ApplicationConfiguration'],
      scripts=['imagefactory.py'],
      data_files = datafiles,
      )
