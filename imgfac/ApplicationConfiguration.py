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
        if not 'debug' in self.configuration:
            # Slightly confusing, I know - For daemon mode we have a debug argument with default False
            # For cli, we debug by default and have a nodebug argument with default False
            # Rest of the code assumes a 'debug' value in app_config so set it here
            self.configuration['debug'] = not self.configuration['nodebug']
        if not 'secondary' in self.configuration:
            # We use this in the non-daemon context so it needs to be set
            # TODO: Something cleaner?
            self.configuration['secondary'] = False
        self.jeos_images = {}
        self.__parse_jeos_images()

    def __init__(self):
        pass

    def __new_argument_parser(self, appname):
        main_description = """Image Factory is an application for creating system images for use on public and private clouds."""

        argparser = argparse.ArgumentParser(description=main_description, prog=appname, version=VERSION)
        argparser.add_argument('--verbose', action='store_true', default=False, help='Set verbose logging.')
        argparser.add_argument('--config', default='/etc/imagefactory/imagefactory.conf', help='Configuration file to use. (default: %(default)s)')
        argparser.add_argument('--imgdir', default='/tmp', help='Build image files in location specified. (default: %(default)s)')
        argparser.add_argument('--timeout', type=int, default=3600, help='Set the timeout period for image building in seconds. (default: %(default)s)')
        argparser.add_argument('--tmpdir', default='/tmp', help='Use the specified location for temporary files.  (default: %(default)s)')
        argparser.add_argument('--plugins', default='/etc/imagefactory/plugins.d', help='Plugin directory. (default: %(default)s)')

        group_ec2 = argparser.add_argument_group(title='EC2 settings')
        group_ec2.add_argument('--ec2-32bit-util', default = 'm1.small', help='Instance type to use when launching a 32 bit utility instance')
        group_ec2.add_argument('--ec2-64bit-util', default = 'm1.large', help='Instance type to use when launching a 64 bit utility instance')

        if(appname == 'imagefactoryd'):
            argparser.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
            argparser.add_argument('--foreground', action='store_true', default=False, help='Stay in the foreground and avoid launching a daemon. (default: %(default)s)')
            group_rest = argparser.add_argument_group(title='REST service options')
            group_rest.add_argument('--port', type=int, default=8075, help='Port to attach the RESTful http interface to. (default: %(default)s)')
            group_rest.add_argument('--address', default='0.0.0.0', help='Interface address to listen to. (default: %(default)s)')
            group_rest.add_argument('--no_ssl', action='store_true', default=False, help='Turn off SSL. (default: %(default)s)')
            group_rest.add_argument('--ssl_pem', default='*', help='PEM certificate file to use for HTTPS access to the REST interface. (default: A transient certificate is generated at runtime.)')
            group_rest.add_argument('--no_oauth', action='store_true', default=False, help='Use 2 legged OAuth to protect the REST interface. (default: %(default)s)')
            group_rest.add_argument('--secondary', action='store_true', default=False, help='Operate as a secondary/helper factory. (default: %(default)s)')
        elif(appname == 'imagefactory'):
            argparser.add_argument('--nodebug', action='store_true', default=False, help='Turn off the default verbose CLI logging')
            argparser.add_argument('--output', choices=('log', 'json'), default='log', help='Choose between log or json output. (default: %(default)s)')
            argparser.add_argument('--raw', action='store_true', default=False, help='Turn off pretty printing.')
            subparsers = argparser.add_subparsers(title='commands', dest='command')
            template_help = 'A file containing the TDL for this image.'
            parameters_help = 'An optional JSON file containing additional parameters to pass to the builders.'

            cmd_base = subparsers.add_parser('base_image', help='Build a generic image.')
            cmd_base.add_argument('template', type=argparse.FileType(), help=template_help)
            cmd_base.add_argument('--parameters', type=argparse.FileType(), help=parameters_help)

            cmd_target = subparsers.add_parser('target_image', help='Customize an image for a given cloud.')
            cmd_target.add_argument('target', help='The name of the target cloud for which to customize the image.')
            target_group = cmd_target.add_mutually_exclusive_group(required=True)
            target_group.add_argument('--id', help='The uuid of the BaseImage to customize.')
            target_group.add_argument('--template', type=argparse.FileType(), help=template_help)
            cmd_target.add_argument('--parameters', type=argparse.FileType(), help=parameters_help)

            cmd_provider = subparsers.add_parser('provider_image', help='Push an image to a cloud provider.')
            cmd_provider.add_argument('target', help='The target type of the given provider')
            cmd_provider.add_argument('provider', help="A file containing the provider description or a string literal starting with '@' such as '@ec2-us-east-1'.")
            cmd_provider.add_argument('credentials', type=argparse.FileType(), help='A file containing the provider credentials')
            provider_group = cmd_provider.add_mutually_exclusive_group(required=True)
            provider_group.add_argument('--id', help='The uuid of the TargetImage to push.')
            provider_group.add_argument('--template', type=argparse.FileType(), help=template_help)
            cmd_provider.add_argument('--parameters', type=argparse.FileType(), help=parameters_help)
            cmd_provider.add_argument('--snapshot', action='store_true', default=False, help='Use snapshot style building. (default: %(default)s)')

            cmd_list = subparsers.add_parser('images', help='List images of a given type or get details of an image.')
            cmd_list.add_argument('fetch_spec', help='JSON formatted string of key/value pairs')

            cmd_delete = subparsers.add_parser('delete', help='Delete an image.')
            cmd_delete.add_argument('id', help='UUID of the image to delete')
            cmd_delete.add_argument('--provider', type=argparse.FileType(), help="A file containing the provider description or a string literal starting with '@' such as '@ec2-us-east-1'.")
            cmd_delete.add_argument('--credentials', type=argparse.FileType(), help='A file containing the provider credentials')
            cmd_delete.add_argument('--target', help='The name of the target cloud for which to customize the image.')
            cmd_delete.add_argument('--parameters', type=argparse.FileType(), help=parameters_help)

            cmd_plugins = subparsers.add_parser('plugins', help='List active plugins or get details of a specific plugin.')
            cmd_plugins.add_argument('--id')
        return argparser

    def __parse_arguments(self):
        appname = sys.argv[0].rpartition('/')[2]
        argparser = self.__new_argument_parser(appname)
        if((appname == 'imagefactory') and (len(sys.argv) == 1)):
            argparser.print_help()
            sys.exit()
        configuration = argparser.parse_args()
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
                defaults = dencode(uconfig)
                argparser.set_defaults(**defaults)
                configuration = argparser.parse_args()
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
        # TODO: Make this path itself configurable?
        config_path = '/etc/imagefactory/jeos_images/'
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
