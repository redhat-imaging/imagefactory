#!/usr/bin/env python
# encoding: utf-8

import unittest
from basebuilder import BaseBuilder

class BaseBuilderTestCase(unittest.TestCase):
	def setUp(self):
		self.builder = BaseBuilder(None, None, None, None)

	def test_something(self):
		self.assert_(self.builder, 'No builder was created...')
			
	
###    
if __name__ == '__main__':
	unittest.main()