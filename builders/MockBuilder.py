#
# Copyright (C) 2010 Red Hat, Inc.
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
import time
# import imagefactory
import logging
from ImageBuilderInterface import ImageBuilderInterface
from BaseBuilder import BaseBuilder
from ApplicationConfiguration import ApplicationConfiguration


class MockBuilder(BaseBuilder):
    # TODO: (redmine 278) - Flesh out this docstring more to document this module.
    """docstring for MockBuilder"""
    zope.interface.implements(ImageBuilderInterface)
    
    # Initializer
    def __init__(self, template='<template><name>Mock</name></template>', target='mock'):
        super(MockBuilder, self).__init__(template, target)
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
    
    # Image actions
    def build(self):
        self.log.debug("build() called on MockBuilder...")
        app_config = ApplicationConfiguration().configuration
        self.log.debug("Getting application configuration: %s" % (app_config, ))
        self.image = "%s/%s.miso" % (app_config['output'], self.image_id)
        self.log.debug("Setting image build path: %s" % (self.image, ))
        self.status = "INITIALIZING"
        self.log.debug("Initializing mock image...")
        self.percent_complete = 0
        
        with open(self.image, 'w') as image_file:
            self.status = "BUILDING"
            self.log.debug("Building mock image...")
            image_file.write(':description: This is a mock build image for testing the image factory.\n')
            self.percent_complete = 5
            image_file.write(':name: Mock Image\n')
            self.percent_complete = 10
            image_file.write(':owner_id: fedoraproject\n')
            self.percent_complete = 15
            image_file.write(':architecture: x86_64\n')
            self.percent_complete = 20
            image_file.close()
        
        time.sleep(2)
        self.percent_complete = 50
        time.sleep(2)
        self.percent_complete = 75
        time.sleep(2)
        self.percent_complete = 95
        self.status = "FINISHING"
        self.log.debug("Finishing mock image...")
        time.sleep(2)
        self.percent_complete = 100
        self.status = "COMPLETED"
        self.log.debug("Completed mock image build...")
        
        if (app_config['warehouse']):
            self.log.debug("Storing mock image at %s..." % (app_config['warehouse'], ))
            self.store_image(app_config['warehouse'])
    
    def abort(self):
        pass
    
