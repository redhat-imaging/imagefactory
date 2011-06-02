# Copyright (C) 2010-2011 Red Hat, Inc.
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

import logging
import os
import os.path

class ReservationManager(object):
    """ TODO: Docstring for ReservationManager """
    instance = None

    DEFAULT_MINIMUM = 21474836480

    ### Properties
    def default_minimum():
        """The property default_minimum"""
        def fget(self):
            return self._default_minimum
        def fset(self, value):
            self._default_minimum = value
        return locals()
    default_minimum = property(**default_minimum())

    @property
    def available_space(self):
        """Dictionary of mount points and bytes available."""
        space = dict()
        for path in self._mounts.keys():
            space.update({path:self.available_space_for_path(path)})
        return space

    @property
    def reservations(self):
        """Dictionary of filepaths and number of bytes reserved for each."""
        reservations = dict()
        for key in self._mounts.keys():
            reservations.update(self._mounts[key]['reservations'])
        return reservations
    ### END Properties

    def __new__(cls, *p, **k):
        if cls.instance is None:
            i = super(ReservationManager, cls).__new__(cls, *p, **k)
            # initialize here, not in __init__()
            i.log = logging.getLogger('%s.%s' % (__name__, i.__class__.__name__))
            i.default_minimum = k.get('default_minimum',
                    p[0] if(len(p) > 0) else cls.DEFAULT_MINIMUM)
            i._mounts = dict()
            cls.instance = i
        return cls.instance

    def __init__(self, default_minimum=None):
        """
        @param default_minimum Default for the minimum amount needed for a path.
        """
        pass

    def reserve_space_for_file(self, size, filepath):
        """
        TODO: Docstring for reserve_space_for_file

        @param size TODO
        @param filepath TODO
        """
        mount_path = self._mount_for_path(filepath)
        mount = self._mounts.setdefault(mount_path,
                {'min_free': self.default_minimum, 'reservations': dict()})
        available = self.available_space_for_path(mount_path) - mount['min_free']
        if(size < available):
            mount['reservations'].update({filepath:size})
            return True
        else:
            return False

    def cancel_reservation_for_file(self, filepath, quiet=True):
        """
        TODO: Docstring for cancel_reservation_for_file

        @param filepath TODO
        """
        mount_path = self._mount_for_path(filepath)

        try:
            mount = self._mounts.get(mount_path)
            try:
                del mount['reservations'][filepath]
            except (TypeError, KeyError), e:
                if(quiet):
                    self.log.warn('No reservation for %s to cancel!' % filepath)
                else:
                    raise e
        except KeyError,e:
            if(quiet):
                self.log.warn('No reservations exist on %s!' % mount_path)
            else:
                raise e

    def _mount_for_path(self, path):
        path = os.path.abspath(path)
        while path != os.path.sep:
            if os.path.ismount(path):
                return path
            path = os.path.abspath(os.path.join(path, os.pardir))
        return path

    def add_path(self, path, min_free=None):
        """
        TODO: Docstring for add_path

        @param path TODO
        @param min_free TODO
        """
        if(isinstance(path, str)):
            mount_path = self._mount_for_path(path)
            mount = self._mounts.setdefault(mount_path,
                    {'min_free':min_free, 'reservations': dict()})
            if(not mount):
                raise RuntimeError("Unable to add path (%s)." % path)
        else:
            raise TypeError("Argument 'path' must be string.")

    def remove_path(self, path, quiet=True):
        """
        Removes a path from the list of watched paths.

        @param path Filesystem path string to remove.
        """
        mount_path = self._mount_for_path(path)
        try:
            del self._mounts[mount_path]
        except KeyError, e:
            if(quiet):
                self.log.warn('%s not in reservation list.' % mount_path)
            else:
                raise e

    def available_space_for_path(self, path):
        """
        TODO: Docstring for available_space_for_path
        
        @param path TODO 
    
        @return TODO
        """
        mount_path = self._mount_for_path(path)
        if(mount_path in self._mounts):
            reservations = self._mounts[mount_path]['reservations'].values()
            reservation_total = sum(reservations)
            consumed_total = 0
            for filepath in self._mounts[mount_path]['reservations'].keys():
                try:
                    consumed_total += os.path.getsize(filepath)
                except os.error:
                    self.log.warn('%s does not exist.' % filepath)
            remaining = reservation_total - consumed_total
            stat = os.statvfs(path)
            available = stat.f_bavail * stat.f_frsize
            return available - (remaining if remaining > 0 else 0)
        else:
            return None
