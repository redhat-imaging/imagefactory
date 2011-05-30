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

class BuildDispatcher(object):

    template = props.prop("_template", "The template property.")
    target = props.prop("_target", "The target property.")
    status = props.prop("_status", "The status property.")
    percent_complete = props.prop("_percent_complete", "The percent_complete property.")
    new_image_id = props.prop("_new_image_id" "The image property.")

    def __init__(self, template, target):
        super(BuildDispatcher, self).__init__()

        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.template = template
        self.target = target
        self.status = "New"
        self.percent_complete = 0

        self._builder = self._get_builder()
        self._builder.delegate = self

        self.new_image_id = self._builder.new_image_id

    def build_image(self):
        self._start_builder_thread("build_image")

    def push_image(self, image_id, provider, credentials):
        kwargs = dict(image_id=image_id, provider=provider, credentials=credentials)
        self._start_builder_thread("push_image", arg_dict=kwargs)

    def abort(self):
        self._builder.abort()

    def builder_did_update_status(self, builder, old_status, new_status):
        self.status = new_status

    def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
        self.percent_complete = new_percentage

    def builder_did_fail(self, builder, failure_type, failure_info):
        pass

    def _get_builder(self):
        template_object = Template(self.template)

        builder_class = MockBuilder.MockBuilder
        if (self.target != "mock"): # If target is mock always run mock builder regardless of template
            parsed_doc = libxml2.parseDoc(template_object.xml)
            node = parsed_doc.xpathEval('/template/os/name')
            os_name = node[0].content
            class_name = "%sBuilder" % (os_name, )
            try:
                module_name = "imagefactory.builders.%s" % (class_name, )
                __import__(module_name)
                builder_class = getattr(sys.modules[module_name], class_name)
            except AttributeError, e:
                self.log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e, os_name)

        return builder_class(template_object, self.target)

    def _start_builder_thread(self, method_name, arg_dict={}):
        thread_name = "%s.%s()" % (self.new_image_id, method_name)
        # using args to pass the method we want to call on the target object.
        builder_thread = Thread(target = self._builder, name=thread_name, args=(method_name), kwargs=arg_dict)
        builder_thread.start()
