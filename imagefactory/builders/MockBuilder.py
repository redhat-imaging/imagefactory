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
        self.warehouse_url = self.app_config['warehouse']
    
    # Image actions
    def build_image(self):
        if(self.template.xml == "<template>FAIL</template>"):
            self.log.debug("build_image() failed for MockBuilder...")
            failing_thread = FailureThread(target=self, kwargs=dict(message="Testing failure conditions via mock target builder..."))
            failing_thread.start()
        else:
            self.log.debug("build_image() called on MockBuilder...")
            self.image = "%s/deltacloud-%s/images/%s.yml" % (self.app_config['output'], os.getlogin(), self.image_id)
            self.log.debug("Setting image build path: %s" % (self.image, ))
            self.status = "INITIALIZING"
            self.log.debug("Initializing mock image...")
            self.percent_complete = 0
            
            directory = os.path.dirname(self.image)
            if (not os.path.exists(directory)):
                os.makedirs(directory)
            
            with open(self.image, 'w') as image_file:
                self.status = "BUILDING"
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
                image_file.write(":uuid: %s\n" % (self.image_id, ))
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
            
            self.store_image()
    
    def push_image(self, image_id, provider, credentials):
        self.status = "INITIALIZING"
        try:
            self.status = "FETCHING IMAGE"
            image, image_metadata = self.warehouse.image_with_id(image_id, ("icicle", ))
            # write the provider image out to the filesystem
            image_path = "%s/deltacloud-%s/%s/images/%s.yml" % (self.app_config['output'], os.getlogin(), provider, self.image_id)
            self.log.debug("Storing mock image for %s at path: %s" % (provider, image_path))
            directory = os.path.dirname(image_path)
            if (not os.path.exists(directory)):
                os.makedirs(directory)
            self.status = "WRITING PROVIDER IMAGE"
            with open(image_path, 'w') as image_file:
                image_file.write(image)
                image_file.close()
            # push the provider image up to the warehouse
            self.status = "PUSHING TO WAREHOUSE"
            metadata = dict(image=image_id, provider=provider, icicle=image_metadata["icicle"], target_identifier="Mock_%s_%s" % (provider, self.image_id))
            self.warehouse.create_provider_image(self.image_id, txt=image)
            self.status = "FINISHING"
            self.log.debug("MockBuilder instance %s pushed image with uuid %s to warehouse location (%s) and set metadata: %s" % (id(self), image_id, this_image_url, metadata))
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
    

        