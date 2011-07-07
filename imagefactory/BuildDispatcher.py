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
import json
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.BuildJob import BuildJob
from imagefactory.BuildWatcher import BuildWatcher
from imagefactory.ImageWarehouse import ImageWarehouse
from imagefactory.PushWatcher import PushWatcher
from imagefactory.Singleton import Singleton
from imagefactory.Template import Template

class BuildDispatcher(Singleton):

    def _singleton_init(self):
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration['warehouse'])

    def import_image(self, image_id, build_id, target_identifier, image_desc, target, provider):
        image_id = self._ensure_image(image_id, image_desc)
        build_id = self._ensure_build(image_id, build_id)

        target_image_id = self._ensure_target_image(build_id, target)
        provider_image_id = self._ensure_provider_image(target_image_id, provider, target_identifier)

        self._commit_build(image_id, build_id)

        return (image_id, build_id, target_image_id, provider_image_id)

    def build_image_for_targets(self, image_id, build_id, template, targets, job_cls = BuildJob, *args, **kwargs):
        if image_id and not targets:
            targets = self._targets_for_image_id(image_id)

        template = self._load_template(image_id, build_id, template)

        image_id = self._ensure_image_with_template(image_id, template)
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

    def _ensure_image_with_template(self, image_id, template):
        name = self._xml_node(template.xml, '/template/name')
        if name:
            image_desc = '<image><name>%s</name></image>' % name
        else:
            image_desc = '</image>'
        return self._ensure_image(image_id, image_desc)

    def _ensure_image(self, image_id, image_desc):
        if image_id:
            return image_id
        else:
            return self.warehouse.store_image(None, image_desc)

    def _ensure_build(self, image_id, build_id):
        if build_id:
            return build_id
        return self.warehouse.store_build(None, dict(image = image_id))

    def _ensure_target_image(self, build_id, target):
        target_image_id = self._target_image_for_build_and_target(build_id, target)
        if target_image_id:
            return target_image_id
        return self.warehouse.store_target_image(None, None, dict(build=build_id, target=target))

    def _ensure_provider_image(self, target_image_id, provider, target_identifier):
        provider_image_id = self._provider_image_for_target_image_and_provider(target_image_id, provider)
        if provider_image_id:
            self._set_provider_image_attr(provider_image_id, 'target_identifier', target_identifier)
        else:
            metadata = dict(target_image=target_image_id, provider=provider, target_identifier=target_identifier)
            return self.warehouse.create_provider_image(None, None, metadata)

    def _load_template(self, image_id, build_id, template):
        if not template:
            if build_id:
                template = self._template_for_build_id(build_id)
            if not template and image_id:
                template = self._template_for_image_id(image_id)
        return Template(template)

    def _commit_build(self, image_id, build_id):
        parent_id = self._latest_build(image_id)
        if parent_id:
            self._set_build_parent(build_id, parent_id)
        self._set_latest_build(image_id, build_id)

    def _latest_build(self, image_id):
        return self.warehouse.metadata_for_id_of_type(['latest_build'], image_id, 'image')['latest_build']

    def _latest_unpushed(self, image_id):
        return self.warehouse.metadata_for_id_of_type(['latest_unpushed'], image_id, 'image')['latest_unpushed']

    def _set_latest_build(self, image_id, build_id):
        self.warehouse.set_metadata_for_id_of_type({'latest_build' : build_id}, image_id, 'image')

    def _set_build_parent(self, build_id, parent_id):
        self.warehouse.set_metadata_for_id_of_type({'parent' : parent_id}, build_id, 'build')

    def _targets_for_build_id(self, build_id):
        targets = []
        for target_image_id in self._target_images_for_build(build_id):
            targets.append(self.warehouse.metadata_for_id_of_type(['target'], target_image_id, 'target_image')['target'])
        return targets

    def _targets_for_image_id(self, image_id):
        build_id = self._latest_build(image_id)
        if not build_id:
            build_id = self._latest_unpushed(image_id)
        return self._targets_for_build_id(build_id) if build_id else []

    def _target_images_for_build(self, build_id):
        return self.warehouse.query("target_image", "$build == \"%s\"" % (build_id,))

    def _target_image_for_build_and_target(self, build_id, target):
        results = self.warehouse.query("target_image", "$build == \"%s\" && $target == \"%s\"" % (build_id, target))
        return results[0] if results else None

    def _provider_image_for_target_image_and_provider(self, target_image_id, provider):
        results = self.warehouse.query("provider_image", "$target_image == \"%s\" && $provider == \"%s\"" % (target_image_id, provider))
        return results[0] if results else None

    def _set_provider_image_attr(provider_image_id, attr, value):
        self.warehouse.set_metadata_for_id_of_type({attr : value}, provider_image_id, "provider_image")

    def _template_for_target_image_id(self, target_image_id):
        return self.warehouse.metadata_for_id_of_type(['template'], target_image_id, 'target_image')['template']

    def _template_for_build_id(self, build_id):
        target_image_ids = self._target_images_for_build(build_id)
        return self._template_for_target_image_id(target_image_ids[0]) if target_image_ids else None

    def _template_for_image_id(self, image_id):
        build_id = self._latest_build(image_id)
        if not build_id:
            build_id = self._latest_unpushed(image_id)
        return self._template_for_build_id(build_id) if build_id else None

    def _is_dynamic_provider(self, provider, filebase):
        provider_json = '/etc/%s.json' % (filebase)
        if not os.path.exists(provider_json):
            return False

        provider_sites = {}
        f = open(provider_json, 'r')
        try:
            provider_sites = json.loads(f.read())
        finally:
            f.close()

        return provider in provider_sites

    # FIXME: this is a hack; conductor is the only one who really
    #        knows this mapping, so perhaps it should provide it?
    #        e.g. pass a provider => target dict into push_image
    #        rather than just a list of providers. Perhaps just use
    #        this heuristic for the command line?
    #
    # provider semantics, per target:
    #  - ec2: region, one of ec2-us-east-1, ec2-us-west-1, ec2-ap-southeast-1, ec2-ap-northeast-1, ec2-eu-west-1
    #  - condorcloud: ignored
    #  - rhevm: a key in /etc/rhevm.json and passed to op=register&site=provider
    #  - vpshere: a key in /etc/vmware.json
    #  - mock: any provider with 'mock' prefix
    #  - rackspace: provider is rackspace
    #
    def _map_provider_to_target(self, provider):
        if provider.startswith('ec2-'):
            return 'ec2'
        elif provider == 'rackspace':
            return 'rackspace'
        elif self._is_dynamic_provider(provider, 'rhevm'):
            return 'rhevm'
        elif self._is_dynamic_provider(provider, 'vmware'):
            return 'vsphere'
        elif provider.startswith('mock'):
            return 'mock'
        else:
            return 'condorcloud' # condorcloud ignores provider
