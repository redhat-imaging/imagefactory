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
import os
import os.path
from threading import Thread
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder
from imagefactory.ApplicationConfiguration import ApplicationConfiguration


class MockBuilder(BaseBuilder):
    """docstring for MockBuilder"""
    zope.interface.implements(IBuilder)

    # Initializer
    def __init__(self, template="<template><name>Mock</name></template>", target='mock'):
        super(MockBuilder, self).__init__(template, target)
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.app_config = ApplicationConfiguration().configuration

    # Image actions
    def build_image(self, build_id=None):
        if(self.template.xml == "<template>FAIL</template>"):
            self.log.debug("build_image() failed for MockBuilder...")
            failing_thread = FailureThread(target=self, kwargs=dict(message="Testing failure conditions via mock target builder..."))
            failing_thread.start()
        else:
            self.log.debug("build_image() called on MockBuilder...")
            self.image = "%s/deltacloud-%s/images/%s.yml" % (self.app_config['imgdir'], os.getlogin(), self.new_image_id)
            self.log.debug("Setting image build path: %s" % (self.image, ))
            self.status = "INITIALIZING"
            self.log.debug("Initializing mock image...")
            self.percent_complete = 0

            directory = os.path.dirname(self.image)
            if (not os.path.exists(directory)):
                os.makedirs(directory)

            with open(self.image, 'w') as image_file:
                self.status = "PENDING"
                self.log.debug("Building mock image...")
                image_file.write(':description: This is a mock build image for testing the image factory.\n')
                self.percent_complete = 5
                image_file.write(':name: Mock Image\n')
                self.percent_complete = 10
                image_file.write(':owner_id: Mock Owner\n')
                self.percent_complete = 15
                image_file.write(':architecture: mock_architecture\n')
                self.percent_complete = 20
                image_file.write(":object_id: %s\n" % (id(self), ))
                image_file.write(":uuid: %s\n" % (self.new_image_id, ))
                image_file.write(":created_by: %s\n" % (sys.argv[0].rpartition('/')[2], ))
                image_file.write(":created_on: %s\n" % (time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()), ))
                image_file.close()

            self.percent_complete = 50
            self.percent_complete = 75
            self.percent_complete = 95
            self.status = "FINISHING"
            self.log.debug("Finishing mock image...")
            self.percent_complete = 100
            self.status = "COMPLETED"
            self.log.debug("Completed mock image build...")

            self.store_image(build_id)

    def push_image(self, target_image_id, provider, credentials):
        self.status = "INITIALIZING"
        try:
            self.status = "PENDING"
            image, image_metadata = self.warehouse.target_image_with_id(target_image_id, metadata_keys=("icicle", ))
            # write the provider image out to the filesystem
            image_path = "%s/deltacloud-%s/%s/images/%s.yml" % (self.app_config['imgdir'], os.getlogin(), provider, self.new_image_id)
            self.log.debug("Storing mock image for %s at path: %s" % (provider, image_path))
            directory = os.path.dirname(image_path)
            if (not os.path.exists(directory)):
                os.makedirs(directory)
            with open(image_path, 'w') as image_file:
                image_file.write(image)
                image_file.close()
            # push the provider image up to the warehouse
            metadata = dict(target_image=target_image_id, provider=provider, icicle=image_metadata["icicle"], target_identifier="Mock_%s_%s" % (provider, self.new_image_id))
            self.warehouse.create_provider_image(self.new_image_id, txt=image, metadata=metadata)
            self.status = "FINISHING"
            self.log.debug("MockBuilder instance %s pushed image with uuid %s to warehouse (%s/%s) and set metadata: %s" % (id(self), target_image_id, self.warehouse.url, self.warehouse.provider_image_bucket, metadata))
            self.status = "COMPLETED"
        except Exception, e:
            failing_thread = FailureThread(target=self, kwargs=dict(message="%s" % (e, )))
            failing_thread.start()

    def abort(self):
        self.log.debug("Method abort() called on MockBuilder instance %s" % (id(self), ))


class FailureThread(Thread):
    """docstring for FailureThread"""
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        super(FailureThread, self).__init__(group=None, target=None, name=None, args=(), kwargs={})
        self.target = target
        self.message = kwargs["message"]

    def run(self):
        time.sleep(1)
        self.target.delegate.builder_did_fail(self, "Mock", self.message)
