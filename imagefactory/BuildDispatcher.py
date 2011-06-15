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
import os.path
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.BuildJob import BuildJob
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.Singleton import Singleton
from imagefactory.Template import Template

#
# TODO:
#  - Split the watcher code out into separate modules
#

class BuildDispatcher(Singleton):

    def _singleton_init(self):
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration['warehouse'])

    def build_image_for_targets(self, image_id, build_id, template, targets, job_cls = BuildJob, *args, **kwargs):
        template = Template(template)

        image_id = self._ensure_image(image_id, template)
        build_id = self._ensure_build(image_id, build_id)

        watcher = BuildWatcher(image_id, build_id, len(targets), self.warehouse)

        jobs = []
        for target in targets:
            job = job_cls(template, target, image_id, build_id, *args, **kwargs)
            job.build_image(watcher)
            jobs.append(job)

        return jobs

    def push_image_to_providers(self, image_id, build_id, providers, credentials, job_cls = BuildJob, *args, **kwargs):
        if not build_id:
            build_id = self._latest_unpushed(image_id)

        watcher = PushWatcher(image_id, build_id, len(providers), self.warehouse)

        jobs = []
        for provider in providers:
            target = self._map_provider_to_target(provider)

            target_image_id = self._target_image_for_build_and_target(build_id, target)

            template = self._template_for_target_image_id(target_image_id)

            job = job_cls(template, target, image_id, build_id, *args, **kwargs)
            job.push_image(target_image_id, provider, credentials, watcher)
            jobs.append(job)

        return jobs

    def _xml_node(self, xml, xpath):
        nodes = libxml2.parseDoc(xml).xpathEval(xpath)
        if not nodes:
            return None
        return nodes[0].content

    def _ensure_image(self, image_id, template):
        if image_id:
            return image_id

        name = self._xml_node(template.xml, '/template/name')
        if name:
            image_xml = '<image><name>%s</name></image>' % name
        else:
            image_xml = '</image>'

        return self.warehouse.store_image(None, image_xml)

    def _ensure_build(self, image_id, build_id):
        if build_id:
            return build_id
        return self.warehouse.store_build(None, dict(image = image_id))

    def _latest_unpushed(self, image_id):
        return self.warehouse.metadata_for_id_of_type(['latest_unpushed'], image_id, 'image')['latest_unpushed']

    def _target_image_for_build_and_target(self, build_id, target):
        return self.warehouse.query("target_image", "$build == \"%s\" && $target == \"%s\"" % (build_id, target))[0]

    def _template_for_target_image_id(self, target_image_id):
        return self.warehouse.metadata_for_id_of_type(['template'], target_image_id, 'target_image')['template']

    def _is_rhevm_provider(self, provider):
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
    def _map_provider_to_target(self, provider):
        if provider.startswith('ec2-'):
            return 'ec2'
        elif provider == 'rackspace':
            return 'rackspace'
        elif self._is_rhevm_provider(provider):
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
