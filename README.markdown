## Usage: ##

	usage: imagefactory [-h] [--version] [-v] [--debug] [--foreground] [--config CONFIG]
	              [imgdir IMGDIR] [--warehouse WAREHOUSE] [--timeout TIMEOUT]
	              [--qmf] [--broker BROKER] [--image IMAGE]
                      [--template TEMPLATE] [--target TARGET]
                      [--provider PROVIDER] [--credentials CREDENTIALS]
	
	System image creation tool...
	
	optional arguments:
	  -h, --help            show this help message and exit
	  --version             Version info
	  -v, --verbose         Set verbose logging.
	  --debug               Set really verbose logging for debugging.
	  --foreground          Stay in the foreground and avoid launching a daemon.
	                        (default: False)
	  --config CONFIG       Configuration file to use. (default:
	                        /etc/imagefactory/imagefactory.conf)
	  --image IMAGE         The UUID of the image to build or push
	  --imgdir IMGDIR       Build image files in location specified. (default:
	                        /tmp)
	  --warehouse WAREHOUSE
	                        URL of the warehouse location to store images.
	  --timeout TIMEOUT     Set the timeout period for image building in seconds.
	                        (default: 3600)
	
	QMF agent:
	  Provide a QMFv2 agent interface.
	
	  --qmf                 Turn on QMF agent interface. (default: False)
	  --qpidd QPIDD         URL of qpidd to connect to. (default: localhost)
	
	Image building:
	  Build specified system and exit.
	
	  --template TEMPLATE   Template XML file to build from.
	  --target TARGET       List of cloud services to target
	
	Image pushing:
	  Push an image and exit.
	
	  --provider PROVIDER   List of cloud service providers to which the image
	                        should be pushed
	  --credentials CREDENTIALS
	                        Cloud provider credentials XML
	
## Dependencies: ##

[QMFv2](https://cwiki.apache.org/qpid/qmfv2-project-page.html) Python bindings - [Download](http://qpid.apache.org/download.cgi)       
These binding are part of the qpid-cpp package    

[Oz](http://aeolusproject.org/oz.html) - [Download](http://aeolusproject.org/oz-download.html)      
Oz is a set of classes and scripts to do automated installations of various guest operating systems.    

[Image Warehouse](http://www.aeolusproject.org/imagewarehouse.html) - [Download](http://people.redhat.com/meyering/iwhd/)     
Provides storage for images and related metadata.       

*Note:* You can install these packages via yum using the Aeolus repository.  See
the [GET AEOLUS][aeolus_getit_page] page for more details on adding this repository
to your yum setup.


[aeolus_getit_page]: http://www.aeolusproject.org/get_it.html
