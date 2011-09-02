#
#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import logging
import zope
import uuid
import libxml2
from os.path import isfile
from IBuilder import IBuilder
from imgfac import props
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageWarehouse import ImageWarehouse
from imgfac.Template import Template

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
    def __init__(self, template, target, config_block = None):
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
        self.config_block = config_block

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

    # Utility methods of use to multiple subclasses
    def add_target_content(self):
        """Merge in target specific package and repo content.
        TDL object must already exist as self.tdlobj"""
        doc = None
        if self.config_block:
            doc = libxml2.parseDoc(self.config_block)
        elif isfile("/etc/imagefactory/target_content.xml"):
            doc = libxml2.parseFile("/etc/imagefactory/target_content.xml")
        else:
            self.log.debug("Found neither a call-time config nor a config file - doing nothing")
            return

        # Purely to make the xpath statements below a tiny bit shorter
        target = self.target
        os=self.tdlobj.distro
        version=self.tdlobj.update
        arch=self.tdlobj.arch

        # We go from most to least specific in this order:
        #   arch -> version -> os-> target
        # Note that at the moment we even allow an include statment that covers absolutely everything.
        # That is, one that doesn't even specify a target - this is to support a very simple call-time syntax
	include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and @arch='%s']" %
				(target, os, version, arch))
	if len(include) == 0:
	    include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and not(@arch)]" %
				    (target, os, version))
	if len(include) == 0:
	    include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and not(@version) and not(@arch)]" %
					(target, os))
	if len(include) == 0:
	    include = doc.xpathEval("/template_includes/include[@target='%s' and not(@os) and not(@version) and not(@arch)]" %
					    (target))
	if len(include) == 0:
	    include = doc.xpathEval("/template_includes/include[not(@target) and not(@os) and not(@version) and not(@arch)]")
	if len(include) == 0:
            self.log.debug("cannot find a config section that matches our build details - doing nothing")
	    return

        # OK - We have at least one config block that matches our build - take the first one, merge it and be done
        # TODO: Merge all of them?  Err out if there is more than one?  Warn?
        include = include[0]        

        packages = include.xpathEval("packages")
        if len(packages) > 0:
            self.tdlobj.merge_packages(str(packages[0]))

        repositories = include.xpathEval("repositories")
        if len(repositories) > 0:
            self.tdlobj.merge_repositories(str(repositories[0]))

