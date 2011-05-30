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

import sys
import libxml2
import logging
import cqpid
from qmf2 import *
from threading import Thread, Lock
from imagefactory import props
from imagefactory.builders import *
from imagefactory.BuildDispatcher import BuildDispatcher

class BuildAdaptor(BuildDispatcher):
    # QMF schema for BuildAdaptor
    qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "BuildAdaptor")
    qmf_schema.addProperty(SchemaProperty("status", SCHEMA_DATA_STRING, desc="string representing the status (see instance_states() on ImageFactory)"))
    qmf_schema.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT, desc="the estimated percentage through an operation"))
    qmf_schema.addProperty(SchemaProperty("image_id", SCHEMA_DATA_STRING, desc="string representation of the assigned uuid"))
    qmf_schema.addMethod(SchemaMethod("abort", desc = "If possible, abort running build."))

    #QMF schema for status change event
    qmf_event_schema_status = Schema(SCHEMA_TYPE_EVENT, "com.redhat.imagefactory", "BuildAdaptorStatusEvent")
    qmf_event_schema_status.addProperty(SchemaProperty("addr", SCHEMA_DATA_MAP, desc="the address of the object raising this event"))
    qmf_event_schema_status.addProperty(SchemaProperty("event", SCHEMA_DATA_STRING, desc="string describing the type of event, in this case 'STATUS'"))
    qmf_event_schema_status.addProperty(SchemaProperty("new_status", SCHEMA_DATA_STRING, desc="string value of the new status"))
    qmf_event_schema_status.addProperty(SchemaProperty("old_status", SCHEMA_DATA_STRING, desc="string value of the old status"))
    #QMF schema for change to percent_complete event
    qmf_event_schema_percentage = Schema(SCHEMA_TYPE_EVENT, "com.redhat.imagefactory", "BuildAdaptorPercentCompleteEvent")
    qmf_event_schema_percentage.addProperty(SchemaProperty("addr", SCHEMA_DATA_MAP, desc="the address of the object raising this event"))
    qmf_event_schema_percentage.addProperty(SchemaProperty("event", SCHEMA_DATA_STRING, desc="string describing the type of event, in this case 'PERCENTAGE'"))
    qmf_event_schema_percentage.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT, desc="the estimated percentage through an operation"))
    #QMF schema for build failure events
    qmf_event_schema_build_failed = Schema(SCHEMA_TYPE_EVENT, "com.redhat.imagefactory", "BuildFailedEvent")
    qmf_event_schema_build_failed.addProperty(SchemaProperty("addr", SCHEMA_DATA_MAP, desc="the address of the object raising this event"))
    qmf_event_schema_build_failed.addProperty(SchemaProperty("event", SCHEMA_DATA_STRING, desc="string describing the type of event, in this case 'FAILURE'"))
    qmf_event_schema_build_failed.addProperty(SchemaProperty("type", SCHEMA_DATA_STRING, desc="short string description of the failure"))
    qmf_event_schema_build_failed.addProperty(SchemaProperty("info", SCHEMA_DATA_STRING, desc="longer string description of the failure"))

    @classmethod
    def object_states(cls):
        """Returns a dictionary representing the finite state machine for instances of this class."""
        return {
                "NEW":({"INITIALIZING":("build_image", "push_image")}, {"PENDING":("build_image", "push_image")}, {"FAILED":("build_image", "push_image")}),
                "INITIALIZING":({"PENDING":("_auto_")}, {"FAILED":("_auto_")}),
                "PENDING":({"FINISHING":("_auto_")}, {"COMPLETED":("_auto_")}, {"FAILED":("_auto_")}),
                "FINISHING":({"COMPLETED":("_auto_")}, {"FAILED":("_auto_")}),
                "COMPLETED":()
                }

    status = props.subprop("qmf_object", "status", "The status property.")
    percent_complete = props.subprop("qmf_object", "percent_complete", "The percent_complete property.")
    new_image_id = props.subprop("qmf_object", "image_id", "The image property.")
    qmf_object = props.prop("_qmf_object", "The qmf_object property.")

    def __init__(self, template, target, agent=None):
        self.qmf_object = Data(BuildAdaptor.qmf_schema)
        super(BuildAdaptor, self).__init__(template, target)
        self.agent = agent

    # Builder delegate methods
    def builder_did_update_status(self, builder, old_status, new_status):
        super(BuildAdaptor, self).builder_did_update_status(builder, old_status, new_status)
        self.log.debug("Raising event with agent handler (%s), changed status from %s to %s" % (self.agent, old_status, new_status))
        event = Data(BuildAdaptor.qmf_event_schema_status)
        event.addr = self.qmf_object.getAddr().asMap()
        event.event = "STATUS"
        event.new_status = str(new_status)
        event.old_status = str(old_status)
        self.agent.session.raiseEvent(data=event, severity=SEV_NOTICE)

        if(new_status == "COMPLETED"):
            self.agent.deregister(self.qmf_object)


    def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
        super(BuildAdaptor, self).builder_did_update_percentage(builder, original_percentage, new_percentage)
        self.log.debug("Raising event with agent handler (%s), changed percent complete from %s to %s" % (self.agent, original_percentage, new_percentage))
        event = Data(BuildAdaptor.qmf_event_schema_percentage)
        event.addr = self.qmf_object.getAddr().asMap()
        event.event = "PERCENTAGE"
        event.percent_complete = new_percentage
        self.agent.session.raiseEvent(data=event, severity=SEV_NOTICE)

    def builder_did_fail(self, builder, failure_type, failure_info):
        super(BuildAdaptor, self).builder_did_fail(builder, failure_type, failure_info)
        self.log.debug("Raising event with agent handler (%s), BUILD FAILED: %s - %s" % (self.agent, failure_type, failure_info))
        event = Data(BuildAdaptor.qmf_event_schema_build_failed)
        event.addr = self.qmf_object.getAddr().asMap()
        event.event = "FAILURE"
        event.type = failure_type
        event.info = failure_info
        self.agent.session.raiseEvent(data=event, severity=SEV_ERROR)


# if __name__ == '__main__':
# 	unittest.main()
