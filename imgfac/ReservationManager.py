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

import logging
import os
import os.path
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from threading import BoundedSemaphore

class ReservationManager(object):
    """ TODO: Docstring for ReservationManager """
    instance = None

    DEFAULT_MINIMUM = 21474836480

    MIN_PORT = 1025
    MAX_PORT = 65535

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

    @property
    def queues(self):
        """The property queues"""
        return self._queues.keys()
    ### END Properties

    def __new__(cls, *p, **k):
        if cls.instance is None:
            i = super(ReservationManager, cls).__new__(cls, *p, **k)
            # initialize here, not in __init__()
            i.log = logging.getLogger('%s.%s' % (__name__, i.__class__.__name__))
            i.default_minimum = cls.DEFAULT_MINIMUM
            i._mounts = dict()
            i.appconfig = ApplicationConfiguration().configuration
            i._queues = dict(local=BoundedSemaphore(i.appconfig.get('max_concurrent_local_sessions', 1)),
                             ec2=BoundedSemaphore(i.appconfig.get('max_concurrent_ec2_sessions', 1)))
            i._named_locks = { } 
            i._named_locks_lock = BoundedSemaphore()
            i._listen_port = cls.MIN_PORT
            i._listen_port_lock = BoundedSemaphore()
            cls.instance = i
        return cls.instance

    def __init__(self):
        """
        @param default_minimum Default for the minimum amount needed for a path.
        """
        pass

    def get_next_listen_port(self):
        self._listen_port_lock.acquire()
        try:
            self._listen_port += 1
            if self._listen_port > self.MAX_PORT:
                self._listen_port = self.MIN_PORT
            return self._listen_port
        finally:
            self._listen_port_lock.release()

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
        except KeyError, e:
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

    def enter_queue(self, name=None):
        """
        Tries to acquire a semaphore for the named queue. Blocks until a slot opens up.
        If no name is given or a queue for the given name is not found, the default 'local' 
        queue will be used.

        @param name - The name of the queue to enter. See the queues property of ReservationManager.
        """
        if(name):
            self.log.debug("ENTERING queue: (%s)" % (name))
            self._queues[name].acquire()
            self.log.debug("SUCCESS ENTERING queue: (%s)" % (name))

    def exit_queue(self, name=None):
        """
        Releases semaphore for the named queue. This opens up a slot for waiting members of the queue.
        If no name is given or a queue for the given name is not found, the default 'local' 
        queue will be used.

        @param name - The name of the queue to enter. See the queues property of ReservationManager.
        """
        if(name):
            self.log.debug("EXITING queue: (%s)" % (name))
            self._queues[name].release()
            self.log.debug("SUCCESS EXITING queue: (%s)" % (name))

    def get_named_lock(self, name):
        """
        Get the named lock.
        If the semaphore representing the lock does not exit, create it in a thread safe way.
        Note that this is always a blocking call that will wait until the lock is available.

        @param name - The name of the lock
        """
        # Global critical section
        self._named_locks_lock.acquire()
        if not name in self._named_locks:
            self._named_locks[name] = BoundedSemaphore()
        self._named_locks_lock.release()
        # End global critical section

        self.log.debug("Grabbing named lock (%s)" % name)
        self._named_locks[name].acquire()
        self.log.debug("Got named lock (%s)" % name)

    def release_named_lock(self, name):
        """
        Release a named lock acquired with get_named_lock()

        @param name - The name of the lock
        """
        self.log.debug("Releasing named lock (%s)" % name)
        self._named_locks[name].release()
