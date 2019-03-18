from __future__ import absolute_import
from builtins import object
import guestfs
import sys
import time
import json
import logging
from .FactoryUtils import launch_inspect_and_mount, qemu_convert_cmd, subprocess_check_output
from .ApplicationConfiguration import ApplicationConfiguration
from .PersistentImageManager import PersistentImageManager
from .BaseImage import BaseImage
from oz.ozutil import copyfile_sparse


class BaseImageImporter(object):

    def __init__(self, image_file=None):
        """ 
        @param image_file The name of a local file to be imported as a BaseImage
        """
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.image_file = image_file

    def do_import(self):
        """
        Import file as a base_image and return the resulting BaseImage object
        """

	g = launch_inspect_and_mount(self.image_file, readonly=True)
	inspection = g.inspect_os()

	os_root = inspection[0]

	i_type=g.inspect_get_type(os_root)
	i_name=g.inspect_get_product_name(os_root)
	i_distro=g.inspect_get_distro(os_root)
	i_major_version=g.inspect_get_major_version(os_root)
	i_minor_version=g.inspect_get_minor_version(os_root)

        ins_res = "guestfs inspection result - type: %s - name: %s - distro: %s - major version: %s - minor version: %s" % \
                  (i_type, i_name, i_distro, i_major_version, i_minor_version)
        self.log.debug(ins_res)

	if i_type != "linux":
	    raise Exception("Can only import Linux distros into Factory at the moment")

	if i_distro in [ 'centos', 'rhel', 'scientificlinux' ]:
	    tdl_os_name = "RHEL-%d" % (i_major_version)
	    tdl_os_version = "%d" % (i_minor_version)
	elif i_distro == 'fedora':
	    tdl_os_name = "Fedora"
	    tdl_os_version = "%d" % (i_major_version)
	elif i_distro == 'ubuntu':
	    tdl_os_name = "Ubuntu"
	    tdl_os_version = "%d.%02d" % (i_major_version, i_minor_version)
	elif i_distro == 'debian':
	    tdl_os_name = "Debian"
	    tdl_os_version = "%d" % (i_major_version)
	else:
	    raise Exception("Unsupported distro for import: %s" % (i_distro))

	ftime = time.strftime("%Y-%m-%d--%H:%M:%S", time.localtime())
	tname = "%s-%s-import-%s" % (tdl_os_name, tdl_os_version, ftime)

	tdl_template="""<template>
	  <name>%s</name>
	  <os>
	    <name>%s</name>
	    <version>%s</version>
	    <arch>x86_64</arch>
	    <install type='url'>
	      <url>http://foo.com/imported/image/do/not/use/url</url>
	    </install>
	  </os>
	  <description>image imported on %s</description>
	</template>
	""" % (tname, tdl_os_name, tdl_os_version, ftime)

	pim = PersistentImageManager.default_manager()
	base_image = BaseImage()
	pim.add_image(base_image)
	base_image.template=tdl_template
        # The input image can be in any format that libguestfs understands
        # Here we convert it to qcow2 - If it is already in qcow2 this is benign
        # and in some cases can tidy up and serialize it
        self.log.debug("Converting and saving intput file %s to final data location %s" % \
                       (self.image_file, base_image.data))
        cmd = qemu_convert_cmd(self.image_file, base_image.data)
        (stdout, stderr, retcode) = subprocess_check_output(cmd)
	base_image.status="COMPLETE"
	base_image.percent_complete=100
	pim.save_image(base_image)
        return base_image
