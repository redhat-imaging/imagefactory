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
socket = connect('ec2-50-17-149-29.compute-1.amazonaws.com', 5672)
connection = Connection(sock=socket, username='Administrator', password='DRDqt-qR2?Z')
connection.start()
session = connection.session(str(uuid4()))

# Setup queue
session.queue_declare(queue='client_queue')
session.exchange_bind(exchange='amq.topic', queue='client_queue', binding_key='routing_key')

# Setup routing properties
properties = session.delivery_properties(routing_key='routing_key')

# Send messages
session.message_transfer(destination='amq.topic', message=Message(properties, 'dir'))
session.message_transfer(destination='amq.topic', message=Message(properties, 'ipconfig'))

#TODO : implement also the listener here to receive messages back from the proxy


# Define local queue
local_queue_name = 'local_queue'

# Create local queue
queue = session.incoming(local_queue_name)

# Route messages from message_queue to my_local_queue
session.message_subscribe(queue='proxy_queue', destination=local_queue_name)
queue.start()

content = ''

while (queue.qsize()) != 0:
    # Get message from the local queue
    message = queue.get(timeout=10)
    # Get body of the message
    content = message.body
    # Accept message (removes it from the queue)
    session.message_accept(RangedSet(message.id))
    # Print message content
    print content 

# Close session
session.close(timeout=100)


