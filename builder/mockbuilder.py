#!/usr/bin/env python
# encoding: utf-8


class BaseBuilder(object):
	"""docstring for BaseBuilder"""

# Properties	
	def idl():
	    doc = "The idl property."
	    def fget(self):
	        return self._idl
	    def fset(self, value):
	        self._idl = value
	    def fdel(self):
	        del self._idl
	    return locals()
	idl = property(**idl())
	
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
	
	def percenty_complete():
	    doc = "The percenty_complete property."
	    def fget(self):
	        return self._percenty_complete
	    def fset(self, value):
	        self._percenty_complete = value
	    def fdel(self):
	        del self._percenty_complete
	    return locals()
	percenty_complete = property(**percenty_complete())
	
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
	def __init__(self, idl, target, uuid, credentials):
		super(BaseBuilder, self).__init__()
		self.idl = idl
		self.target = target
		self.uuid = uuid
		self.credentials = credentials
		

# Image actions
	def generate_image(self):
		pass
		
	def abort(self):
		pass
		
