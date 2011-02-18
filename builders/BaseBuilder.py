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

import logging
import zope
import uuid
import os
import pycurl
import httplib2
from IBuilder import IBuilder

# TODO: (redmine 256) - add build_states() analagous to instance_states() in core - http://deltacloud.org/framework.html
class BaseBuilder(object):
    """BaseBuilder provides a starting point for builder classes conforming to the IBuilder interface.  Subclasses of BaseBuilder 
    can focus on the OS/Provider specific activity for creating and deploying images."""
    zope.interface.implements(IBuilder)
    
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
    
    def target_id():
        doc = "The target_id property."
        def fget(self):
            return self._target_id
        def fset(self, value):
            self._target_id = value
        def fdel(self):
            del self._target_id
        return locals()
    target_id = property(**target_id())
    
    def provider():
        doc = "The provider property."
        def fget(self):
            return self._provider
        def fset(self, value):
            self._provider = value
        def fdel(self):
            del self._provider
        return locals()
    provider = property(**provider())
    
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
        
        return locals()
    percent_complete = property(**percent_complete())
    
    def output_descriptor():
        doc = "The output_descriptor property."
        def fget(self):
            return self._output_descriptor
        def fset(self, value):
            self._output_descriptor = value
        def fdel(self):
            del self._output_descriptor
        return locals()
    output_descriptor = property(**output_descriptor())
    
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
    def __init__(self, template=None, target=None):
        super(BaseBuilder, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.template = template
        self.target = target
        self.target_id = None
        self.provider = None
        self.image_id = uuid.uuid4()
        self.image = None
        self._status = "NEW"
        self._percent_complete = 0
        self.output_descriptor = "<icicle></icicle>"
        self.delegate = None
    
    # Make instances callable for passing to thread objects
    def __call__(self, *args, **kwargs):
        # the method that we want to call on self is in args... kwargs is the method parameters, if there are any.
        getattr(self, str().join(args))(**kwargs)
    
    # Image actions
    def build_image(self):
        """Build the image file.  This method is implemented by subclasses of BaseBuilder to handle OS specific build mechanics."""
        raise NotImplementedError
    
    def abort(self):
        """Stop building the image file.  This method is implemented by subclasses of BaseBuilder to handle OS specific build mechanics."""
        raise NotImplementedError
    
    def store_image(self, location, target_parameters=None):
        """Store the image in an instance of Image Warehouse specified by 'location'.  Any provider specific 
        parameters needed for later deploying images are passed as an XML block in 'target_parameters'."""
        
        http = httplib2.Http()
        http_headers = {'content-type':'text/plain'}
        
        # since there is no way to know if the bucket exists or not, do the put on the base URL first since it seems to be non-destructive
        try:
            http.request(location, "PUT", headers=http_headers)
            
            if (not location.endswith('/')):
                location = "%s/" % (location, )
            
            base_url = "%s%s" % (location, self.image_id)
            self.log.debug("File (%s) to be stored at %s" % (self.image, base_url))
            image_file = open(self.image)
            
            # Upload the image itself
            image_size = os.path.getsize(self.image)
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, base_url)
            curl.setopt(pycurl.HTTPHEADER, ["User-Agent: Load Tool (PyCURL Load Tool)"])
            curl.setopt(pycurl.PUT, 1)
            curl.setopt(pycurl.INFILE, image_file)
            curl.setopt(pycurl.INFILESIZE, image_size)
            curl.perform()
            curl.close()
            image_file.close()
            
            metadata = dict(uuid=self.image_id, type="image", template=self.template, target=self.target, target_parameters=target_parameters, icicle=self.output_descriptor)
            self.__set_storage_metadata(base_url, metadata)
        except Exception, e:
            self.log.exception("Image could not be stored...  Check status of image warehouse!  \nCaught exception while trying to store image(%s):\n%s" % (self.image_id, e))
        
    
    def __set_storage_metadata(self, url, metadata):
        http = httplib2.Http()
        for item in metadata:
            http.request("%s/%s" % (url, item), "PUT", body=str(metadata[item]), headers={'content-type':'text/plain'})
    
    def push_image(self, image_id, provider, credentials):
        """Prep the image for the provider and deploy.  This method is implemented by subclasses of the BaseBuilder to handle OS/Provider specific mechanics."""
        raise NotImplementedError
    
