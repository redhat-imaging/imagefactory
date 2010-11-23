#!/usr/bin/env python

# Copyright (C) 2010 Red Hat, Inc.
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

import qmf
import sys
import time
import Build, ImageFactory

class FactoryApp(qmf.AgentHandler):
    '''
    Image Factory appliation handler object
    '''
    def get_query(self, context, query, userId):
        '''
        Console query requests end up here
        '''
        print "Query: user=%s context=%d class=%s" % (userId, context, query.class_name())
        if query.object_id():
            print "Query contains object_id: %s " % ( query.object_id() )

        # We can get querys for all objects of a given class
        # or for a specific object ID

        if query.class_name() == 'ImageFactory':
            self._agent.query_response(context, self._image_factory.qmf_object)
        elif query.class_name() == 'Build':
            # List all BuildAdaptors
            # For each one take the associated qmf_object and fire a query response
            for _instance in Build.BuildAdaptor.class_instances:
                self._agent.query_response(context, _instance.qmf_object)
        elif query.object_id():
            # Two possible matches - The ImageBuilder or one of the ActiveBuilds
            if query.object_id()  == self._image_factory.qmf_object.object_id():
                self._agent.query_response(context, self._image_factory.qmf_object)
            else:
                # If object ID is in our dictionary return a query response of that object
                _adaptor = Build.BuildAdaptor.find_by_qmf_id(query.object_id())
                if _adaptor:
                    self._agent.query_response(context, _adaptor.qmf_object)
        self._agent.query_complete(context)

    
    def method_call(self, context, name, object_id, args, userId):
        '''
        Console method calls end up here
        '''
        print "Method: name=%s user=%s context=%d object_id=%s args=%s" % (name, userId, context, object_id, args)

        if name == "build_image":
            _build_adaptor = self._image_factory.build_image(args["descriptor"],args["target"],args["image_uuid"],args["sec_credentials"])
            args['build'] = _build_adaptor.qmf_object.object_id()
            self._agent.method_response(context, 0, "OK", args)
        else:
            self._agent.method_response(context, 1, "Method %s not implemented" % name, args)


    def main(self):
        '''
        Factory primary startup code
        '''
        # Connect to the broker
        self._settings = qmf.ConnectionSettings()
        self._settings.sendUserId = True
        if len(sys.argv) > 1:
            self._settings.host = str(sys.argv[1])
        if len(sys.argv) > 2:
            self._settings.port = int(sys.argv[2])
        self._connection = qmf.Connection(self._settings)

        # Instantiate an Agent to serve me queries and method calls
        self._agent = qmf.Agent(self, "image_factory_agent")

        # The ImageFactory and Build schemas are class attributes
        # register them with the Agent
        self._agent.register_class(ImageFactory.ImageFactory.qmf_schema)
        self._agent.register_class(Build.BuildAdaptor.qmf_schema)

        # The classes need a reference to the agent in order to internally
        # create their QMF bus objects - Currently doing this with class attributes
        # TODO: Better way?
        ImageFactory.ImageFactory.qmf_agent = self._agent
        Build.BuildAdaptor.qmf_agent = self._agent

        # Tell the agent about our connection to the broker
        self._agent.set_connection(self._connection)

        # This seems to be required to let the connection settle
        # Without this we get a different object ID
        time.sleep(5)

        # Instantiate and populate the one and only ImageBuilder
        self._image_factory = ImageFactory.ImageFactory()
    
        print "root ImageFactory has following object id: %s " % (self._image_factory.qmf_object.object_id())

        # Now wait for events arriving on the connection
        # to the broker...
        # We might in future wake up occasionally and do some housekeeping
        while True:
            time.sleep(1000)


app = FactoryApp()
app.main()

