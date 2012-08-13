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
import oz.Fedora
import oz.RHEL_5
import oz.RHEL_6
import oz.TDL
import subprocess
import os
import os.path
import re
import guestfs
import string
import libxml2
import httplib2
import traceback
import pycurl
import gzip
import ConfigParser
from time import *
from tempfile import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.ReservationManager import ReservationManager

from imgfac.OSDelegate import OSDelegate
from imgfac.BaseImage import BaseImage
from imgfac.TargetImage import TargetImage

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
        self.active_image = self.builder.target_image

        # Merge together any TDL-style customizations requested via our plugin-to-plugin interface
        # with any target specific packages, repos and commands and then run a second Oz customization
        # step.
        self.tdlobj = oz.TDL.TDL(xmlstring=builder.base_image.template.xml, rootpw_required=True)
        
        # We remove any packages and commands from the original TDL - these have already been
        # installed/executed.  We leave the repos in place, as it is possible that the target
        # specific packages or commands may require them.
        self.tdlobj.packages = [ ]
        self.tdlobj.commands = { }
        self.add_target_content()

        # populate our target_image bodyfile with the original base image
        # which we do not want to modify in place
        self.activity("Copying BaseImage to modifiable TargetImage")
        self.log.debug("Copying base_image file (%s) to new target_image file (%s)" % (builder.base_image.data, builder.target_image.data))
        shutil.copy2(builder.base_image.data, builder.target_image.data)
        self.image = builder.target_image.data

        # Retrieve original libvirt_xml from base image - update filename
        input_doc = libxml2.parseDoc(builder.base_image.parameters['libvirt_xml'])
        disknodes = input_doc.xpathEval("/domain/devices/disk")
        for disknode in disknodes:
            if disknode.prop('device') == 'disk':
                disknode.xpathEval('source')[0].setProp('file', builder.target_image.data)

        libvirt_xml = xml = input_doc.serialize(None, 1)

        self._init_oz()

        try:
            self.log.debug("Doing second-stage target_image customization and ICICLE generation")
            #self.percent_complete = 30
            self.output_descriptor = self.guest.customize_and_generate_icicle(libvirt_xml)
            self.log.debug("Customization and ICICLE generation complete")
            #self.percent_complete = 50
        finally:
            self.activity("Cleaning up install artifacts")
            self.guest.cleanup_install()


    def add_target_content(self):
        """Merge in target specific package and repo content.
        TDL object must already exist as self.tdlobj"""
        doc = None
        if self.config_block:
            doc = libxml2.parseDoc(self.config_block)
        elif isfile("/etc/imagefactory/target_content.xml"):
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
        config_obj = ApplicationConfiguration()
        self.app_config = config_obj.configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        if "ec2" in config_obj.jeos_images:
            self.ec2_jeos_amis = config_obj.jeos_images['ec2']
        else:
            self.log.warning("No JEOS amis defined for ec2.  Snapshot builds will not be possible.")
            self.ec2_jeos_amis = {}


    def _init_oz(self):
        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = self.base_image.identifier

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
        self.oz_config.read("/etc/oz/oz.cfg")
        self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])
        # make this a property to enable quick cleanup on abort
        self.instance = None

        # Here we are always dealing with a local install
        self.init_guest()


    ## INTERFACE METHOD
    def create_base_image(self, builder, template, parameters):
        self.log.info('create_base_image() called for FedoraOS plugin - creating a BaseImage')

        self.tdlobj = oz.TDL.TDL(xmlstring=template.xml, rootpw_required=True)

        # TODO: Standardize reference scheme for the persistent image objects in our builder
        #   Having local short-name copies like this may well be a good idea though they
        #   obscure the fact that these objects are in a container "upstream" of our plugin object
        self.base_image = builder.base_image

        # Set to the image object that is actively being created or modified
        # Used in the logging helper function above
        self.active_image = self.base_image

        self._init_oz()

        self.guest.diskimage = self.base_image.data
        # The remainder comes from the original build_upload(self, build_id)

        self.status="BUILDING"
        try:
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
                self.output_descriptor = self.guest.customize_and_generate_icicle(libvirt_xml)
                self.log.debug("Customization and ICICLE generation complete")
                self.percent_complete = 50
            finally:
                self.activity("Cleaning up install artifacts")
                self.guest.cleanup_install()

            self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
            # OK great, we now have a customized KVM image

        finally:
            pass
            # TODO: Create the base_image object representing this
            # TODO: Create the base_image object at the beginning and then set the diskimage accordingly

    def init_guest(self):
        # TODO: See if we can make this a bit more dynamic
        if self.tdlobj.distro == "RHEL-5":
            self.guest = oz.RHEL_5.get_class(self.tdlobj, self.oz_config, None)
        elif self.tdlobj.distro == "RHEL-6":
            self.guest = oz.RHEL_6.get_class(self.tdlobj, self.oz_config, None)
        elif self.tdlobj.distro == "Fedora":
            self.guest = oz.Fedora.get_class(self.tdlobj, self.oz_config, None)
        else:
            raise ImageFactoryException("OS plugin does not support distro (%s) in TDL" % (self.tdlobj.distro) )

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
        res_mgr = ReservationManager()
        res_mgr.get_named_lock(queue_name)
        try:
            guest.generate_install_media(force_download=False)
        finally:
            res_mgr.release_named_lock(queue_name)


