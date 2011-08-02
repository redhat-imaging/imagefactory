## Introduction ##

The script imagefactory can be used to start a daemon running a QMF agent.  Using the 'qpidd' option, the host that qpidd is running on can be set.  Currently this defaults to the default qpidd port on localhost.  Future versions will accept an amqp:// URL to fully configure the agent session.

	Example usage:
	
		./imagefactory --verbose --qmf --qpidd localhost

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
	
		In [15]: factory.build_image("", "", "<template></template>", ["mock"])
		Out[15]: 
		{'build_adaptors': [{'_agent_epoch': 1L,
		                     '_agent_name': 'redhat.com:imagefactory:5edbf641-78ba-4375-8ec8-f60f555e173a',
		                     '_object_name': 'build_adaptor:db21dd5e-b3b6-49d1-a432-07f9f2d1c3c5'}]}
		
The console can poll the build_adaptor for build status or receive events listed below.

	Example 4 - Querying for build status
	
		In [20]: response = factory.build_image("", "" "<template></template>", ["mock"])
		In [21]: build_addr = DataAddr(response['build_adaptors'][0])
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
* `build_image(image, build, template, targets)`
        
        method name = "build_image"
        desc = "Build an image for the given targets"
        arguments:
            name = "image"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an existing image, or the empty string"
            name = "build"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an existing build, or the empty string"
            name = "template"
                dtype = SCHEMA_DATA_STRING
                desc = "string of xml, uuid, or url"
            name = "targets"
                dtype = SCHEMA_DATA_LIST
                desc = "names of the clouds to target"
        return values:
            name = "build_adaptors"
                dtype = SCHEMA_DATA_LIST
                desc = "the QMF addresses of the build_adaptors instantiated"

* `provider_image(image, build, providers, credentials)`
        
        method name = "push_image"
        desc = "Push an image to the given providers."
        arguments:
            name = "image"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an existing image"
            name = "build"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an existing build, or the empty string"
            name = "providers"
                dtype = SCHEMA_DATA_LIST
                desc = "the name of the cloud providers, often target cloud regions"
            name = "credentials"
                dtype = SCHEMA_DATA_STRING
                desc = "an xml string representation of the credentials"
        return values:
            name = "build_adaptors"
                dtype = SCHEMA_DATA_LIST
                desc = "the QMF addresses of the build_adaptors instantiated"

* `import_image(image, build, target_identifier, image_desc, target, provider)`
        
        method name = "import_image"
        desc = "Import an image using a target specific image identifier"
        arguments:
            name = "image"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an existing image"
            name = "build"
                dtype = SCHEMA_DATA_STRING
                desc = "the uuid of an existing build, or the empty string"
            name = "target_identifier"
                dtype = SCHEMA_DATA_STRING
                desc = "the target specific image ID"
            name = "image_desc"
                dtype = SCHEMA_DATA_STRING
                desc = "an xml string description of the image"
            name = "target"
                dtype = SCHEMA_DATA_STRING
                desc = "name of the cloud to target"
            name = "provider"
                dtype = SCHEMA_DATA_STRING
                desc = "the name of the cloud provider, often a region"
        return values:
            name = "image"
                dtype = SCHEMA_DATA_STRING
                desc = "the UUID of an image previously built"
            name = "build"
                dtype = SCHEMA_DATA_STRING
                desc = "the UUID of a previous build of the image"
            name = "target_image"
                dtype = SCHEMA_DATA_STRING
                desc = "the UUID of the target image object"
            name = "provider_image"
                dtype = SCHEMA_DATA_STRING
                desc = "the UUID of the provider image object"

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
* Image
        
        name = "image"
            dtype = SCHEMA_DATA_STRING
            desc = "the uuid of the image being built or pushed"
* Build
        
        name = "build"
            dtype = SCHEMA_DATA_STRING
            desc = "the uuid of the image build being built or pushed"
* Status
        
        name = "status"
            dtype = SCHEMA_DATA_STRING
            desc = "string representing the status (see instance_states() on ImageFactory)"
* Percentage Complete
        
        name = "percent_complete"
            dtype = SCHEMA_DATA_INT
            desc = "the estimated percentage through an operation"
* Target/Provider Image ID
        
        name = "image_id"
            dtype = SCHEMA_DATA_STRING
            desc = "the uuid of the newly created target or provider image"

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
                desc = "string describing the type of event, in this case 'PERCENTAGE'"
            name = "percent_complete"
                dtype = SCHEMA_DATA_INT
                desc = "the estimated percentage through an operation"
        
* Failure Notification
        
        name = "BuildFailedEvent"
        package = "com.redhat.imagefactory"
        attributes:
            name = "addr"
                dtype = SCHEMA_DATA_MAP
                desc = "the address of the object raising this event"
            name = "event"
                dtype = SCHEMA_DATA_STRING
                desc = "string describing the type of event, in this case 'FAILURE'"
            name = "type"
                dtype = SCHEMA_DATA_STRING
                desc = "short string description of the failure"
            name = "info"
                dtype = SCHEMA_DATA_STRING
                desc = "longer string description of the failure"

