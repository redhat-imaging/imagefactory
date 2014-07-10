# encoding: utf-8
#
#   Copyright 2014 Red Hat, Inc.
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

import logging
import zope
import os.path
import shutil
import libxml2
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.FactoryUtils import enable_root, disable_root, ssh_execute_command
from imgfac.OSDelegate import OSDelegate
from imgfac.ImageFactoryException import ImageFactoryException
from novaimagebuilder.Builder import Builder
from novaimagebuilder.StackEnvironment import StackEnvironment
from time import sleep
from base64 import b64decode
#TODO: remove dependency on Oz
from ConfigParser import SafeConfigParser
from oz.TDL import TDL
import oz.GuestFactory

PROPERTY_NAME_GLANCE_ID = 'x-image-properties-glance_id'


class Nova(object):
    """
    Nova implements the ImageFactory OSDelegate interface for the Nova plugin.
    """
    zope.interface.implements(OSDelegate)

    def __init__(self):
        super(Nova, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.nib = None
        self._cloud_plugin_content = []

    def abort(self):
        """
        Abort the current operation.
        """
        if self.nib and isinstance(self.nib, Builder):
            status = self.nib.abort()
            self.log.debug('aborting... status: %s' % status)
        else:
            self.log.debug('No active Nova Image Builder instance found, nothing to abort.')

    def create_base_image(self, builder, template, parameters):
        """
        Create a JEOS image and install any packages specified in the template.

        @param builder The Builder object coordinating image creation.
        @param template A Template object.
        @param parameters Dictionary of target specific parameters.

        @return A BaseImage object.
        """
        self.log.info('create_base_image() called for Nova plugin - creating a BaseImage')

        self.log.debug('Nova.create_base_image() called by builder (%s)' % builder)
        if not parameters:
            parameters = {}
        self.log.debug('parameters set to %s' % parameters)

        builder.base_image.update(5, 'PENDING', 'Collecting build arguments to pass to Nova Image Builder...')
        # Derive the OSInfo OS short_id from the os_name and os_version in template
        if template.os_version:
            if template.os_name[-1].isdigit():
                install_os = '%s.%s' % (template.os_name, template.os_version)
            else:
                install_os = '%s%s' % (template.os_name, template.os_version)
        else:
            install_os = template.os_name

        install_os = install_os.lower()

        install_location = template.install_location
        # TDL uses 'url' but Nova Image Builder uses 'tree'
        install_type = 'tree' if template.install_type == 'url' else template.install_type
        install_script = parameters.get('install_script')
        install_config = {'admin_password': parameters.get('admin_password'),
                          'license_key': parameters.get('license_key'),
                          'arch': template.os_arch,
                          'disk_size': parameters.get('disk_size'),
                          'flavor': parameters.get('flavor'),
                          'storage': parameters.get('storage'),
                          'name': template.name,
                          'direct_boot': parameters.get('direct_boot', False),
                          'timeout': parameters.get('timeout', 1800),
                          'public': parameters.get('public', False),
                          'floating_ip': parameters.get('request_floating_ip', False)}

        builder.base_image.update(10, 'BUILDING', 'Created Nova Image Builder instance...')
        self.nib = Builder(install_os, install_location, install_type, install_script, install_config)
        self.nib.run()

        builder.base_image.update(10, 'BUILDING', 'Waiting for Nova Image Builder to complete...')
        jeos_image_id = self.nib.wait_for_completion(180)
        if jeos_image_id:
            builder.base_image.update(30, 'BUILDING',
                                      'JEOS image in glance with id (%s), starting customization...' % jeos_image_id)

            self.log.debug('Launching Nova instance with image (%s) for customization & icicle generation.' %
                           jeos_image_id)
            img_name = self.nib.env.glance.images.get(jeos_image_id).name
            jeos_instance = self.nib.env.launch_instance(name='Customize %s and Generate ICICLE' % img_name,
                                                         root_disk=jeos_image_id,
                                                         flavor=parameters.get('flavor', None))
            if not jeos_instance:
                raise ImageFactoryException('Reached timeout waiting for customization instance...')

            self.log.debug('Launched Nova instance (id: %s) for customization & icicle generation.' % jeos_instance.id)
            if not jeos_instance.open_ssh():  # Add a security group for ssh access
                raise ImageFactoryException('Failed to add security group for ssh, cannot continue...')

            user = parameters.get('default_user')
            private_key_file = jeos_instance.key_dir + jeos_instance.key_pair.name
            # Get an IP address to use below for ssh connections to the instance.
            if self._networking_is_active_for_instance(jeos_instance):
                if install_config['floating_ip']:
                    jeos_instance_addr = self._create_ipaddr_for_instance(jeos_instance)
                else:
                    jeos_instance_addr = self._get_ipaddr_for_instance(jeos_instance, user, private_key_file)
                if not jeos_instance_addr:
                    jeos_instance_addr = self._create_ipaddr_for_instance(jeos_instance)
            else:
                raise ImageFactoryException('Networking not active for instance %s, cannot continue!' %
                                            jeos_instance.id)
            if not jeos_instance_addr:
                raise ImageFactoryException('Unable to obtain an IP address for instance %s' % jeos_instance.id)

            # Enable root for customization steps
            cmd_prefix = parameters.get('command_prefix')
            if user and user != 'root':
                if self._enable_root_from_user_with_command_prefix(user, cmd_prefix, jeos_instance_addr,
                                                                   private_key_file):
                    self.log.debug('Temporarily enabled root user for image customization steps...')
                else:
                    raise ImageFactoryException('Unable to access %s as root. Cannot continue...' % jeos_instance_addr)

            oz_config = self._oz_config(private_key_file)
            if not oz_config:
                raise ImageFactoryException('No Oz config file found. Cannot continue.')

            oz_guest = oz.GuestFactory.guest_factory(tdl=TDL(str(template)), config=oz_config, auto=None)

            if self._confirm_ssh_access(oz_guest, jeos_instance_addr):
                self.log.debug('Starting base image customization.')
                oz_guest.do_customize(jeos_instance_addr)
                self.log.debug('Completed base image customization.')

                self.log.debug('Starting ICICLE generation.')
                builder.base_image.update(90, 'BUILDING', 'Starting ICICLE generation (glance: %s)...' % jeos_image_id)
                builder.base_image.icicle = oz_guest.do_icicle(jeos_instance_addr)
                self.log.debug('Completed ICICLE generation')

                # Disable ssh access for root
                if user and user != 'root':
                    disable_root(jeos_instance_addr, private_key_file, user, cmd_prefix)
                    self.log.debug('Disabling root ssh access now that customization is complete...')

                jeos_instance.close_ssh()  # Remove security group for ssh access

            else:
                raise ImageFactoryException('Unable to reach %s via ssh.' % jeos_instance_addr)

            if jeos_instance.shutoff():
                base_image_id = jeos_instance.create_snapshot(template.name + '-base')
                builder.base_image.properties[PROPERTY_NAME_GLANCE_ID] = base_image_id
                builder.base_image.update(100, 'COMPLETE', 'Image stored in glance with id (%s)' % base_image_id)
                jeos_instance.terminate()
            else:
                raise ImageFactoryException('JEOS build instance (%s) never shutdown in Nova.' % jeos_instance.id)

        else:
            exc_msg = 'Nova Image Builder failed to return a Glance ID, failing...'
            builder.base_image.update(status='FAILED', error=exc_msg)
            self.log.exception(exc_msg)
            raise ImageFactoryException(exc_msg)

    def create_target_image(self, builder, target, base_image, parameters):
        """
        *** NOT YET IMPLEMENTED ***
        Performs cloud specific customization on the base image.

        @param builder The builder object.
        @param base_image The BaseImage to customize.
        @param target The cloud type to customize for.
        @param parameters Dictionary of target specific parameters.

        @return A TargetImage object.
        """
        self.log.info('create_target_image() called for Nova plugin - creating a TargetImage')

        # Merge together any TDL-style customizations requested via our plugin-to-plugin interface  with any target
        #  specific packages, repos and commands and then run a second Oz customization step.
        tdl = TDL(xmlstring=builder.target_image.template, rootpw_required=self.app_config['tdl_require_root_pw'])

        # We remove any packages, commands and files from the original TDL - these have already been
        # installed/executed.  We leave the repos in place, as it is possible that the target
        # specific packages or commands may require them.
        tdl.packages = []
        tdl.commands = {}
        tdl.files = {}

        # Get user defined repositories and packages from a local config file
        repositories, packages = self._target_content(tdl, target)
        if repositories:
            tdl.merge_repositories(repositories)
        if packages:
            tdl.merge_packages(packages)

        # Content provided by the target plugin for the target plugin
        if len(self._cloud_plugin_content) > 0:
            tdl = self.merge_cloud_content_with_tdl(self._cloud_plugin_content, tdl)

        # If there are no new commands, packages or files, we can stop here
        if (len(tdl.packages) + len(tdl.commands) + len(tdl.files)) == 0:
            self.log.debug('No further modification of the TargetImage to perform in the OS Plugin - returning')
            return

        base_image_id = base_image.properties[PROPERTY_NAME_GLANCE_ID]
        stack_env = StackEnvironment()
        base_instance = stack_env.launch_instance(name='Target Image Prep',
                                                  root_disk=('glance', base_image_id),
                                                  flavor=parameters.get('flavor'))
        if not base_instance:
            raise ImageFactoryException('Reached timeout waiting for base instance...')
        self.log.debug('Launched Nova instance (id: %s) for target specific customization.' % base_instance.id)

        if not base_instance.open_ssh():  # Add A security group for ssh access
            raise ImageFactoryException('Failed to add security group for ssh, cannot continue...')

        user = parameters.get('default_user', 'root')
        private_key_file = base_instance.key_dir + base_instance.key_pair.name
        # Get an IP address to use for ssh connections
        if self._networking_is_active_for_instance(base_instance):
            if parameters.get('request_floating_ip', False):
                base_instance_addr = self._create_ipaddr_for_instance(base_instance)
            else:
                base_instance_addr = self._get_ipaddr_for_instance(base_instance, user, private_key_file)
            if not base_instance_addr:
                base_instance_addr = self._create_ipaddr_for_instance(base_instance)
        else:
            raise ImageFactoryException('Networking not active for instance %s, cannot continue!' % base_instance.id)
        if not base_instance_addr:
            raise ImageFactoryException('Unable to obtain IP address for instance %s' % base_instance.id)

        # Enable root for target prep steps
        cmd_prefix = parameters.get('command_prefix')
        if user and user != 'root':
            if self._enable_root_from_user_with_command_prefix(user, cmd_prefix, base_instance_addr, private_key_file):
                self.log.debug('Temporarily enabled root user for target preparation steps...')
            else:
                raise ImageFactoryException('Unable to access %s as root. Cannot continue...' % base_instance_addr)

        oz_config = self._oz_config(private_key_file)
        if not oz_config:
            raise ImageFactoryException('No Oz config file found. Cannot continue.')

        oz_guest = oz.GuestFactory.guest_factory(tdl=tdl, config=oz_config, auto=None)

        if self._confirm_ssh_access(oz_guest, base_instance_addr):
            self.log.debug('Starting base image customization.')
            oz_guest.do_customize(base_instance_addr)
            self.log.debug('Completed base image customization.')

            self.log.debug('Starting ICICLE generation.')
            builder.target_image.update(85, 'BUILDING', 'Starting ICICLE generation (glance: %s)...' % base_image_id)
            builder.target_image.icicle = oz_guest.do_icicle(base_instance_addr)
            self.log.debug('Completed ICICLE generation')

            # Disable ssh access for root
            if user and user != 'root':
                disable_root(base_instance_addr, private_key_file, user, cmd_prefix)
                self.log.debug('Disabling root ssh access now that customization is complete...')

            base_instance.close_ssh()  # Remove security group for ssh access

        else:
            raise ImageFactoryException('Unable to reach %s via ssh.' % base_instance_addr)

        if base_instance.shutoff():
            target_image_id = base_instance.create_snapshot(tdl.name + '-base')
            builder.target_image.properties[PROPERTY_NAME_GLANCE_ID] = target_image_id
            builder.target_image.update(90, 'BUILDING', 'Target Image stored in glance with id (%s)' % target_image_id)
            base_instance.terminate()
        else:
            raise ImageFactoryException('JEOS build instance (%s) never shutdown in Nova.' % base_instance.id)

        builder.target_image.update(95, 'BUILDING', 'Downloading target image...')
        target_img_download = StackEnvironment().download_image_from_glance(target_image_id)
        with open(builder.target_image.data, 'wb') as target_img_file:
            shutil.copyfileobj(target_img_download, target_img_file)
            target_img_file.close()
        target_img_download.close()

    def add_cloud_plugin_content(self, content):
        """
        This is a method that cloud plugins can call to deposit content/commands to
        be run during the OS-specific first stage of the Target Image creation.

        There is no support for repos at the moment as these introduce external
        dependencies that we may not be able to resolve.

        @param content dict containing commands and file.
        """
        self._cloud_plugin_content.append(content)

    def merge_cloud_content_with_tdl(self, contents, tdl):
        """
        Merge 'files' and 'commands' content into an existing TDL instance.

        @param contents: Array of content.
        @param tdl: TDL instance
        @return: @raise ImageFactoryException:
        """
        for item in contents:
            if 'files' in item:
                for entry in item['files']:
                    if not 'name' in entry:
                        raise ImageFactoryException('File given without a name')
                    if not 'type' in entry:
                        raise ImageFactoryException('File given without a type')
                    if not 'file' in entry:
                        raise ImageFactoryException('File given without any content')
                    if entry['type'] == 'raw':
                        tdl.files[entry['name']] = entry['file']
                    elif entry['type'] == 'base64':
                        if len(entry['file']) == 0:
                            self.log.warning('File given with zero length... %s' % entry['name'])
                            tdl.files[entry['name']] = ''
                        else:
                            tdl.files[entry['name']] = b64decode(entry['file'])
                    else:
                        raise ImageFactoryException('File given with invalid type (%s)' % entry['type'])

            if 'commands' in item:
                for entry in item['commands']:
                    if not 'name' in entry:
                        raise ImageFactoryException('Command given without a name')
                    if not 'type' in entry:
                        raise ImageFactoryException('Command given without a type')
                    if not 'command' in entry:
                        raise ImageFactoryException('Command given without any content')
                    if entry['type'] == 'raw':
                        tdl.commands[entry['name']] = entry['command']
                    elif entry['type'] == 'base64':
                        if len(entry['command']) == 0:
                            self.log.warning('Command given with zero length... %s' % entry['name'])
                            tdl.commands[entry['name']] = ''
                        else:
                            tdl.commands[entry['name']] = b64decode(entry['command'])
                    else:
                        raise ImageFactoryException('Command given with invalid type (%s)' % entry['type'])

        return tdl

    def _target_content(self, tdl, target):
        target_xml = '/etc/imagefactory/target_content.xml'
        if os.path.isfile(target_xml):
            doc = libxml2.parseFile(target_xml)
        else:
            self.log.debug("Found neither a call-time config nor a config file - doing nothing")
            return None, None

        # We go from most to least specific in this order:
        #   arch -> version -> os-> target
        # Note that at the moment we even allow an include statment that covers absolutely everything.
        # That is, one that doesn't even specify a target - this is to support a very simple call-time syntax
        include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and @arch='%s']"
                                % (target, tdl.distro, tdl.update, tdl.arch))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and \
            not(@arch)]" % (target, tdl.distro, tdl.update))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and not(@version) and \
            not(@arch)]" % (target, tdl.distro))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and not(@os) and not(@version) and \
            not(@arch)]" % target)
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[not(@target) and not(@os) and not(@version) and \
            not(@arch)]")
        if len(include) == 0:
            self.log.debug("cannot find a config section that matches our build details - doing nothing")
            return None, None

        # OK - We have at least one config block that matches our build - take the first one, merge it and be done
        # TODO: Merge all of them?  Err out if there is more than one?  Warn?
        include = include[0]

        packages = include.xpathEval("packages")
        if len(packages) > 0:
            ret_pkgs = packages[0]
        else:
            ret_pkgs = None

        repositories = include.xpathEval("repositories")
        if len(repositories) > 0:
            ret_repos = repositories[0]
        else:
            ret_repos = None

        return ret_repos, ret_pkgs

    def _confirm_ssh_access(self, guest, addr, timeout=300):
        confirmation = False

        for index in range(timeout/10):
            if index % 10 == 0:
                self.log.debug('Checking ssh access to %s - %d' % (addr, index))
            try:
                guest.guest_execute_command(addr, '/bin/true', timeout=10)
                confirmation = True
                break
            except Exception as e:
                self.log.exception('Caught exception while checking ssh access to %s: %s' % (addr, e))

            sleep(1)

        if not confirmation:
            self.log.debug('Unable to confirm ssh access to %s after %s minutes...' % (addr, timeout/60))

        return confirmation

    def _oz_config(self, private_key_file):
        config = SafeConfigParser()
        if config.read("/etc/oz/oz.cfg"):
            config.set('paths', 'output_dir', self.app_config['imgdir'])
            config.set('paths', 'sshprivkey', private_key_file)
            if 'oz_data_dir' in self.app_config:
                config.set('paths', 'data_dir', self.app_config['oz_data_dir'])
            if 'oz_screenshot_dir' in self.app_config:
                config.set('paths', 'screenshot_dir', self.app_config['oz_screenshot_dir'])
            return config
        else:
            return None

    def _networking_is_active_for_instance(self, srvr_instance):
        for index in range(0, 120, 5):
            self.log.debug('Polling for networks associated with instance %s' % srvr_instance.id)
            if len(srvr_instance.instance.networks) > 0:
                return True
            else:
                sleep(5)
        return False

    def _get_ipaddr_for_instance(self, srvr_instance, user, key):
        for index in range(0, 300, 5):
            try:
                for network in srvr_instance.instance.networks.values():
                    for address in network:
                        try:
                            stdout, stderr, retcode = ssh_execute_command(str(address), key, '/bin/id', user=user)
                            if retcode == 0:
                                self.log.debug('Connected to %s' % address)
                                return address
                        except Exception as e:
                            self.log.debug('Failed to connect to instance %s with address %s. Caught exception %s' %
                                           (srvr_instance.id, address, e))
            except Exception as e:
                self.log.exception('Caught exception while polling networks of instance %s: %s' % (srvr_instance.id, e))
                return None
            sleep(5)
        return None

    def _create_ipaddr_for_instance(self, srvr_instance):
        try:
            address = str(srvr_instance.add_floating_ip().ip)
            self.log.debug('Using address %s to reach instance %s' % (address, srvr_instance.id))
            return address
        except Exception as e:
            self.log.exception('Caught exception trying to add floating IP to instance %s: %s' % (srvr_instance.id, e))
            return None

    def _enable_root_from_user_with_command_prefix(self, user, cmd_prefix, ip_addr, private_key):
        for index in range(0, 120, 5):
            try:
                enable_root(ip_addr, private_key, user, cmd_prefix)
                return True
            except Exception as e:
                if index < 120:
                    self.log.debug(e)
                    sleep(5)
                else:
                    return False
