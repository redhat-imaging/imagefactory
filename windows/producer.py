#!/usr/bin/env python
# encoding: utf-8

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

from qpid.messaging import *
from qpid.util import URL
import base64

# Create connection and session
connection = Connection('ec2-50-17-149-29.compute-1.amazonaws.com', username='Administrator', password='DRDqt-qR2?Z')
connection.open()
session = connection.session(str(uuid4()))

sender = session.sender("amq.topic")
receiver = session.receiver('reply-%s; {create:always, delete:always}' % session.name)
messages = ["netstat", "ipconfig", "dir"]

def send_message(command):
    msg = Message(base64.b64encode(command))
    msg.reply_to = 'reply-%s' % session.name
    sender.send(msg)
    message = receiver.fetch()
    print base64.b64decode(message.content)
    session.acknowledge()

for command in messages:
    send_message(command)


connection.close()
