---
layout: page
title: user manual (imagefactory)
---

% IMAGEFACTORY(1) Version 2.0 - November 16, 2012 | User Manual

**NAME**  

> imagefactory - create virtual machine images for use on a variety of clouds

**SYNOPSIS**  

    imagefactory [-h] [-v] [--verbose] [--debug] [--config CONFIG]
                 [--imgdir IMGDIR] [--timeout TIMEOUT] [--tmpdir TMPDIR]
                 [--plugins PLUGINS] [--ec2-32bit-util EC2_32BIT_UTIL]
                 [--ec2-64bit-util EC2_64BIT_UTIL]
                 
                 {base_image,target_image,provider_image,images,delete,plugins}
                 ...

**DESCRIPTION**

> **imagefactory** is the command line interface to the Image Factory framework,
allowing one to create, push, inspect, and delete images without the REST service.

> Image Factory builds virtual machine images using an image template document
(also known as a component outline), which is an abstract description of the
system to be built. See the [TDL schema documentation][tdl-schema] for a full description
of what can be specified in a template. Built images can then be pushed to cloud
providers such as Amazon EC2 or VMware vSphere where they can be launched as
instances.

> Command line options are described further down in this document. For more
configuration options, see the [Image Factory configuration][conf-doc]
documentation.


**OPTIONS**

    -h, --help            show this help message and exit
    -v, --version         show program's version number and exit
    --verbose             Set verbose logging.
    --config CONFIG       Configuration file to use. (default:
                            /etc/imagefactory/imagefactory.conf)
    --imgdir IMGDIR       Build image files in location specified. (default:
                            /tmp)
    --timeout TIMEOUT     Set the timeout period for image building in seconds.
                            (default: 3600)
    --tmpdir TMPDIR       Use the specified location for temporary files.
                            (default: /tmp)
    --plugins PLUGINS     Plugin directory. (default:
                            /etc/imagefactory/plugins.d)
    --nodebug             Turn off the default verbose CLI logging
    --output {log,json}   Choose between log or json output. (default: log)
    --raw                 Turn off pretty printing.
    
    EC2 settings:
        --ec2-32bit-util EC2_32BIT_UTIL
                            Instance type to use when launching a 32 bit utility
                            instance
        --ec2-64bit-util EC2_64BIT_UTIL
                            Instance type to use when launching a 64 bit utility
                            instance
    
    commands:
        {base_image,target_image,provider_image,images,delete,plugins}
        base_image          Build a generic image.
        target_image        Customize an image for a given cloud.
        provider_image      Push an image to a cloud provider.
        images              List images of a given type or get details of an
                            image.
        delete              Delete an image.
        plugins             List active plugins or get details of a specific
                            plugin.
**COMMANDS**

__*base_image*__

    usage: imagefactory base_image [-h] [--paramaters PARAMATERS] template
    
    positional arguments:
      template              A file containing the image template or component
                            outline, compatible with the TDL schema
                            (http://imgfac.org/documentation/tdl).
    
    optional arguments:
      -h, --help            show this help message and exit
      --paramaters PARAMATERS

__*target_image*__

    usage: imagefactory target_image [-h] (--id ID | --template TEMPLATE)
                                     [--parameters PARAMETERS]
                                     target
    
    positional arguments:
      target                The name of the target cloud for which to customize
                            the image.
    
    optional arguments:
      -h, --help            show this help message and exit
      --id ID               The uuid of the BaseImage to customize.
      --template TEMPLATE   A file containing the image template or component
                            outline, compatible with the TDL schema
                            (http://imgfac.org/documentation/tdl).
      --parameters PARAMETERS

__*provider_image*__  
For the *provider* and *credentials* parameters, see the [provider and credential examples][provider_examples] for more information.

    usage: imagefactory provider_image [-h] (--id ID | --template TEMPLATE)
                                       [--parameters PARAMETERS]
                                       target provider credentials
    
    positional arguments:
      target                The target type of the given cloud provider
      provider              A file containing the cloud provider description
                            or a string literal starting with '@' such as
                            '@ec2-us-east-1'.
      credentials           A file containing the cloud provider credentials
    
    optional arguments:
      -h, --help            show this help message and exit
      --id ID               The uuid of the TargetImage to push.
      --template TEMPLATE   A file containing the image template or component
                            outline, compatible with the TDL schema
                            (http://imgfac.org/documentation/tdl).
      --parameters PARAMETERS

__*images*__

    usage: imagefactory images [-h] fetch_spec
    
    positional arguments:
      fetch_spec  JSON formatted string of key/value pairs
    
    optional arguments:
      -h, --help  show this help message and exit

__*delete*__  
For the *provider* and *credentials* parameters, see the [provider and credential examples][provider_examples] for more information.

    usage: imagefactory delete [-h] [--provider PROVIDER]
                               [--credentials CREDENTIALS] [--target TARGET]
                               [--parameters PARAMETERS]
                               id
    
    positional arguments:
      id                    UUID of the image to delete
    
    optional arguments:
      -h, --help            show this help message and exit
      --provider PROVIDER   A file containing the cloud provider description or
                            a string literal starting with '@' such as
                            '@ec2-us-east-1'.
      --credentials CREDENTIALS
                            A file containing the provider credentials
      --target TARGET       The name of the target cloud for which to customize
                            the image.
      --parameters PARAMETERS

__*plugins*__

    usage: imagefactory plugins [-h] [--id ID]
    
    optional arguments:
      -h, --help  show this help message and exit
      --id ID

**EXAMPLES**

> Create a base image and customize it for a given target:

    imagefactory target_image EC2Cloud --template ~/fedora16_64.tdl

> Push an image to a cloud provider:

    imagefactory provider_image ~/rhevm.json ~/credentials.xml --id "dd083ab5-65d9-4f3b-b118-5a5892ca6316"

> Get the details of an image:

    imagefactory images '{"identifier": "b91586df-761d-40a9-8423-5392f2a1143f"}'

> List images of a specific type:

    imagefactory images '{"type": "BaseImage"}'

> Delete an image:

    imagefactory delete "c09f3926-59ac-4e83-a7a8-d816b623f3e2"

> List the active plugins:

    imagefactory plugins

> View a specific plugin:

    imagefactory plugins --id RHEVM


[tdl-schema]: http://aeolusproject.github.com/imagefactory/tdl/ (TDL schema documentation)
[conf-doc]: https://github.com/aeolusproject/imagefactory/blob/master/Documentation/imagefactory_conf.md (Image Factory configuration)
[provider_examples]: http://imgfac.org/documentation/cred_provider_examples.html (Provider Definition and Credentials examples)
