#
# Copyright (C) 2010-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import zope
import sys
import time
import logging
import httplib2
import libxml2
import os
import os.path
import oz.Windows
import oz.TDL
from threading import Thread
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from WindowsBuilderWorker import WindowsBuilderWorker
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
#import WindowsBuilderWorker

class WindowsBuilder(BaseBuilder):
    """docstring for WindowsBuilder"""
    zope.interface.implements(IBuilder)

    # Reference vars - don't change these
    upload_clouds = [ "rhev-m", "vmware" ]
    nonul_clouds = [ "rackspace", "gogrid", "ec2" ]

    # Initializer
    def __init__(self, template="<template><name>Windows</name></template>", target=None):
        super(WindowsBuilder, self).__init__(template, target)
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']

    # Image actions
    def build_image(self):
        if(self.template.xml == "<template>FAIL</template>"):
            self.log.debug("build_image() failed for WindowsBuilder...")
            failing_thread = FailureThread(target=self, kwargs=dict(message="Testing failure conditions via mock target builder..."))
            failing_thread.start()
        else:
            self.log.debug("build_image() called on WindowsBuilder...")
            if self.target in self.nonul_clouds:
                self.log.debug("Building Windows for a non-upload cloud")
                self.image = "%s/placeholder-windows-image-%s" % (self.app_config['imgdir'], self.image_id)
                image_file = open(self.image, 'w')
                image_file.write("Placeholder for non upload cloud Windows image")
                image_file.close()
                self.percent_complete = 100
                self.status = "COMPLETED"
                self.log.debug("Completed mock image build...")
                self.store_image()
            # This gets the original template and target stored along with the placeholder image
            else:
                self.log.debug("Building Windows for an upload cloud")

    def push_image(self, image_id, provider, credentials):
        self.status = "INITIALIZING"

        # Decode credentials
        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()

        rackspace_user_id = ctxt.xpathEval("//provider_credentials/rackspace_credentials/username")[0].content
        rackspace_key = ctxt.xpathEval("//provider_credentials/rackspace_credentials/api_key")[0].content

        doc.freeDoc()
        ctxt.xpathFreeContext()

        creds = {'userid':rackspace_user_id, 'api-key':rackspace_key}

        # By this point the original image placeholder has been read and the template and target retrieved
        if self.target in self.nonul_clouds:
            # This is where we do the real work of a build
            new_object = WindowsBuilderWorker(self.template, creds, provider)
            self.log.status = "BUILDING"
            icicle, provider_image_id = new_object.create_provider_image()
            metadata = dict(image=image_id, provider=provider, target_identifier=provider_image_id, icicle=icicle)
            self.warehouse.create_provider_image(self.image_id, txt="This is a placeholder provider_image for Windows", metadata=metadata)
            self.percent_complete=100
            self.status = "COMPLETED"
