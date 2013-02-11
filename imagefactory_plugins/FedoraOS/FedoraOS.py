#
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

import logging
import zope
import oz.GuestFactory
import oz.TDL
import oz.ozutil
import subprocess
import libxml2
import traceback
import ConfigParser
from os.path import isfile
from time import *
from tempfile import NamedTemporaryFile
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.ReservationManager import ReservationManager
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist

from imgfac.OSDelegate import OSDelegate

def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    stdout, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = ' '.join(*popenargs)
        raise ImageFactoryException("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)



class FedoraOS(object):
    zope.interface.implements(OSDelegate)

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    ## INTERFACE METHOD
    def create_target_image(self, builder, target, base_image, parameters):
        self.log.info('create_target_image() called for FedoraOS plugin - creating a TargetImage')
        self.active_image = builder.target_image
        self.target = target
        self.base_image = builder.base_image

        # populate our target_image bodyfile with the original base image
        # which we do not want to modify in place
        self.activity("Copying BaseImage to modifiable TargetImage")
        self.log.debug("Copying base_image file (%s) to new target_image file (%s)" % (builder.base_image.data, builder.target_image.data))
        oz.ozutil.copyfile_sparse(builder.base_image.data, builder.target_image.data)
        self.image = builder.target_image.data

        # Merge together any TDL-style customizations requested via our plugin-to-plugin interface
        # with any target specific packages, repos and commands and then run a second Oz customization
        # step.
        self.tdlobj = oz.TDL.TDL(xmlstring=builder.base_image.template, rootpw_required=self.app_config["tdl_require_root_pw"])
        
        # We remove any packages, commands and files from the original TDL - these have already been
        # installed/executed.  We leave the repos in place, as it is possible that the target
        # specific packages or commands may require them.
        self.tdlobj.packages = [ ]
        self.tdlobj.commands = { }
        self.tdlobj.files = { } 
        # This is user-defined target-specific packages and repos in a local config file
        self.add_target_content()
        # This is content deposited by cloud plugins - typically commands to run to prep the image further
        self.merge_cloud_plugin_content()

        # If there are no new commands, packages or files, we can stop here - there is no need to run Oz again
        if (len(self.tdlobj.packages) + len(self.tdlobj.commands) + len(self.tdlobj.files)) == 0:
            self.log.debug("No further modification of the TargetImage to perform in the OS Plugin - returning")
            return 

        # We have some additional work to do - create a new Oz guest object that we can use to run the guest
        # customization a second time
        self._init_oz()

        self.guest.diskimage = builder.target_image.data

        libvirt_xml = self.guest._generate_xml("hd", None)

        # One last step is required here - The persistent net rules in some Fedora and RHEL versions
        # Will cause our new incarnation of the image to fail to get network - fix that here
        # We unfortunately end up having to duplicate this a second time in the cloud plugins
        # when we are done with our second  stage customizations
        # TODO: Consider moving all of that back here

        guestfs_handle = launch_inspect_and_mount(builder.target_image.data)
        remove_net_persist(guestfs_handle)
        shutdown_and_close(guestfs_handle)

        try:
            self.log.debug("Doing second-stage target_image customization and ICICLE generation")
            #self.percent_complete = 30
            self.output_descriptor = self.guest.customize_and_generate_icicle(libvirt_xml)
            self.log.debug("Customization and ICICLE generation complete")
            #self.percent_complete = 50
        finally:
            self.activity("Cleaning up install artifacts")
            self.guest.cleanup_install()

    def add_cloud_plugin_content(self, content):
        # This is a method that cloud plugins can call to deposit content/commands to be run
        # during the OS-specific first stage of the Target Image creation.
        # The expected input is a dict containing commands and files
        # No support for repos at the moment as these introduce external deps that we may not be able to count on
        # Add this to an array which will later be merged into the TDL object used to drive Oz
        self.cloud_plugin_content.append(content)

    def merge_cloud_plugin_content(self):
        for content in self.cloud_plugin_content:
            if 'files' in content:
                for fileentry in content['files']:
                    if not 'name' in fileentry:
                        raise ImageFactoryException("File given without a name")
                    if not 'type' in fileentry:
                        raise ImageFactoryException("File given without a type")
                    if not 'file' in fileentry:
                        raise ImageFactoryException("File given without any content")
                    if fileentry['type'] == 'raw':
                        self.tdlobj.files[fileentry['name']] = fileentry['file']
                    elif fileentry['type'] == 'base64':
                        if len(fileentry['file']) == 0:
                            self.tdlobj.files[fileentry['name']] = ""
                        else:
                            self.tdlobj.files[fileentry['name']] = base64.b64decode(fileentry['file'])
                    else:
                        raise ImageFactoryException("File given with invalid type (%s)" % (file['type']))

            if 'commands' in content:
                for command in content['commands']:
                    if not 'name' in command:
                        raise ImageFactoryException("Command given without a name")
                    if not 'type' in command:
                        raise ImageFactoryException("Command given without a type")
                    if not 'command' in command:
                        raise ImageFactoryException("Command given without any content")
                    if command['type'] == 'raw':
                        self.tdlobj.commands[command['name']] = command['command']
                    elif command['type'] == 'base64':
                        if len(command['command']) == 0:
                            self.log.warning("Command with zero length given")
                            self.tdlobj.commands[command['name']] = ""
                        else:
                            self.tdlobj.commandss[command['name']] = base64.b64decode(command['command'])
                    else:
                        raise ImageFactoryException("Command given with invalid type (%s)" % (command['type']))


    def add_target_content(self):
        """Merge in target specific package and repo content.
        TDL object must already exist as self.tdlobj"""
        doc = None
        if isfile("/etc/imagefactory/target_content.xml"):
            doc = libxml2.parseFile("/etc/imagefactory/target_content.xml")
        else:
            self.log.debug("Found neither a call-time config nor a config file - doing nothing")
            return

        # Purely to make the xpath statements below a tiny bit shorter
        target = self.target
        os=self.tdlobj.distro
        version=self.tdlobj.update
        arch=self.tdlobj.arch

        # We go from most to least specific in this order:
        #   arch -> version -> os-> target
        # Note that at the moment we even allow an include statment that covers absolutely everything.
        # That is, one that doesn't even specify a target - this is to support a very simple call-time syntax
        include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and @arch='%s']" %
                  (target, os, version, arch))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and not(@arch)]" %
                      (target, os, version))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and not(@version) and not(@arch)]" %
                      (target, os))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and not(@os) and not(@version) and not(@arch)]" %
                      (target))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[not(@target) and not(@os) and not(@version) and not(@arch)]")
        if len(include) == 0:
            self.log.debug("cannot find a config section that matches our build details - doing nothing")
            return

        # OK - We have at least one config block that matches our build - take the first one, merge it and be done
        # TODO: Merge all of them?  Err out if there is more than one?  Warn?
        include = include[0]

        packages = include.xpathEval("packages")
        if len(packages) > 0:
            self.tdlobj.merge_packages(str(packages[0]))

        repositories = include.xpathEval("repositories")
        if len(repositories) > 0:
            self.tdlobj.merge_repositories(str(repositories[0]))


    def __init__(self):
        super(FedoraOS, self).__init__()
        self.cloud_plugin_content = [ ]
        config_obj = ApplicationConfiguration()
        self.app_config = config_obj.configuration
        self.res_mgr = ReservationManager()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.parameters = None
        self.install_script_object = None
        self.guest = None

    def _init_oz(self):
        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = self.active_image.identifier

        # Create a name combining the TDL name and the UUID for use when tagging EC2 AMIs
        self.longname = self.tdlobj.name + "-" + self.new_image_id
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        # 18-Jul-2011 - Moved to constructor and modified to change TDL object name itself
        #   Oz now uses the tdlobject name property directly in several places so we must change it
        self.tdlobj.name = "factory-build-" + self.new_image_id

        # populate a config object to pass to OZ; this allows us to specify our
        # own output dir but inherit other Oz behavior
        self.oz_config = ConfigParser.SafeConfigParser()
        if self.oz_config.read("/etc/oz/oz.cfg") != []:
            self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])
        else:
            raise ImageFactoryException("No Oz config file found. Can't continue.")

        # make this a property to enable quick cleanup on abort
        self.instance = None

        # Here we are always dealing with a local install
        self.init_guest()


    ## INTERFACE METHOD
    def create_base_image(self, builder, template, parameters):
        self.log.info('create_base_image() called for FedoraOS plugin - creating a BaseImage')

        self.tdlobj = oz.TDL.TDL(xmlstring=template.xml, rootpw_required=self.app_config["tdl_require_root_pw"])
        if parameters:
            self.parameters = parameters
        else:
            self.parameters = { }

        # TODO: Standardize reference scheme for the persistent image objects in our builder
        #   Having local short-name copies like this may well be a good idea though they
        #   obscure the fact that these objects are in a container "upstream" of our plugin object
        self.base_image = builder.base_image

        # Set to the image object that is actively being created or modified
        # Used in the logging helper function above
        self.active_image = self.base_image

        try:
            self._init_oz()
            self.guest.diskimage = self.base_image.data
            self.activity("Cleaning up any old Oz guest")
            self.guest.cleanup_old_guest()
            self.activity("Generating JEOS install media")
            self.threadsafe_generate_install_media(self.guest)
            self.percent_complete=10

            # We want to save this later for use by RHEV-M and Condor clouds
            libvirt_xml=""

            try:
                self.activity("Generating JEOS disk image")
                self.guest.generate_diskimage()
                # TODO: If we already have a base install reuse it
                #  subject to some rules about updates to underlying repo
                self.activity("Execute JEOS install")
                libvirt_xml = self.guest.install(self.app_config["timeout"])
                self.base_image.parameters['libvirt_xml'] = libvirt_xml
                self.image = self.guest.diskimage
                self.log.debug("Base install complete - Doing customization and ICICLE generation")
                self.percent_complete = 30
                # Power users may wish to avoid ever booting the guest after the installer is finished
                # They can do so by passing in a { "generate_icicle": False } KV pair in the parameters dict
                if self.parameters.get("generate_icicle", True):
                    self.output_descriptor = self.guest.customize_and_generate_icicle(libvirt_xml)
                else:
                    self.output_descriptor = self.guest.customize(libvirt_xml)
                self.log.debug("Customization and ICICLE generation complete")
                self.percent_complete = 50
            finally:
                self.activity("Cleaning up install artifacts")
                if self.guest:
                    self.guest.cleanup_install()
                if self.install_script_object:
                    # NamedTemporaryFile - removed on close
                    self.install_script_object.close()    

            self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
            # OK great, we now have a customized KVM image

        finally:
            pass
            # TODO: Create the base_image object representing this
            # TODO: Create the base_image object at the beginning and then set the diskimage accordingly

    def init_guest(self):
        # Use the factory function from Oz directly
        # This raises an exception if the TDL contains an unsupported distro or version
        # Cloud plugins that use KVM directly, such as RHEV-M and openstack-kvm can accept
        # any arbitrary guest that Oz is capable of producing
        try:
            install_script_name = None
            install_script = self.parameters.get("install_script", None)
            if install_file:
                self.install_script_object = NamedTemporaryFile()
                self.install_script_object.write(install_script)
                self.install_script_object.flush()
                install_script_name = self.install_script_object.name
            self.guest = oz.GuestFactory.guest_factory(self.tdlobj, self.oz_config, install_script_name)
            # Oz just selects a random port here - This could potentially collide if we are unlucky
            self.guest.listen_port = self.res_mgr.get_next_listen_port()
        except:
            raise ImageFactoryException("OS plugin does not support distro (%s) update (%s) in TDL" % (self.tdlobj.distro, self.tdlobj.update) )

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())
        self.active_image.status_detal['error'] = traceback.format_exc()

    def threadsafe_generate_install_media(self, guest):
        # Oz caching of install media and modified install media is not thread safe
        # Make it safe here using some locks
        # We can only have one active generate_install_media() call for each unique tuple:
        #  (OS, update, architecture, installtype)

        tdl = guest.tdl
        queue_name = "%s-%s-%s-%s" % (tdl.distro, tdl.update, tdl.arch, tdl.installtype)
        self.res_mgr.get_named_lock(queue_name)
        try:
            guest.generate_install_media(force_download=False)
        finally:
            self.res_mgr.release_named_lock(queue_name)


