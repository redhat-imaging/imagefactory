## Executive Summary ##

This is a plugin that was originally created to generate LiveCD images
using the livemedia-creator project in Fedora.

I named it "IndirectionCloud" because really, it is a pluging to allow
you do build an image using the tools inside of another image, instead
of using any specific code in the plugin itself.

For Fedora Live CD images, the process for doing this is roughly as follows:

1) You build a base image using one of the existing accepted "spin kickstart"
files.  This image is the content that will eventually be turned into a live CD.

Details of spin-kickstarts and the existing live CD creation process:

http://fedoraproject.org/wiki/Talk:How_to_create_and_use_a_Live_CD
https://git.fedorahosted.org/cgit/spin-kickstarts.git


2) You build a base image containing the environment in which you wish to run
livemedia-creator.  Typically this is a JEOS-ish build of the same OS version
from #1 with lorax (and this livemedia-creator) and its dependencies added.  
In theory, it could actually be the _same_ image as #1 although we have not yet 
tried this.  We call this the Utility Image.

3) You build a target_image using the "indirection" plugin.  You pass it the images
from #1 and #2 along with a fragment of TDL that drives the running of livemedia-creator.
When this is finished the indirection plugin extracts the output of lmc from
a known location and stores it as the target_image.  (This output is the ISO)


## Details and examples ##

* Utility Image

This image is where lmc (or potentially other tools) will be run.  At the
moment, it should be built with all required tools specified as packages
and repos in the TDL.

Here is an example of the TDL I used to generate the utility image for
creating an F18 ISO:

<template>
  <name>f18utility</name>
  <os>
    <rootpw>ozrootpw</rootpw>
    <name>Fedora</name>
    <version>18</version>
    <arch>x86_64</arch>
    <install type='url'>
<url>http://download.fedora.com/install_trees/fedora/F-18/64bit/</url>
    </install>
  </os>
  <description>Fedora 18 64 bit image with packages needed for live CD
creation</description>
  <packages>
      <package name='lorax'/>
      <package name='hfsplus-tools'/>
  </packages>
</template>


* Input Image

This is the image that will be used as the input into lmc.  In short, it
should be a base image built with the flattened spin kickstart.


* Target Image

You then create a target image with the following inputs and parameters.

base_image - The base image should be set to the UUID of the Input Image
generate in the step above.

parameters - Just as with the base image creation step, this holds a
dictionary of additional parameters that may be specific to a particular
plugin.  The Live CD plugin expects the following:

utility_image - This should be the UUID of the Utility Image generated
in the step above.

utility_customizations - This is a _partial_ TDL document that
contains the commands necessary to generate the ISO.  These commands are
run inside of a VM created from a copy of utility image that has been
booted to runlevel 3.  This VM also has an additional unmounted
filesystem available to it as /dev/vdb1 with the following
characteristics:

1) The input image is available as the file "/input_image.raw"

2) Once the customization TDL has finished running and the VM has shut
down, the plugin expects to find the results in
"/results/images/boot.iso"

Both of these paths are relative to the filesystem root of /dev/vdb1.

The TDL fragment necessary to generate an ISO ends up being very simple.
Here is an example for F18:

<template>
<commands>
   <command name='mount'>mount /dev/vdb1 /mnt</command>
   <command name='livecd'>livemedia-creator --make-iso
--disk-image /mnt/input_image.raw --resultdir /mnt/results</command>
</commands>
</template>


## Next Steps - Image Factory ##

1) Make the input image filename and the expected output image location
additional parameters with defaults of what is described above.  This is
quite simple but should make the plugin quite a bit more flexible.

UPDATE: This is now done.  Details are in the comments at the top of the source
flie.

2) Test out installing the lmc enabling packages as part of the target
image step.  The code to allow this is already part of what processes
the partial TDL that drives the ISO creation.  I just haven't yet tried
to add repos or packages in this step.

3) Use qcow2 snapshots of the utility image rather than doing a bulk
copy.  This is an optimization.

UPDATE: I have a pull request in to add a general purpose version of
this to Oz.  If this is accepted we can use it here as well.

4) Present the input image to the utility instance as a read only device
rather than as a file inside of the working space partition.  I tested
this very early on in my work and lmc seemed to be capable of accepting
an actual device rather than a file as its input image.  This is another
optimization as it avoids another bulk copy.  (Make this a special case
of the parameter specification in #1)

UPDATE: This is now an option via parameters but I have not yet tested
it.

## Next Steps - Not Image Factory ##

1) Ensure that what lmc is producing is an acceptable substitute for
what live CD creator is producing - I'm only aware of one potential
issue at this point, which is size.  Thus far my test ISO builds based
on the flattened F18 live CD spin kickstarts from git have been about 
1 GB in size.  That is, larger than a CD.  
