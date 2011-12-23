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
import logging
import os
import time
from imgfac.ReservationManager import ReservationManager
from threading import Thread, Semaphore


class testReservationManager(unittest.TestCase):
    """ TODO: Docstring for testReservationManager  """

    def __init__(self, methodName='runTest'):
        super(testReservationManager, self).__init__(methodName)
        logging.basicConfig(level=logging.NOTSET,
                            format='%(asctime)s \
                                    %(levelname)s \
                                    %(name)s \
                                    pid(%(process)d) \
                                    Message: %(message)s',
                            filename='/tmp/imagefactory-unittests.log')

    def setUp(self):
        self.test_path = '/tmp/imagefactory.unittest.ReservationManager'
        self.test_file = '%s/reservation.test' % self.test_path
        os.mkdir(self.test_path)
        fstat = os.statvfs(self.test_path)
        self.max_free = fstat.f_bavail * fstat.f_frsize
        self.min_free = self.max_free / 2
        self.res_mgr = ReservationManager()

    def tearDown(self):
        self.res_mgr.remove_path(self.test_path)
        os.rmdir(self.test_path)
        del self.res_mgr

    def testSingleton(self):
        """
        Prove this class produces a singelton object.
        """
        self.assertEqual(id(self.res_mgr), id(ReservationManager()))

    def testDefaultMinimumProperty(self):
        """
        TODO: Docstring for testDefaultMinimumProperty
        """
        self.res_mgr.default_minimum = self.min_free
        self.assertEqual(self.min_free, self.res_mgr.default_minimum)

    def testAddRemovePath(self):
        """
        TODO: Docstring for testRemovePath
        """
        path = '/'
        # start off with nothing tracked
        self.assertFalse(path in self.res_mgr.available_space)
        # add / and check that it's listed in the dictionary returned by
        # available_space
        self.res_mgr.add_path('/')
        self.assertTrue(path in self.res_mgr.available_space)
        # remove / and check that it's no longer listed in the dictionary
        # returned by available_space
        self.res_mgr.remove_path('/')
        self.assertFalse(path in self.res_mgr.available_space)

    def testReserveSpaceForFile(self):
        """
        TODO: Docstring for testReserveSpaceForFile
        """
        self.res_mgr.default_minimum = self.min_free
        size = self.min_free / 10
        result = self.res_mgr.reserve_space_for_file(size, self.test_file)
        self.assertTrue(result)
        self.assertTrue(self.test_file in self.res_mgr.reservations)

    def testReserveSpaceForFileThatIsTooBig(self):
        """
        TODO: Docstring for testReserveSpaceForFile
        """
        size = self.max_free * 10
        result = self.res_mgr.reserve_space_for_file(size, self.test_file)
        self.assertFalse(result)
        self.assertFalse(self.test_file in self.res_mgr.reservations)

    def testCancelReservationForFile(self):
        """
        TODO: Docstring for testCancelReservationForFile
        """
        size = self.min_free / 10
        self.res_mgr.default_minimum = self.min_free
        if(self.res_mgr.reserve_space_for_file(size, self.test_file)):
            self.assertTrue(self.test_file in self.res_mgr.reservations)
            self.res_mgr.cancel_reservation_for_file(self.test_file)
            self.assertFalse(self.test_file in self.res_mgr.reservations)
        else:
            self.fail('Failed to reserve space...')

    def testCancelNonExistentReservation(self):
        """
        TODO: Docstring for testCancelNonExistentReservation
        """
        self.assertRaises((TypeError, KeyError), self.res_mgr.cancel_reservation_for_file, *('/tmp/not.there', False))

    def testAvailableSpaceForPath(self):
        """
        TODO: Docstring for testAvailableSpace
        """
        size = self.min_free / 10
        self.res_mgr.add_path(self.test_path, self.min_free)
        available = self.res_mgr.available_space_for_path(self.test_path)
        if(self.res_mgr.reserve_space_for_file(size, self.test_file)):
            now_available = self.res_mgr.available_space_for_path(self.test_path)
            self.assertEqual(now_available, (available - size))
        else:
            self.fail('Failed to reserve space...')

    def testJobQueue(self):
        """
        TODO: Docstring for testJobQueue
        """
        job_number = 3
        job_threads = []
        job_output = []
        for i in range(job_number):
            for name in ReservationManager().queues:
                job_threads.append(MockJob(kwargs=dict(qname=name, position=i, output=job_output)))
        for job in job_threads:
            job.start()
        for job in job_threads:
            if job.isAlive():
                job.join()
        #self.log.info(job_output)
        self.assertEqual((3 * job_number * len(ReservationManager().queues)), len(job_output))


class MockJob(Thread):
    """ TODO: Docstring for MockJob  """

    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        super(MockJob, self).__init__(group=None, target=None, name=None, args=(), kwargs={})
        self.qname = kwargs['qname']
        self.position = kwargs['position']
        self.output = kwargs['output']

    def run(self):
        resmgr = ReservationManager()
        str_args = (self.qname, self.position)
        self.output.append('enter-%s-%d' % str_args)
        resmgr.enter_queue(self.qname)
        self.output.append('start-%s-%d' % str_args)
        if(self.qname == 'local'):
            time.sleep(4)
        else:
            time.sleep(1)
        self.output.append('exit-%s-%d' % str_args)
        resmgr.exit_queue(self.qname)


if __name__ == '__main__':
    unittest.main()
