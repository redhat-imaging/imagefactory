#  Copyright (c) 2001-2009 Rincon Research Corporation, Richard T. Saunders
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#  1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#  3. The name of the author may not be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
#  IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
#  OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
#  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
#  NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
#  THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
////////////////////////////////// ArrayDisposition_e ////////////////
// Different kinds of POD (Plain Old Data: int_1, int_2, real_4, etc.) arrays: 
// there are essentially 4 different types of POD arrays that might be moving 
// around: 
//
// (1) a = [1,2,3]  
//     Python styles lists (which are inefficient for storing 
//     homogeneous data)
//
// (2) import array; a = array.array('i',[1,2,3])
//     the arrays from the Python module array 
//     Unfortunately, they pickle different from 2.6 to 2.7, so we
//     prefer not to use these.
//   
// (3) import Numeric: a = Numeric.array([1,2,3], 'i')
//     the Numeric arrays which are built in to XMPY,
//     but most standard Pythons do not have it installed.
//
// (4) import numpy; a = numpy.array([1,2,3], dtype=numpy.int32)
//     numpy is an external package, but a reasonably de-facto
//     standard (replacing Numeric)
//
// In C++, POD arrays are handled as Array<T>, thus (2) & (3) & (4)
// are handled with the same:  (1) is handled as the C++ Arr.  
// These distinctions are more important if you are in Python, or talking 
// to a Python system, as you have to specify how a C++ Array
// converts to a Python POD array.
//
// These 4 distinctions are made because Python doesn't deal
// well with POD (plain old data) arrays well:  This option allows
// you to choose what you want when dealing with POD when you
// convert between systems.  Consider:
// (1) Python style lists work, but are horribly inefficient for
//     large arrays of just plain numbers, both from a storage
//     perspective or accessing.  Also, you "lose" the fact 
//     that this is true POD array if you go back to C++.
// (2) Numeric is old, but handles all the different types well,
//     including complex (although Numeric doesn't deal with int_8s!).
//     It is also NOT a default-installed package: you may have to find
//     the proper RPM for this to work.
// (3) Python array from the array module are default but have issues:
//     (a) can't do complex data 
//     (b) may or may not support int_8
//     (c) pickling changes at 2.3.4 and 2.6, so if you are
//        3 pickling with protocol 2, you may have issues.
// (4) NumPy arrays are well-supported and pretty much the de-facto
//     standard.  Their only real drawback is that they are not
//     necessarily installed by default, but most likely they are
//
// NUMERIC_WRAPPER is for the XML classes, but unsupported elsewhere.
//
// None of these solutions is perfect, but going to NumPy will
// probably fix most of these issues in the future.
/////////////////////////////////////////////////////////////////////
"""

# Different kinds of Arrays: there are essentially 3 different types
# of arrays that might be moving arround: Python styles lists (which
# are inefficient for storing homogeneous data), the arrays from the
# Python module array (which doesn't work well with Pickling until
# sometime after 2.3.4), and the Numeric arrays which is built in to
# XMPY, but most standard Pythons do not have it installed.
ARRAYDISPOSITION_AS_NUMERIC = 0
ARRAYDISPOSITION_AS_LIST = 1
ARRAYDISPOSITION_AS_PYTHON_ARRAY = 2   # New feature
ARRAYDISPOSITION_AS_NUMERIC_WRAPPER = 3   
ARRAYDISPOSITION_AS_NUMPY = 4   # New feature


