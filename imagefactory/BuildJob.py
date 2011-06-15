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

import libxml2
import logging
import props
import sys
import threading
from imagefactory.builders import *
from imagefactory.Template import Template

class BuildJob(object):

    template = props.prop("_template", "The template property.")
    target = props.prop("_target", "The target property.")
    image_id = props.prop("_image_id", "The UUID of the image.")
    build_id = props.prop("_build_id", "The UUID of the build.")
    provider = props.prop("_provider", "The provider being pushed to.")
    status = props.prop("_status", "The status property.")
    percent_complete = props.prop("_percent_complete", "The percent_complete property.")
    new_image_id = props.prop("_new_image_id" "The image property.")

    def __init__(self, template, target, image_id = '', build_id = ''):
        super(BuildJob, self).__init__()

        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.template = template if isinstance(template, Template) else Template(template)
        self.target = target
        self.image_id = image_id
        self.build_id = build_id
        self.provider = None
        self.status = "New"
        self.percent_complete = 0
        self._watcher = None

        self._builder = self._get_builder()
        self._builder.delegate = self

        self.new_image_id = self._builder.new_image_id

    def build_image(self, watcher=None):
        self._watcher = watcher
        kwargs = dict(build_id=self.build_id)
        self._start_builder_thread("build_image", arg_dict=kwargs)

    def push_image(self, target_image_id, provider, credentials, watcher=None):
        self._watcher = watcher
        self.provider = provider
        kwargs = dict(target_image_id=target_image_id, provider=provider, credentials=credentials)
        self._start_builder_thread("push_image", arg_dict=kwargs)

    def abort(self):
        self._builder.abort()

    def builder_did_update_status(self, builder, old_status, new_status):
        self.status = new_status
        if self.status == "COMPLETED" and self._watcher:
            self._watcher.completed()
            self._watcher = None

    def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
        self.percent_complete = new_percentage

    def builder_did_fail(self, builder, failure_type, failure_info):
        pass

    def _get_builder(self):
        builder_class = MockBuilder.MockBuilder
        if (self.target != "mock"): # If target is mock always run mock builder regardless of template
            os_name = self._xml_node(self.template.xml, '/template/os/name')
            class_name = "%sBuilder" % (os_name, )
            try:
                module_name = "imagefactory.builders.%s" % (class_name, )
                __import__(module_name)
                builder_class = getattr(sys.modules[module_name], class_name)
            except AttributeError, e:
                self.log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e, os_name)

        return builder_class(self.template, self.target)

    def _start_builder_thread(self, method_name, arg_dict={}):
        thread_name = "%s.%s()" % (self.new_image_id, method_name)
        # using args to pass the method we want to call on the target object.
        builder_thread = threading.Thread(target = self._builder, name=thread_name, args=(method_name), kwargs=arg_dict)
        builder_thread.start()

    def _xml_node(self, xml, xpath):
        nodes = libxml2.parseDoc(xml).xpathEval(xpath)
        if not nodes:
            return None
        return nodes[0].content
