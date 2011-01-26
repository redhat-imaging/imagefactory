Title: Image Factory README
Format: complete
Author: Steve Loranz
Date: January 12, 2011
Revision: 1.0
Keywords: aeolus,image_factory,cloud


	usage: imagefactory.py [-h] [-v] [--qmf] [--url URL]
                       [--build-template BUILD_TEMPLATE]
                       [--build-output BUILD_OUTPUT] [--version]
					
	System image creation tool...
	
	optional arguments:
  		-h, --help            show this help message and exit
  		-v, --verbose         Set verbose logging for debugging.
  		--qmf                 Provide QMFv2 agent interface.
  		--url URL             URL of qpidd to connect to.
  		--build-template BUILD_TEMPLATE
                        	  NOT YET IMPLEMENTED: 
								Build specified system and exit.
  		--build-output BUILD_OUTPUT
                        	  NOT YET IMPLEMENTED: 
							  	Store built image in location specified.
  		--version             Version info


**Dependencies**
----------------
QMFv2 Python bindings
: [QMF-Homepage][]  
*Note:* QMFv2 is currently only available by checking out the C++ source from [QPID-Repo][].

Oz
: [Oz-Repo][]  
Oz is a set of classes and scripts to do automated installations of various
guest operating systems.


[QMF-Homepage]: https://cwiki.apache.org/qpid/qpid-management-framework.html
[QPID-Repo]: https://svn.apache.org/repos/asf/qpid/trunk/qpid/cpp/
[Oz-Repo]: https://github.com/clalancette/oz