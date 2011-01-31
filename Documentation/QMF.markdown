Title: Image Factory QMF API
Format: complete
Author: Steve Loranz
Date: January 26, 2011
Revision: 1.0
Keywords: aeolus,image_factory,cloud,qmf,qmf2,api

## Introduction ##

The script imagefactory.py can be used to start a daemon running a QMF agent.  Using the 'broker' option, the host that qpidd is running on can be set.  Currently this defaults to the default qpidd port on localhost.  Future versions will accept an amqp:// URL to fully configure the agent session.

	Example usage:
	
		./imagefactory.py --verbose --qmf --broker localhost

Once the agent has opened a session with the broker, QMF consoles can send messages to the agent start image builds, get status on builds, etc.

---

## Image Factory Agent ##

Once a console connects to the same broker as the Image Factory, the agent can be found given the vendor ("redhat.com") and product ("imagefactory") portions of the agent name.  

	Example 1 - Getting an agent list in python
	
		In [1]: import cqpid
		In [2]: from qmf2 import *
		In [3]: connection = cqpid.Connection("localhost")
		In [4]: session = ConsoleSession(connection)
		In [5]: connection.open()
		In [6]: session.open()
		In [7]: session.getAgents()
		Out[7]: 
		[apache.org:qpidd:41fc7abd-56cc-4090-97a8-011ef1104f7f, redhat.com:imagefactory:5edbf641-78ba-4375-8ec8-f60f555e173a]
		
Given an agent, an imagefactory can be fetched:

	Example 2 - Querying for an imagefactory
	
		In [14]: factory = agent.query("{class:ImageFactory, package:'com.redhat.imagefactory'}")[0]
		
The imagefactory can then be sent a message to build an image:

	Example 3 - Building an image
	
		In [15]: factory.build_image("<template></template>", "mock", "foo", "bar")
		Out[15]: 
		{'build_adaptor': {'_agent_epoch': 1L,
		                   '_agent_name': 'redhat.com:imagefactory:5edbf641-78ba-4375-8ec8-f60f555e173a',
		                   '_object_name': 'build_adaptor-db21dd5e-b3b6-49d1-a432-07f9f2d1c3c5'}}
		
The console can poll the build_adaptor for build status.  Future releases of Image Factory will send QMF events when build status changes to obviate the need for consoles to poll the agent.

	Example 4 - Querying for build status
	
		In [20]: response = factory.build_image("<template></template>", "mock", "foo", "bar")
		In [21]: build_addr = DataAddr(response['build_adaptor'])
		In [22]: query = Query(build_addr)
		In [23]: agent.query(query)[0].status
		Out[23]: 'BUILDING'
		In [24]: agent.query(query)[0].status
		Out[24]: 'FINISHING'
		In [25]: agent.query(query)[0].status
		Out[25]: 'COMPLETED'
		
---
## Schemas for Image Factory classes ##

### ImageFactory ###
	qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "ImageFactory")
    _method = SchemaMethod("build_image", desc="Build a new image")
    _method.addArgument(SchemaProperty("descriptor", SCHEMA_DATA_STRING, direction=DIR_IN))
    _method.addArgument(SchemaProperty("target", SCHEMA_DATA_STRING, direction=DIR_IN))
    _method.addArgument(SchemaProperty("image_uuid", SCHEMA_DATA_STRING, direction=DIR_IN))
    _method.addArgument(SchemaProperty("sec_credentials", SCHEMA_DATA_STRING, direction=DIR_IN))
    _method.addArgument(SchemaProperty("build_adaptor", SCHEMA_DATA_MAP, direction=DIR_OUT))
    
### BuildAdaptor ###
	qmf_schema = Schema(SCHEMA_TYPE_DATA, "com.redhat.imagefactory", "BuildAdaptor")
    qmf_schema.addProperty(SchemaProperty("descriptor", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("target", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("status", SCHEMA_DATA_STRING))
    qmf_schema.addProperty(SchemaProperty("percent_complete", SCHEMA_DATA_INT))
    qmf_schema.addProperty(SchemaProperty("finished_image", SCHEMA_DATA_STRING))
    
