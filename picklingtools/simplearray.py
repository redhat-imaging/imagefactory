#! /bin/env

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


"""Simple array wrapper: Looks like the Numeric array (with same constructors
   and the like), but implemented as a Python array"""

import array
import pretty
import struct

# Array is very pickly about what fits inside, so we have to
# manually stomp the ranges
TypeRanges = {
  'b': (1, [-128,127,0xff,'b','B',int]),
  'B': (1, [0,255,0xff,'b','B',int]),
  'h': (2, [-32768,32767,0xffff,'h','H',int]),
  'H': (2, [0,65535,0xffff, 'h','H',int]),
  'i': (4, [-2147483648,2147483647, 0xffffffff, 'i', 'I', int]),
  'I': (4, [0, 4294967295, 0xffffffff, 'i', 'I', int]),
  'l': (8, [-9223372036854775808,9223372036854775807, 0xffffffffffffffff, 'l', 'L', int]),
  'L': (8, [0, 18446744073709551615, 0xffffffffffffffff, 'l', 'L', int]),
  'f': (4, [float('-inf'), float("inf"), 0, 'f', 'f', float]),
  'd': (4, [float('-inf'), float("inf"), 0, 'd', 'd', float]),                 
}

# Allow us to convert between Numeric typecodes and "array" typecodes
NumericToArray = {
    '1': ('b',1), 'b':('B',1),
    's': ('h',1), 'w':('H',1),
    'i': ('i',1), 'u':('I',1),
    'l': ('l',1), # 'l':('L',1),
    'f': ('f',1), 'd':('d',1),
    'F': ('f',2), 'D':('d',2), # complex supported but at TWICE the size
}
class SimpleArray(object) :
    """Simple array wrapper that looks like a simple Numeric array,
    but uses Python array underneath.  Not a full implementation, but
    handles complex numbers (unlike array) and also clips overflowing
    values (array likes to throw exceptions if the values are out of range)"""

    def __init__(self, initializing_list, typecode) :
        """Create an Numeric-like array object, using Numeric typecodes"""
        global TypeRanges, NumericToArray
        array_typecode = NumericToArray[typecode][0]
        self.numeric_typecode = typecode
        self.impl = array.array(array_typecode)
        self.complex = (typecode=='F' or typecode=='D')
        for x in initializing_list :
            self.append(x)
            
    def append(self, value) :
        """Append the appropriate item into the list"""
        global TypeRanges, NumericToArray
        a = self.impl
        if self.complex : # complex, append twice!
            if type(value) == complex :
                a.append(value.real)
                a.append(value.imag)
            else :
                a.append(float(value))
                a.append(0.0)
            
        else :
            a.append(self._crop(value))

    def _crop(self, value) :
        # Convert integer values out of range into proper range
        a = [left, right, mask, signed_code, unsigned_code, converter] = TypeRanges[self.impl.typecode][1]
        if value < left or value > right:
            value = value & mask
            if left < 0 :  # Handle signed as C would
                b = struct.pack(unsigned_code, value)
                value = struct.unpack(signed_code, b)[0]
        return converter(value)
        
    def __getitem__(self,ii) :
        a = self.impl
        if self.complex :
            return complex(a[ii*2], a[ii*2+1])
        else :
            return a[ii]

    def __setitem__(self, ii, value) :
        a = self.impl
        if self.complex :
            if type(value)==complex :
                a[ii*2] = value.real
                a[ii*2+1] = value.imag
            else :
                a[ii*2] = float(value)
                a[ii*2+1] = 0.0
        else :
            a[ii] = self._crop(value)

    def __len__ (self) :
        a = self.impl
        if self.complex : return len(a)/2
        return len(a)

    def __str__(self) :
        a = self.impl
        length = len(self)
        out = "array(["
        for ii in xrange(0, length) :
            out += str(self[ii])
            if ii!=length-1 : out += ","
        out += "], "+repr(self.numeric_typecode)+")"
        return out

    def __repr__(self) :
        a = self.impl
        length = len(self)
        numeric_typecode = self.numeric_typecode
        out = "array(["
        for ii in xrange(0, length) :
            out += pretty.NumericString_(numeric_typecode, self[ii]) 
            if ii!=length-1 : out += ","
        out += "], "+repr(numeric_typecode)+")"
        return out

    def __eq__ (self, rhs) :
        if type(rhs) != type(self) : return False
        if len(self)==len(rhs) and self.numeric_typecode==rhs.numeric_typecode :
            for x in xrange(0,len(self)) :
                if self[x] != rhs[x] :
                    return False
            return True
        return False
    
    def toarray (self) :
        """Return the underlying Python array: Note that complex data are
        stored as real, imag pairs in a float array."""
        return self.impl
    def tolist (self) :
        """Convert the array to a Python list"""
        if self.complex :
            result = []
            for x in xrange(0,len(self)) :
                result.append(self[x])
            return result
        else :
            return self.impl.tolist()

    def typecode (self) :
        """Return the typecode as Numeric would"""
        return self.numeric_typecode

if __name__ == "__main__" :
    a = SimpleArray([1,2,3], 'i')
    print a[0]
    print len(a)
    a.append(4)
    print a[3]
    print a
    print repr(a)
    b = SimpleArray([1+2j,3+4j], 'D')
    print b[0]
    print len(b)
    b.append(1)
    b.append(6+7j)
    print b[2]
    print b[3]
    print b
    print repr(b)
