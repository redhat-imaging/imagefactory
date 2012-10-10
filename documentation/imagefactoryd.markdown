---
layout: page
title: user manual (daemon)
---

% IMAGEFACTORYD(1) Version 2.0 - July 27, 2012 | User Manual

**NAME**  

> imagefactoryd - create virtual machine images for use on a variety of clouds

**SYNOPSIS**  

    imagefactoryd [-h] [-v] [--verbose] [--debug] [--config CONFIG]
                  [--imgdir IMGDIR] [--timeout TIMEOUT] [--tmpdir TMPDIR]
                  [--plugins PLUGINS] [--ec2-32bit-util EC2_32BIT_UTIL]
                  [--ec2-64bit-util EC2_64BIT_UTIL] [--foreground]
                  [--port PORT] [--address ADDRESS] [--no_ssl]
                  [--ssl_pem SSL_PEM] [--no_oauth]

**DESCRIPTION**

> **imagefactoryd** is the command for starting the Image Factory REST API.

> Image Factory builds virtual machine images using a template document,
which is an abstract description of the system to be built. See the 
[TDL schema documentation][tdl-schema] for a full description of what can be
specified in a template. Built images can then be pushed to cloud providers
such as Amazon EC2 or VMware vSphere where they can be launched as instances.

> imagefactoryd provides a RESTful API to the Image Factory framework for
for building and pushing images. See the [Image Factory REST API][rest-doc]
documentation for more details.

> Command line options are described further down in this document. For more
configuration options, see the [Image Factory configuration][conf-doc]
documentation.

> **Starting and Stopping imagefactoryd**

> Image Factory can be started, stopped, and restarted like most other services.

> >     % service imagefactoryd start
> >     % service imagefactoryd stop

**OPTIONS**

    -h, --help            show this help message and exit
    -v, --version         show version number and exit
    --verbose             Set verbose logging.
    --debug               Set really verbose logging for debugging.
    --config CONFIG       Configuration file to use. (default:
                          /etc/imagefactory/imagefactory.conf)
    --imgdir IMGDIR       Build image files in location specified. (default:
                            /tmp)
    --timeout TIMEOUT     Set the timeout period for image building in seconds.
                            (default: 3600)
    --tmpdir TMPDIR       Use the specified location for temporary files.
                            (default: /tmp)
    --plugins PLUGINS     Plugin directory. (default: /etc/imagefactory/plugins.d)
    --foreground          Stay in the foreground and avoid launching a daemon.
                            (default: False)
    
    EC2 settings:
        --ec2-32bit-util EC2_32BIT_UTIL
                            Instance type to use when launching a 32 bit utility
                            instance
        --ec2-64bit-util EC2_64BIT_UTIL
                            Instance type to use when launching a 64 bit utility
                            instance
    
    REST service options:
        --port PORT           Port to attach the RESTful http interface to. (defaul:
                                8075)
        --address ADDRESS     Interface address to listen to. (defaul: 0.0.0.0)
        --no_ssl              Turn off SSL. (default: False)
        --ssl_pem SSL_PEM     PEM certificate file to use for HTTPS access to the
                                REST interface. (default: A transient certificate is
                                generated at runtime.)
        --no_oauth            Use 2 legged OAuth to protect the REST interface.
                                (default: False)

[tdl-schema]: http://aeolusproject.github.com/imagefactory/tdl/ (TDL schema documentation)
[conf-doc]: https://github.com/aeolusproject/imagefactory/blob/master/Documentation/imagefactory_conf.md (Image Factory configuration)
[rest-doc]: https://github.com/aeolusproject/imagefactory/blob/master/Documentation/ImageFactory-REST.md (Image Factory REST API)
