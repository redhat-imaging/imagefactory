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
import logging
import props

class ApplicationConfiguration(object):
    instance = None

    configuration = props.prop("_configuration", "The configuration property.")

    def __new__(cls, *p, **k):
        if cls.instance is None:
            i = super(ApplicationConfiguration, cls).__new__(cls, *p, **k)
            #initialize here, not in __init__()
            i.log = logging.getLogger('%s.%s' % (__name__, i.__class__.__name__))

            i.configuration = i.__parse_arguments()

            cls.instance = i
        elif(len(p) | len(k) > 0):
            cls.instance.log.warn('Attempted re-initialize of singleton: %s' % (cls.instance, ))
        return cls.instance

    def __init__(self):
            pass

    def __new_argument_parser(self):
        main_description = """Image Factory is an application for creating system images to run virtual machines in various public and private \
                                clouds.  The imgfac command can be used to start a daemon providing a QMFv2 agent interface, allowing for \
                                remote interaction.  An alternate method of running imgfac allows for one-off image building and deployment \
                                and does not connect to a qpidd."""
        qmf_description = """Provide a QMFv2 agent interface. (see https://cwiki.apache.org/qpid/qmfv2-project-page.html for more information)"""
        cli_build_description = """Build specified system and exit."""
        cli_push_description = """Instantiate an image and exit."""
        warehouse_description = """Options for specifying Image Warehouse (http://aeolusproject.org/imagewarehouse.html) base URL and bucket names."""

        argparser = argparse.ArgumentParser(description=main_description, prog='imgfac')
        argparser.add_argument('--version', action='version', version='%(prog)s 0.1', help='Version info')
        argparser.add_argument('-v', '--verbose', action='store_true', default=False, help='Set verbose logging.')
        argparser.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
        argparser.add_argument('--foreground', action='store_true', default=False, help='Stay in the foreground and avoid launching a daemon. (default: %(default)s)')
        argparser.add_argument('--config', default='/etc/imagefactory.conf', help='Configuration file to use. (default: %(default)s)')
        argparser.add_argument('--imgdir', default='/tmp', help='Build image files in location specified. (default: %(default)s)')
        argparser.add_argument('--timeout', type=int, default=3600, help='Set the timeout period for image building in seconds. (default: %(default)s)')
        argparser.add_argument('--tmpdir', default='/tmp', help='Use the specified location for temporary files.  (default: %(default)s)')
        group_qmf = argparser.add_argument_group(title='QMF agent', description=qmf_description)
        group_qmf.add_argument('--qmf', action='store_true', default=False, help='Turn on QMF agent interface. (default: %(default)s)')
        group_qmf.add_argument('--qpidd', default='localhost', help='URL of qpidd to connect to. (default: %(default)s)')
        group_build = argparser.add_argument_group(title='Image building', description=cli_build_description)
        group_build.add_argument('--template', help='Template XML file to build from.')
        group_build.add_argument('--target', help='Cloud service to target')
        group_push = argparser.add_argument_group(title='Image instantiation', description=cli_push_description)
        group_push.add_argument('--image', help='Image to instantiate')
        group_push.add_argument('--provider', help='Cloud service provider upon which to instantiate the image')
        group_push.add_argument('--credentials', help='Cloud provider credentials')
        group_warehouse = argparser.add_argument_group(title='Image Warehouse', description=warehouse_description)
        group_warehouse.add_argument('--warehouse', default='http://localhost:9090/', help='URL of the warehouse location to store images. (default: %(default)s)')
        group_warehouse.add_argument('--image_bucket', help='Name of warehouse bucket to look in for images. (default: %(default)s)')
        group_warehouse.add_argument('--template_bucket', help='Name of warehouse bucket to look in for templates. (default: %(default)s)')
        group_warehouse.add_argument('--icicle_bucket', help='Name of warehouse bucket to look in for icicles. (default: %(default)s)')
        group_warehouse.add_argument('--provider_bucket', help='Name of warehouse bucket to look in for provider image instances. (default: %(default)s)')

        return argparser

    def __parse_args(self, defaults=None):
        if(defaults):
            self.argparser.set_defaults(**defaults)
        if(len(sys.argv) == 1):
            self.argparser.print_help()
            sys.exit()
        elif(sys.argv[0].endswith("imgfac.py")):
            return self.argparser.parse_args()
        elif(sys.argv[0].endswith("unittest")):
            return self.argparser.parse_args('--image_bucket unittests_images --template_bucket unittests_templates --icicle_bucket unittests_icicles --provider_bucket unittests_provider_images'.split())
        else:
            return self.argparser.parse_args([])

    def __parse_arguments(self):
        self.argparser = self.__new_argument_parser()
        configuration = self.__parse_args()
        if (os.path.isfile(configuration.config)):
            try:
                config_file = open(configuration.config)
                uconfig = json.load(config_file)
                # coerce this dict to ascii for python 2.6
                config = {}
                for k, v in uconfig.items():
                    config[k.encode('ascii')]=v.encode('ascii')
                configuration = self.__parse_args(defaults=config)
            except IOError, e:
                i.log.exception(e)
        return configuration.__dict__
