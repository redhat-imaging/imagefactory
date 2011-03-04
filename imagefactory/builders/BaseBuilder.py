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

import logging
import zope
import uuid
import os
import httplib2
from IBuilder import IBuilder
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.Template import Template

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
    
    def warehouse():
        doc = "The warehouse property."
        def fget(self):
            return self._warehouse
        def fset(self, value):
            self._warehouse = value
        def fdel(self):
            del self._warehouse
        return locals()
    warehouse = property(**warehouse())
    
    # Initializer
    def __init__(self, template, target):
        super(BaseBuilder, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.image_id = uuid.uuid4()
        if(type(template) == Template):
            self.template = template
        elif(type(template) == str):
            self.template = Template(template)
        else:
            raise TypeError("template should be a string representation of UUID, URL, or XML document...")
        self.target = target
        self.target_id = None
        self.provider = None
        self.image = None
        self._status = "NEW"
        self._percent_complete = 0
        self.output_descriptor = "<icicle></icicle>"
        self.delegate = None
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
    
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
    
    def store_image(self, target_parameters=None):
        template_id = self.warehouse.store_template(self.template.xml, self.template.identifier)
        icicle_id = self.warehouse.store_icicle(self.output_descriptor)
        metadata = dict(template=template_id, target=self.target, icicle=icicle_id, target_parameters=target_parameters)
        self.warehouse.store_image(self.image_id, self.image, metadata)
    
    def push_image(self, image_id, provider, credentials):
        """Prep the image for the provider and deploy.  This method is implemented by subclasses of the BaseBuilder to handle OS/Provider specific mechanics."""
        raise NotImplementedError
    
