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

#
# TODO:
#  - add support for read-only properties
#

#
# Return a copy of dict d with the specified keys filtered out
#
def filter_dict(d, keys):
    return dict(map(lambda k: [k, d[k]], filter(lambda k: not k in keys, d.keys())))

#
# Return a property backed by the given attribute
#
def prop(attr, doc = None):
    def fget(self):
        return getattr(self, attr)
    def fset(self, value):
        setattr(self, attr, value)
    def fdel(self):
        delattr(self, attr)
    return property(**filter_dict(locals().copy(), ['attr']))

#
# A variant of the above where the property is backed by an
# attribute of an attribute
#
def subprop(attr, subattr, doc = None):
    def fget(self):
        return getattr(getattr(self, attr), subattr)
    def fset(self, value):
        setattr(getattr(self, attr), subattr, value)
    def fdel(self):
        delattr(getattr(self, attr), subattr)
    return property(**filter_dict(locals().copy(), ['attr', 'subattr']))
