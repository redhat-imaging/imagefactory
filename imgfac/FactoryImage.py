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
from Notification import Notification


STATUS_STRINGS = ('NEW','PENDING', 'COMPLETE', 'FAILED')
NOTIFICATIONS = ('image.status', 'image.percentage')


class FactoryImage(object):
    """ TODO: Docstring for FactoryImage  """

##### PROPERTIES
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

    def __init__(self, template):
        """ TODO: Fill me in
        
        @param template TODO
        """
        super(FactoryImage, self).init()
        self.identifier = uuid.uuid4()
        self.data = None
        self.icicle = None
