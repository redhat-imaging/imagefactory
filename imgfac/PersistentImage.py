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

from props import prop
import uuid
import logging
from Notification import Notification
from NotificationCenter import NotificationCenter


METADATA =  ('identifier', 'data', 'icicle', 'status_detail', 'status', 'percent_complete')
STATUS_STRINGS = ('NEW','PENDING', 'COMPLETE', 'FAILED')
NOTIFICATIONS = ('image.status', 'image.percentage')


class PersistentImage(object):
    """ TODO: Docstring for PersistentImage  """

##### PROPERTIES
    def metadata():
        """Persistent properties tuple"""
        def fget(self):
            parent = super(self.__class__, self)
            if(isinstance(parent, PersistentImage)):
                return frozenset(parent.metadata + METADATA)
            else:
                return frozenset(METADATA)
        def fset(self, value):
            pass
        def fdel(self):
            pass
        return locals()
    metadata = property(**metadata())

    persistence_manager = prop("_persistence_manager")
    identifier = prop("_identifier")
    data = prop("_data")
    icicle = prop("_icicle")
    status_detail = prop("_status_detail")

    def status():
        doc = "A string value."
        def fget(self):
            return self._status

        def fset(self, value):
            value = value.upper()
            if(value in STATUS_STRINGS):
                old_value = self._status
                self._status = value
                notification = Notification(message=NOTIFICATIONS[0],
                                            sender=self,
                                            user_info=dict(old_status=old_value, new_status=value))
                self.notification_center.post_notification(notification)
            else:
                raise KeyError('Status (%s) unknown. Use one of %s.' % (value, STATUS_STRINGS))

        return locals()
    status = property(**status())

    def percent_complete():
        doc = "The percentage through an operation."
        def fget(self):
            return self._percent_complete

        def fset(self, value):
            old_value = self._percent_complete
            self._percent_complete = value
            notification = Notification(message=NOTIFICATIONS[1],
                                        sender=self,
                                        user_info=dict(old_percentage=old_value, new_percentage=value))
            self.notification_center.post_notification(notification)

        return locals()
    percent_complete = property(**percent_complete())
##### End PROPERTIES

    def __init__(self, image_id=None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.notification_center = NotificationCenter()
        # We have never had use for the UUID object itself - make this a string
        # TODO: Root out all places where were str() convert this elsewhere
        self.identifier = image_id if image_id else str(uuid.uuid4())
        self.persistence_manager = None
        self.data = None
        self.status_detail = None
        # Setting these to None or setting initial value via the properties breaks the prop code above
        self._status = "NEW"
        self._percent_complete = 0
        self.icicle = None
