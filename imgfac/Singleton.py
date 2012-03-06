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

class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
            instance._singleton_init(*args, **kwargs)
            cls._instance = instance
        elif args or kwargs:
            cls._instance.log.warn('Attempted re-initialize of singleton: %s' % (cls._instance, ))
        return cls._instance

    def __init__(self):
        pass

    def _singleton_init(self):
        """Initialize a singleton instance before it is registered."""
        pass
