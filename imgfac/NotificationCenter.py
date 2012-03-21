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
        _observer = _Observer(observer, method, message, sender)
        self.observers[message].add(_observer)
        self.lock.release()

    def remove_observer(self, observer, message='all', sender=None):
        """
        TODO: Docstring for remove_observer
        
        @param observer TODO
        @param message TODO
        @param sender TODO
        """
        self.lock.acquire()
        if observer in self.observers[message]:
            self.observers[message].remove(observer)
            if len(self.observers[message] == 0):
                self.observers.pop(message)
        self.lock.release()

    def post_notification(self, notification):
        """
        TODO: Docstring for post_notification
        
        @param notification TODO
        """
        self.lock.acquire()
        for _observer in self.observers[notification.message]:
            if ((not _observer.sender) or (_observer.sender == notification.sender)):
                try:
                    getattr(_observer.obj, _observer.method)(notification)
                except AttributeError as e:
                    self.log.exception('Caught exception: posting notification to object (%s) with method (%s)' % (_observer.obj, _observer.method))
        self.lock.release()

    def post_notification_with_info(self, message, sender, user_info=None):
        """
        TODO: Docstring for post_notification_with_info
        
        @param message TODO
        @param sender TODO
        @param user_info TODO
        """
        self.post_notification(Notification(message, sender, user_info))

class _Observer(object):
    obj = prop("_obj")
    method = prop("_method")
    message = prop("_message")
    sender = prop("_sender")

    def __init__(self, obj, method, message, sender):
        self.obj = obj
        self.method = method
        self.message = message
        self.sender = sender
