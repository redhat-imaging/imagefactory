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


class MockBuilder(object):
	"""docstring for MockBuilder"""
	zope.interface.implements(ImageBuilderInterface)
	

# Properties
	def template():
	    doc = "The template property."
	    def fget(self):
	        return self._template
	    def fset(self, value):
	        self._template = value
	    def fdel(self):
	        del self._template
	    return locals()
	template = property(**template())
	
	def target():
	    doc = "The target property."
	    def fget(self):
	        return self._target
	    def fset(self, value):
	        self._target = value
	    def fdel(self):
	        del self._target
	    return locals()
	target = property(**target())
	
	def uuid():
	    doc = "The uuid property."
	    def fget(self):
	        return self._uuid
	    def fset(self, value):
	        self._uuid = value
	    def fdel(self):
	        del self._uuid
	    return locals()
	uuid = property(**uuid())
	
	def credentials():
	    doc = "The credentials property."
	    def fget(self):
	        return self._credentials
	    def fset(self, value):
	        self._credentials = value
	    def fdel(self):
	        del self._credentials
	    return locals()
	credentials = property(**credentials())
	
	def status():
	    doc = "The status property."
	    def fget(self):
	        return self._status
	    def fset(self, value):
	        self._status = value
	    def fdel(self):
	        del self._status
	    return locals()
	status = property(**status())
	
	def percent_complete():
	    doc = "The percent_complete property."
	    def fget(self):
	        return self._percent_complete
	    def fset(self, value):
	        self._percent_complete = value
	    def fdel(self):
	        del self._percent_complete
	    return locals()
	percent_complete = property(**percent_complete())
	
	def image():
	    doc = "The image property."
	    def fget(self):
	        return self._image
	    def fset(self, value):
	        self._image = value
	    def fdel(self):
	        del self._image
	    return locals()
	image = property(**image())
	

# Initializer
	def __init__(self, template=None, target=None, uuid=None, credentials=None):
		super(MockBuilder, self).__init__()
		self.template = template
		self.target = target
		self.uuid = uuid
		self.credentials = credentials
		

# Image actions
	def build(self):
		pass
		
	def abort(self):
		pass
		
