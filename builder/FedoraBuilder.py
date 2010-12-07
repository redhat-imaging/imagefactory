#
# Copyright (C) 2010 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import zope
from ImageBuilderInterface import ImageBuilderInterface
from BaseBuilder import BaseBuilder
import oz.Fedora
import oz.TDL


class FedoraBuilder(BaseBuilder):
	# TODO: sloranz@redhat.com - Flesh out this docstring more to document this module.
	"""docstring for FedoraBuilder"""
	zope.interface.implements(ImageBuilderInterface)
	
# Initializer
	def __init__(self, template, target, uuid=None, credentials=None):
		super(FedoraBuilder, self).__init__(template, target, image_id, credentials)
		self._tdl = oz.TDL(tdl_doc=template)
		self.guest = oz.Fedora.get_class(tdl, None)
	
# Image actions
	def build(self):
		self.guest.cleanup_old_guest()
		self.guest.generate_install_media(force_download)
		try:
		    self.guest.generate_diskimage()
		    try:
		        libvirt_xml = self.guest.install()
		        # if customize:
		        #     guest.customize(libvirt_xml)
		        # if generate_cdl:
		        #     print guest.generate_cdl(libvirt_xml)
		        # else:
		        #     print libvirt_xml
		    except:
		        self.guest.cleanup_old_guest()
		        raise
		finally:
		    self.guest.cleanup_install()
	
	def abort(self):
		pass
	
