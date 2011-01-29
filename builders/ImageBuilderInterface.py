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

from zope.interface import Interface
from zope.interface import Attribute


class ImageBuilderInterface(Interface):
	# TODO: (redmine 249) - make the comments more useful as external documentation.
	"""This documentation needs to be written.  Should describe the 
	interface that classes must implement to provide image building
	service to the image factory."""
	
	template = Attribute("""The IDL input template definition of the image.""")
	target = Attribute("""The target backend the image is being built for.""")
	image_id = Attribute("""A Universal Unique Identifier for the image.""")

	def status():
		"""Status of the image build process."""
	
	def percent_complete():
		"""Completion percentage for an image build in progress."""
	
	def image():
		"""The image being built."""
	
	def build():
		"""Tell the builder to start building the image."""
	
	def abort():
		"""Tell the builder to stop building the image."""