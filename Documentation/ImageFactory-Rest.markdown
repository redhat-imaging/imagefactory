% IMAGEFACTORY REST API(1) Version 2.0 - April 27, 2012

Image Factory is the ideal system image creation engine for any application that needs to support a variety of virtualization and cloud services. Our REST API provides developers with a straightforward and easy way to develop solutions on top of Image Factory. This document describes the Image Factory REST API for building and pushing images as well as getting the status of builder operations.

## Starting imagefactory in REST mode

---

*   To use the REST API, imagefactory must be started with the `--rest` command line argument. 
    *   _DEFAULT_: imagefactory listens on port 8075.
    *   `--port` can be specified on the command line to change the port imagefactory listens on.
*   _DEFAULT_: imagefactory will use SSL and generate a self signed key. 
    *   `--no_ssl` can be specified on the command line to turn off SSL.
    *   `--ssl_pem` can be used on the command line to specify the path to a different certificate.
*   _DEFAULT_: imagefactory uses OAuth to authenticate connections.
    *   `--no_oauth` can be specified on the command line to turn off OAuth.
    *   More detail on how Image Factory uses OAuth can be found [below](#oauth)

**NOTE:** As an alternative to specifying arguments on the command line, options can be set in the imagefactory configuration file. Just leave the dashes off of the option name.

## Using the Image Factory REST API

---

To use the Image Factory REST API, send an HTTP request to any of the [resources][] Image Factory provides.  Each resource supports one or more of the stand HTTP methods (POST, GET, PUT, DELETE) which map to the operations Create, Read, Update, and Delete. More detail on what methods are supported and what parameters are required by each resource can be found in the [resources][] section.

Responses are formatted as JSON in all cases.  POST requests can also be formatted as JSON if the HTTP header, `Content-Type`, is set to `application/json`. Response contents are documented for each specific resource in the [resources][] section.


<a id="oauth"></a>
## OAuth Authentication

---

Image Factory uses two-legged OAuth to protect writable operations from unauthorized access. This means that even when OAuth is configured and enabled, Image Factory allows all read-only requests. This makes it simple to use any browser to get a quick status of current builder activity.

Any number of consumer_key / shared_secret pairs can be used. Just add these to the `clients` section of the `imagefactory.conf` file.

_Example:_  
    `"clients": {
        "client1": "our-secret",
        "client2": "just-between-us"
    }`

<a id="resources"></a>
## Resources

---

### API Information

* __*/imagefactory*__  
    **Methods:**
    
    * **GET**

    > **Description:** Returns the version string for the API
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
      
    > > __None__
    >
    > **Responses:**  
      
    > > __200__ - Image Factory version (version), API name (name), API version (api_version)  
    >
    > *Example:*  
    > `% curl http://imgfac-host:8075/imagefactory`
    > 
    > `{"version": "1.1", "name": "imagefactory", "api_version": "2.0"}`

### Listing Images

* __*/imagefactory/base_images*__
* __*/imagefactory/base_images/:base_image_id/target_images*__
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images*__
* __*/imagefactory/target_images*__
* __*/imagefactory/target_images/:target_image_id/provider_images*__
* __*/imagefactory/provider_images*__
    **Methods:**

    * **GET**
    
    >  **Description:** Lists the image collection
    >
    > **OAuth protected:** YES
    >
    > **Responses:**  
    
    > > __200__ - Image list 
    > > __500__ - Server error
    >
    > *Example:*  
    > 
        % curl http://imgfac-host:8075/imagefactory/base_images 
    >
    >  
        {"base_images": [{"status": "COMPLETE", "_type": "BaseImage", "icicle"  
        : null, "status_detail": null, "href": "http://imgfac-host:8075/imagef  
        actory/base_images/20942760-2c5c-4fd2-8d5a-40f5533a11ec", "percent_com  
        plete": 0, "id": "20942760-2c5c-4fd2-8d5a-40f5533a11ec"}, {"status":    
        "FAILED", "_type": "BaseImage", "icicle": null, "status_detail": null,  
        "href": "http://imgfac-host:8075/imagefactory/base_images/27860416-b6c  
        a-49a4-9668-09c69f419a4d", "percent_complete": 0, "id": "27860416-b6ca  
        -49a4-9668-09c69f419a4d"}]}

### Image Creation

#### Base Images

* __*/imagefactory/base_images*__  
    **Methods:**

    * **POST**
    
    >  **Description:** Builds a new BaseImage.
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __template__ - TDL document
    >
    > **Responses:**  
    
    > > __202__ - New image  
    > > __400__ - Missing parameters  
    > > __500__ - Server error
    >
    > *Example:*  
    >  
        curl -d "template=<template><name>mock</name><os><name>RHELMock</name>  
        <version>1</version><arch>x86_64</arch><install type='iso'><iso>http:/  
        /mockhost/RHELMock1-x86_64-DVD.iso</iso></install><rootpw>password</ro  
        otpw></os><description>Mock Template</description></template>" http://  
        imgfac-host:8075/imagefactory/base_images
    >
    >  
        {"status": "NEW", "_type": "BaseImage", "icicle": null, "status_detail  
        ": null, "href": "http://imgfac-host:8075/imagefactory/base_images/209  
        42760-2c5c-4fd2-8d5a-40f5533a11ec", "percent_complete": 0, "id": "2094  
        2760-2c5c-4fd2-8d5a-40f5533a11ec"}

#### Target Images

* __*/imagefactory/target_images*__  
* __*/imagefactory/base_images/:base_image_id/target_images*__  
    **Methods:**

    * **POST**
    
    >  **Description:** Builds a new TargetImage.
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __base_image_id__ - uuid of the base_image to build from. If not provided, a BaseImage will be built.  
    > > __template__ - TDL document  
    > > __target__ - cloud target name  
    > > __parameters__ - Optional parameters that may change the nature of the image being built.  This may include things such as on-disk format or the build mechanism itself.  Parameters are never required as sensible defaults will always be used and will be made part of the queryable properties of an image.
    >
    > **Responses:**  
    
    > > __202__ - New image  
    > > __400__ - Missing parameters  
    > > __404__ - BaseImage not found  
    > > __500__ - Error building image
    >
    > *Example:*  
    >  
        curl -d "template=<template><name>mock</name><os><name>RHELMock</name>  
        <version>1</version><arch>x86_64</arch><install type='iso'><iso>http:/  
        /mockhost/RHELMock1-x86_64-DVD.iso</iso></install><rootpw>password</ro  
        otpw></os><description>Mock Template</description></template>;target=M  
        ockSphere" http://imgfac-host:8075/imagefactory/target_images
    >
    >  
        {"status": "NEW", "_type": "TargetImage", "icicle": null, "status_deta  
        il": null, "href": "http://imgfac-host:8075/imagefactory/target_images  
        /4cc3b024-5fe7-4b0b-934b-c5d463b990b0", "percent_complete": 0, "id": "  
        4cc3b024-5fe7-4b0b-934b-c5d463b990b0"}

#### Provider Images

* __*/imagefactory/provider_images*__  
* __*/imagefactory/target_images/:target_image_id/provider_images*__  
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images*__  
    **Methods:**

    * **POST**
    
    >  **Description:** Builds a new ProviderImage
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __target_image_id__ - uuid of the target image to push. If not provided and not an image snapshot, a TargetImage will be created.  
    > > __template__ - TDL document  
    > > __target__ - The target to which the provider belongs. This would be the same target used for building a TargetImage.  
    > > __provider__ - cloud provider name  
    > > __credentials__ - cloud provider credentials xml  
    > > __parameters__ - Optional parameters that may change the nature of the image being built.  This may include things such as on-disk format or the build mechanism itself.  Parameters are never required as sensible defaults will always be used and will be made part of the queryable properties of an image.
    >
    > **Responses:**  
    
    > > __202__ - New image  
    > > __400__ - Missing parameters  
    > > __404__ - BaseImage or TargetImage not found  
    > > __500__ - Error building image
    >

### Image Inspection

* __*/imagefactory/base_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/target_images/:image_id*__
* __*/imagefactory/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/provider_images/:image_id*__
    
    > __image_id__ - uuid of the image to inspect  

    **Methods:**
    
    * **GET**
    
    >  **Description:** Get image details
    >
    > **OAuth protected:** YES
    >
    > **Responses:**  
    
    > > __200__ - Image  
    > > __404__ - Image Not Found  
    > > __500__ - Server error
    >
    > *Example:*  
    >  
        curl http://imgfac-host:8075/imagefactory/base_images/20942760-2c5c-4f  
        d2-8d5a-40f5533a11ec
    >
    >  
        {"status": "COMPLETE", "_type": "BaseImage", "icicle": null, "status_d  
        etail": null, "href": "http://imgfac-host:8075/imagefactory/base_image  
        s/20942760-2c5c-4fd2-8d5a-40f5533a11ec/20942760-2c5c-4fd2-8d5a-40f5533  
        a11ec", "percent_complete": 0, "id": "20942760-2c5c-4fd2-8d5a-40f5533a  
        11ec"}

### Image Deletion

* __*/imagefactory/base_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/target_images/:image_id*__
* __*/imagefactory/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/provider_images/:image_id*__
    
    > __image_id__ - uuid of the image to delete  

    **Methods:**
    
    * **DELETE**
    
    >  **Description:** Delete the image specified with *image_id*
    >
    > **OAuth protected:** YES
    >
    > **Responses:**  
    
    > > __200__  
    > > __404__ - Image Not Found  
    > > __500__ - Server error
    >
    > *Example:*  
    >  
        curl -X DELETE http://imgfac-host:8075/imagefactory/base_images/209427  
        60-2c5c-4fd2-8d5a-40f5533a11ec
    >
    >  

### Plugins

* __*/imagefactory/plugins*__
    **Methods:**

    * **GET**
    
    >  **Description:** Lists the loaded plugins
    >
    > **OAuth protected:** YES
    >
    > **Responses:**  
    
    > > __200__ - Plugin list 
    > > __500__ - Server error
    >
    > *Example:*  
    > 
        % curl http://imgfac-host:8075/imagefactory/plugins 
    >
    >  
        {"plugins": [{"_type": "plugin", "maintainer": {"url": "http://www.aeo  
        lusproject.org/imagefactory.html", "name": "Red Hat, Inc.", "email": "  
        aeolus-devel@lists.fedorahosted.org"}, "description": "Mock cloud plug  
        in for testing imagefactory plugin code", "license": "Copyright 2012 R  
        ed Hat, Inc. - http://www.apache.org/licenses/LICENSE-2.0", "href": "h  
        ttp://imgfac-host:8075/imagefactory/plugins/MockSphere", "id": "MockSp  
        here", "version": "1.0", "type": "cloud", "targets": ["MockSphere"]},   
        {"_type": "plugin", "maintainer": {"url": "http://www.aeolusproject.or  
        g/imagefactory.html", "name": "Red Hat, Inc.", "email": "aeolus-devel@  
        lists.fedorahosted.org"}, "description": "Mock OS plugin for testing i  
        magefactory plugin code", "license": "Copyright 2012 Red Hat, Inc. - h  
        ttp://www.apache.org/licenses/LICENSE-2.0", "href": "http://imgfac-hos  
        t:8075/imagefactory/plugins/MockRPMBasedOS", "id": "MockRPMBasedOS", "  
        version": "1.0", "type": "os", "targets": [["FedoraMock", null, null],  
        ["RHELMock", "1", "x86_64"]]}]}

* __*/imagefactory/plugins/:plugin_id*__
    **Methods:**

    * **GET**
    
    >  **Description:** Get the details for plugin with a given id.
    >
    > **OAuth protected:** YES
    >
    > **Responses:**  
    
    > > __200__ - Plugin 
    > > __500__ - Server error
    >
    > *Example:*  
    > 
        % curl http://imgfac-host:8075/imagefactory/plugins/MockSphere 
    >
    >  
        {"_type": "plugin", "maintainer": {"url": "http://www.aeolusproject.or  
        g/imagefactory.html", "name": "Red Hat, Inc.", "email": "aeolus-devel@  
        lists.fedorahosted.org"}, "description": "Mock cloud plugin for testin  
        g imagefactory plugin code", "license": "Copyright 2012 Red Hat, Inc.   
        - http://www.apache.org/licenses/LICENSE-2.0", "targets": ["MockSphere  
        "], "href": "http://imgfac-host:8075/imagefactory/plugins/MockSphere/M  
        ockSphere", "version": "1.0", "type": "cloud", "id": "MockSphere"}

### Cloud Targets and Providers

* __*/imagefactory/targets*__
* __*/imagefactory/targets/:target_id*__
* __*/imagefactory/targets/:target_id/providers*__
* __*/imagefactory/targets/:target_id/providers/:provider_id*__

    **NOT IMPLEMENTED**

<!-- links -->
[resources]: #resources (Resources)
