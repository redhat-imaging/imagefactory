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
import libxml2
import logging
import props
from threading import Thread, Lock
from imagefactory.builders import *
from imagefactory.Template import Template

class BaseAdaptor(object):

    template = props.prop("_template", "The template property.")
    target = props.prop("_target", "The target property.")
    status = props.prop("_status", "The status property.")
    percent_complete = props.prop("_percent_complete", "The percent_complete property.")
    image_id = props.prop("_image_id" "The image property.")

    def __init__(self, template, target):
        super(BaseAdaptor, self).__init__()

        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.template = template
        self.target = target
        self.status = "New"
        self.percent_complete = 0
        self.image_id = "None"

        self.builder = BuildDispatcher.builder_for_target_with_template(template=template, target=target)
        self.builder.delegate = self
        self.image_id = self.builder.image_id

    def build_image(self):
        BuildDispatcher.builder_thread_with_method(builder=self.builder, method_name="build_image")

    def push_image(self, image_id, provider, credentials):
        kwargs = dict(image_id=image_id, provider=provider, credentials=credentials)
        BuildDispatcher.builder_thread_with_method(builder=self.builder, method_name="push_image", arg_dict=kwargs)

    def abort(self):
        self.builder.abort()

    def builder_did_update_status(self, builder, old_status, new_status):
        self.status = new_status

    def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
        self.percent_complete = new_percentage

    def builder_did_fail(self, builder, failure_type, failure_info):
        pass

class BuildDispatcher(object):

    @classmethod
    def builder_for_target_with_template(cls, target, template):
        log = logging.getLogger('%s.%s' % (__name__, cls.__name__))

        template_object = Template(template)

        builder_class = MockBuilder.MockBuilder
        if (target != "mock"): # If target is mock always run mock builder regardless of template
            parsed_doc = libxml2.parseDoc(template_object.xml)
            node = parsed_doc.xpathEval('/template/os/name')
            os_name = node[0].content
            class_name = "%sBuilder" % (os_name, )
            try:
                module_name = "imagefactory.builders.%s" % (class_name, )
                __import__(module_name)
                builder_class = getattr(sys.modules[module_name], class_name)
            except AttributeError, e:
                log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e, os_name)

        return builder_class(template_object, target)

    @classmethod
    def builder_thread_with_method(cls, builder, method_name, arg_dict={}, autostart=True):
        log = logging.getLogger('%s.%s' % (__name__, cls.__name__))

        thread_name = "%s.%s()" % (builder.image_id, method_name)
        # using args to pass the method we want to call on the target object.
        builder_thread = Thread(target = builder, name=thread_name, args=(method_name), kwargs=arg_dict)
        if(autostart):
            builder_thread.start()

        return builder_thread
