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


import argparse
from qpid.messaging import *
from qpid.util import URL
import base64
from subprocess import Popen, STDOUT, PIPE


parser = argparse.ArgumentParser(description = "Qpid broker with windows command execution")
parser.add_argument('--broker', action='store', dest='broker', default='localhost', help="Broker's address, default is localhost")
parser.add_argument('--username', action='store', dest='username', help='Username for broker', required=True)
parser.add_argument('--password', action='store', dest='password', help='Password for broker', required=True)
arguments = parser.parse_args()

connection = Connection(arguments.broker, username=arguments.username, password=arguments.password)
connection.open()
session = connection.session(str(uuid4()))

receiver = session.receiver('amq.topic')

while True:
    message = receiver.fetch()
    session.acknowledge()
    sender = session.sender(message.reply_to)
    
    proc = Popen(base64.b64decode(message.content), shell=True, stderr=STDOUT, stdin=PIPE, stdout=PIPE)
    output, _ = proc.communicate()
    result = Message(base64.b64encode(output))
    result.properties["exit"] = proc.returncode
    sender.send(result)

connection.close()
