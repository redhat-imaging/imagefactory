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
import os.path
import props
from threading import Thread, Lock
from imagefactory.builders import *
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageFactoryException import ImageFactoryException
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.Template import Template

#
# TODO:
#  - Split the watcher code out into separate modules
#  - Make use of a singleton instead of class methods
#

class BuildDispatcher(object):

    template = props.prop("_template", "The template property.")
    target = props.prop("_target", "The target property.")
    image_id = props.prop("_image_id", "The UUID of the image.")
    build_id = props.prop("_build_id", "The UUID of the build.")
    provider = props.prop("_provider", "The provider being pushed to.")
    status = props.prop("_status", "The status property.")
    percent_complete = props.prop("_percent_complete", "The percent_complete property.")
    new_image_id = props.prop("_new_image_id" "The image property.")

    def __init__(self, template, target, image_id = '', build_id = ''):
        super(BuildDispatcher, self).__init__()

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
            os_name = self.__class__._xml_node(self.template.xml, '/template/os/name')
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
        builder_thread = Thread(target = self._builder, name=thread_name, args=(method_name), kwargs=arg_dict)
        builder_thread.start()

    @classmethod
    def build_image_for_targets(cls, image_id, build_id, template, targets):
        warehouse = cls._get_warehouse()

        template = Template(template)

        image_id = cls._ensure_image(warehouse, image_id, template)
        build_id = cls._ensure_build(warehouse, image_id, build_id)

        watcher = BuildWatcher(image_id, build_id, len(targets), warehouse)

        dispatchers = []
        for target in targets:
            dispatcher = BuildDispatcher(template, target, image_id, build_id)
            dispatcher.build_image(watcher)
            dispatchers.append(dispatcher)

        return dispatchers

    @classmethod
    def push_image_to_providers(cls, image_id, build_id, providers, credentials):
        warehouse = cls._get_warehouse()

        if not build_id:
            build_id = cls._latest_unpushed(warehouse, image_id)

        watcher = PushWatcher(image_id, build_id, len(providers), warehouse)

        dispatchers = []
        for provider in providers:
            target = cls._map_provider_to_target(provider)

            target_image_id = cls._target_image_for_build_and_target(warehouse, build_id, target)

            template = cls._template_for_target_image_id(warehouse, target_image_id)

            dispatcher = BuildDispatcher(template, target, image_id, build_id)
            dispatcher.push_image(target_image_id, provider, credentials, watcher)
            dispatchers.append(dispatcher)

        return dispatchers

    @classmethod
    def _get_warehouse(cls):
        return ImageWarehouse(ApplicationConfiguration().configuration['warehouse'])

    @classmethod
    def _xml_node(cls, xml, xpath):
        nodes = libxml2.parseDoc(xml).xpathEval(xpath)
        if not nodes:
            return None
        return nodes[0].content

    @classmethod
    def _ensure_image(cls, warehouse, image_id, template):
        if image_id:
            return image_id

        name = cls._xml_node(template.xml, '/template/name')
        if name:
            image_xml = '<image><name>%s</name></image>' % name
        else:
            image_xml = '</image>'

        return warehouse.store_image(None, image_xml)

    @classmethod
    def _ensure_build(cls, warehouse, image_id, build_id):
        if build_id:
            return build_id
        return warehouse.store_build(None, dict(image = image_id))

    @classmethod
    def _latest_unpushed(cls, warehouse, image_id):
        return warehouse.metadata_for_id_of_type(['latest_unpushed'], image_id, 'image')['latest_unpushed']

    @classmethod
    def _target_image_for_build_and_target(cls, warehouse, build_id, target):
        return warehouse.query("target_image", "$build == \"%s\" && $target == \"%s\"" % (build_id, target))[0]

    @classmethod
    def _template_for_target_image_id(cls, warehouse, target_image_id):
        return warehouse.metadata_for_id_of_type(['template'], target_image_id, 'target_image')['template']

    @classmethod
    def _is_rhevm_provider(cls, provider):
        rhevm_json = '/etc/rhevm.json'
        if not os.path.exists(rhevm_json):
            return False

        rhevm_sites = {}
        f = open(rhevm_json, 'r')
        try:
            rhevm_sites = json.loads(f.read())
        finally:
            f.close()

        return provider in rhevm_sites

    # FIXME: this is a hack; conductor is the only one who really
    #        knows this mapping, so perhaps it should provide it?
    #        e.g. pass a provider => target dict into push_image
    #        rather than just a list of providers. Perhaps just use
    #        this heuristic for the command line?
    #
    # provider semantics, per target:
    #  - ec2: region, one of ec2-us-east-1, ec2-us-west-1, ec2-ap-southeast-1, ec2-ap-northeast-1, ec2-eu-west-1
    #  - condorcloud: ignored
    #  - rhev-m: a key in /etc/rhevm.json and passed to op=register&site=provider
    #  - mock: any provider with 'mock' prefix
    #  - rackspace: provider is rackspace
    #
    @classmethod
    def _map_provider_to_target(cls, provider):
        if provider.startswith('ec2-'):
            return 'ec2'
        elif provider == 'rackspace':
            return 'rackspace'
        elif cls._is_rhevm_provider(provider):
            return 'rhev-m'
        elif provider.startswith('mock'):
            return 'mock'
        else:
            return 'condorcloud' # condorcloud ignores provider

class Watcher(object):
    def __init__(self, image_id, build_id, remaining, warehouse):
        self.remaining = remaining
        self.warehouse = warehouse
        self.image_id = image_id
        self.build_id = build_id

    def completed(self):
        self.remaining -= 1
        if self.remaining == 0:
            self.all_completed()

    def all_completed(self):
        pass

    def _image_attr(self, attr):
        return self.warehouse.metadata_for_id_of_type([attr], self.image_id, 'image')[attr]

    def _set_image_attr(self, attr, value):
        self.warehouse.set_metadata_for_id_of_type({attr : value}, self.image_id, 'image')

    def _latest_build(self):
        return self._image_attr('latest_build')

    def _set_latest_build(self, build_id):
        self._set_image_attr('latest_build', build_id)

    def _latest_unpushed(self):
        return self._image_attr('latest_unpushed')

    def _set_latest_unpushed(self, build_id):
        self._set_image_attr('latest_unpushed', build_id)

    def _set_build_parent(self, parent_id):
        self.warehouse.set_metadata_for_id_of_type({'parent' : parent_id}, self.build_id, 'build')

class BuildWatcher(Watcher):
    def all_completed(self):
        parent_id = self._latest_unpushed()
        if not parent_id:
            parent_id = self._latest_build()
        self._set_latest_unpushed(self.build_id)
        if parent_id:
            self._set_build_parent(parent_id)

class PushWatcher(Watcher):
    def all_completed(self):
        self._set_latest_build(self.build_id)
        self._set_latest_unpushed(None)
