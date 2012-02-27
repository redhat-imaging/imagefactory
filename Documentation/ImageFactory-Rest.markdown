% IMAGEFACTORY REST API(1) Version 1.0 - February 10, 2012

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
      
    > > __200__ - Name and version of the API  
    >
    > *Example:*  
    > `% curl http://imgfac-host:8075/imagefactory`
    > 
    > `{"version": "1.0", "name": "imagefactory"}`

* __*/imagefactory/images*__  
    **Methods:**

    * **POST**
    
    >  **Description:** Builds a new target image.
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __targets__ - comma separated string  
    > > __template__ - string representation of XML document, UUID, or URL
    >
    > **Responses:**  
    
    > > __202__ - New image  
    > > __400__ - Missing parameters  
    > > __500__ - Error building image
    >
    > *Example:*  
    >  
        % curl -d "targets=mock&template=<template><name>f14jeos</name><os>   
        <name>Fedora</name> <version>14</version> <arch>x86_64</arch> <install  
        type='url'> <url>http://download.fedoraproject.org/pub/fedora/linux/re  
        leases/14/Fedora/x86_64/os/</url></install><rootpw>p@55w0rd!</rootpw>  
        </os><description>Fedora 14</description></template>"  
        http://imgfac-host:8075/imagefactory/images
    >
    >  
        {"_type": "image", "href": "http://imgfac-host:8075/imagefactory/images  
        /0e5b4e6b-c658-4a16-bc71-88293cb1cadf", "id": "0e5b4e6b-c658-4a16-bc71-  
        88293cb1cadf", "build": {"target_images": [{"_type": "target_image", "h  
        ref": "http://imgfac-host:8075/imagefactory/images/0e5b4e6b-c658-4a16-b  
        c71-88293cb1cadf/builds/29085ce6-3e31-4dc4-b8fc-74622f2b5ad7/target_ima  
        ges/569121e2-5c5e-4457-b88c-13a925eee01d", "id": "569121e2-5c5e-4457-b8  
        8c-13a925eee01d"}], "_type": "build", "href": "http://imgfac-host:8075/  
        imagefactory/images/0e5b4e6b-c658-4a16-bc71-88293cb1cadf/builds/29085ce  
        6-3e31-4dc4-b8fc-74622f2b5ad7", "id": "29085ce6-3e31-4dc4-b8fc-74622f2b  
        5ad7"}}

* __*/imagefactory/images/:image_id*__
    
    > __image_id__ - uuid of the image to be rebuilt  

    **Methods:**
    
    * **PUT**
    
    >  **Description:** Rebuild an existing target image
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __targets__ - comma separated string  
    > > __template__ - string representation of XML document, UUID, or URL
    >
    > **Responses:**  
    
    > > __202__ - New image  
    > > __400__ - Missing parameters  
    > > __500__ - Error building image
    >
    > *Example:*  
    >  
        % curl -d "targets=mock&template=<template><name>f14jeos</name><os>  
        <name>Fedora</name><version>14</version><arch>x86_64</arch><install typ  
        e='url'><url>http://download.fedoraproject.org/pub/fedora/linux/release  
        s/14/Fedora/x86_64/os/</url></install><rootpw>p@55w0rd!</rootpw></os>  
        <description>Fedora 14</description></template>" -X PUT  
        http://imgfac-host:8075/imagefactory/images/0e5b4e6b-c658-x4a16-bc71-88293cb1cadf
    >
    >  
        {"_type": "image", "href": "http://imgfac-host:8075/imagefactory/images  
        /0e5b4e6b-c658-4a16-bc71-88293cb1cadf", "id": "0e5b4e6b-c658-4a16-bc71-  
        88293cb1cadf", "build": {"target_images": [{"_type": "target_image", "h  
        ref": "http://imgfac-host:8075/imagefactory/images/0e5b4e6b-c658-4a16-b  
        c71-88293cb1cadf/builds/c68f4d55-0785-4460-9092-07fc7c126935/target_ima  
        ges/f721adc4-ea4c-4d20-adf9-1a02153a9cc6", "id": "f721adc4-ea4c-4d20-ad  
        f9-1a02153a9cc6"}], "_type": "build", "href": "http://imgfac-host:8075/  
        imagefactory/images/0e5b4e6b-c658-4a16-bc71-88293cb1cadf/builds/c68f4d5  
        5-0785-4460-9092-07fc7c126935", "id": "c68f4d55-0785-4460-9092-07fc7c12  
        6935"}}

* __*/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images*__
    
    > __image_id__ - uuid of the image  
    > __build_id__ - uuid of the image build  
    > __target_image_id__ - uuid of the target image to push
    
    **Methods:**

    * **POST**  
    
    > **Description:** Creates a provider image using the specified target image and pushes it up to a cloud provider using the given credentials.
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __provider__ - provider name as a string  
    > > __credentials__ - XML string representation of credentials for the given provider
    >
    > **Responses:**  
    
    > > __202__ - New provider image  
    > > __400__ - Missing parameters  
    > > __500__ - Error pushing image
    >
    > *Example:*
    > `To be filled in...`

* __*/imagefactory/provider_images*__

    **Methods:**
    
    * **POST**  
    
    > **Description:** Creates a provider image using the specified target image and pushes it up to a cloud provider using the given credentials. This is an alternate URI for the resource above.
    >
    > **OAuth protected:** YES
    >
    > **Parameters:**  
    
    > > __image_id__ - uuid of the image  
    > > __build_id__ - uuid of the image build  
    > > __target_image_id__ - uuid of the target image to push  
    > > __provider__ - provider name as a string  
    > > __credentials__ - XML string representation of credentials for the given provider
    >
    > **Responses:**  
    
    > > __202__ - New provider image  
    > > __400__ - Missing parameters  
    > > __500__ - Error pushing image
    >
    > *Example:*
    > `To be filled in...`

* __*/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id*__
    
    > __image_id__ - uuid of the image  
    > __build_id__ - uuid of the image build  
    > __target_image_id__ - uuid of the target image being built

    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays the details of the Image Factory builder object responsible for building the target image.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder details  
    > > __400__ - Missing parameters  
    > > __500__ - Error getting builder details
    >
    > *Example:*  
    >  
        % curl http://imgfac-host:8075/imagefactory/images/0e5b4e6b-c658-4a16-b  
        c71-88293cb1cadf/builds/c68f4d55-0785-4460-9092-07fc7c126935/target_ima  
        ges/f721adc4-ea4c-4d20-adf9-1a02153a9cc6
    >
    >  
        {"status": "COMPLETED", "_type": "target_image_status", "completed": 10  
        0, "provider_account_identifier": null, "image_id": "0e5b4e6b-c658-4a16  
        -bc71-88293cb1cadf", "href": "http://imgfac-host:8075/imagefactory/imag  
        es/0e5b4e6b-c658-4a16-bc71-88293cb1cadf/builds/c68f4d55-0785-4460-9092-  
        07fc7c126935/target_images/f721adc4-ea4c-4d20-adf9-1a02153a9cc6", "oper  
        ation": "build", "id": "f721adc4-ea4c-4d20-adf9-1a02153a9cc6", "build_i  
        d": "c68f4d55-0785-4460-9092-07fc7c126935", "target": "mock", "provider  
        ": null, "target_image_id": null}

* __*/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/status*__
    
    > __image_id__ - uuid of the image  
    > __build_id__ - uuid of the image build  
    > __target_image_id__ - uuid of the target image being built

    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays just the status of the Image Factory builder object responsible for building the target image.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder status  
    > > __400__ - Missing parameters  
    > > __500__ - Error getting builder details
    >
    > *Example:*  
    >  
        % curl http://imgfac-host:8075/imagefactory/images/0e5b4e6b-c658-4a16-b  
        c71-88293cb1cadf/builds/c68f4d55-0785-4460-9092-07fc7c126935/target_ima  
        ges/f721adc4-ea4c-4d20-adf9-1a02153a9cc6/status
    >
    >  
        {"status": "COMPLETED", "_type": "target_image_status", "href": "http:/  
        /imgfac-host:8075/imagefactory/images/0e5b4e6b-c658-4a16-bc71-88293cb1c  
        adf/builds/c68f4d55-0785-4460-9092-07fc7c126935/target_images/f721adc4-  
        ea4c-4d20-adf9-1a02153a9cc6/status", "id": "f721adc4-ea4c-4d20-adf9-1a0  
        2153a9cc6"}

* __*/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id*__
    
    > __image_id__ - uuid of the image  
    > __build_id__ - uuid of the image build  
    > __target_image_id__ - uuid of the target image  
    > __provider_image_id__ - uuid of the provider image being pushed

    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays the details of the Image Factory builder object responsible for pushing the provider image.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder details  
    > > __400__ - Missing parameters  
    > > __500__ - Error getting builder details
    >
    > *Example:*  
    > `To be filled in...`

* __*/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id/status*__
    
    > __image_id__ - uuid of the image  
    > __build_id__ - uuid of the image build  
    > __target_image_id__ - uuid of the target image  
    > __provider_image_id__ - uuid of the provider image being pushed

    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays just the status of the Image Factory builder object responsible for pushing the provider image.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder status  
    > > __400__ - Missing parameters  
    > > __500__ - Error getting builder details
    >
    > *Example:*  
    > `To be filled in...`

* __*/imagefactory/builders*__
    
    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays a list of all current Image Factory builder objects.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder list  
    > > __500__ - Error getting builder list
    >
    > *Example:*  
    >  
        % curl http://imgfac-host:8075/imagefactory/builders
    >
    >  
        {"_type": "builders", "href": "http://imgfac-host:8075/imagefactory/bui  
        lders", "builders": [{"status": "COMPLETED", "_type": "builder", "compl  
        eted": 100, "provider_account_identifier": null, "image_id": "6b558510-  
        15db-4beb-b385-843241ea0639", "href": "http://imgfac-host:8075/imagefac  
        tory/builders/acd2e7fd-2dda-4aa1-aee1-23e207782f39", "operation": "buil  
        d", "id": "acd2e7fd-2dda-4aa1-aee1-23e207782f39", "build_id": "6297c0f7  
        -d6f1-41fc-a87d-4afbc582b57a", "target": "mock", "provider": null, "tar  
        get_image_id": null}, {"status": "COMPLETED", "_type": "builder", "comp  
        leted": 100, "provider_account_identifier": null, "image_id": "0e5b4e6b  
        -c658-4a16-bc71-88293cb1cadf", "href": "http://imgfac-host:8075/imagefa  
        ctory/builders/f721adc4-ea4c-4d20-adf9-1a02153a9cc6", "operation": "bui  
        ld", "id": "f721adc4-ea4c-4d20-adf9-1a02153a9cc6", "build_id": "c68f4d5  
        5-0785-4460-9092-07fc7c126935", "target": "mock", "provider": null, "ta  
        rget_image_id": null}, {"status": "COMPLETED", "_type": "builder", "com  
        pleted": 100, "provider_account_identifier": null, "image_id": "0e5b4e6  
        b-c658-4a16-bc71-88293cb1cadf", "href": "http://imgfac-host:8075/imagef  
        actory/builders/569121e2-5c5e-4457-b88c-13a925eee01d", "operation": "bu  
        ild", "id": "569121e2-5c5e-4457-b88c-13a925eee01d", "build_id": "29085c  
        e6-3e31-4dc4-b8fc-74622f2b5ad7", "target": "mock", "provider": null, "t  
        arget_image_id": null}]}

* __*/imagefactory/builders/:builder_id*__
    
    > __builder_id__ - uuid of the builder
    
    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays the details for a specific builder object.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder detail  
    > > __404__ - Builder not found  
    > > __500__ - Error getting builder details
    >
    > *Example:*  
    >  
        % curl http://imgfac-host:8075/imagefactory/builders/acd2e7fd-2dda-4aa1  
        -aee1-23e207782f39
    >
    >  
        {"status": "COMPLETED", "_type": "builder", "completed": 100, "provider  
        _account_identifier": null, "image_id": "6b558510-15db-4beb-b385-843241  
        ea0639", "href": "http://imgfac-host:8075/imagefactory/builders/acd2e7f  
        d-2dda-4aa1-aee1-23e207782f39", "operation": "build", "id": "acd2e7fd-2  
        dda-4aa1-aee1-23e207782f39", "build_id": "6297c0f7-d6f1-41fc-a87d-4afbc  
        582b57a", "target": "mock", "provider": null, "target_image_id": null}

* __*/imagefactory/builders/:builder_id/status*__
    
    > __builder_id__ - uuid of the builder
    
    **Methods:**
    
    * **GET**  
    
    > **Description:** Displays just the status for a specific builder object.
    >
    > **OAuth protected:** NO
    >
    > **Parameters:**  
    
    > > __None__
    >
    > **Responses:**  
    
    > > __200__ - Builder status  
    > > __404__ - Builder not found  
    > > __500__ - Error getting builder details
    >
    > *Example:*  
    >  
        % curl http://imgfac-host:8075/imagefactory/builders/acd2e7fd-2dda-4aa1  
        -aee1-23e207782f39/status
    >
    >  
        {"status": "COMPLETED", "_type": "builder_status", "href": "http://imgf  
        ac-host:8075/imagefactory/builders/acd2e7fd-2dda-4aa1-aee1-23e207782f39  
        /status", "id": "acd2e7fd-2dda-4aa1-aee1-23e207782f39"}


<!-- links -->
[resources]: #resources (Resources)
