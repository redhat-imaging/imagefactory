#
#   Copyright 2016 Red Hat, Inc.
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

import zope
import oz.GuestFactory
import oz.TDL
import os
import guestfs
import libxml2
import traceback
import json
import ConfigParser
import logging
import subprocess
from xml.etree.ElementTree import fromstring
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist, create_cloud_info
from imgfac.CloudDelegate import CloudDelegate

class HyperV(object):
    """HyperV target plugin"""
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        super(HyperV, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        raise Exception("delete_from_provider not yet implemented for HyperV")

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_should_create_target_image() called on HyperV plugin - returning True')
        return True

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        pass

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('builder_did_create_target_image() called in HyperV plugin')
        self.status="BUILDING"

        # On entry the image points to either a raw or qcow2 image
        # Convert to vpc and then update the image property
        image = builder.target_image.data
        target_image = image + ".tmp.vpc"
        self.log.debug("Converting input image (%s) to VPC/VHD (%s) using qemu-img" % (image, target_image))
        qemu_img_cmd = [ 'qemu-img', 'convert', '-O', 'vpc', image, target_image ]
        subprocess.check_call(qemu_img_cmd)
        self.log.debug("VPC/VHD conversion complete")
        os.unlink(image)
        os.rename(target_image, image)

        self.percent_complete=100
        self.status="COMPLETED"

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        raise Exception('push_image_to_provider() not yet implemented for HyperV')

    def abort(self):
        pass
