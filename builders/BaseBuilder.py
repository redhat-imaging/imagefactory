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
        self.delegate = None
        self._status = None
        self._percent_complete = 0
        self.template = template
        self.target = target
        self.image_id = uuid.uuid4()
        self.output_descriptor = "<icicle></icicle>"
    
    # Make instances callable for passing to thread objects
    def __call__(self):
        self.build()
    
    # Image actions
    def build(self):
        raise NotImplementedError
    
    def abort(self):
        raise NotImplementedError
    
    def store_image(self, location, target_args=None):
        # TODO: sloranz@redhat.com - Check to make sure the bucket exists. If not do a PUT on it first.
        if (not location.endswith('/')):
            location = "%s/" % (location, )
        image_url = "%simage.%s" % (location, self.image_id)
        self.log.debug("File (%s) to be stored at %s" % (self.image, image_url))
        image_file = open(self.image)
        # Upload the image itself
        image_size = os.path.getsize(self.image)
        curl = pycurl.Curl()
        curl.setopt(pycurl.URL, image_url)
        curl.setopt(pycurl.HTTPHEADER, ["User-Agent: Load Tool (PyCURL Load Tool)"])
        curl.setopt(pycurl.PUT, 1)
        curl.setopt(pycurl.INFILE, image_file)
        curl.setopt(pycurl.INFILESIZE, image_size)
        curl.perform()
        curl.close()
        image_file.close()
        # Set metadata on the image
        http = httplib2.Http()
        http_headers = {'content-type':'text/plain'}
        http.request("%s/template" % (image_url, ), "PUT", body=self.template, headers=http_headers)
        http.request("%s/target" % (image_url, ), "PUT", body=self.target, headers=http_headers)
        if (target_args):
            http.request("%s/target-parameters" % (image_url, ), "PUT", body=self.target, headers=http_headers)
        if (self.output_descriptor):
            http.request("%s/icicle" % (image_url, ), "PUT", body=self.output_descriptor, headers=http_headers)
    
    def push_image(self, image, provider, target_id, credentials):
        raise NotImplementedError
    
