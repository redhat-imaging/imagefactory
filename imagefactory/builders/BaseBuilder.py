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
from imagefactory import props
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.Template import Template

class BaseBuilder(object):
    """BaseBuilder provides a starting point for builder classes conforming to the IBuilder interface.
    Subclasses of BaseBuilder can focus on the OS/Provider specific activity for creating and
    deploying images."""
    zope.interface.implements(IBuilder)

    template = props.prop("_template", "An instance of the Template class.")
    target = props.prop("_target", "The target cloud for which to build this image.")
    target_id = props.prop("_target_id", "The identifier provided by the target.")
    provider = props.prop("_provider", "The a string name of the target region or provider.")
    new_image_id = props.prop("_new_image_id", "The uuid of the newly created target or provider image.")
    image = props.prop("_image", "The image file path.")
    output_descriptor = props.prop("_output_descriptor", "An XML string describing the completed image, aka: CDL or ICICLE.")
    delegate = props.prop("_delegate", "An object that responds to IBuilderDelegate methods.")
    warehouse = props.prop("_warehouse", "A warehouse object used to store/fetch images, templates, icicle, provider_images, etc...")

    def status():
        doc = "A string value."
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
        doc = "The percentage through an operation."
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

    # Initializer
    def __init__(self, template, target):
        super(BaseBuilder, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.new_image_id = str(uuid.uuid4())
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
    def build_image(self, build_id=None):
        """Build the image file.  This method is implemented by subclasses of BaseBuilder to handle
        OS specific build mechanics."""
        raise NotImplementedError

    def abort(self):
        """Stop building the image file.  This method is implemented by subclasses of BaseBuilder to handle
        OS specific build mechanics."""
        raise NotImplementedError

    def store_image(self, build_id, target_parameters=None):
        template_id = self.warehouse.store_template(self.template.xml, self.template.identifier)
        # Snapshot images do not have ICICLE
        # allow builders to null the descriptor to store a sane indicator in warehouse
        if self.output_descriptor:
            icicle_id = self.warehouse.store_icicle(self.output_descriptor)
        else:
            icicle_id = "none"
        metadata = dict(template=template_id, target=self.target, icicle=icicle_id, target_parameters=target_parameters)
        if build_id:
            metadata['build'] = build_id
        self.warehouse.store_target_image(self.new_image_id, self.image, metadata=metadata)

    def push_image(self, target_image_id, provider, credentials):
        """Prep the image for the provider and deploy.  This method is implemented by subclasses of the
        BaseBuilder to handle OS/Provider specific mechanics."""
        raise NotImplementedError
