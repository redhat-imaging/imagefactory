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
from imagebuilderinterface import ImageBuilderInterface
from basebuilder import BaseBuilder
import uuid
import time


class MockBuilder(BaseBuilder):
	# TODO: sloranz@redhat.com - Flesh out this docstring more to document this module.
	"""docstring for MockBuilder"""
	zope.interface.implements(ImageBuilderInterface)
	
# Initializer
	def __init__(self, template=None, target=None, image_id=uuid.uuid4(), credentials=None):
		super(MockBuilder, self).__init__(template, target, image_id, credentials)
	
# Image actions
	def build(self):
		image_path = "/tmp/image_factory-{!s}".format(str(self.image_id))
		self.status = "INITIALIZING"
		self.percent_complete = 0
		
		with open(image_path, 'w') as image_file:
			self.status = "BUILDING"
			image_file.write(':description: This is a mock build image for testing the image factory.\n')
			self.percent_complete = 5
			image_file.write(':name: Mock Image\n')
			self.percent_complete = 10
			image_file.write(':owner_id: fedoraproject\n')
			self.percent_complete = 15
			image_file.write(':architecture: x86_64\n')
			self.percent_complete = 20
		
		time.sleep(2)
		self.percent_complete = 50
		time.sleep(2)
		self.percent_complete = 75
		time.sleep(2)
		self.percent_complete = 95
		self.status = "FINISHING"
		time.sleep(2)
		self.percent_complete = 100
		self.status = "COMPLETED"
	
	def abort(self):
		pass
	
