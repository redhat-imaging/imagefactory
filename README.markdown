## Usage: ##

	usage: imgfac [-h] [--version] [-v] [--debug] [--foreground] [--config CONFIG]
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
	                        /etc/imagefactory.conf)
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

[QMFv2](https://cwiki.apache.org/qpid/qmfv2-project-page.html) Python bindings       
These binding are part of the qpid-cpp package    
*Note:* You can install qpid-cpp with yum using the Aeolus testing [repository][aeolus_testing_repo].

[Oz](http://aeolusproject.org/oz.html) - [Download](http://aeolusproject.org/oz-download.html)      
Oz is a set of classes and scripts to do automated installations of various guest operating systems.    
*Note:* You can install oz with yum using the Aeolus testing [repository][aeolus_testing_repo].

[Image Warehouse](http://git.fedorahosted.org/git/?p=iwhd.git)     
Provides storage for images and related metadata.       
*Note:* You can install iwhd with yum using the Aeolus [repository][aeolus_package_repo]


[aeolus_testing_repo]: http://repos.fedorapeople.org/repos/aeolus/packages-testing/
[aeolus_package_repo]: http://repos.fedorapeople.org/repos/aeolus/packages/
