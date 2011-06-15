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

class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
            instance._singleton_init()
            cls._instance = instance
        elif args or kwargs:
            cls._instance.log.warn('Attempted re-initialize of singleton: %s' % (cls._instance, ))
        return cls._instance

    def __init__(self):
        pass

    def _singleton_init(self):
        """Initialize a singleton instance before it is registered."""
        pass
