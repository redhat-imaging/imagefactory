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

import libxml2
import os.path
import json
import logging
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildJob import BuildJob
from imgfac.BuildWatcher import BuildWatcher
from imgfac.ImageWarehouse import ImageWarehouse
from imgfac.PushWatcher import PushWatcher
from imgfac.Singleton import Singleton
from imgfac.Template import Template
from imgfac.JobRegistry import JobRegistry
# Yes - we already import libxml2 - xml is built in - there is no harm here and I like the API
from xml.etree.ElementTree import fromstring
from Builder import Builder

class BuildDispatcher(Singleton):

    def _singleton_init(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration['warehouse'])
        self.job_registry = JobRegistry()
        self.builders = dict()

##### BEGIN new BuildDispatcher code for plugins and no warehouse #####

    def builder_for_base_image(self, template, parameters=None):
        builder = Builder()
        builder.build_image_from_template(template)
        self.builders[builder.base_image.identifier] = builder
        return builder

    def builder_for_target_image(self, target, image_id=None, template=None, parameters=None):
        builder = Builder()
        builder.customize_image_for_target(target, image_id, template, parameters)
        self.builders[builder.target_image.identidier] = builder
        return builder

    def builder_for_provider_image(self, provider, credentials, image_id=None, template=None, parameters=None):
        builder = Builder()
        builder.create_image_on_provider(provider, credentials, image_id, template, parameters)
        self.builders[builder.provider_image.identifier] = builder
        return builder

##### END new BuildDispatcher code

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

        self.job_registry.register(jobs)

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

        self.job_registry.register(jobs)

        return jobs

    def get_dynamic_provider_data(self, provider):
        # Get provider details for RHEV-M or VSphere
        # First try to interpret this as an ad-hoc/dynamic provider def
        # If this fails, try to find it in one or the other of the config files
        # If this all fails return None
        # We use this in the builders as well so I have made it "public"

        try:
            xml_et = fromstring(provider)
            return xml_et.attrib
        except Exception as e:
            self.log.debug('Testing provider for XML: %s' % e)
            pass

        try:
            jload = json.loads(provider)
            return jload
        except ValueError as e:
            self.log.debug('Testing provider for JSON: %s' % e)
            pass

        rhevm_data = self._return_dynamic_provider_data(provider, "rhevm")
        if rhevm_data:
            rhevm_data['target'] = "rhevm"
            rhevm_data['name'] = provider
            return rhevm_data

        vsphere_data = self._return_dynamic_provider_data(provider, "vsphere")
        if vsphere_data:
            vsphere_data['target'] = "vsphere"
            vsphere_data['name'] = provider
            return vsphere_data
        
        # It is not there
        return None

    def _xml_node(self, xml, xpath):
        nodes = libxml2.parseDoc(xml).xpathEval(xpath)
        if not nodes:
            return None
        return nodes[0].content

    def _ensure_image_with_template(self, image_id, template, image_desc=None):
        if not (type(template) == Template):
            template = Template(template)
        if not image_desc:
            name = self._xml_node(template.xml, '/template/name')
            if name:
                image_desc = '<image><name>%s</name></image>' % name
            else:
                image_desc = '<image/>'
        if not template.identifier:
            template.identifier = self.warehouse.store_template(template.xml)
        return self._ensure_image(image_id, image_desc, template.identifier)

    def _ensure_image(self, image_id, image_desc, template_id=None):
        if image_id:
            return image_id
        elif(template_id):
            return self.warehouse.store_image(None, image_desc, dict(template=template_id))
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

    def _set_provider_image_attr(self, provider_image_id, attr, value):
        self.warehouse.set_metadata_for_id_of_type({attr : value},
                                                   provider_image_id,
                                                   "provider_image")

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

    def _return_dynamic_provider_data(self, provider, filebase):
        provider_json = '/etc/imagefactory/%s.json' % (filebase)
        if not os.path.exists(provider_json):
            return False

        provider_sites = {}
        f = open(provider_json, 'r')
        try:
            provider_sites = json.loads(f.read())
        finally:
            f.close()

        if provider in provider_sites:
            return provider_sites[provider]
        else:
            return None

    # FIXME: this is a hack; conductor is the only one who really
    #        knows this mapping, so perhaps it should provide it?
    #        e.g. pass a provider => target dict into push_image
    #        rather than just a list of providers. Perhaps just use
    #        this heuristic for the command line?
    #
    # provider semantics, per target:
    #  - ec2: region, one of ec2-us-east-1, ec2-us-west-1, ec2-ap-southeast-1, ec2-ap-northeast-1, ec2-eu-west-1
    #  - condorcloud: ignored
    #  - mock: any provider with 'mock' prefix
    #  - rackspace: provider is rackspace
    # UPDATE - Sept 13, 2011 for dynamic providers
    #  - vpshere: encoded in provider string or a key in /etc/vmware.json
    #  - rhevm: encoded in provider string or a key in /etc/rhevm.json
    #
    def _map_provider_to_target(self, provider):
        # Check for dynamic providers first
        provider_data = self.get_dynamic_provider_data(provider)
        if provider_data:
            try:
                return provider_data['target']
            except KeyError as e:
                self.log.debug('Provider data does not specify target!\n%s' % provider_data)
                raise Exception('Provider data does not specify target!\n%s' % provider_data)
        elif provider.startswith('ec2-'):
            return 'ec2'
        elif provider == 'rackspace':
            return 'rackspace'
        elif provider.startswith('mock'):
            return 'mock'
        else:
            self.log.warn('No matching provider found for %s, using "condorcloud" by default.' % (provider))
            return 'condorcloud' # condorcloud ignores provider
