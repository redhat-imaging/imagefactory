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
import logging
import Provider
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildJob import BuildJob
from imgfac.BuildWatcher import BuildWatcher
from imgfac.PushWatcher import PushWatcher
from imgfac.Singleton import Singleton
from imgfac.Template import Template
from imgfac.JobRegistry import JobRegistry
from Builder import Builder


class BuildDispatcher(Singleton):

    def _singleton_init(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.job_registry = JobRegistry()
        self.builders = dict()

    def builder_for_base_image(self, template, parameters=None):
        builder = Builder()
        builder.build_image_from_template(template)
        self.builders[builder.base_image.identifier] = builder
        return builder

    def builder_for_target_image(self, target, image_id=None, template=None, parameters=None):
        builder = Builder()
        builder.customize_image_for_target(target, image_id, template, parameters)
        self.builders[builder.target_image.identifier] = builder
        return builder

    def builder_for_provider_image(self, provider, credentials, target, image_id=None, template=None, parameters=None):
        builder = Builder()
        builder.create_image_on_provider(provider, credentials, target, image_id, template, parameters)
        self.builders[builder.provider_image.identifier] = builder
        return builder
