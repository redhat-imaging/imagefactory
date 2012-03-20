# encoding: utf-8

#   Copyright 2012 Red Hat, Inc.
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

from props import prop

class Notification(object):
    """ TODO: Docstring for Notification  """

    name = prop("_name")
    sender = prop("_sender")
    user_info = prop("_user_info")

    def __init__(self, name, sender, user_info=None):
        """ TODO: Fill me in
        
        @param name TODO
        @param sender TODO
        @param user_info TODO
        """
        super(Notification, self).init()
        self._name = name
        self._sender = sender
        self._user_info = user_info
        
