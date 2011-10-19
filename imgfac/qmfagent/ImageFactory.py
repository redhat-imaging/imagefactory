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

import sys
import cqpid
from qmf2 import *
import httplib2
from BuildAdaptor import BuildAdaptor
from imgfac import props
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.ImageWarehouse import ImageWarehouse
from imgfac.Singleton import Singleton
from imgfac.Template import Template
import logging

# Singleton representing the Factory itself

class ImageFactory(Singleton):

    # QMF schema for ImageFactory
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "ImageFactory")
    # method for building an image
    _build_image_method = SchemaMethod("image", desc="Build a new image for a given target cloud")
    _build_image_method.addArgument(SchemaProperty("template", SCHEMA_DATA_STRING, direction=DIR_IN, desc="string of xml, uuid, or url"))
    _build_image_method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN, desc="name of the cloud to target"))
    _build_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT, desc="the QMF address of the build_adaptor instantiated"))
    qmf_schema.addMethod(_build_image_method)
    # method for building images
    _build_images_method = SchemaMethod("build_image", desc="Build an image for the given target clouds")
    _build_images_method.addArgument(SchemaProperty("image", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the UUID of an image previously built"))
    _build_images_method.addArgument(SchemaProperty("build", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the UUID of a previous build of the image"))
    _build_images_method.addArgument(SchemaProperty("template", SCHEMA_DATA_STRING, direction=DIR_IN, desc="string of xml, uuid, or url"))
    _build_images_method.addArgument(SchemaProperty("targets", SCHEMA_DATA_LIST, direction=DIR_IN, desc="names of the clouds to target"))
    _build_images_method.addArgument(SchemaProperty("build_adaptors", SCHEMA_DATA_LIST, direction=DIR_OUT, desc="the QMF addresses of the build_adaptors instantiated"))
    qmf_schema.addMethod(_build_images_method)
    # method for creating a provider_image from an image
    _push_image_method = SchemaMethod("provider_image", desc="Push an image to a provider.")
    _push_image_method.addArgument(SchemaProperty("image_id", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the uuid of an image previously built"))
    _push_image_method.addArgument(SchemaProperty("provider", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the name of the cloud provider, often a region"))
    _push_image_method.addArgument(SchemaProperty("credentials", SCHEMA_DATA_STRING, direction=DIR_IN, desc="an xml string representation of the credentials"))
    _push_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT, desc="the QMF address of the build_adaptor instantiated"))
    qmf_schema.addMethod(_push_image_method)
    # method for pushing an image to multiple providers
    _push_images_method = SchemaMethod("push_image", desc="Push an image to multiple providers.")
    _push_images_method.addArgument(SchemaProperty("image", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the UUID of an image previously built"))
    _push_images_method.addArgument(SchemaProperty("build", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the UUID of a previous build of the image"))
    _push_images_method.addArgument(SchemaProperty("providers", SCHEMA_DATA_LIST, direction=DIR_IN, desc="the names of the cloud providers, often regions"))
    _push_images_method.addArgument(SchemaProperty("credentials", SCHEMA_DATA_STRING, direction=DIR_IN, desc="an xml string representation of the credentials"))
    _push_images_method.addArgument(SchemaProperty("build_adaptors", SCHEMA_DATA_LIST, direction=DIR_OUT, desc="the QMF addresses of the build_adaptors instantiated"))
    qmf_schema.addMethod(_push_images_method)
    # method for importing a provider image
    _import_image_method = SchemaMethod("import_image", desc="Import an image using a target specific image identifier")
    _import_image_method.addArgument(SchemaProperty("image", SCHEMA_DATA_STRING, direction=DIR_IN_OUT, desc="the UUID of an image previously built"))
    _import_image_method.addArgument(SchemaProperty("build", SCHEMA_DATA_STRING, direction=DIR_IN_OUT, desc="the UUID of a previous build of the image"))
    _import_image_method.addArgument(SchemaProperty("target_identifier", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the target specific image ID"))
    _import_image_method.addArgument(SchemaProperty("image_desc", SCHEMA_DATA_STRING, direction=DIR_IN, desc="an xml string description of the image"))
    _import_image_method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN, desc="name of the cloud to target"))
    _import_image_method.addArgument(SchemaProperty("provider", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the name of the cloud provider, often a region"))
    _import_image_method.addArgument(SchemaProperty("target_image", SCHEMA_DATA_STRING, direction=DIR_OUT, desc="the UUID of the target image object"))
    _import_image_method.addArgument(SchemaProperty("provider_image", SCHEMA_DATA_STRING, direction=DIR_OUT, desc="the UUID of the provider image object"))
    qmf_schema.addMethod(_import_image_method)
    # this method will return a representation of the object's finite state machine
    _states_method = SchemaMethod("instance_states", desc = "Returns a dictionary representing the finite state machine for instances.")
    _states_method.addArgument(SchemaProperty("class_name", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the name of the class to query for instance states"))
    _states_method.addArgument(SchemaProperty("states", SCHEMA_DATA_STRING, direction=DIR_OUT, desc="string representation of a dictionary describing the workflow"))
    qmf_schema.addMethod(_states_method)

    @classmethod
    def object_states(cls):
        """Returns a dictionary representing the finite state machine for instances of this class."""
        return {}

    qmf_object = props.prop("_qmf_object", "The qmf_object property.")
    agent = props.prop("_agent", "The property agent")

    def _singleton_init(self):
        super(ImageFactory, self)._singleton_init()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.qmf_object = Data(ImageFactory.qmf_schema)
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])

    def __init__(self):
        pass

    def image(self,template,target):
        template_object = Template(template=template)
        build_adaptor = BuildAdaptor(template_object,target,agent=self.agent)
        # Needed to allow us to walk all builders during a shutdown
        BuildDispatcher().job_registry.register(build_adaptor)
        build_adaptor.build_image()
        return build_adaptor

    def provider_image(self, image_id, provider, credentials):
        target_image_id = image_id

        image_metadata = self.warehouse.metadata_for_id_of_type(("template", "target"), target_image_id, "target_image")
        template_id = image_metadata["template"]
        target = image_metadata["target"]

        if (template_id and target):
            build_adaptor = BuildAdaptor(Template(uuid=template_id),target,agent=self.agent)
            # Needed to allow us to walk all builders during a shutdown
            BuildDispatcher().job_registry.register(build_adaptor)
            build_adaptor.push_image(target_image_id, provider, credentials)
            return build_adaptor
        else:
            raise RuntimeError("Could not return build_adaptor!\nimage_metadata: %s\ntemplate_id: %s\ntemplate: %s\n" % (image_metadata, template_id, target))

    def build_image(self, image, build, template, targets):
        return BuildDispatcher().build_image_for_targets(image, build, template, targets, BuildAdaptor, self.agent)

    def push_image(self, image, build, providers, credentials):
        return BuildDispatcher().push_image_to_providers(image, build, providers, credentials, BuildAdaptor, self.agent)

    def import_image(self, image, build, target_identifier, image_desc, target, provider):
        ids = BuildDispatcher().import_image(image, build, target_identifier, image_desc, target, provider)
        return {"image" : ids[0], "build" : ids[1], "target_image" : ids[2], "provider_image" : ids[3]}

    def instance_states(self, class_name):
        """Returns a dictionary representing the finite state machine for instances of the class specified."""
        module_name = "imgfac.qmfagent.%s" % (class_name, )
        __import__(module_name)
        return dict(states=str(getattr(sys.modules[module_name], class_name).object_states()))
