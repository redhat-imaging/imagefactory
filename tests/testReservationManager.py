# Copyright (C) 2010 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import unittest
import logging
import os
from imagefactory.ReservationManager import ReservationManager


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
        self.res_mgr = ReservationManager(self.min_free)

    def tearDown(self):
        self.res_mgr.remove_path(self.test_path)
        os.rmdir(self.test_path)
        del self.res_mgr

    def testSingleton(self):
        """
        Prove this class produces a singelton object.
        """
        self.assertIs(self.res_mgr, ReservationManager())

    def testDefaultMinimumProperty(self):
        """
        TODO: Docstring for testDefaultMinimumProperty
        """
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
        with self.assertRaises((TypeError, KeyError)):
            self.res_mgr.cancel_reservation_for_file('/tmp/not.there', False)

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


if __name__ == '__main__':
    unittest.main()
