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

    ## INTERFACE METHOD
    def create_target_image(self, builder, target, base_image, parameters):
        self.log.info('create_target_image() called for FedoraOS plugin - creating a TargetImage')
        self.log.debug("Currently create_target_image() does nothing here")
        pass

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

    ## INTERFACE METHOD
    def create_base_image(self, builder, template, parameters):
        self.log.info('create_base_image() called for FedoraOS plugin - creating a BaseImage')

        self.tdlobj = oz.TDL.TDL(xmlstring=template.xml, rootpw_required=True)

        # TODO: Standardize reference scheme for the persistent image objects in our builder
        #   Having local short-name copies like this may well be a good idea though they
        #   obscure the fact that these objects are in a container "upstream" of our plugin object
        self.base_image = builder.base_image

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

        # This comes from the original init_guest()
        # Here we are always dealing with a local install
        self.guest = oz.Fedora.get_class(self.tdlobj, self.oz_config, None)

        self.guest.diskimage = self.base_image.datafile
        # The remainder comes from the original build_upload(self, build_id)

        #self.log.debug("Fedora_ec2_Builder: build_upload() called for target %s with warehouse config %s" % (self.target, self.app_config['warehouse']))
        self.status="BUILDING"
        try:
            self.guest.cleanup_old_guest()
            self.threadsafe_generate_install_media(self.guest)
            self.percent_complete=10

            # We want to save this later for use by RHEV-M and Condor clouds
            libvirt_xml=""

            try:
                self.guest.generate_diskimage()
                # TODO: If we already have a base install reuse it
                #  subject to some rules about updates to underlying repo
                self.log.debug("Doing base install via Oz")
                libvirt_xml = self.guest.install(self.app_config["timeout"])
                self.image = self.guest.diskimage
                self.log.debug("Base install complete - Doing customization and ICICLE generation")
                self.percent_complete = 30
                self.output_descriptor = self.guest.customize_and_generate_icicle(libvirt_xml)
                self.log.debug("Customization and ICICLE generation complete")
                self.percent_complete = 50
            finally:
                self.guest.cleanup_install()

            self.log.debug("Generated disk image (%s)" % (self.guest.diskimage))
            # OK great, we now have a customized KVM image

        finally:
            pass
            # TODO: Create the base_image object representing this
            # TODO: Create the base_image object at the beginning and then set the diskimage accordingly

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())

    ## INTERFACE METHOD
    def build_snapshot(self, build_id):
        # All we need do here is store the relevant bits in the Warehouse
        self.status = "BUILDING"
        self.log.debug("Building Linux for non-upload cloud (%s)" % (self.target))
        self.image = "%s/placeholder-linux-image-%s" % (self.app_config['imgdir'], self.new_image_id)
        image_file = open(self.image, 'w')
        image_file.write("Placeholder for non upload cloud Linux image")
        image_file.close()
        self.output_descriptor = None
        self.log.debug("Storing placeholder object for non upload cloud image")
        self.store_image(build_id)
        self.percent_complete = 100
        self.status = "COMPLETED"
        self.log.debug("Completed placeholder warehouse object for linux non-upload image...")
        sleep(5)


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


