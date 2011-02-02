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
    
    
    # Initializer
    def __init__(self, template=None, target=None):
        super(BaseBuilder, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.image = None
        self.delegate = None
        self._status = None
        self._percent_complete = 0
        self.template = template
        self.target = target
        self.image_id = uuid.uuid4()
        self.output_descriptor = "<icicle></icicle>"
    
    # Make instances callable for passing to thread objects
    def __call__(self, *args, **kwargs):
        getattr(self, str().join(args))(**kwargs)
    
    # Image actions
    def build_image(self):
        """Build the image file.  This method is implemented by subclasses of BaseBuilder to handle OS specific build mechanics."""
        raise NotImplementedError
    
    def abort(self):
        """Stop building the image file.  This method is implemented by subclasses of BaseBuilder to handle OS specific build mechanics."""
        raise NotImplementedError
    
    def store_image(self, location, target_args=None):
        """Store the image in an instance of Image Warehouse specified by 'location'.  Any provider specific 
        parameters needed for later deploying images are passed as an XML block in 'target_args'."""
        http = httplib2.Http()
        http_headers = {'content-type':'text/plain'}
        
        # since there is no way to know if the bucket exists or not, do the put on the base URL first since it seems to be non-destructive
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
        
        # Set metadata on the image
        http.request("%s/uuid" % (base_url, ), "PUT", body=str(self.image_id), headers=http_headers)
        http.request("%s/type" % (base_url, ), "PUT", body="image", headers=http_headers)
        http.request("%s/template" % (base_url, ), "PUT", body=self.template, headers=http_headers)
        http.request("%s/target" % (base_url, ), "PUT", body=self.target, headers=http_headers)
        if (target_args):
            http.request("%s/target-parameters" % (base_url, ), "PUT", body=target_args, headers=http_headers)
        if (self.output_descriptor):
            http.request("%s/icicle" % (base_url, ), "PUT", body=self.output_descriptor, headers=http_headers)
    
    def push_image(self, image_id, provider, credentials):
        """Prep the image for the provider and deploy.  This method is implemented by subclasses of the BaseBuilder to handle OS/Provider specific mechanics."""
        raise NotImplementedError
    
