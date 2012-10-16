#Image Factory#
*Your infrastructure in a sky full of clouds.*

Image Factory enables appliance creation and deployment to multiple virtualization
and Cloud providers.

##Features##
*   Build guest images for a growing list of operating system and cloud combinations.
    * Current guest OS support: Fedora 7-16, RHEL 5.x and 6.x
    * Current cloud support: Red Hat Enterprise Virtualization, VMware vSphere, Amazon EC2, Rackspace
*   Image Factory supports "build and upload" or snapshotting of existing images.
*   RESTful API makes integrating Image Factory into existing workflows simple.

##Using Image Factory##
Building an image begins with a template describing what to build. See an example
of such a template below. See the [schema documentation for TDL](http://imgfac.org/documentation/tdl/TDL.html)
for more detail on creating a template. Note that a template is **not** tied to
a specific cloud. 

    <template>
        <name>f12jeos</name>
        <os>
            <name>Fedora</name>
            <version>12</version>
            <arch>x86_64</arch>
            <install type='iso'>
                <iso>http://download.fedoraproject.org/pub/fedora/linux/releases/12/Fedora/x86_64/os/</iso>
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

That's it!  You can now launch an instance of this image using either the cloud
provider's management console or a cloud management tool such as 
**[Aeolus](http://www.aeolusproject.org/)**.

##Installing Image Factory##
Installing Image Factory is quick and easy.  Fedora 15-16 and RHEL 5-6 users can
add the Aeolus repository for either RHEL or Fedora as described on the
[Aeolus | Get It](http://www.aeolusproject.org/get_it.html#stable) page.  Once
configured, yum can be used to install Image Factory with:

    $ sudo yum install imagefactory

Other, unsupported, systems can install Image Factory using setuptools:

    $ git clone git://github.com/aeolusproject/imagefactory.git
    ...
    $ cd imagefactory
    $ sudo setup.py install
