#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2010-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import sys
import os
import argparse
import json

class ApplicationConfiguration(object):
    instance = None
    
    def configuration():
        doc = "The configuration property."
        def fget(self):
            return self._configuration
        def fset(self, value):
            self._configuration = value
        def fdel(self):
            del self._configuration
        return locals()
    configuration = property(**configuration())
    
    
    def __new__(cls, *p, **k):
        if cls.instance is None:
            cls.instance = object.__new__(cls, *p, **k)
        return cls.instance
    
    def __init__(self):
        super(ApplicationConfiguration, self).__init__()
        self.configuration = {}
        arguments = self.parse_arguments()
        
        config_file_path = arguments.config
        if (os.path.isfile(config_file_path)):
            try:
                config_file = open(config_file_path)
                uconfig = json.load(config_file)
                # coerce this dict to ascii for python 2.6
                config = {}
                for k, v in uconfig.items():
                    config[k.encode('ascii')]=v.encode('ascii')
                self.configuration = self.parse_arguments(defaults=config).__dict__
            except IOError, e:
                logging.exception(e)
                self.configuration = arguments
            
    
    def parse_arguments(self, defaults=None):
        argparser = argparse.ArgumentParser(description='System image creation tool...', prog='imgfac')
        argparser.add_argument('--version', action='version', version='%(prog)s 0.1', help='Version info')
        argparser.add_argument('-v', '--verbose', action='store_true', default=False, help='Set verbose logging.')
        argparser.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
        argparser.add_argument('--foreground', action='store_true', default=False, help='Stay in the foreground and avoid launching a daemon. (default: %(default)s)')
        argparser.add_argument('--config', default='/etc/imagefactory.conf', help='Configuration file to use. (default: %(default)s)')
        argparser.add_argument('--imgdir', default='/tmp', help='Build image files in location specified. (default: %(default)s)')
        argparser.add_argument('--timeout', type=int, default=3600, help='Set the timeout period for image building in seconds. (default: %(default)s)')
        argparser.add_argument('--tmpdir', default='/tmp', help='Use the specified location for temporary files.  (default: %(default)s)')
        group_qmf = argparser.add_argument_group(title='QMF agent', description='Provide a QMFv2 agent interface.')
        group_qmf.add_argument('--qmf', action='store_true', default=False, help='Turn on QMF agent interface. (default: %(default)s)')
        group_qmf.add_argument('--qpidd', default='localhost', help='URL of qpidd to connect to. (default: %(default)s)')
        group_build = argparser.add_argument_group(title='Image building', description='NOT YET IMPLEMENTED: Build specified system and exit.')
        group_build.add_argument('--template', help='Template XML file to build from.')
        group_build.add_argument('--target', help='Cloud service to target')
        group_push = argparser.add_argument_group(title='Image instantiation', description='NOT YET IMPLEMENTED: Instantiate an image and exit.')
        group_push.add_argument('--image', help='Image to instantiate')
        group_push.add_argument('--provider', help='Cloud service provider upon which to instantiate the image')
        group_push.add_argument('--credentials', help='Cloud provider credentials')
        group_warehouse = argparser.add_argument_group(title='Image Warehouse', description='Options for specifying Image Warehouse base URL and bucket names.')
        group_warehouse.add_argument('--warehouse', default='http://localhost:9090/', help='URL of the warehouse location to store images. (default: %(default)s)')
        group_warehouse.add_argument('--image_bucket', help='Name of warehouse bucket to look in for images. (default: %(default)s)')
        group_warehouse.add_argument('--template_bucket', help='Name of warehouse bucket to look in for templates. (default: %(default)s)')
        group_warehouse.add_argument('--icicle_bucket', help='Name of warehouse bucket to look in for icicles. (default: %(default)s)')
        group_warehouse.add_argument('--provider_bucket', help='Name of warehouse bucket to look in for provider image instances. (default: %(default)s)')
        
        if(defaults):
            argparser.set_defaults(**defaults)
        
        if (sys.argv[0].endswith("imgfac.py")):
            return argparser.parse_args()
        elif(sys.argv[0].endswith("unittest")):
            return argparser.parse_args('--image_bucket unittests_images --template_bucket unittests_templates --icicle_bucket unittests_icicles --provider_bucket unittests_provider_images'.split())
        else:
            return argparser.parse_args([])
    
