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


METADATA =  ( 'identifier', 'data', 'template', 'icicle', 'status_detail', 'status', 'percent_complete', 'parameters' )
STATUS_STRINGS = ('NEW','PENDING', 'COMPLETE', 'FAILED', 'DELETING', 'DELETEFAILED')
NOTIFICATIONS = ('image.status', 'image.percentage')


class PersistentImage(object):
    """ TODO: Docstring for PersistentImage  """

##### PROPERTIES
    persistence_manager = prop("_persistence_manager")
    identifier = prop("_identifier")
    data = prop("_data")
    template = prop("_template")
    icicle = prop("_icicle")
    status_detail = prop("_status_detail")

    def status():
        doc = "A string value."
        def fget(self):
            return self._status

        def fset(self, value):
            value = value.upper()
            if(value == self._status):
                # Do not update or send a notification if nothing has changed
                return
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
            if value == old_value:
                # Do not update or send a notification if nothing has changed
                return
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
        # 'activity' should be set to a single line indicating, in as much detail as reasonably possible,
        #   what it is that the plugin operating on this image is doing at any given time.
        # 'error' should remain None unless an exception or other fatal error has occurred.  Error may
        #   be a multiline string
        self.status_detail = { 'activity': 'Initializing image prior to Cloud/OS customization', 'error':None }
        # Setting these to None or setting initial value via the properties breaks the prop code above
        self._status = "NEW"
        self._percent_complete = 0
        self.icicle = None
        self.parameters = { }

    def metadata(self):
        self.log.debug("Executing metadata in class (%s) my metadata is (%s)" % (self.__class__, METADATA))
        return METADATA
