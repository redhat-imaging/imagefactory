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
    return subprop(attr, subattr, doc, True)
