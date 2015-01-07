#!/usr/bin/python
#
#   Copyright 2012 Red Hat, Inc.
#   Portions Copyright (C) 2012,2013  Chris Lalancette <clalancette@gmail.com>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import logging
import zope
import oz.TDL
import oz.GuestFactory
import oz.ozutil
import guestfs
# TODO: We've had to migrate to lxml here because of Oz changes
#       see if we can't move the libvirt stuff as well
# For now we import both
import libxml2
import lxml
import ConfigParser
import tempfile
import base64
import os
import os.path
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.CloudDelegate import CloudDelegate
from imgfac.PersistentImageManager import PersistentImageManager
from imgfac.ReservationManager import ReservationManager

# This makes extensive use of parameters with some sensible defaults
# Try to keep an accurate list up here

# Parameter     -  Default - 
# Description

# utility_image - <base_image_id>
# Description: UUID of the image that will be launched to do the modification of the 
#              the base_image referenced in this target_image build.  Note that the 
#              utility image should itself be a base image and can, if constructed properly,
#              be the same as the base image that is being modified.  The plugin makes a copy
#              of the utility image before launching it, which allows safe modification during 
#              the target_image creation process.


# input_image_file - /input_image.raw (but only if input_image_device is not specified)
# Description: The name of the file on the working space disk where the base_image is presented

# input_image_device - None
# Description: The name of the device where the base_image is presented to the utility VM.
#              (e.g. vdc)

# NOTE: You can specify one or the other of these options but not both.  If neither are specified
#       you will end up with the default value for input_image_file.

# utility_cpus - None
# Description: Number of CPUs in the utility VM - this can also be set in the global Oz config
#              The lmc Live CD creation process benefits greatly from extra CPUs during the squashfs
#              creation step.  The performance improvement is almost perfectly O(n) w.r.t CPU.

# utility_customizations - None
# Description: A partial TDL document to drive the actions of the utility VM - only repos, packages,
#              files and commands will be used - all other content is ignored

# results_location - /results/images/boot.iso

# Description: Location inside of the working space image from which to extract the results.

# Borrowed from Oz by Chris Lalancette
def data_from_type(name, contenttype, content):
    '''
    A function to get data out of some content, possibly decoding it depending
    on the content type.  This function understands three types of content:
    raw (where no decoding is necessary), base64 (where the data needs to be
    base64 decoded), and url (where the data needs to be downloaded).  Because
    the data might be large, all data is sent to file handle, which is returned
    from the function.
    '''

    out = tempfile.NamedTemporaryFile()
    if contenttype == 'raw':
        out.write(content)
    elif contenttype == 'base64':
        base64.decode(StringIO.StringIO(content), out)
    elif contenttype == 'url':
        url = urlparse.urlparse(content)
        if url.scheme == "file":
            with open(url.netloc + url.path) as f:
                out.write("".join(f.readlines()))
        else:
            oz.ozutil.http_download_file(content, out.fileno(), False, None)
    else:
        raise oz.OzException.OzException("Type for %s must be 'raw', 'url' or 'base64'" % (name))

    # make sure the data is flushed to disk for uses of the file through
    # the name
    out.flush()
    out.seek(0)

    return out


class IndirectionCloud(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        super(IndirectionCloud, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.pim = PersistentImageManager.default_manager()
        self.res_mgr = ReservationManager()


    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        # This plugin wants to be the only thing operating on the input image
        # We do all our work here and then return False which stops any additional activity

        self.working_space_image = None
        self.utility_image_tmp = None
        try:
            self._builder_should_create_target_image(builder, target, image_id, template, parameters)
        finally:
            self.log.debug("Cleaning up temporary utility image and working space image")
            for fname in [ self.working_space_image, self.utility_image_tmp ]:
                if fname and os.path.isfile(fname):
                    os.unlink(fname)
        return False


    def _builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        # User may specify a utility image - if they do not we assume we can use the input image
        utility_image_id = parameters.get('utility_image', image_id)

        # The utility image is what we actually re-animate with Oz
        # We borrow these variable names from code that is very similar to the Oz/TinMan OS plugin
        self.active_image = self.pim.image_with_id(utility_image_id)
        if not self.active_image:
            raise Exception("Could not find utility image with ID (%s)" % (utility_image_id) )
        self.tdlobj = oz.TDL.TDL(xmlstring=self.active_image.template)

        # Later on, we will either copy in the base_image content as a file, or expose it as a device
        # to the utility VM.  We cannot do both.  Detect invalid input here before doing any long running
        # work
        input_image_device = parameters.get('input_image_device', None)
        input_image_file = parameters.get('input_image_filename', None)

        if input_image_device and input_image_file:
            raise Exception("You can specify either an input_image_device or an input_image_file but not both")

        if (not input_image_device) and (not input_image_file):
            input_image_file="/input_image.raw"

        # We remove any packages, commands and files from the original TDL - these have already been
        # installed/executed.  We leave the repos in place, as it is possible that commands executed
        # later may depend on them
        self.tdlobj.packages = [ ]
        self.tdlobj.commands = { }
        self.tdlobj.files = { } 

        # This creates a new Oz object - replaces the auto-generated disk file location with
        # a copy of the utility image we will make later, and prepares an initial libvirt_xml string
        self._init_oz()
        self.utility_image_tmp = self.app_config['imgdir'] + "/tmp-utility-image-" + str(builder.target_image.identifier)
        self.guest.diskimage = self.utility_image_tmp
        # Below we will create this file as a qcow2 image using the original utility image as
        # a backing store - For the follow-on XML generation to work correctly, we need to force
        # Oz to use qcow2 as the image type
        self.guest.image_type = 'qcow2'

        if 'utility_cpus' in parameters:
            self.guest.install_cpus = int(parameters['utility_cpus'])

        libvirt_xml = self.guest._generate_xml("hd", None)
        libvirt_doc = libxml2.parseDoc(libvirt_xml)

        # Now we create a second disk image as working/scratch space
        # Hardcode at 30G
        # TODO: Make configurable
        # Make it, format it, copy in the base_image 
        self.working_space_image = self.app_config['imgdir'] + "/working-space-image-" + str(builder.target_image.identifier)
        self.create_ext2_image(self.working_space_image)

        # Modify the libvirt_xml used with Oz to contain a reference to a second "working space" disk image
        working_space_device = parameters.get('working_space_device', 'vdb')
        self.add_disk(libvirt_doc, self.working_space_image, working_space_device)

        self.log.debug("Updated domain XML with working space image:\n%s" % (libvirt_xml))

        # We expect to find a partial TDL document in this parameter - this is what drives the
        # tasks performed by the utility image
        if 'utility_customizations' in parameters:
            self.oz_refresh_customizations(parameters['utility_customizations'])
        else:
            self.log.info('No additional repos, packages, files or commands specified for utility tasks')

        # Create a qcow2 image using the original utility image file (which may be read-only) as a
        # backing store.
        self.log.debug("Creating temporary writeable qcow2 working copy of utlity image (%s) as (%s)" % (self.active_image.data, self.utility_image_tmp))
        self.guest._internal_generate_diskimage(image_filename=self.utility_image_tmp, backing_filename=self.active_image.data)

        if input_image_file: 
            # Here we finally involve the actual Base Image content - it is made available for the utlity image to modify
            self.copy_content_to_image(builder.base_image.data, self.working_space_image, input_image_file)
        else:
            # Note that we know that one or the other of these are set because of code earlier
            self.add_disk(libvirt_doc, builder.base_image.data, input_image_device)

        # Run all commands, repo injection, etc specified
        try:
            self.log.debug("Launching utility image and running any customizations specified")
            libvirt_xml = libvirt_doc.serialize(None, 1)
            self.guest.customize(libvirt_xml)
            self.log.debug("Utility image tasks complete")
        finally:
            self.log.debug("Cleaning up install artifacts")
            self.guest.cleanup_install()

        # After shutdown, extract the results
        results_location = parameters.get('results_location', "/results/images/boot.iso")
        self.copy_content_from_image(results_location, self.working_space_image, builder.target_image.data)


    def add_disk(self, libvirt_doc, disk_image_file, device_name):
	devices = libvirt_doc.xpathEval("/domain/devices")[0]
	new_dev = devices.newChild(None, "disk", None)
	new_dev.setProp("type", "file")
	new_dev.setProp("device", "disk")
	source = new_dev.newChild(None, "source", None)
	source.setProp("file", disk_image_file)
	target = new_dev.newChild(None, "target", None)
	target.setProp("dev", device_name)
	target.setProp("bus", self.guest.disk_bus)


    def oz_refresh_customizations(self, partial_tdl):
        # This takes our already created and well formed TDL object with already blank customizations
        # and attempts to add in any additional customizations found in partial_tdl
        # partial_tdl need not contain the <os>, <name> or <description> sections
        # if it does they will be ignored
        # TODO: Submit an Oz patch to make this shorter or a utility function within the TDL class

        doc = lxml.etree.fromstring(partial_tdl)
        self.tdlobj.doc = doc 

        packageslist = doc.xpath('/template/packages/package')
        self.tdlobj._add_packages(packageslist)

        for afile in doc.xpath('/template/files/file'):
            name = afile.get('name')
            if name is None:
                raise Exception("File without a name was given")
            contenttype = afile.get('type')
            if contenttype is None:
                contenttype = 'raw'

            content = afile.text
            if content:
                content = content.strip()
            else:
                content = ''
            self.tdlobj.files[name] = data_from_type(name, contenttype, content)

        repositorieslist = doc.xpath('/template/repositories/repository')
        self.tdlobj._add_repositories(repositorieslist)

        self.tdlobj.commands = self.tdlobj._parse_commands()


    def _init_oz(self):
        # populate a config object to pass to OZ; this allows us to specify our
        # own output dir but inherit other Oz behavior
        self.oz_config = ConfigParser.SafeConfigParser()
        if self.oz_config.read("/etc/oz/oz.cfg") != []:
            self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])
            if "oz_data_dir" in self.app_config:
                self.oz_config.set('paths', 'data_dir', self.app_config["oz_data_dir"])
            if "oz_screenshot_dir" in self.app_config:
                self.oz_config.set('paths', 'screenshot_dir', self.app_config["oz_screenshot_dir"])
        else:
            raise ImageFactoryException("No Oz config file found. Can't continue.")

        # Use the factory function from Oz directly
        try:
            # Force uniqueness by overriding the name in the TDL
            self.tdlobj.name = "factory-build-" + self.active_image.identifier
            self.guest = oz.GuestFactory.guest_factory(self.tdlobj, self.oz_config, None)
            # Oz just selects a random port here - This could potentially collide if we are unlucky
            self.guest.listen_port = self.res_mgr.get_next_listen_port()
        except libvirtError, e:
            raise ImageFactoryException("Cannot connect to libvirt.  Make sure libvirt is running. [Original message: %s]" %  e.message)
        except OzException, e:
            if "Unsupported" in e.message:
                raise ImageFactoryException("TinMan plugin does not support distro (%s) update (%s) in TDL" % (self.tdlobj.distro, self.tdlobj.update) )
            else:
                raise e


    def create_ext2_image(self, image_file, image_size=(1024*1024*1024*30)):
        # Why ext2?  Why not?  There's no need for the overhead of journaling.  This disk will be mounted once and thrown away.
        self.log.debug("Creating disk image of size (%d) in file (%s) with single partition containint ext2 filesystem" % (image_size, image_file))
        raw_fs_image=open(image_file,"w")
        raw_fs_image.truncate(image_size)
        raw_fs_image.close()
        g = guestfs.GuestFS()
        g.add_drive(image_file)
        g.launch()
        g.part_disk("/dev/sda","msdos")
        g.part_set_mbr_id("/dev/sda",1,0x83)
        g.mkfs("ext2", "/dev/sda1")
        g.sync()

    def copy_content_to_image(self, filename, target_image, target_filename):
        self.log.debug("Copying file (%s) into disk image (%s)" % (filename, target_image))
        g = guestfs.GuestFS()
        g.add_drive(target_image)
        g.launch()
        g.mount_options ("", "/dev/sda1", "/")
        g.upload(filename, target_filename)
        g.sync()

    def copy_content_from_image(self, filename, target_image, destination_file):
        self.log.debug("Copying file (%s) out of disk image (%s) into (%s)" % (filename, target_image, destination_file))
        g = guestfs.GuestFS()
        g.add_drive(target_image)
        g.launch()
        g.mount_options ("", "/dev/sda1", "/")
        g.download(filename,destination_file)
        g.sync()

