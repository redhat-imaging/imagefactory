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
import os.path
import argparse
import json
import logging
import props
from Singleton import Singleton
from imgfac.Version import VERSION as VERSION
from urlgrabber import urlopen


class ApplicationConfiguration(Singleton):
    configuration = props.prop("_configuration", "The configuration property.")

    def _singleton_init(self, configuration = None):
        super(ApplicationConfiguration, self)._singleton_init()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.jeos_images = { }

        if configuration:
            if not isinstance(configuration, dict):
                raise Exception("ApplicationConfiguration configuration argument must be a dict")
            self.log.debug("ApplicationConfiguration passed a dictionary - ignoring any local config files including JEOS configs")
            self.configuration = configuration
        else:
            self.configuration = self.__parse_arguments()
            self.__parse_jeos_images()

        if not 'debug' in self.configuration:
            # This most likely means we are being used as a module/library and are not running CLI or daemon
            self.configuration['debug'] = False

        if not 'secondary' in self.configuration:
            # We use this in the non-daemon context so it needs to be set
            # TODO: Something cleaner?
            self.configuration['secondary'] = False

    def __init__(self, configuration = None):
        pass

    def __new_argument_parser(self, appname):
        main_description = """Image Factory is an application for creating system images for use on public and private clouds."""

        argparser = argparse.ArgumentParser(description=main_description, prog=appname)
        argparser.add_argument('--version', action='version', default=argparse.SUPPRESS, version=VERSION, help='Show the version number and exit')
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
            debug_group = argparser.add_mutually_exclusive_group()
            debug_group.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
            debug_group.add_argument('--nodebug', dest='debug', action='store_false', help='Turn off the default verbose CLI logging')
            argparser.add_argument('--foreground', action='store_true', default=False, help='Stay in the foreground and avoid launching a daemon. (default: %(default)s)')
            group_rest = argparser.add_argument_group(title='REST service options')
            group_rest.add_argument('--port', type=int, default=8075, help='Port to attach the RESTful http interface to. (default: %(default)s)')
            group_rest.add_argument('--address', default='0.0.0.0', help='Interface address to listen to. (default: %(default)s)')
            group_rest.add_argument('--no_ssl', action='store_true', default=False, help='Turn off SSL. (default: %(default)s)')
            group_rest.add_argument('--ssl_pem', default='*', help='PEM certificate file to use for HTTPS access to the REST interface. (default: A transient certificate is generated at runtime.)')
            group_rest.add_argument('--no_oauth', action='store_true', default=False, help='Use 2 legged OAuth to protect the REST interface. (default: %(default)s)')
            group_rest.add_argument('--secondary', action='store_true', default=False, help='Operate as a secondary/helper factory. (default: %(default)s)')
        elif(appname == 'imagefactory'):
            debug_group = argparser.add_mutually_exclusive_group()
            debug_group.add_argument('--debug', action='store_true', default=True, help='Set really verbose logging for debugging.')
            debug_group.add_argument('--nodebug', dest='debug', action='store_false', help='Turn off the default verbose CLI logging')
            argparser.add_argument('--output', choices=('log', 'json'), default='log', help='Choose between log or json output. (default: %(default)s)')
            argparser.add_argument('--raw', action='store_true', default=False, help='Turn off pretty printing.')
            subparsers = argparser.add_subparsers(title='commands', dest='command')
            template_help = 'A file containing the image template or component outline, compatible with the TDL schema (http://imgfac.org/documentation/tdl).'

            cmd_base = subparsers.add_parser('base_image', help='Build a generic image.')
            cmd_base.add_argument('template', type=argparse.FileType(), help=template_help)
            self.__add_param_arguments(cmd_base)

            cmd_target = subparsers.add_parser('target_image', help='Customize an image for a given cloud.')
            cmd_target.add_argument('target', help='The name of the target cloud for which to customize the image.')
            target_group = cmd_target.add_mutually_exclusive_group(required=True)
            target_group.add_argument('--id', help='The uuid of the BaseImage to customize.')
            target_group.add_argument('--template', type=argparse.FileType(), help=template_help)
            self.__add_param_arguments(cmd_target)

            cmd_provider = subparsers.add_parser('provider_image', help='Push an image to a cloud provider.')
            cmd_provider.add_argument('target', help='The target type of the given cloud provider')
            cmd_provider.add_argument('provider', help="A file containing the cloud provider description or a string literal starting with '@' such as '@ec2-us-east-1'.")
            cmd_provider.add_argument('credentials', type=argparse.FileType(), help='A file containing the cloud provider credentials')
            provider_group = cmd_provider.add_mutually_exclusive_group(required=True)
            provider_group.add_argument('--id', help='The uuid of the TargetImage to push.')
            provider_group.add_argument('--template', type=argparse.FileType(), help=template_help)
            self.__add_param_arguments(cmd_provider)
            cmd_provider.add_argument('--snapshot', action='store_true', default=False, help='Use snapshot style building. (default: %(default)s)')

            cmd_list = subparsers.add_parser('images', help='List images of a given type or get details of an image.')
            cmd_list.add_argument('fetch_spec', help='JSON formatted string of key/value pairs')

            cmd_delete = subparsers.add_parser('delete', help='Delete an image.')
            cmd_delete.add_argument('id', help='UUID of the image to delete')
            cmd_delete.add_argument('--provider', help="A file containing the cloud provider description or a string literal starting with '@' such as '@ec2-us-east-1'.")
            cmd_delete.add_argument('--credentials', type=argparse.FileType(), help='A file containing the cloud provider credentials')
            cmd_delete.add_argument('--target', help='The name of the target cloud for which to customize the image.')
            self.__add_param_arguments(cmd_delete)

            cmd_plugins = subparsers.add_parser('plugins', help='List active plugins or get details of a specific plugin.')
            cmd_plugins.add_argument('--id')
        return argparser

    def __add_param_arguments(self, parser):
        # We do this for all three image types so lets make it a util function
        parameters_help = 'An optional JSON file containing additional parameters to pass to the builders.'
        parser.add_argument('--parameters', type=argparse.FileType(), help=parameters_help)
        parser.add_argument('--parameter', nargs=2, action='append', help='A parameter name and the literal value to assign it.  Can be used more than once.')
        parser.add_argument('--file-parameter', nargs=2, action='append', help='A parameter name and a file to insert into it.  Can be used more than once.')

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
        log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        # our multi-dimensional-dict has the following keys
        # target - provider - os - version - arch - provider_image_id - user - cmd_prefix
        for i in range(8):
            try:
                image_detail[i] = image_detail[i].strip()
            except IndexError:
                image_detail.append(None)

        (target, provider, os, version, arch, provider_image_id, user, cmd_prefix) = image_detail
        if not (target in self.jeos_images):
            self.jeos_images[target] = {}
        if not (provider in self.jeos_images[target]):
            self.jeos_images[target][provider] = {}
        if not (os in self.jeos_images[target][provider]):
            self.jeos_images[target][provider][os] = {}
        if not (version in self.jeos_images[target][provider][os]):
            self.jeos_images[target][provider][os][version] = {}
        if arch in self.jeos_images[target][provider][os][version]:
            log.warning("JEOS image defined more than once for %s - %s - %s - %s - %s" % (target, provider, os, version, arch))
            log.warning("Replacing (%s) with (%s)" % (self.jeos_images[target][provider][os][version][arch], provider_image_id))

        self.jeos_images[target][provider][os][version][arch] = {'img_id':provider_image_id,
                                                                 'user':user,
                                                                 'cmd_prefix':cmd_prefix}

    def __parse_jeos_images(self):
        log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        config_urls = self.configuration['jeos_config']
        # Expand directories from the config and url-ify files
        # Read inlist - replace directories with their contents
        nextlist = []
        for path in config_urls:
            if os.path.isdir(path):
                for filename in os.listdir(path):
                    fullname = os.path.join(path, filename)
                    if os.path.isfile(fullname):
                        nextlist.append(fullname)
            else:
                nextlist.append(path)

        # Read nextlist - replace files with file:// URLs
        finalist = []
        for path in nextlist:
            if os.path.isfile(path):
                finalist.append("file://" + path)
            else:
                finalist.append(path)

        for url in finalist:
            try:
                filehandle = urlopen(str(url))
                line = filehandle.readline().strip()
            except:
                log.warning("Failed to open JEOS URL (%s)" % url)
                continue
            line_number = 1

            while line:
                # Lines that start with '#' are a comment
                if line[0] == "#":
                    pass
                # Lines that are zero length are whitespace
                elif len(line.split()) == 0:
                    pass
                else:
                    image_detail = line.split(":")
                    if len(image_detail) >= 6:
                        self.__add_jeos_image(image_detail)
                    else:
                        log.warning("Failed to parse line %d in JEOS config (%s):\n%s" % (line_number, url, line))

                line = filehandle.readline()
                line_number += 1

            filehandle.close()
