Title: Image Factory README
Format: complete
Author: Steve Loranz
Date: January 12, 2011
Revision: 1.0
Keywords: aeolus,image_factory,cloud

## Usage ##

	usage: imagefactory [-h] [--version] [-v] [--debug] [--config CONFIG]
	                    [--output OUTPUT] [--warehouse WAREHOUSE] [--qmf]
	                    [--broker BROKER] [-b] [-t TEMPLATE]
	
	System image creation tool...
	
	optional arguments:
	  -h, --help            show this help message and exit
	  --version             Version info
	  -v, --verbose         Set verbose logging.
	  --debug               Set really verbose logging for debugging.
	  --config CONFIG       Configuration file to use. (default:
	                        /etc/imagefactory.conf)
	  --output OUTPUT       Build image files in location specified. (default:
	                        /tmp)
	  --warehouse WAREHOUSE
	                        URL of the warehouse location to store images.
	
	QMF options:
	  Provide a QMFv2 agent interface.
	
	  --qmf                 Turn on QMF agent interface. (default: False)
	  --broker BROKER       URL of qpidd to connect to. (default: localhost)
	
	One time build options:
	  NOT YET IMPLEMENTED: Build specified system and exit.
	
	  -b, --build           Build image specified by template.
	  -t TEMPLATE, --template TEMPLATE
	                        Template XML file to build from.
	
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