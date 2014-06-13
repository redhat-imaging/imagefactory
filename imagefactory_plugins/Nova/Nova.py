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
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.FactoryUtils import enable_root, disable_root
from imgfac.OSDelegate import OSDelegate
from imgfac.ImageFactoryException import ImageFactoryException
from novaimagebuilder.Builder import Builder as NIB
from novaimagebuilder.StackEnvironment import StackEnvironment
from time import sleep
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
        if self.nib and isinstance(self.nib, NIB):
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
                          'direct_boot': False}

        builder.base_image.update(10, 'BUILDING', 'Created Nova Image Builder instance...')
        self.nib = NIB(install_os, install_location, install_type, install_script, install_config)
        self.nib.run()

        builder.base_image.update(10, 'BUILDING', 'Waiting for Nova Image Builder to complete...')
        jeos_image_id = self.nib.wait_for_completion(180)
        if jeos_image_id:
            builder.base_image.update(30, 'BUILDING',
                                      'JEOS image in glance with id (%s), starting customization...' % jeos_image_id)

            self.log.debug('Launching Nova instance with image (%s) for customization & icicle generation.' %
                           jeos_image_id)
            img_name = self.nib.env.glance.images.get(jeos_image_id).name
            jeos_instance = self.nib.env.launch_instance('Customize %s and Generate ICICLE' % img_name, jeos_image_id)
            self.log.debug('Launched Nova instance (id: %s) for customization & icicle generation.' % jeos_instance.id)
            if not jeos_instance.open_ssh():  # Add a security group for ssh access
                raise ImageFactoryException('Failed to add security group for ssh, cannot continue...')

            # Get an IP address to use below for ssh connections to the instance.
            jeos_instance_addr = None
            for index in range(0, 120, 5):
                self.log.debug('Networks associated with instance %s: %s' % (jeos_instance.id,
                                                                             jeos_instance.instance.networks))
                if len(jeos_instance.instance.networks) > 0:
                    #TODO: Enable and test using a floating IP instead of the fixed private IP
                    #jeos_instance_addr = str(jeos_instance.add_floating_ip().ip)
                    jeos_instance_addr = str(jeos_instance.instance.networks['private'][0])
                    self.log.debug('Using address %s to reach instance %s' % (jeos_instance_addr, jeos_instance.id))
                    break
                else:
                    sleep(5)

            if not jeos_instance_addr:
                raise ImageFactoryException('Unable to obtain an IP address for instance %s' % jeos_instance.id)

            private_key_file = jeos_instance.key_dir + jeos_instance.key_pair.name

            # Enable root for customization steps
            user = parameters.get('default_user')
            cmd_prefix = parameters.get('command_prefix')
            if user and user != 'root':
                self.log.debug('Temporarily enabling root user for customization steps...')
                enable_root(jeos_instance_addr, private_key_file, user, cmd_prefix)

            oz_config = SafeConfigParser()
            if oz_config.read("/etc/oz/oz.cfg") != []:
                oz_config.set('paths', 'output_dir', self.app_config['imgdir'])
                oz_config.set('paths', 'sshprivkey', private_key_file)
                if 'oz_data_dir' in self.app_config:
                    oz_config.set('paths', 'data_dir', self.app_config['oz_data_dir'])
                if 'oz_screenshot_dir' in self.app_config:
                    oz_config.set('paths', 'screenshot_dir', self.app_config['oz_screenshot_dir'])
            else:
                raise ImageFactoryException('No Oz config file found. Cannot continue.')

            oz_guest = oz.GuestFactory.guest_factory(tdl=TDL(str(template)),
                                                     config=oz_config,
                                                     auto=install_script)

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

        glance_id = base_image.properties[PROPERTY_NAME_GLANCE_ID]
        stack_env = StackEnvironment()
        nova_instance = stack_env.launch_instance(root_disk=('glance', glance_id))

        ### TODO: Snapshot the image in glance, launch in nova, and ssh in to customize.
        # The following is incomplete and not correct as it assumes local manipulation of the image
        # self.log.info('create_target_image() called for Nova plugin - creating TargetImage')
        # base_img_path = base_image.data
        # target_img_path = builder.target_image.data
        #
        # builder.target_image.update(status='PENDING', detail='Copying base image...')
        # if os.path.exists(base_img_path) and os.path.getsize(base_img_path):
        #     try:
        #         shutil.copyfile(base_img_path, target_img_path)
        #     except IOError as e:
        #         builder.target_image.update(status='FAILED', error='Error copying base image: %s' % e)
        #         self.log.exception(e)
        #         raise e
        # else:
        #     glance_id = base_image.properties[PROPERTY_NAME_GLANCE_ID]
        #     base_img_file = StackEnvironment().download_image_from_glance(glance_id)
        #     with open(builder.target_image.data, 'wb') as target_img_file:
        #         shutil.copyfileobj(base_img_file, target_img_file)
        #     base_img_file.close()

    def add_cloud_plugin_content(self, content):
        """
        This is a method that cloud plugins can call to deposit content/commands to
        be run during the OS-specific first stage of the Target Image creation.

        There is no support for repos at the moment as these introduce external
        dependencies that we may not be able to resolve.

        @param content dict containing commands and file.
        """
        self._cloud_plugin_content.append(content)

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