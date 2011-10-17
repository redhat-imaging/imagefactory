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
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException

class Windows_ec2_Builder(BaseBuilder):
    """docstring for WindowsBuilder"""
    zope.interface.implements(IBuilder)

    # Reference vars - don't change these
    upload_clouds = [ "rhev-m", "vmware" ]
    nonul_clouds = [ "rackspace", "gogrid", "ec2" ]

    # Initializer
    def __init__(self, template="<template><name>Windows</name></template>", target=None):
        super(Windows_ec2_Builder, self).__init__(template, target)
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        try:
            self.proxy_ami_id = self.app_config['proxy_ami_id']
        except:
            raise ImageFactoryException("Windows Proxy ami_id is missing from imagefactory.conf")


    # Image actions
    def build_image(self, build_id):
        if(self.template.xml == "<template>FAIL</template>"):
            self.log.debug("build_image() failed for Windows_ec2_Builder...")
            failing_thread = FailureThread(target=self, kwargs=dict(message="Testing failure conditions via mock target builder..."))
            failing_thread.start()
        else:
            self.log.debug("build_image() called on Windows_ec2_Builder...")
            if self.target in self.nonul_clouds:
                self.log.debug("Building Windows for a non-upload cloud")
                self.image = "%s/placeholder-windows-image-%s" % (self.app_config['imgdir'], self.new_image_id)
                image_file = open(self.image, 'w')
                image_file.write("Placeholder for non upload cloud Windows image")
                image_file.close()
                self.percent_complete = 100
                self.status = "COMPLETED"
                self.log.debug("Completed mock image build...")
                self.store_image(build_id)
                self.log.debug("Image Warehouse storage complete")
            # This gets the original template and target stored along with the placeholder image
            else:
                self.log.debug("Building Windows for an upload cloud")

    def push_image(self, target_image_id, provider, credentials):
        self.status = "INITIALIZING"

        # Decode credentials
        doc = libxml2.parseDoc(credentials)
        ctxt = doc.xpathNewContext()

        ec2_user_id = ctxt.xpathEval("//provider_credentials/ec2_credentials/userid")[0].content
        ec2_api_key = ctxt.xpathEval("//provider_credentials/ec2_credentials/api_key")[0].content

        doc.freeDoc()
        ctxt.xpathFreeContext()

        creds = {'userid':ec2_user_id, 'api-key':ec2_api_key}

        # By this point the original image placeholder has been read and the template and target retrieved
        if self.target in self.nonul_clouds:
            # This is where we do the real work of a build
            new_object = WindowsBuilderWorker(self.template, creds, ec2_region_details[provider], self.proxy_ami_id)
            self.log.status = "BUILDING"
            icicle, provider_image_id, ami_id = new_object.create_provider_image()
            metadata = dict(image=provider_image_id, provider=provider, target_identifier=ami_id, icicle=icicle)
            self.warehouse.create_provider_image(self.new_image_id, txt="This is a placeholder provider_image for Windows", metadata=metadata)
            self.percent_complete=100
            self.status = "COMPLETED"

ec2_region_details={
         'ec2-us-east-1':      { 'host':'us-east-1',      'x86_64': 'ami-1cbd4475' },
         'ec2-us-west-1':      { 'host':'us-west-1',      'x86_64': 'ami-07d28f42' },
         'ec2-ap-southeast-1': { 'host':'ap-southeast-1', 'x86_64': 'ami-4edca21c' },
         'ec2-ap-northeast-1': { 'host':'ap-northeast-1', 'x86_64': 'ami-c01cb7c1' },
         'ec2-eu-west-1':      { 'host':'eu-west-1',      'x86_64': 'ami-f8c9ff8c' } }
