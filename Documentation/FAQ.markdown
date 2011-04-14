# Frequently Asked Questions #

## Installation ##
1.  Q: How do I install image_factory?      
    A: The simplest approach is to install from rpm.  To read about creating the rpm and/or other installation options, please read the [INSTALL](https://github.com/aeolusproject/image_factory/blob/master/Documentation/INSTALL.markdown) document in the Documentation directory of source distribution.

## Configuration ##
1.  Q: Where does the configuration live?       
    A: `/etc/imagefactory.conf`

2.  Q: Where does imagefactory log by default?      
    A: `/var/log/imagefactory.log`

3.  Q: Where does Image Factory put the images that are created?        
    A: There are really three parts to this answer...
    
    1. Image Factory stores a local copy of the image in the path pointed to by the configuration option `imgdir`, which defaults to `/var/tmp`
    2. Oz caches .iso files in `/var/lib/oz`
    3. If an Image Warehouse is configured and the JEOS was created by Image Factory, the resulting image is uploaded to the Image Warehouse in the `images` bucket.

## Running and using Image Factory ##
1.  Q: How do I enable Image Factory?       
    A: Run `service imagefactory start`

2.  Q: How do I run Image Factory in debug mode?        
    A: Shut the service down with `service imagefactory stop`.  Then run `imgfac.py --qmf --debug` as root.

3.  Q: How do I interact with the Image Factory daemon?     
    A: Please read through the QMF guide in the Documentation directory for some examples.

4.  Q: How do I run the tests to know that what I have works?       
    A: The unit tests can be run from the top level of the source tree with the command `python -m unittest discover -v`

## Troubleshooting ##
1.  Q: After starting imagefactory, the log shows "Please enter your password" instead of "image_factory has qmf/qpid address...".      
    A: Put the following in /etc/qpidd.conf
        
        cluster-mechanism=ANONYMOUS
        auth=no

2.  Q: The imagefactory log shows an exception "AttributeError: 'NoneType' object has no attribute 'makefile'"      
    A: Please make certain the image warehouse is reachable and responds.

