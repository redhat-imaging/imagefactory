#!/usr/bin/env python
# encoding: utf-8

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

import unittest
from imgfac.NotificationCenter import NotificationCenter

class testNotificationCenter(unittest.TestCase):
    def setUp(self):
        self.notification_center = NotificationCenter()

    def tearDown(self):
        del self.notification_center

    def testAddRemoveObservers(self):
        o1 = MockObserver()
        o2 = MockObserver()
        nc = self.notification_center
        self.assertEqual(len(nc.observers), 0)
        nc.add_observer(o1, 'receive')
        self.assertEqual(len(nc.observers), 1)
        nc.add_observer(o1, 'receive', 'test')
        self.assertEqual(len(nc.observers), 2)
        nc.add_observer(o2, 'receive', 'test2', self)
        self.assertEqual(len(nc.observers), 3)
        nc.remove_observer(o1, 'receive')
        self.assertEqual(len(nc.observers), 2)
        nc.remove_observer(o1, 'receive', 'test')
        self.assertEqual(len(nc.observers), 1)
        nc.remove_observer(o2, 'receive', 'test2', self)
        self.assertEqual(len(nc.observers), 0)

    def testPostNotification(self):
        o1 = MockObserver()
        o2 = MockObserver()
        o3 = MockObserver()
        mock_sender = object()
        mock_usr_info = dict(test_key='test_value')
        self.assertIsNone(o1.notification)
        nc = self.notification_center
        nc.add_observer(o1, 'receive')
        nc.add_observer(o2, 'receive', 'test')
        nc.add_observer(o3, 'receive', sender=mock_sender)

        nc.post_notification_with_info('any_message', self)
        self.assertEqual(o1.notification.message, 'any_message')
        self.assertIsNone(o2.notification)
        self.assertIsNone(o3.notification)

        nc.post_notification_with_info('test', self)
        self.assertEqual(o1.notification.message, 'test')
        self.assertEqual(o2.notification.message, 'test')
        self.assertIsNone(o3.notification)

        nc.post_notification_with_info('test2', mock_sender)
        self.assertEqual(o1.notification.message, 'test2')
        self.assertNotEqual(o2.notification.message, 'test2')
        self.assertEqual(o3.notification.message, 'test2')

        self.assertIsNone(o1.notification.user_info)
        nc.post_notification_with_info('test3', self, mock_usr_info)
        self.assertDictEqual(o1.notification.user_info, mock_usr_info)
        self.assertEqual(o1.notification.message, 'test3')
        self.assertNotEqual(o2.notification.message, 'test3')
        self.assertNotEqual(o3.notification.message, 'test3')

class MockObserver(object):
    def __init__(self):
        self.notification = None

    def receive(self, notification):
        self.notification = notification

if __name__ == '__main__':
    unittest.main()
