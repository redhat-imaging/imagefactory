# encoding: utf-8

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

import sys
import os
import argparse
import json
import logging
import props
from Singleton import Singleton
from imgfac.Version import VERSION as VERSION

class ApplicationConfiguration(Singleton):
    configuration = props.prop("_configuration", "The configuration property.")

    def _singleton_init(self):
        super(ApplicationConfiguration, self)._singleton_init()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.configuration = self.__parse_arguments()
        self.jeos_images = {}
        self.__parse_jeos_images()

    def __init__(self):
        pass

    def __new_argument_parser(self):
        main_description = """Image Factory is an application for creating system images to run virtual machines in various public and private \
                                clouds.  The imagefactory command can be used to start a daemon providing a QMFv2 agent interface, allowing for \
                                remote interaction.  An alternate method of running imagefactory allows for one-off image building and deployment \
                                and does not connect to a qpidd."""
        cli_build_description = """Build specified system and exit."""
        cli_push_description = """Push an image and exit."""
        warehouse_description = """Options for specifying Image Warehouse (http://aeolusproject.org/imagewarehouse.html) base URL and bucket names."""
        ec2_description = """Options specifying EC2 instance types to use for various functions"""
        rest_description = """Enable the RESTful interface."""

        argparser = argparse.ArgumentParser(description=main_description, prog='imagefactory', version=VERSION)
        argparser.add_argument('--verbose', action='store_true', default=False, help='Set verbose logging.')
        argparser.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
        argparser.add_argument('--image', help='UUID of iwhd image object to rebuild or push')
        argparser.add_argument('--foreground', action='store_true', default=False, help='Stay in the foreground and avoid launching a daemon. (default: %(default)s)')
        argparser.add_argument('--config', default='/etc/imagefactory/imagefactory.conf', help='Configuration file to use. (default: %(default)s)')
        argparser.add_argument('--imgdir', default='/tmp', help='Build image files in location specified. (default: %(default)s)')
        argparser.add_argument('--timeout', type=int, default=3600, help='Set the timeout period for image building in seconds. (default: %(default)s)')
        argparser.add_argument('--tmpdir', default='/tmp', help='Use the specified location for temporary files.  (default: %(default)s)')
        argparser.add_argument('--plugins', default='/etc/imagefactory/plugins.d', help='Plugin directory. (default: %(default)s)')
        argparser.add_argument('--jeos_imgdir', default='/etc/imagefactory/jeos_images/', help='JeOS image files in location specified. (default: %(default)s)')
        argparser.add_argument('--test_jeos_imgdir', default='conf/', help='JeOS image files when testing without installation. (default: %(default)s)')


        group_rest = argparser.add_argument_group(title='RESTful Interface', description=rest_description)
        group_rest.add_argument('--rest', action='store_true', default=False, help='Turn on the RESTful http interface. (default: %(default)s)')
        group_rest.add_argument('--port', type=int, default=8075, help='Port to attach the RESTful http interface to. (defaul: %(default)s)')
        group_rest.add_argument('--address', default='0.0.0.0', help='Interface address to listen to. (defaul: %(default)s)')
        group_rest.add_argument('--no_ssl', action='store_true', default=False, help='Turn off SSL. (default: %(default)s)')
        group_rest.add_argument('--ssl_pem', default='*', help='PEM certificate file to use for HTTPS access to the REST interface. (default: A transient certificate is generated at runtime.)')
        group_rest.add_argument('--no_oauth', action='store_true', default=False, help='Use 2 legged OAuth to protect the REST interface. (default: %(default)s)')

        group_qmf = argparser.add_argument_group(title='QMF agent', description="NO LONGER SUPPORTED")
        group_qmf.add_argument('--qmf', action='store_true', default=False, help='NO LONGER SUPPORTED')

        group_build = argparser.add_argument_group(title='Image building', description=cli_build_description)
        group_build.add_argument('--template', help='Template XML file to build from.')
        group_build.add_argument('--target', action='append', help='Cloud services to target (e.g. ec2, rhevm, vsphere, rackspace, condorcloud, etc.)')

        group_push = argparser.add_argument_group(title='Image pushing', description=cli_push_description)
        group_push.add_argument('--provider', action='append', help='Cloud service providers to push the image (e.g. ec2-us-east-1, rackspace, etc.)')
        group_push.add_argument('--credentials', help='Cloud provider credentials XML (i.e. <provider_credentials/> document)')

        group_ec2 = argparser.add_argument_group(title='EC2 activities', description=ec2_description)
        group_ec2.add_argument('--ec2-32bit-util', default = 'm1.small', help='Instance type to use when launching a 32 bit utility instance')
        group_ec2.add_argument('--ec2-64bit-util', default = 'm1.large', help='Instance type to use when launching a 64 bit utility instance')

        group_build = argparser.add_argument_group(title='Image importing', description=cli_build_description)
        group_build.add_argument('--target-image', help='Target specific identifier for the image to import.')
        group_build.add_argument('--image-desc', help='XML document describing the imported image.')

        group_warehouse = argparser.add_argument_group(title='Image Warehouse', description=warehouse_description)
        group_warehouse.add_argument('--warehouse', default='http://localhost:9090/', help='URL of the warehouse location to store images. (default: %(default)s)')
        group_warehouse.add_argument('--image_bucket', help='Name of warehouse bucket to look in images. (default: %(default)s)')
        group_warehouse.add_argument('--build_bucket', help='Name of warehouse bucket to look in builds. (default: %(default)s)')
        group_warehouse.add_argument('--target_bucket', help='Name of warehouse bucket to look in for target images. (default: %(default)s)')
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
        elif(sys.argv[0].endswith("imagefactory")):
            return self.argparser.parse_args()
        elif(sys.argv[0].endswith("unittest" or "nosetests")):
            return self.argparser.parse_args('--image_bucket unittests_images --build_bucket unittests_builds --target_bucket unittests_target_images --template_bucket unittests_templates --icicle_bucket unittests_icicles --provider_bucket unittests_provider_images'.split())
        else:
            return self.argparser.parse_args([])

    def __parse_arguments(self):
        self.argparser = self.__new_argument_parser()
        configuration = self.__parse_args()
        if (os.path.isfile(configuration.config)):
            try:
                def dencode(a_dict, encoding='ascii'):
                    new_dict = {}
                    for k,v in a_dict.items():
                        ek = k.encode(encoding)
                        if(isinstance(v, unicode)):
                            new_dict[ek] = v.encode(encoding)
                        elif(isinstance(v, dict)):
                            new_dict[ek] = dencode(v)
                        else:
                            new_dict[ek] = v
                    return new_dict

                config_file = open(configuration.config)
                uconfig = json.load(config_file)
                config_file.close()
                configuration = self.__parse_args(defaults=dencode(uconfig))
            except Exception, e:
                self.log.exception(e)
        return configuration.__dict__

    def __add_jeos_image(self, image_detail):
        # our multi-dimensional-dict has the following keys
        # target - provider - os - version - arch
        for i in range(6):
            image_detail[i] = image_detail[i].strip()

        ( target, provider, os, version, arch, provider_image_id) = image_detail
        if not (target in self.jeos_images):
            self.jeos_images[target] = {}
        if not (provider in self.jeos_images[target]):
            self.jeos_images[target][provider] = {}
        if not (os in self.jeos_images[target][provider]):
            self.jeos_images[target][provider][os] = {}
        if not (version in self.jeos_images[target][provider][os]):
            self.jeos_images[target][provider][os][version] = {}
        if arch in self.jeos_images[target][provider][os][version]:
            pass
            #TODO
            #We really should warn here but we have a bootstrap problem - loggin isn't initialized until after the singleton is created
            #self.log.warning("JEOS image defined more than once for %s - %s - %s - %s - %s" % (target, provider, os, version, arch))
            #self.log.warning("Replacing (%s) with (%s)" % (self.jeos_images[target][provider][os][version][arch], provider_image_id))

        self.jeos_images[target][provider][os][version][arch] = provider_image_id

    def __parse_jeos_images(self):
        # Loop through all JEOS configuration files to populate our jeos_images dictionary
        self.appconfig = self.configuration
        if os.path.exists(self.appconfig['jeos_imgdir']):
            config_path = self.appconfig['jeos_imgdir'] 
        else:
            # test path to allow for testing without install
            config_path = self.appconfig['test_jeos_imgdir']
        listing = os.listdir(config_path)
        for infile in listing:
            fileIN = open(config_path + infile, "r")
            line = fileIN.readline()

            while line:
                if line[0] == "#":
                    # Comment
                    pass
                if len(line.strip()) == 0:
                    # Whitespace
                    pass
                image_detail = line.split(":")
                if len(image_detail) == 6:
                    self.__add_jeos_image(image_detail)
                else:
                    pass
                    #TODO
                    #We really should warn here but we have a bootstrap problem - loggin isn't initialized until after the singleton is created
                    #self.log.warning("Found unparsable JEOS config line in (%s)" % (config_path + infile))

                line = fileIN.readline()
