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


class IBuilderDelegate(Interface):
	"""Builders should call these methods on their delegate if assigned.
	Subclasses of the BaseBuilder class will get this for free.  Classes
	that conform to the IBuilderDelegate interface can selectively
	implement methods from this interface."""
	
	def builder_will_update_status(self, builder, original_status, new_status):
		"""The builder will update from original_status to new_status."""
	
	def builder_did_update_status(self, builder, original_status, new_status):
		"""The builder updated the status from original_status to new_status."""
	
	def builder_should_update_status(self, builder, original_status, new_status):
		"""Returns whether the builder should update the status from original_status to new_status."""
	
	def builder_will_update_percentage(self, builder, original_percentage, new_percentage):
		"""The builder will update from original_percentage to new_percentage."""
	
	def builder_did_update_percentage(self, builder, original_percentage, new_percentage):
		"""The builder updated from original_percentage to new_percentage."""
	
	def builder_should_update_percentage(self, builder, original_percentage, new_percentage):
		"""Returns whether the builder should update from original_percentage to new_percentage."""
	
