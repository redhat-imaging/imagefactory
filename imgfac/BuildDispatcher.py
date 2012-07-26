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

import logging
from imgfac.Singleton import Singleton
from Builder import Builder
from imgfac.NotificationCenter import NotificationCenter


class BuildDispatcher(Singleton):

    def _singleton_init(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.builders = dict()
        NotificationCenter().add_observer(self, 'handle_state_change', 'image.status')

    def handle_state_change(self, notification):
        if(notification.user_info['new_status'] in ('COMPLETED', 'FAILED', 'DELETED', 'DELETEFAILED')):
            try:
                del self.builders[notification.sender.new_image_id]
            except KeyError as e:
                self.log.exception('Trying to remove unknown builder from BuildDispatcher: %s' % e)

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
