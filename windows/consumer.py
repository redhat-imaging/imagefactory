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

from qpid.connection import Connection
from qpid.datatypes import RangedSet, Message, uuid4
from qpid.util import connect

# Create connection and session
socket = connect('localhost', 5672)
connection = Connection(sock=socket, username='guest', password='guest')
connection.start()
session = connection.session(str(uuid4()))

# Define local queue
local_queue_name = 'local_queue'

# Create local queue
queue = session.incoming(local_queue_name)

# Route messages from message_queue to my_local_queue
session.message_subscribe(queue='client_queue', destination=local_queue_name)
queue.start()

content = ''

#Setup proxy queue
session.queue_declare(queue='proxy_queue')
session.exchange_bind(exchange='amq.topic', queue='proxy_queue', binding_key='proxy_key')

#Setup routing properties
properties = session.delivery_properties(routing_key='proxy_key')

output=''

while True:
    # Get message from the local queue
    message = queue.get()
    # Get body of the message
    content = message.body
    # Accept message (removes it from the queue)
    session.message_accept(RangedSet(message.id))
    # Print message content
    #print content

    from System.Diagnostics import Process
    proc = Process()
    proc.StartInfo.FileName = 'cmd.exe'
    proc.StartInfo.Arguments = "/c %s"  % content
    proc.StartInfo.UseShellExecute = False
    proc.StartInfo.RedirectStandardOutput = True
    proc.StartInfo.RedirectStandardError = True
    proc.Start()
    proc.WaitForExit()
    stdout = proc.StandardOutput.ReadToEnd()
    stderr = proc.StandardError.ReadToEnd()
    session.message_transfer(destination='amq.topic', message=Message(properties, stdout))

session.close(timeout=10)
# Close session
