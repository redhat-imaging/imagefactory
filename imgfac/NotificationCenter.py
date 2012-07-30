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
from Singleton import Singleton
from props import prop
from collections import defaultdict
from threading import RLock
from Notification import Notification

class NotificationCenter(Singleton):
    """ TODO: Docstring for NotificationCenter  """

    observers = prop("_observers")

    def _singleton_init(self, *args, **kwargs):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.observers = defaultdict(set)
        self.lock = RLock()

    def add_observer(self, observer, method, message='all', sender=None):
        """
        TODO: Docstring for add_observer
        
        @param observer TODO
        @param method TODO
        @param message TODO
        @param sender TODO
        """
        self.lock.acquire()
        self.observers[message].add((observer, method, sender))
        self.lock.release()

    def remove_observer(self, observer, method, message='all', sender=None):
        """
        TODO: Docstring for remove_observer
        
        @param observer TODO
        @param message TODO
        @param sender TODO
        """
        self.lock.acquire()
        _observer = (observer, method, sender)
        self.observers[message].discard(_observer)
        if (len(self.observers[message]) == 0):
            del self.observers[message]
        self.lock.release()

    def post_notification(self, notification):
        """
        TODO: Docstring for post_notification
        
        @param notification TODO
        """
        self.lock.acquire()
        _observers = self.observers['all'].union(self.observers[notification.message])
        for _observer in _observers:
            _sender = _observer[2]
            if ((not _sender) or (_sender == notification.sender)):
                try:
                    getattr(_observer[0], _observer[1])(notification)
                except AttributeError as e:
                    self.log.exception('Caught exception: posting notification to object (%s) with method (%s)' % (_observer[0], _observer[1]))
        self.lock.release()

    def post_notification_with_info(self, message, sender, user_info=None):
        """
        TODO: Docstring for post_notification_with_info
        
        @param message TODO
        @param sender TODO
        @param user_info TODO
        """
        self.post_notification(Notification(message, sender, user_info))
