# encoding: utf-8

#   Copyright 2012 Red Hat, Inc.
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
import uuid
import zope
import inspect
from imgfac.CloudDelegate import CloudDelegate

class MockCloud(object):
    zope.interface.implements(CloudDelegate)


    def __init__(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        self.log.info('%s called in MockCloud plugin' % (inspect.stack()[1][3]))
        builder.provider_image.identifier_on_provider = str(uuid.uuid4())
        builder.provider_image.provider_account_identifier = 'mock_user'

    def snapshot_image_on_provider(self, builder, provider, credentials, target, template, parameters):
        self.log.info('%s called in MockCloud plugin' % (inspect.stack()[1][3]))
        builder.provider_image.identifier_on_provider = str(uuid.uuid4())
        builder.provider_image.provider_account_identifier = 'mock_user'

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('%s called in MockCloud plugin' % (inspect.stack()[1][3]))
        return True

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('%s called in MockCloud plugin' % (inspect.stack()[1][3]))

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.info('%s called in MockCloud plugin' % (inspect.stack()[1][3]))

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        self.log.info('%s called in MockCloud plugin' % (inspect.stack()[1][3]))
