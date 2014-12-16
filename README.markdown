#Image Factory#

Image Factory enables appliance creation and deployment to multiple virtualization
and Cloud providers.

##Features##
*   Build guest images for a growing list of operating system and cloud combinations.
    * Current guest OS support: Fedora 7-19, RHEL 5.x and 6.x
    * Current cloud support: Red Hat Enterprise Virtualization, VMware vSphere, Amazon EC2, Rackspace, OpenStack, and more...
*   Image Factory supports "build and upload" or snapshotting of existing images.
*   RESTful API makes integrating Image Factory into existing workflows simple.


##Using Image Factory##
Building an image begins with a template describing what to build. See an example
of such a template below. See the [schema documentation for TDL](http://imgfac.org/documentation/tdl/TDL.html)
for more detail on creating a template. Note that a template is **not** tied to
a specific cloud. 

    <template>
        <name>f21</name>
        <os>
            <name>Fedora</name>
            <version>21</version>
            <arch>x86_64</arch>
            <install type='iso'>
                <iso>http://download.fedoraproject.org/pub/fedora/linux/releases/21/Cloud/x86_64/os/</iso>
            </install>
            <rootpw>p@55word!</rootpw>
        </os>
    </template>

Ensure to change the element to your desired root password.

Next, use the imagefactory command and specify the template to use and for which
clouds to build an image. The above template example was saved to a file name f12_64.tdl.

    $ sudo imagefactory --template f12_64.tdl --target ec2

Once the image has been built, use the imagefactory command again, this time to
push the image into the cloud.

    $ sudo imagefactory --provider ec2-us-west-1 --credentials ec2_credentials.xml

That's it!  You can now launch an instance of this image using the cloud
provider's management console.

##Installing Image Factory##
Installing Image Factory is quick and easy.  See the
[imagefactory rpm installation](http://imgfac.org/documentation/install.html#rpm)
instructions for more detail.

## Dev Setup ##
If you are wanting to use Imagefactory in a dev environment, then you can run from source.  Run the 'imagefactory_dev_setup.sh' script found in the scripts directory.  This will setup a dev environment which allows you to run from source.  Once this is complete run ./imagefactoryd --foreground to start the server.

## Documentation ##
More documentation on how to configure, use, and develop for imagefactory can be found on the [Image Factory website](http://imgfac.org). 
