#
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

from zope.interface import Interface
from zope.interface import Attribute


class IBuilderDelegate(Interface):
    """Builders should call these methods on their delegate if assigned.
    Subclasses of the BaseBuilder class will get this for free.  Classes
    that conform to the IBuilderDelegate interface can selectively
    implement methods from this interface."""

    def builder_will_update_status(self, builder, original_status, new_status):
		"""The builder will update from original_status to new_status."""

    def builder_did_update_status(self, builder, original_status, new_status):
		"""The builder updated the status from original_status to new_status."""

    def builder_should_update_status(self, builder, original_status, new_status):
		"""Returns whether the builder should update the status from original_status to new_status."""

    def builder_will_update_percentage(self, builder, original_percentage, new_percentage):
		"""The builder will update from original_percentage to new_percentage."""

    def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
		"""The builder updated from original_percentage to new_percentage."""

    def builder_should_update_percentage(self, builder, original_percentage, new_percentage):
        """Returns whether the builder should update from original_percentage to new_percentage."""

    def builder_did_fail(self, builder, failure_type, failure_info):
        """Notification that there was a failure of specified type, with further information describing what happened."""
