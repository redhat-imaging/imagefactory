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

import sys
import cqpid
from qmf2 import *
import BuildAdaptor
import httplib2
from imagefactory import props
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.Template import Template
import logging

# Singleton representing the Factory itself

class ImageFactory(object):
    instance = None

    # QMF schema for ImageFactory
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "ImageFactory")
    # method for building images
    _build_image_method = SchemaMethod("image", desc="Build a new image")
    _build_image_method.addArgument(SchemaProperty("template", SCHEMA_DATA_STRING, direction=DIR_IN, desc="string of xml, uuid, or url"))
    _build_image_method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN, desc="name of the cloud to target"))
    _build_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT, desc="the QMF address of the build_adaptor instantiated"))
    qmf_schema.addMethod(_build_image_method)
    # method for creating a provider_image from an image
    _push_image_method = SchemaMethod("provider_image", desc="Push an image to a provider.")
    _push_image_method.addArgument(SchemaProperty("image_id", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the uuid of an image previously built"))
    _push_image_method.addArgument(SchemaProperty("provider", SCHEMA_DATA_STRING, direction=DIR_IN, desc="the name of the cloud provider, often a region"))
    _push_image_method.addArgument(SchemaProperty("credentials", SCHEMA_DATA_STRING, direction=DIR_IN, desc="an xml string representation of the credentials"))
    _push_image_method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT, desc="the QMF address of the build_adaptor instantiated"))
    qmf_schema.addMethod(_push_image_method)
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

    def __new__(cls, *p, **k):
        if cls.instance is None:
            i = super(ImageFactory, cls).__new__(cls, *p, **k)
            # initialize here, not in __init__()
            i.log = logging.getLogger('%s.%s' % (__name__, i.__class__.__name__))
            i.qmf_object = Data(ImageFactory.qmf_schema)
            #i.agent = k.get('agent', p[0] if (len(p) > 0) else None)
            i.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
            cls.instance = i
        elif(len(p) | len(k) > 0):
            cls.instance.log.warn('Attempted re-initialize of singleton: %s' % (cls.instance, ))
        return cls.instance

    def __init__(self):
        pass

    def image(self,template,target):
        template_object = Template(template=template)
        build_adaptor = BuildAdaptor.BuildAdaptor(template_object,target,self.agent)
        build_adaptor.build_image()
        return build_adaptor

    def provider_image(self,image_id, provider, credentials):
        image_metadata = self.warehouse.metadata_for_id_of_type(("template", "target"), image_id, "image")
        template_id = image_metadata["template"]
        target = image_metadata["target"]

        if (template_id and target):
            build_adaptor = BuildAdaptor.BuildAdaptor(Template(uuid=template_id),target,self.agent)
            build_adaptor.push_image(image_id, provider, credentials)
            return build_adaptor
        else:
            raise RuntimeError("Could not return build_adaptor!\nimage_metadata: %s\ntemplate_id: %s\ntemplate: %s\n" % (image_metadata, template_id, target))

    def instance_states(self, class_name):
        """Returns a dictionary representing the finite state machine for instances of the class specified."""
        module_name = "imagefactory.qmfagent.%s" % (class_name, )
        __import__(module_name)
        return dict(states=str(getattr(sys.modules[module_name], class_name).object_states()))
