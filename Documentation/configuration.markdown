# Image Factory configuration

---

Image Factory looks for a configuration file at `/etc/imagefactory/imagefactory.conf` by default. The configuration file uses JSON for the format. This document describes the configuration options for Image Factory below.

## General options

Options setting the overall behavior of Image Factory.

+ **debug**
    - _Description:_ Turns on verbose debugging messages in the log file.
    - _Default:_ False
+ **imgdir**
    - _Description:_ Filesystem location in which to build images.
    - _Default:_ /tmp
+ **max_concurrent_local_sessions**
    - _Description:_ The maximum number of concurrent local builds to allow. A local build starts a KVM guest to perform a JEOS install, consuming disk space and memory on the host. Once the number of concurrent builds is reached, any other builds will entera queue and continue as previous builds complete.
    - _Default:_ 2
+ **timeout**
    - _Description:_ Sets the timeout period for image building in seconds.
    - _Default:_ 3600
+ **tmpdir**
    - _Description:_ Filesystem location to use for temporary files.
    - _Default:_ /tmp

## REST API options

Options for enabling the REST API and configuring how it is accessed.

+ **rest**
    - _Description:_ Enable the REST API
    - _Default:_ False
+ **port**
    - _Description:_ Network port to listen on for REST API
    - _Default:_ 8075
+ **address**
    - _Description:_ Network address to listen on for REST API
    - _Default:_ 0.0.0.0
+ **ssl_pem**
    - _Description:_ Path to ssl certificate. If no certificate is specified, a self signed certificate will be generated when imagefactory starts.
    - _Default:_ None
+ **no_ssl**
    - _Description:_ Turn off SSL access to REST API.
    - _Default:_ False
+ **no_oauth**
    - _Description:_ Turn off OAuth authentication for REST API.
    - _Default:_ False
+ **clients**
    - _Description:_ Dictionary of client keys and shared secrets assigned to clients authenticating with OAuth.
    - _Default:_ None
    - _Example:_ `"clients": {"client1": "secret1", "client2": "secret2"}`

## Amazon EC2 options

Options specific to Amazon EC2.

+ **ec2_build_style**
    - _Description:_ How images should be built for EC2. As the name implies, an upload build will install an OS in a VM locally to be customized and prepared for upload to EC2. A snapshot build will copy an existing AMI to be customized.
    - _Default:_ snapshot
    - _Values:_ snapshot, upload
+ **ec2_ami_type**
    - _Description:_ The EC2 storage type to use for AMIs.
    - _Default:_ s3
    - _Values:_ s3, ebs
+ **ec2-32bit-util**
    - _Description:_ Instance type to use when launching a 32 bit utility instance.
    - _Default:_ m1.small
+ **ec2-64bit-util**
    - _Description:_ Instance type to use when launching a 64 bit utility instance.
    - _Default:_ m1.large
+ **max_concurrent_ec2_sessions**
    - _Description:_ The maximum number of concurrent EC2 snapshot builds to allow. Once the number of concurrent builds is reached, any other builds will entera queue and continue as previous builds complete.
    - _Default:_ 2

## RHEVM options

Options specific to Red Hat Enterprise Virtualization

+ **rhevm_image_format**
    - _Description:_ The format to use for RHEVM images.
    - _Default:_ kvm
    - _Values:_ qcow2

## Image Warehouse options

Settings for using the Aeolus Image Warehouse (iwhd) component.

+ **warehouse**
    - _Description:_ URL of the warehouse location to store images.
    - _Default:_ `http://localhost:9090/`
+ **warehouse_key**
    - _Description:_ OAuth key to use for iwhd.
    - _Default:_ None
+ **warehouse_secret**
    - _Description:_ OAuth shared secret to use for iwhd.
    - _Default:_ None
+ **image_bucket**
    - _Description:_ Name of warehouse bucket to look in images.
    - _Default:_ images
+ **build_bucket**
    - _Description:_ Name of warehouse bucket to look in builds.
    - _Default:_ builds
+ **target_bucket**
    - _Description:_ Name of warehouse bucket to look in for target images.
    - _Default:_ target_images
+ **template_bucket**
    - _Description:_ Name of warehouse bucket to look in for templates.
    - _Default:_ templates
+ **icicle_bucket**
    - _Description:_ Name of warehouse bucket to look in for icicles.
    - _Default:_ icicles
+ **provider_bucket**
    - _Description:_ Name of warehouse bucket to look in for provider image instances.
    - _Default:_ provider_images

