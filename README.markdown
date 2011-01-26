Title: Image Factory README
Format: complete
Author: Steve Loranz
Date: January 12, 2011
Revision: 1.0
Keywords: aeolus,image_factory,cloud

## Usage ##

	usage: imagefactory.py [-h] [-v] [--debug] [--output OUTPUT] [--version]
	                       {build,qmf} ...
	
	System image creation tool...
	
	optional arguments:
	  -h, --help       show this help message and exit
	  -v, --verbose    Set verbose logging.
	  --debug          Set really verbose logging for debugging.
	  --output OUTPUT  Store built images in location specified. Defaults to /tmp
	  --version        Version info
	
	commands:
	  {build,qmf}
	    qmf            Provide a QMFv2 agent interface.
	    build          NOT YET IMPLEMENTED: Build specified system and exit.

## Dependencies ##

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