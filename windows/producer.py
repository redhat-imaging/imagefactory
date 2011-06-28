#!/usr/bin/env python
# encoding: utf-8

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
