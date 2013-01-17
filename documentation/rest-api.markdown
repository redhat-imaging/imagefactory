---
layout: page
title: user manual (REST API)
---

% IMAGEFACTORY REST API(1) Version 2.0 - November 16, 2012

Image Factory is the ideal system image creation engine for any application that needs to support a variety of virtualization and cloud services. Our REST API provides developers with a straightforward and easy way to develop solutions on top of Image Factory. This document describes the Image Factory REST API for building and pushing images as well as getting the status of builder operations.

## Starting imagefactory in REST mode

---

*   Running `imagefactoryd` enables the REST api, allowing remote clients to build, inspect, customize, upload, and delete images.
    *   _DEFAULT_: imagefactory listens on port 8075.
    *   `--port` can be specified to the `imagefactoryd` command to change the port imagefactory listens on.
*   _DEFAULT_: imagefactory will use SSL and generate a self signed key. 
    *   `--no_ssl` can be specified on the command line to turn off SSL.
    *   `--ssl_pem` can be used on the command line to specify the path to a different certificate.
*   _DEFAULT_: imagefactory uses OAuth to authenticate connections.
    *   `--no_oauth` can be specified on the command line to turn off OAuth.
    *   More detail on how Image Factory uses OAuth can be found [below](#oauth)

**NOTE:** As an alternative to specifying arguments on the command line, options can be set in the imagefactory configuration file. Just leave the dashes off of the option name.

## Using the Image Factory REST API

---

To use the Image Factory REST API, send an HTTP request to any of the [resources][] Image Factory provides.  Each resource supports one or more of the standard HTTP methods (POST, GET, PUT, DELETE) which map to the operations Create, Read, Update, and Delete. More detail on what methods are supported and what parameters are required by each resource can be found in the [resources][] section.

### Request - Response formatting

* PUT/POST requests  
    * _DEFAULT_: form data is assumed to be formatted as `application/x-www-form-urlencoded`.  
    * form data can be formatted as JSON if the HTTP header, `Content-Type`, is set to `application/json`.  
    * form data can be formatted as XML if the HTTP header, `Content-Type`, is set to `application/xml` or `text/xml`.  
* Responses are formatted as JSON by default. XML responses will be returned if specified in the `Accept` http header.  

Response contents are documented for each specific resource in the [resources][] section.


<a id="oauth"></a>
## OAuth Authentication

---

Image Factory uses two-legged OAuth to protect writable operations from unauthorized access. This means that even when OAuth is configured and enabled, Image Factory allows all read-only requests. This makes it simple to use any browser to get a quick status of current builder activity.

Any number of consumer_key / shared_secret pairs can be used. Just add these to the `clients` section of the `imagefactory.conf` file.

_Example:_  
<pre>
    ...
    "clients": {
        "client1": "our-secret",
        "client2": "just-between-us"
    }
    ...
</pre>

<a id="resources"></a>
## Resources

_Note:_ The examples below use [HTTPie](http://httpie.org/ "HTTPie: a CLI, cURL-like tool for humans"), an alternative to curl.

---

### API Information

* __*/imagefactory*__  
    **Methods:**  
    **GET**
    
    **Description:**  
    Returns the version string for the API
    
    **OAuth protected:**  
    NO
    
     **Parameters:**  
    __None__
    
    **Responses:**  
    __200__ - Image Factory version (version), API name (name), API version (api_version)  
    __500__ - Server error
    
    **Example:**  
        
        >>> http http://f17.vm.private:8075/imagefactory                       
        HTTP/1.0 200 OK
        Content-Length: 79
        Content-Type: application/json
        Date: Fri, 16 Nov 2012 19:34:19 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "api_version": "2.0", 
            "name": "imagefactory", 
            "version": "1.1.2-328-g9f87e24"
        }

### Listing Images

* __*/imagefactory/base_images*__
* __*/imagefactory/base_images/:base_image_id/target_images*__
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images*__
* __*/imagefactory/target_images*__
* __*/imagefactory/target_images/:target_image_id/provider_images*__
* __*/imagefactory/provider_images*__  
    
    **Methods:**  
    **GET**
    
    **Description:**  
    Lists the image collection
    
    **OAuth protected:**  
    YES
    
    **Responses:**  
    __200__ - Image list  
    __500__ - Server error  
    
    **Example:**  
        
        >>> http http://f17.vm.private:8075/imagefactory/target_images  
        HTTP/1.0 200 OK
        Content-Length: 381
        Content-Type: application/json
        Date: Fri, 16 Nov 2012 16:28:41 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "target_images": [
                {
                    "target_image": {
                        "_type": "TargetImage", 
                        "href": "http://f17.vm.private:8075/imagefactory/target_images/208a3c18-8609-4441-9230-4a278660240e", 
                        "id": "208a3c18-8609-4441-9230-4a278660240e"
                    }
                }, 
                {
                    "target_image": {
                        "_type": "TargetImage", 
                        "href": "http://f17.vm.private:8075/imagefactory/target_images/95ce7283-b3ad-4e15-acc0-e1adcb063cc1", 
                        "id": "95ce7283-b3ad-4e15-acc0-e1adcb063cc1"
                    }
                }
            ]
        }

### Image Creation

#### Base Images

* __*/imagefactory/base_images*__  
    
    **Methods:**  
    **POST**  
    
    **Description:**  
    Builds a new BaseImage.  
    
    **OAuth protected:**  
    YES
    
    **Parameters:**  
    __template__ - An image template or component outline compatible with the TDL schema (http://imgfac.org/documentation/tdl).  
    
    **Responses:**  
    __202__ - New image  
    __400__ - Missing parameters  
    __500__ - Server error
    
    **Example:**  
        
        >>> cat | http POST http://f17.vm.private:8075/imagefactory/base_images
        {
            "base_image": {
                "template": "<template>\n <name>f17jeos</name>\n <os>\n <rootpw>changeme</rootpw>\n <name>Fedora</name>\n <version>17</version>\n <arch>x86_64</arch>\n <install type='url'>\n <url>http://download.fedoraproject.org/pub/fedora/linux/releases/17/Fedora/x86_64/os/</url>\n </install>\n </os>\n <description>Fedora 17</description>\n </template>"
            }
        }
        ^D
        HTTP/1.0 202 Accepted
        Content-Length: 690
        Content-Type: application/json
        Date: Fri, 16 Nov 2012 17:14:27 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "base_image": {
                "_type": "BaseImage", 
                "href": "http://f17.vm.private:8075/imagefactory/base_images/7df54954-4b95-4061-85f2-8598f326107e", 
                "icicle": null, 
                "id": "7df54954-4b95-4061-85f2-8598f326107e", 
                "parameters": {}, 
                "percent_complete": 0, 
                "status": "NEW", 
                "status_detail": {
                    "activity": "Initializing image prior to Cloud/OS customization", 
                    "error": null
                }, 
                "template": "<template>\n <name>f17jeos</name>\n <os>\n <rootpw>changeme</rootpw>\n <name>Fedora</name>\n <version>17</version>\n <arch>x86_64</arch>\n <install type='url'>\n <url>http://download.fedoraproject.org/pub/fedora/linux/releases/17/Fedora/x86_64/os/</url>\n </install>\n </os>\n <description>Fedora 17</description>\n </template>"
            }
        }

#### Target Images

* __*/imagefactory/target_images*__  
* __*/imagefactory/base_images/:base_image_id/target_images*__  
    
    **Methods:**  
    **POST**  
    
    **Description:**  
    Builds a new TargetImage.  
    
    **OAuth protected:**  
    YES  
    
    **Parameters:**  
    __base_image_id__ - The uuid of a base_image to build from. Not needed if specifying a template. This can be specified in the resource path as shown in the example below.  
    __template__ - An image template or component outline compatible with the TDL schema (http://imgfac.org/documentation/tdl) for creating a base image if a base image id is not specified.  
    __target__ - A cloud target name such as 'rhevm', 'ec2', 'vsphere', 'openstack', etc... This must match the target field of a loaded cloud plugin.   
    __parameters__ - Optional parameters that may change the nature of the image being built.  This may include things such as on-disk format or the build mechanism itself.  Parameters are never required as sensible defaults will always be used and will be made part of the queryable properties of an image.
    
    **Responses:**  
    __202__ - New image  
    __400__ - Missing parameters  
    __404__ - BaseImage not found  
    __500__ - Error building image
    
    **Example:**  
        
        >>> cat | http POST http://f17.vm.private:8075/imagefactory/base_images/7df54954-4b95-4061-85f2-8598f326107e/target_images Content-Type:application/xml
        <target_image>
            <target>ec2</target>
        </target_image>
        ^D
        HTTP/1.0 202 Accepted
        Content-Length: 830
        Content-Type: application/json
        Date: Fri, 16 Nov 2012 18:53:44 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "target_image": {
                "_type": "TargetImage", 
                "base_image_id": "7df54954-4b95-4061-85f2-8598f326107e", 
                "href": "http://f17.vm.private:8075/imagefactory/base_images/7df54954-4b95-4061-85f2-8598f326107e/target_images/333122dc-43c4-4f3f-b689-6dcd96bdfebe", 
                "icicle": null, 
                "id": "333122dc-43c4-4f3f-b689-6dcd96bdfebe", 
                "parameters": {}, 
                "percent_complete": 0, 
                "status": "NEW", 
                "status_detail": {
                    "activity": "Initializing image prior to Cloud/OS customization", 
                    "error": null
                }, 
                "target": "ec2", 
                "template": "<template>\n <name>f17jeos</name>\n <os>\n <rootpw>changeme</rootpw>\n <name>Fedora</name>\n <version>17</version>\n <arch>x86_64</arch>\n <install type='url'>\n <url>http://download.fedoraproject.org/pub/fedora/linux/releases/17/Fedora/x86_64/os/</url>\n </install>\n </os>\n <description>Fedora 17</description>\n </template>"
            }
        }


#### Provider Images

* __*/imagefactory/provider_images*__  
* __*/imagefactory/target_images/:target_image_id/provider_images*__  
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images*__  
    
    **Methods:**  
    * **POST**  
    
    **Description:**  
    Builds a new ProviderImage  
    
    **OAuth protected:**  
    YES  
    
    **Parameters:**  
    __target_image_id__ - The uuid of a target image to push. Not needed if specifying a template.  This can also be specified in the resource path as shown in the example below.  
    __template__ - An image template or component outline compatible with the TDL schema (http://imgfac.org/documentation/tdl) for creating base image and target image. Not needed if specifying a target image id.  
    __target__ - The target to which the provider belongs. This would be the same target used for building a TargetImage.  
    __provider__ - The cloud provider definition.  See the [provider definition examples][provider_examples] for more information.  
    __credentials__ - The cloud provider credentials.  See the [credential examples][provider_examples] for more information.  
    __parameters__ - Optional parameters that may change the nature of the image being built.  This may include things such as on-disk format or the build mechanism itself.  Parameters are never required as sensible defaults will always be used and will be made part of the queryable properties of an image.
    
    **Responses:**  
    __202__ - New image  
    __400__ - Missing parameters  
    __404__ - BaseImage or TargetImage not found  
    __500__ - Error building image  

    **Example:**  
        
        >>> cat | http -f POST http://f17.vm.private:8075/imagefactory/base_images/c55674e1-c5b6-4cc9-b471-5fdc2ff095fc/target_images/208a3c18-8609-4441-9230-4a278660240e/provider_images target=ec2&provider=ec2-us-east-1&credentials=<provider_credentials>
            <ec2_credentials>
                <account_number>1234-5678-9012</account_number>   
                <access_key>BEEFFEEDBEEFFEEDBEEF</access_key>   
                <secret_access_key>asdHGK46783HGAlasdfc12FjerIe7g</secret_access_key>
                <certificate>
                    -----BEGIN CERTIFICATE-----
                    ChM0WE1MIFNlY3VyaXR5IExpYnJhcnkgKGh0dHA6Ly93d3cuYWxla3NleS5jb20v
                    eG1sc2VjKTEZMBcGA1UECxMQUm9vdCBDZXJ0aWZpY2F0ZTEWMBQGA1UEAxMNQWxl
                    a3NleSBTYW5pbjEhMB8GCSqGSIb3DQEJARYSeG1sc2VjQGFsZWtzZXkuY29tMB4X
                    DTAzMDMzMTA0MDIyMloXDTEzMDMyODA0MDIyMlowgb8xCzAJBgNVBAYTAlVTMRMw
                    EQYDVQQIEwpDYWxpZm9ybmlhMT0wOwYDVQQKEzRYTUwgU2VjdXJpdHkgTGlicmFy
                    eSAoaHR0cDovL3d3dy5hbGVrc2V5LmNvbS94bWxzZWMpMSEwHwYDVQQLExhFeGFt
                    cGxlcyBSU0EgQ2VydGlmaWNhdGUxFjAUBgNVBAMTDUFsZWtzZXkgU2FuaW4xITAf
                    BgkqhkiG9w0BCQEWEnhtbHNlY0BhbGVrc2V5LmNvbTCCASIwDQYJKoZIhvcNAQEB
                    BQADggEPADCCAQoCggEBAJe4/rQ/gzV4FokE7CthjL/EXwCBSkXm2c3p4jyXO0Wt
                    quaNC3dxBwFPfPl94hmq3ZFZ9PHPPbp4RpYRnLZbRjlzVSOq954AXOXpSew7nD+E
                    mTqQrd9+ZIbGJnLOMQh5fhMVuOW/1lYCjWAhTCcYZPv7VXD2M70vVXDVXn6ZrqTg
                    w3dcTZBoihHftE8=
                    -----END CERTIFICATE-----
                </certificate>
                <key>
                    -----BEGIN PRIVATE KEY-----
                    MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAMtnxavY/9jvytQlDI/fiZ3o+j3b
                    nDhE0woQVqzuLT2brUUB3bSdvLsupV/wISLFRSTaKenZ2Bgi3mTrBjEdZs/qipsw4phrwVPaUp/q
                    Gz1XreE6RK4LBjlbQS+pIkLg3eem9whCXgmRZJFhX3tDIL75oWYOFFEXZaAjmQUNpj3BAgMBAAEC
                    trO9JAvQH/3z0B53tofvgA8U00kndI8MoiRbN/eUiSRFAN2DRnVYKS4ZCcVBOOBwQ7eEcktrn9M2
                    VidjtAafdNADzwD+tJohsWECQQD2eT4JNTcI+xkQu53qODXoeEzusosXfmC5/+mwXMJp/3kv/jmO
                    GwuLdlvD/e0R0imZ+GHNiw6MyfEWhiepYmGtAkEA00RjBRUex0Z5oTz/WIc6gyqkxMPAwxNOrXxu
                    J1tokgITO/DCCJ1Xs8edDeq3cps2CpeHwIHC1o+GaVyG4BR3goNn6BUaK6qvWA0CQBrpLyPKmO0R
                    URT0zCHet9lVaT+XH8q5fuAiZXncCOA7f37Se0hojqYEXvCRFeTNi9Fconl9pICelvIpDSL5cvEC
                    SGsMB351VonwYzr49uSNdeGINw8bUhN/osdj6v8gxjmhbUAW5QJBALeuyY3BK9+0igyPVfN8qqgy
                    gYEAkHapa/346EiW08lkfKKVCPQ5Fsns0AIBqToldTjMJN92VnaW0frd2kus5NCVmC5nh17zOcWg
                    QEtAy9gMuRO46tJwXrN+hurJdicrbushw0GZA/TukgUnPPpldgxpkH6JFgbsl8XdrfAbMXuiAex/
                    V3wdTItQ6So=
                    -----END PRIVATE KEY-----
                </key>
            </ec2_credentials>
        </provider_credentials>
        ^D
        HTTP/1.0 202 Accepted
        Content-Length: 2656
        Content-Type: application/json
        Date: Wed, 14 Nov 2012 17:10:01 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "provider_image": {
                "_type": "ProviderImage", 
                "href": "http://f17.vm.private:8075/imagefactory/base_images/c55674e1-c5b6-4cc9-b471-5fdc2ff095fc/target_images/208a3c18-8609-4441-9230-4a278660240e/provider_images/03957dc3-a51b-41af-af3d-8544f4fa2b47", 
                "icicle": null, 
                "id": "03957dc3-a51b-41af-af3d-8544f4fa2b47", 
                "identifier_on_provider": null, 
                "parameters": null, 
                "percent_complete": 0, 
                "provider": "ec2-us-east-1", 
                "provider_account_identifier": null, 
                "status": "NEW", 
                "status_detail": {
                    "activity": "Initializing image prior to Cloud/OS customization", 
                    "error": null
                }, 
                "target_image_id": "208a3c18-8609-4441-9230-4a278660240e", 
                "template": "<template>\n  <name>ApacheWebServer</name>\n  <description>Apache httpd server, running on Fedora 16</description>\n  <os>\n    <name>Fedora</name>\n    <version>16</version>\n    <arch>x86_64</arch>\n    <install type=\"url\">\n\n      <!-- This is the Fedora 16 base repository -->\n      <url>http://download.fedoraproject.org/pub/fedora/linux/releases/16/Everything/x86_64/os/</url>\n\n      <!-- Note that only a base package installation is done. -->\n      <!-- No yum updates are automatically applied.  If you   -->\n      <!-- want updates (and you do! :>), you'll need to have  -->\n      <!-- a \"yum update -y\" in the command list below.        -->\n\n    </install>\n\n    <!-- The password for the root user.  You can use this to  -->\n    <!-- log in remotely if desired.                           -->\n    <rootpw>p@ssw0rd</rootpw>\n\n  </os>\n\n\n  <!-- After the main OS has been installed, the packages below are installed --> \n  <!-- in a separate step.  It takes into account the repositories in         -->\n  <!-- /etc/yum.repos.d/, unlike the base OS installation which doesn't.      -->\n\n  <packages>\n\n    <!-- These packages install Wordpress on this node.  In theory, just specifying -->\n    <!-- \"wordpress\" should be good enough.  In reality, that didn't consistently   -->\n    <!-- work for me.  Specifying httpd, php-gettext, and wordpress does.           -->\n    <!-- Note though, that could just be due to some unknown transient repo error   -->\n    <!-- or something. -->\n    <package name=\"httpd\"/>\n    <package name=\"php-gettext\"/>\n    <package name=\"wordpress\"/>\n\n  </packages>\n\n\n  <!-- After the above packages have been installed, -->\n  <!-- the commands below are run, in order.         -->\n\n  <commands>\n\n    <!-- This pulls in updated Fedora packages.  Practically mandatory  -->\n    <!-- in any real world deployment. :>                               -->\n    <command name=\"yum-update\">yum update -y</command>\n\n  </commands>\n\n</template>\n"
            }
        }

### Image Inspection

* __*/imagefactory/base_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/target_images/:image_id*__
* __*/imagefactory/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/provider_images/:image_id*__
    
    __image_id__ - uuid of the image to inspect  
    
    **Methods:**  
    **GET**  
    
    **Description:**  
    Get image details  
    
    **OAuth protected:**  
    YES  
    
    **Responses:**  
    __200__ - Image  
    __404__ - Image Not Found  
    __500__ - Server error
    
    **Example:**  
        
        >>> http http://f17.vm.private:8075/imagefactory/base_images/c55674e1-c5b6-4cc9-b471-5fdc2ff095fc
        HTTP/1.0 200 OK
        Content-Length: 3665
        Content-Type: application/json
        Date: Mon, 29 Oct 2012 22:46:12 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "base_image": {
                "_type": "BaseImage", 
                "href": "http://f17.vm.private:8075/imagefactory/base_images/c55674e1-c5b6-4cc9-b471-5fdc2ff095fc", 
                "icicle": null, 
                "id": "c55674e1-c5b6-4cc9-b471-5fdc2ff095fc", 
                "parameters": {
                    "libvirt_xml": "<?xml version=\"1.0\"?>\n<domain type=\"kvm\">\n  <name>factory-build-c55674e1-c5b6-4cc9-b471-5fdc2ff095fc</name>\n  <memory>1048576</memory>\n  <currentMemory>1048576</currentMemory>\n  <uuid>909f8df1-1d01-4413-b7dc-eccd9240fa5e</uuid>\n  <clock offset=\"utc\"/>\n  <vcpu>1</vcpu>\n  <features>\n    <acpi/>\n    <apic/>\n    <pae/>\n  </features>\n  <os>\n    <type>hvm</type>\n    <boot dev=\"hd\"/>\n  </os>\n  <on_poweroff>destroy</on_poweroff>\n  <on_reboot>destroy</on_reboot>\n  <on_crash>destroy</on_crash>\n  <devices>\n    <graphics port=\"-1\" type=\"vnc\"/>\n    <interface type=\"bridge\">\n      <source bridge=\"virbr0\"/>\n      <mac address=\"52:54:00:af:08:52\"/>\n      <model type=\"virtio\"/>\n    </interface>\n    <input bus=\"ps2\" type=\"mouse\"/>\n    <console type=\"pty\">\n      <target port=\"0\"/>\n    </console>\n    <serial type=\"tcp\">\n      <source mode=\"bind\" host=\"127.0.0.1\" service=\"19883\"/>\n      <protocol type=\"raw\"/>\n      <target port=\"1\"/>\n    </serial>\n    <disk device=\"disk\" type=\"file\">\n      <target dev=\"vda\" bus=\"virtio\"/>\n      <source file=\"/var/lib/imagefactory/storage/c55674e1-c5b6-4cc9-b471-5fdc2ff095fc.body\"/>\n    </disk>\n  </devices>\n</domain>\n"
                }, 
                "percent_complete": 0, 
                "status": "COMPLETE", 
                "status_detail": {
                    "activity": "Cleaning up install artifacts", 
                    "error": null
                }, 
                "target_images": {
                    "target_images": []
                }, 
                "template": "<template>\n  <name>ApacheWebServer</name>\n  <description>Apache httpd server, running on Fedora 16</description>\n  <os>\n    <name>Fedora</name>\n    <version>16</version>\n    <arch>x86_64</arch>\n    <install type=\"url\">\n\n      <!-- This is the Fedora 16 base repository -->\n      <url>http://download.fedoraproject.org/pub/fedora/linux/releases/16/Everything/x86_64/os/</url>\n\n      <!-- Note that only a base package installation is done. -->\n      <!-- No yum updates are automatically applied.  If you   -->\n      <!-- want updates (and you do! :>), you'll need to have  -->\n      <!-- a \"yum update -y\" in the command list below.        -->\n\n    </install>\n\n    <!-- The password for the root user.  You can use this to  -->\n    <!-- log in remotely if desired.                           -->\n    <rootpw>p@ssw0rd</rootpw>\n\n  </os>\n\n\n  <!-- After the main OS has been installed, the packages below are installed --> \n  <!-- in a separate step.  It takes into account the repositories in         -->\n  <!-- /etc/yum.repos.d/, unlike the base OS installation which doesn't.      -->\n\n  <packages>\n\n    <!-- These packages install Wordpress on this node.  In theory, just specifying -->\n    <!-- \"wordpress\" should be good enough.  In reality, that didn't consistently   -->\n    <!-- work for me.  Specifying httpd, php-gettext, and wordpress does.           -->\n    <!-- Note though, that could just be due to some unknown transient repo error   -->\n    <!-- or something. -->\n    <package name=\"httpd\"/>\n    <package name=\"php-gettext\"/>\n    <package name=\"wordpress\"/>\n\n  </packages>\n\n\n  <!-- After the above packages have been installed, -->\n  <!-- the commands below are run, in order.         -->\n\n  <commands>\n\n    <!-- This pulls in updated Fedora packages.  Practically mandatory  -->\n    <!-- in any real world deployment. :>                               -->\n    <command name=\"yum-update\">yum update -y</command>\n\n  </commands>\n\n</template>\n"
            }
        }


### Image Deletion

* __*/imagefactory/base_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:image_id*__
* __*/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/target_images/:image_id*__
* __*/imagefactory/target_images/:target_image_id/provider_images/:image_id*__
* __*/imagefactory/provider_images/:image_id*__
    
    __image_id__ - uuid of the image to delete  
    
    **Methods:**  
    **DELETE**  
    
    **Description:**  
    Delete the image specified with *image_id*  
    
    **OAuth protected:**  
    YES  
    
    **Responses:**  
    __204__ - No Content  
    __404__ - Image Not Found  
    __500__ - Server error  
    
    **Example:**  
        
        >>> http DELETE http://f17.vm.private:8075/imagefactory/provider_images/7b301688-2b7f-49e8-b744-6b8a450fac25
        HTTP/1.0 204 No Content
        Content-Length: 0
        Date: Fri, 16 Nov 2012 18:59:45 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        

### Plugins

* __*/imagefactory/plugins*__
    
    **Methods:**  
    **GET**  
    
    **Description:**  
    Lists the loaded plugins  
    
    **OAuth protected:**  
    YES  
    
    **Responses:**  
    __200__ - Plugin list  
    __500__ - Server error
    
    **Example:**  
        
        >>> http http://f17.vm.private:8075/imagefactory/plugins
        HTTP/1.0 200 OK
        Content-Length: 3369
        Content-Type: application/json
        Date: Fri, 16 Nov 2012 19:03:37 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        
        {
            "plugins": [
                {
                    "_type": "plugin", 
                    "description": "Fedora, RHEL-5 and RHEL-6 OS plugin", 
                    "href": "http://f17.vm.private:8075/imagefactory/plugins/FedoraOS", 
                    "id": "FedoraOS", 
                    "license": "Copyright 2012 Red Hat, Inc. - http://www.apache.org/licenses/LICENSE-2.0", 
                    "maintainer": {
                        "email": "aeolus-devel@lists.fedorahosted.org", 
                        "name": "Red Hat, Inc.", 
                        "url": "http://imgfac.org"
                    }, 
                    "targets": [
                        [
                            "Fedora", 
                            null, 
                            null
                        ], 
                        [
                            "RHEL-6", 
                            null, 
                            null
                        ], 
                        [
                            "RHEL-5", 
                            null, 
                            null
                        ]
                    ], 
                    "type": "os", 
                    "version": "1.0"
                }, 
                {
                    "_type": "plugin", 
                    "description": "EC2 cloud plugin for imagefactory", 
                    "href": "http://f17.vm.private:8075/imagefactory/plugins/EC2Cloud", 
                    "id": "EC2Cloud", 
                    "license": "Copyright 2012 Red Hat, Inc. - http://www.apache.org/licenses/LICENSE-2.0", 
                    "maintainer": {
                        "email": "aeolus-devel@lists.fedorahosted.org", 
                        "name": "Red Hat, Inc.", 
                        "url": "http://imgfac.org"
                    }, 
                    "targets": [
                        [
                            "ec2"
                        ]
                    ], 
                    "type": "cloud", 
                    "version": "1.0"
                }
            ]
        }

* __*/imagefactory/plugins/:plugin_id*__
    
    **Methods:**  
    **GET**  
    
    **Description:**  
    Get the details for plugin with a given id.  
    
    **OAuth protected:**  
    YES  
    
    **Responses:**  
    __200__ - Plugin  
    __500__ - Server error  
    
    **Example:**  
        
        >>> http http://f17.vm.private:8075/imagefactory/plugins/OpenStackCloud
        HTTP/1.0 200 OK
        Content-Length: 495
        Content-Type: application/json
        Date: Fri, 16 Nov 2012 19:07:56 GMT
        Server: PasteWSGIServer/0.5 Python/2.7.3
        ]
        {
            "_type": "plugin", 
            "description": "OpenStack KVM cloud plugin for imagefactory", 
            "href": "http://f17.vm.private:8075/imagefactory/plugins/OpenStackCloud/OpenStackCloud", 
            "id": "OpenStackCloud", 
            "license": "Copyright 2012 Red Hat, Inc. - http://www.apache.org/licenses/LICENSE-2.0", 
            "maintainer": {
                "email": "aeolus-devel@lists.fedorahosted.org", 
                "name": "Red Hat, Inc.", 
                "url": "http://imgfac.org"
            }, 
            "targets": [
                [
                    "openstack-kvm"
                ]
            ], 
            "type": "cloud", 
            "version": "1.0"
        }

### Cloud Targets and Providers

* __*/imagefactory/targets*__
* __*/imagefactory/targets/:target_id*__
* __*/imagefactory/targets/:target_id/providers*__
* __*/imagefactory/targets/:target_id/providers/:provider_id*__

    **NOT IMPLEMENTED**

<!-- links -->
[resources]: #resources (Resources)
[provider_examples]: http://imgfac.org/documentation/cred_provider_examples.html (Provider Definition and Credentials examples)
