Title: Image Factory QMF API
Format: complete
Author: Steve Loranz
Date: March 24, 2011
Revision: 1.1
Keywords: aeolus,image_factory,cloud,qmf,qmf2,api

## Introduction ##

The script imagefactory.py can be used to start a daemon running a QMF agent.  Using the 'qpidd' option, the host that qpidd is running on can be set.  Currently this defaults to the default qpidd port on localhost.  Future versions will accept an amqp:// URL to fully configure the agent session.

	Example usage:
	
		./imgfac.py --verbose --qmf --qpidd localhost

Once the agent has opened a session, QMF consoles can send messages to the agent start image builds, get status on builds, etc.

---

## Image Factory Agent ##

Once a console connects to the same QMF bus as the Image Factory, the agent can be found given the vendor ("redhat.com") and product ("imagefactory") portions of the agent name.  

	Example 1 - Getting an agent list in python
	
		In [1]: import cqpid
		In [2]: from qmf2 import *
		In [3]: connection = cqpid.Connection("localhost")
		In [4]: connection.open()
		In [5]: session = ConsoleSession(connection)
		In [6]: session.open()
		In [7]: session.getAgents()
		Out[7]: 
		[apache.org:qpidd:41fc7abd-56cc-4090-97a8-011ef1104f7f, redhat.com:imagefactory:5edbf641-78ba-4375-8ec8-f60f555e173a]
		
Given an agent, an imagefactory can be fetched:

	Example 2 - Querying for an imagefactory
	
		In [14]: factory = agent.query("{class:ImageFactory, package:'com.redhat.imagefactory'}")[0]
		
The imagefactory can then be sent a message to build an image:

	Example 3 - Building an image
	
		In [15]: factory.image("<template></template>", "mock")
		Out[15]: 
		{'build_adaptor': {'_agent_epoch': 1L,
		                   '_agent_name': 'redhat.com:imagefactory:5edbf641-78ba-4375-8ec8-f60f555e173a',
		                   '_object_name': 'build_adaptor:db21dd5e-b3b6-49d1-a432-07f9f2d1c3c5'}}
		
The console can poll the build_adaptor for build status or receive events listed below.

	Example 4 - Querying for build status
	
		In [20]: response = factory.image("<template></template>", "mock")
		In [21]: build_addr = DataAddr(response['build_adaptor'])
		In [22]: query = Query(build_addr)
		In [23]: agent.query(query)[0].status
		Out[23]: 'PENDING'
		In [24]: agent.query(query)[0].status
		Out[24]: 'FINISHING'
		In [25]: agent.query(query)[0].status
		Out[25]: 'COMPLETED'
		
---
## Schemas for Image Factory classes ##

### ImageFactory class ###
    name = "ImageFactory"
    package = "com.redhat.imagefactory"
#### Methods: ####
* `image(template, target)`
        
        method name = "image"
        desc = "Build a new image"
        arguments:
            name = "template"
                dtype = SCHEMA_DATA_STRING
                desc = "string of xml, uuid, or url"
            name = "target"
                dtype = SCHEMA_DATA_STRING
                desc = "name of the cloud to target"
        return values:
            name = "build_adaptor"
                dtype = SCHEMA_DATA_MAP
                desc = "the QMF address of the build_adaptor instantiated"

* `provider_image(image_id, provider, credentials)`
        
        method name = "provider_image"
        desc = "Push an image to a provider."
        arguments:
            name = "image_id"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an image previously built"
            name = "provider"
                dtype = SCHEMA_DATA_STRING
                desc = "the name of the cloud provider, often a region"
            name = credentials"
                dtype = SCHEMA_DATA_STRING
                desc = "an xml string representation of the credentials"
        return values:
            name = "build_adaptor"
                dtype = SCHEMA_DATA_MAP
                desc = "the QMF address of the build_adaptor instantiated"

* `instance_states(class_name)`
        
        method name = "instance_states"
        desc = "Returns a dictionary representing the finite state machine for instances."
        arguments:
            name = "class_name"
                dtype = SCHEMA_DATA_STRING
                desc = "the name of the class to query for instance states"
        return values:
            name = "states"
                dtype = SCHEMA_DATA_STRING
                desc = "string representation of a dictionary describing the workflow"
    
### BuildAdaptor class ###
    name = "BuildAdaptor"
    package = "com.redhat.imagefactory"

#### Properties: ####
* Status
        
        name = "status"
            dtype = SCHEMA_DATA_STRING
            desc = "string representing the status (see instance_states() on ImageFactory)"
* Percentage Complete
        
        name = "percent_complete"
            dtype = SCHEMA_DATA_INT
            desc = "the estimated percentage through an operation"
* Image ID
        
        name = "image_id"
            dtype = SCHEMA_DATA_STRING
            desc = "string representation of the assigned uuid"

#### Methods: ####
* `abort()`
        
        name = "abort"
        desc = "If possible, abort running build."

#### Events: ####
* Status Updates
        
        name = "BuildAdaptorStatusEvent"
        package = "com.redhat.imagefactory"
        attributes:
            name = "addr"
                dtype = SCHEMA_DATA_MAP
                desc = "the address of the object raising this event"
            name = "event"
                dtype = SCHEMA_DATA_STRING
                desc = "string describing the type of event, in this case 'STATUS'"
            name = "new_status"
                dtype = SCHEMA_DATA_STRING
                desc = "string value of the new status"
            name = "old_status"
                dtype = SCHEMA_DATA_STRING
                desc = "string value of the old status"
        
* Updates to the Percentage Complete
        
        name = "BuildAdaptorPercentCompleteEvent"
        package = "com.redhat.imagefactory"
        attributes:
            name = "addr"
                dtype = SCHEMA_DATA_MAP
                desc = "the address of the object raising this event"
            name = "event"
                dtype = SCHEMA_DATA_STRING
                desc = "string describing the type of event, in this case 'STATUS'"
            name = "percent_complete"
                dtype = SCHEMA_DATA_INT
                desc = "string value of the new status"
        
* Failure Notification
        
        name = "BuildFailedEvent"
        package = "com.redhat.imagefactory"
        attributes:
            name = "addr"
                dtype = SCHEMA_DATA_MAP
                desc = "the address of the object raising this event"
            name = "event"
                dtype = SCHEMA_DATA_STRING
                desc = "string describing the type of event, in this case 'STATUS'"
            name = "type"
                dtype = SCHEMA_DATA_STRING
                desc = "string value of the new status"
            name = "info"
                dtype = SCHEMA_DATA_STRING
                desc = "string value of the old status"

