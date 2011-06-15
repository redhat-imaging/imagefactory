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
# Return a property backed by the given attribute
#
def prop(attr, doc = None, ro = None):
    def fget(self):
        return getattr(self, attr)
    def fset(self, value):
        setattr(self, attr, value)
    def fdel(self):
        delattr(self, attr)
    return property(fget, fset if not ro else None, fdel if not ro else None, doc)

def ro_prop(attr, doc = None):
    return prop(attr, doc, True)

#
# A variant of the above where the property is backed by an
# attribute of an attribute
#
def subprop(attr, subattr, doc = None, ro = False):
    def fget(self):
        return getattr(getattr(self, attr), subattr)
    def fset(self, value):
        setattr(getattr(self, attr), subattr, value)
    def fdel(self):
        delattr(getattr(self, attr), subattr)
    return property(fget, fset if not ro else None, fdel if not ro else None, doc)

def ro_subprop(attr, subattr, doc = None):
    return prop(attr, subattr, doc, True)
