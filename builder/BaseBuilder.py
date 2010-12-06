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
from ImageBuilderInterface import ImageBuilderInterface

# TODO: sloranz@redhat.com - add build_states() analagous to instance_states() in core - http://deltacloud.org/framework.html
class BaseBuilder(object):
	"""docstring for BaseBuilder"""
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
	
	def image_id():
	    doc = "The image_id property."
	    def fget(self):
	        return self._image_id
	    def fset(self, value):
	        self._image_id = value
	    def fdel(self):
	        del self._image_id
	    return locals()
	image_id = property(**image_id())
	
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
			if(self.delegate):
				try: #check with the delegate if we should update
					_shouldSet = getattr(self.delegate, "builder_should_update_status")(self, self._status, value)
				except AttributeError, e: #if the delegate doesn't respond to this method, we'll just go ahead with it
					_shouldSet = True
				try: #give the delegate a chance to intervene on the update
					if _shouldSet : value = getattr(self.delegate, "builder_will_update_status")(self, self._status, value)
				except AttributeError, e:
					pass
				if(_shouldSet):
					_original_status = self._status
					self._status = value
					try: #tell the delegate that the update occurred
						getattr(self.delegate, "builder_did_update_status")(self, _original_status, self._status)
					except AttributeError, e:
						pass
			else:
				self._status = value
		
	    # def fdel(self):
	    #     del self._status
		
	    return locals()
	status = property(**status())
	
	def percent_complete():
	    doc = "The percent_complete property."
	    def fget(self):
	        return self._percent_complete
		
	    def fset(self, value):
			if(self.delegate):
				try: #check with the delegate if we should update
					_shouldSet = getattr(self.delegate, "builder_should_update_percentage")(self, self._percent_complete, value)
				except AttributeError, e: #if the delegate doesn't respond to this method, we'll just go ahead with it
					_shouldSet = True
				try: #give the delegate a chance to intervene on the update
					if _shouldSet : value = getattr(self.delegate, "builder_will_update_percentage")(self, self._percent_complete, value)
				except AttributeError, e:
					pass
				if(_shouldSet):
					_original_percentage = self._percent_complete
					self._percent_complete = value
					try: #tell the delegate that the update occurred
						getattr(self.delegate, "builder_did_update_percentage")(self, _original_percentage, self._percent_complete)
					except AttributeError, e:
						pass
			else:
				self._percent_complete = value
		
	    # def fdel(self):
	    #     del self._percent_complete
		
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
	
	def delegate():
	    doc = "The delegate property."
	    def fget(self):
	        return self._delegate
	    def fset(self, value):
	        self._delegate = value
	    def fdel(self):
	        del self._delegate
	    return locals()
	delegate = property(**delegate())
	

# Initializer
	def __init__(self, template=None, target=None, image_id=None, credentials=None):
		super(BaseBuilder, self).__init__()
		self.delegate = None
		self._status = None
		self._percent_complete = 0
		self.template = template
		self.target = target
		self.image_id = image_id
		self.credentials = credentials
	
# Make instances callable for passing to thread objects
	def __call__(self):
		self.build()
	
# Image actions
	def build(self):
		pass
	
	def abort(self):
		pass
	
