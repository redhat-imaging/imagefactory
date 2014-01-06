#!/usr/bin/python
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
import libxml2
import json
import os
import struct
import subprocess
from xml.etree.ElementTree import fromstring
from imgfac.Template import Template
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist, create_cloud_info

class Docker(object):
    zope.interface.implements(CloudDelegate)

    compress_commands = { "xz":    "xz -T 0 --stdout %s > %s",
                          "gzip":  "gzip -c %s > %s",
                          "bzip2": "bzip2 -c %s > %s" }

    def __init__(self):
        super(Docker, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        raise ImageFactoryException("Pushing not currently supported for Docker image builds")

    def snapshot_image_on_provider(self, builder, provider, credentials, template, parameters):
        # TODO: Implement snapshot builds
        raise ImageFactoryException("Snapshot builds not currently supported for Docker")

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.debug("builder_should_create_target_image called for Docker plugin - doing all our work here then stopping the process")
        # At this point our input base_image is available as builder.base_image.data
        # We simply mount it up in libguestfs and tar out the results as builder.target_image.data
        compress_type = parameters.get('compress', None)
        if compress_type:
            if compress_type in self.compress_commands.keys():
                compress_command = self.compress_commands[compress_type]
            else:
                raise Exception("Passed unknown compression type (%s) for Docker plugin" % (compress_type))
        else:
            compress_command = None
        guestfs_handle = launch_inspect_and_mount(builder.base_image.data, readonly = True)
        self.log.debug("Creating tar of root directory of input image %s saving as output image %s" % 
                       (builder.base_image.data, builder.target_image.data) )
        guestfs_handle.tar_out_opts("/", builder.target_image.data)
        if compress_command:
            self.log.debug("Compressing tar file using %s" % (compress_type))
            rawimage =  builder.target_image.data
            compimage =  builder.target_image.data + ".tmp.%s" % (compress_type)
            result = subprocess.call(compress_command % ( rawimage, compimage), shell = True)
            if result:
                raise Exception("Compression of image failed")
            self.log.debug("Compression complete, replacing original")
            os.unlink(rawimage)
            os.rename(compimage, rawimage)
            self.log.debug("Done")
        return False

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        raise ImageFactoryException("builder_will_create_target_image called in Docker plugin - this should never happen")


    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        raise ImageFactoryException("builder_did_create_target_image called in Docker plugin - this should never happen") 
