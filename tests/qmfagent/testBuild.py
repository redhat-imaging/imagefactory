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


import unittest
from xml.dom import minidom
from qmfagent.Build import BuildAdaptor
from builder import *

class testBuild(unittest.TestCase):
	def setUp(self):
		self.tdl_string = """\
		<image>
		  <name>f14jeos</name>
		  <os>
		    <name>Fedora</name>
		    <version>14</version>
		    <arch>x86_64</arch>
		    <install type='url'>
		      <url>http://download.fedoraproject.org/pub/fedora/linux/releases/14/Fedora/x86_64/os/</url>
		    </install>
		  </os>
		  <description>Fedora 14</description>
		</image>
		"""
		# dom_tdl = minidom.parseString(tdl_string)
	
	# def testInstantiateBuilder(self):
	# 	build_adaptor = BuildAdaptor(self.tdl_string, None, None, None)
	# 	self.assert_(build_adaptor._builder.__class__ == FedoraBuilder.FedoraBuilder)
	# 
    
if __name__ == '__main__':
	unittest.main()