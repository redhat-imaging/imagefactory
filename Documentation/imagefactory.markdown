% IMAGEFACTORY(1) Version 1.0 - February 10, 2012 | User Manual

**NAME**  

> imagefactory - create virtual machine images for use on a variety of clouds

**SYNOPSIS**  

> **imagefactory** \[optional arguments\]

**DESCRIPTION**

> **imagefactory** is the command for starting the Image Factory REST API.
**imagefactory** can also be used to create virtual machine images and push
these images to cloud providers from the command line without starting the 
REST API.

> Image Factory builds virtual machine images using a template document,
which is an abstract description of the system to be built. See the 
[TDL schema documentation][tdl-schema] for a full description of what can be
specified in a template. Built images can then be pushed to cloud providers
such as Amazon EC2 or VMware vSphere where they can be launched as instances.

> Image Factory uses the Image Warehouse to store images and image metadata.
More information about Image Warehouse can be found at the [project page][iwhd-link]
on AeolusProject.org.

&nbsp; &nbsp; **Using imagefactory**

> The **imagefactory** command can be considered to have two modes of operation. 
One mode is used to start a daemon providing the REST API for use by remote clients.

> >     imagefactory --rest

> Another mode of operation is as a local command line utility for building
images and/or pushing them to a cloud provider.  Specifying a template and
target will build an image.

> >     imagefactory --target rhevm --template `cat f15_64bit.tdl`

> Specifying a provider, credentials, and an image id will push an image
previously built for a target cloud to the cloud provider.

> >     imagefactory --provider rhevm-1 --credentials `cat creds.xml` \
        --image 2d73cd08-1924-4f02-80e9-f6d7bb1a68bd

> A full description of **imagefactory** options is provided below.

**OPTIONS**  

&nbsp; &nbsp; **General options**

> **-h** or **--help**

> > Shows a help message with short descriptions of these options and exits.

> **--version**

> > Shows the version information for Image Factory and exits.

> **-v** or **--verbose**

> > Turn on verbose logging.

> **--debug**

> > Turn on debug logging.

> **--foreground**

> > Keep imagefactory running in the foreground. Logs will be written to stdout.

> **--config** CONFIGFILE

> > Path to the configuration file to use. The default location is
`/etc/imagefactory/imagefactory.conf`. For more information about the format of
the configuration file, see the **imagefactory.conf(5)** man page or the
[online documentation][conf-doc].

> **--imgdir** IMGDIR

> > The filesystem path in which to build images. The default location is `/tmp`.

> **--timeout** TIMEOUT

> > Sets the timeout period for image building in seconds. Default value is `3600`.

> **--tmpdir** TMPDIR

> > The filesystem path in which to store temporary files. The default location
is `/tmp`.

&nbsp; &nbsp; **REST API options**

> For a full discussion of the REST API, see the **imagefactory.rest(7)** man
page or the [online documentation][rest-doc].

> **--rest**

> > Start the imagefactory daemon and enable the REST interface.

> **--port** PORT

> > The network port the daemon should listen to. Default: `8075`

> **--address** ADDR

> > The network address the daemon should lisen on. Default: `0.0.0.0` (listen
on all interfaces)

> **--no_ssl**

> > Turns off SSL.

> **--ssl_pem** CERTPATH

> > The path to the SSL certificate to use. If this is not specified either on
the command line or in the configuration file, **imagefactory** will generate
a temporary, self-signed, certificate each time **imagefactory** is started.

> **--no_oauth**

> > Turn off OAuth authentication.

&nbsp; &nbsp; **Image build options**

> **--target** TARGET

> > Name of the cloud for which to build an image. Ex. rhevm, ec2, vsphere,
rackspace, etc...

> **--template** TEMPLATE

> > An XML document describing the system to be built. The template schema
is described in the [online documentation][tdl-schema].

&nbsp; &nbsp; **Image push options**

> **--image** IMAGE ID

> > The UUID of a previously built image.

> **--provider** PROVIDER NAME

> > The name of the provider to push to. This name will be matched to providers
Image Factory knows about either. These can either be existing regions in a
public cloud such as Amazon's EC2 or configured in the private cloud definitions
such as `rhevm.json` and `vsphere.json` found in `/etc`.

> > The private cloud provider definitions use the following format:  

> > *rhevm.json*  
> >     
        {
            "name": 
            {
                "api-url": URL,
                "api-key": KEY,
                "api-secret": SECRET,
                "nfs-dir": DIR,
                "nfs-path": PATH,
                "nfs-host": HOST
            }
        }

> > *vsphere.json*
> >     
        {
            "name":
            {
                "api-url": URL,
                "datastore": STORE_NAME,
                "network_name": NETWORK_NAME
            }
        }

> > It is possible to also pass in a provider definition. In this case, only
the inner dictionary is used and the keys 'name' and 'target' must be added.
For example, a definition for a vSphere provider would be:
> >     
        {
            "name": PROVIDER_NAME,
            "target": "vsphere",
            "api-url": URL,
            "datastore": STORE_NAME,
            "network_name": NETWORK_NAME
        }

> **--credentials** CREDENTIALS

> > XML formatted credentials for authentication with the cloud provider.
*Schema documentation for credentials is forthcoming...*

&nbsp; &nbsp; **EC2 options**

> **--ec2-32bit-util** INSTANCE TYPE

> > The instance type to use when launching a 32 bit utility instance.
Example: m1.small

> **--ec2-64bit-util** INSTANCE TYPE

> > The instance type to use when launching a 64 bit utility instance.
Example: m1.large

&nbsp; &nbsp; **Image Warehouse options**

> Image Warehouse is a component of Aeolus Project for generic object storage.
Image Factory stores images and image metadata in the Image Warehouse consumption
by other Aeolus components, such as Conductor.

> **--warehouse** WAREHOUSE URL

> > The URL to the iwhd to use.  Default: `http://localhost:9090/`

> **--image_bucket** BUCKET

> > Name of the bucket in Image Warehouse to use for image storage.
Default: `images`

> **--build_bucket** BUCKET

> > Name of the bucket in Image Warehouse to use for builds.
Default: `builds`

> **--target_bucket** BUCKET

> > Name of the bucket in Image Warehouse to use for target images.
Default: `target_images`

> **--template_bucket** BUCKET

> > Name of the bucket in Image Warehouse to use for templates.
Default: `templates`

> **--icicle_bucket** BUCKET

> > Name of the bucket in Image Warehouse to use for icicle documents.
Default: `icicles`

> **--provider_bucket** BUCKET

> > Name of the bucket in Image Warehouse to use for provider images.
Default: `provider_images`

&nbsp; &nbsp; **Image import options**

> Image importing establishes records in the Image Warehouse for images built
without Image Factory. This allows such images to be used by other Aeolus
components, such as Conductor.

> **--target-image** TARGET IMAGE ID

> > The cloud specific identifier of the image to import.

> **--image-desc** IMAGE DESCRIPTION

> > An XML document describing the image being imported. *Schema documentation
for image description is forthcoming...*


[tdl-schema]: http://aeolusproject.github.com/imagefactory/tdl/ (TDL schema)
[conf-doc]: https://github.com/aeolusproject/imagefactory/blob/master/Documentation/configuration.markdown (Image Factory configuration)
[rest-doc]: https://github.com/aeolusproject/imagefactory/blob/master/Documentation/REST.markdown (Image Factory REST API)
[iwhd-link]: http://www.aeolusproject.org/imagewarehouse.html (Image Warehouse)
