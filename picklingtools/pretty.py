#!/usr/bin/env python

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


"""Similar to to pprint from the pprint module, but tends to expose
nested tables and lists much better for a human-readable format. For
example:

 >>> from pretty import pretty
 >>> a = {'a':1, 'b':[1,2], 'c':{'nest':None} }
 >>> print a
 {'a': 1, 'c': {'nest': None}, 'b': [1, 2]}
 >>> pretty(a)
{
    'a':1,
    'b':[
        1,
        2
    ],
    'c':{
        'nest':None
    }
}

Note that pretty always sorts the keys.  This is essentially how prettyPrint
works in OpenContainers and prettyPrint works in Midas 2k OpalTables.
NOTE!  This was recently updated to remove the excess spaces:  the
prettyPrint in Python and C++ should print exactly the same (i.e.,
you can use diff with them)
"""

# Make it so we can print out nan and inf and eval them too!
# IMPORTANT!  You need these in your environment before you eval
# any tables so that you can get eval to work.  For example:
# >>> a = float('inf')
# >>> print a
# inf
# >>> x = { 'i' : a }
# >>> print x
# {'i': inf}
# >>> eval(repr(x))
# Traceback (most recent call last):
#   File "<stdin>", line 1, in ?
#   File "<string>", line 0, in ?
# NameError: name 'inf' is not defined
# >>>
# >>> from pretty import *          # grabs inf and nan
# >>>
# >>> eval(repr(x))                 # Now it works!!
# {'i': inf}
inf = float('inf')
nan = float('nan')

from pprint import pprint

supports_numeric = False
try :
    import Numeric
    supports_numeric = True
except :
    pass

# Not until 2.7, keep as plain dict then
try :
    from collections import OrderedDict
except :
    OrderedDict = dict


def indentOut_ (stream, indent) :
    """Indent the given number of spaces"""
    if indent == 0 :
        return
    else :
        stream.write(" "*indent)

    
def prettyPrintDictHelper_ (d, stream, indent, pretty_print=True, indent_additive=4) :
    """Helper routine to print nested dicts and arrays with more structure"""
    
    # Base case, empty table
    entries = len(d)
    if entries==0 :
        stream.write("{ }")
        return

    # Recursive case
    stream.write("{")
    if pretty_print: stream.write('\n')

    # Iterate through, printing each element
    ii=0
    keys = d.keys()
    keys.sort()
    for key in keys :  # Sorted order on keys
        if pretty_print : indentOut_(stream, indent+indent_additive)
        stream.write(repr(key)+":")
        value = d[key]
        specialStream_(value, stream, indent, pretty_print, indent_additive)
        if entries>1 and ii!=entries-1 :
            stream.write(",")
        if pretty_print: stream.write('\n')
        ii += 1
        
    if pretty_print : indentOut_(stream, indent)        
    stream.write("}")



# TODO: What should the default of OTab pretty print be?
# o{ 'a': 1, 'b':1 } 
# ['a':1, 'b':2]
# OrderedDict([('a',1), ('b':2)])
# Easiest right now is o{ }, but will revisit
# I also like odict() instead of dict.
OTabEmpty=[ "OrderedDict([])", "o{ }","OrderedDict([])" ]
OTabLeft =[ "OrderedDict([", "o{", "[" ]
OTabRight=[ "])", "}", "]" ]
# OC_DEFAULT_OTAB_REPR = 1
if not "OC_DEFAULT_OTAB_REPR" in dir() :
   OC_DEFAULT_OTAB_REPR  = 1
OTabRepr = OC_DEFAULT_OTAB_REPR;

# To change the printing of OrderedDict
# import pretty
# pretty.OTabRepr = 0

def prettyPrintODictHelper_ (d, stream, indent, pretty_print=True, indent_additive=4) :
    """Helper routine to print nested dicts and arrays with more structure"""
    global OTabRepr
    # Base case, empty table
    entries = len(d)
    if entries==0 :
        stream.write(OTabEmpty[OTabRepr]) # "o{ }"
        return

    # Recursive case
    stream.write(OTabLeft[OTabRepr]) # "o{"
    if pretty_print: stream.write('\n')

    # Iterate through, printing each element
    ii=0
    keys = d.keys()
    for key in keys :  # Insertion order on keys
        if pretty_print : indentOut_(stream, indent+indent_additive)
        if OTabRepr == 0 :
            stream.write("("+repr(key)+", ")
        else :
            stream.write(repr(key)+":")
        value = d[key]
        specialStream_(value, stream, indent, pretty_print, indent_additive)
        if OTabRepr == 0 :
            stream.write(")")
            
        if entries>1 and ii!=entries-1 :
            stream.write(",")
        if pretty_print: stream.write('\n')
        ii += 1
        
    if pretty_print : indentOut_(stream, indent)        
    stream.write(OTabRight[OTabRepr])  # "}"


def prettyPrintListHelper_ (l, stream, indent, pretty_print=True, indent_additive=4) :
    """Helper routine to print nested lists and arrays with more structure"""
    
    # Base case, empty table
    entries = len(l)
    if entries==0 :
        stream.write("[ ]")
        return
    
    # Recursive case
    stream.write("[")
    if pretty_print: stream.write('\n')

    # Iterate through, printing each element
    for ii in xrange(0,entries) :
        if pretty_print : indentOut_(stream, indent+indent_additive)
        specialStream_(l[ii], stream, indent, pretty_print, indent_additive)
        if entries>1 and ii!=entries-1 :
            stream.write(",")
        if pretty_print: stream.write('\n')

    if pretty_print : indentOut_(stream, indent); 
    stream.write("]")



def prettyPrintStringHelper_ (s, stream, indent, pretty_print=True, indent_additive=4):
    """Helper routine to print strings"""
    stream.write(repr(s))

# List of special pretty Print methods
OutputMethod = { str           :prettyPrintStringHelper_,
                 OrderedDict   :prettyPrintODictHelper_,
                 dict          :prettyPrintDictHelper_,
                 list          :prettyPrintListHelper_
               }

def formatHelp_ (format_str, value, strip_all_zeros=False) :
    s = format_str % value
    # All this crap: for complex numbers 500.0+0.0j should be 500+0
    # (notice it strips all zeros for complexes) 
    if strip_all_zeros :
        where_decimal_starts = s.find('.')
        if where_decimal_starts == -1 :
            return s   # all done, no 0s to strip after .
        where_e_starts = s.find('E')
        if where_e_starts == -1 :  # no e
            where_e_starts = len(s)
        dot_to_e = s[where_decimal_starts:where_e_starts].rstrip('0')
        if len(dot_to_e)==1 : # just a .
            dot_to_e = ""
        return s[:where_decimal_starts]+dot_to_e+s[where_e_starts:]
    else :
        if not ('E' in s) and s.endswith('0') and '.' in s:
            s = s.rstrip('0')
            if s[-1]=='.' : s+='0'
    return s

def NumericString_ (typecode, value) :
    """ floats need to print 7 digits of precision, doubles 16"""
    if typecode == 'f'   :
        return formatHelp_("%#.7G", value)
    
    elif typecode == 'd' :
        return formatHelp_("%#.16G", value)
    
    elif typecode == 'F' :
        front = '('+formatHelp_("%#.7G", value.real, strip_all_zeros=True)
        if value.imag==0 :
            front += "+0j)"
        else :
            front += formatHelp_("%+#.7G", value.imag, strip_all_zeros=True)+"j)"
        return front
        
    elif typecode == 'D' :
        front = '('+formatHelp_("%#.16G", value.real, strip_all_zeros=True)
        if value.imag==0 :
            front += "+0j)"
        else :
            front += formatHelp_("%+#.16G", value.imag, strip_all_zeros=True)+"j)"
        return front
    
    else :
        return str(value)
    
def specialStream_ (value, stream, indent, pretty_print, indent_additive) :
    """Choose the proper pretty printer based on type"""
    global OutputMethod
    type_value = type(value)
    if type_value in OutputMethod:  # Special, indent
        output_method = OutputMethod[type_value]
        indent_plus = 0;
        if pretty_print:indent_plus = indent+indent_additive
        output_method(value, stream, indent_plus, pretty_print, indent_additive)
    elif supports_numeric and type_value == type(Numeric.array([])) :
        stream.write('array([')
        l = value.tolist()
        typecode = value.typecode()
        for x in xrange(0,len(l)) :
            r = NumericString_(typecode, l[x])
            stream.write(r)
            if x<len(l)-1 : stream.write(",")
        stream.write('], '+repr(value.typecode())+")")
    elif type_value in [float, complex] : 
        typecode = { float: 'd', complex: 'D' }
        stream.write(NumericString_(typecode[type_value], value))
    else :
        stream.write(repr(value))

import sys

def pretty (value, stream=sys.stdout, starting_indent=0, indent_additive=4) :
    """Output the given items in such a way as to highlight
    nested structures of Python dictionaries or Lists.  By default,
    it prints to sys.stdout, but can easily be redirected to any file:
    >>> f = file('goo.txt', 'w')
    >>> pretty({'a':1}, f)
    >>> f.close()
    """
    indentOut_(stream, starting_indent)
    pretty_print = 1
    specialStream_(value, stream, starting_indent-indent_additive, pretty_print, indent_additive)
    if type(value) in [list, dict, OrderedDict] :
        stream.write('\n')


if __name__=="__main__":
    # Test it
    import sys
    a = [1, 'two', 3.1]
    pretty(a)
    pretty(a,sys.stdout,2)
    pretty(a,sys.stdout,2,2)

    pretty(a)
    pretty(a,sys.stdout,1)
    pretty(a,sys.stdout,1,1)

    t = {'a':1, 'b':2}
    pretty(t)
    pretty(t,sys.stdout,2)
    pretty(t,sys.stdout,2,2)

    pretty(t)
    pretty(t,sys.stdout,1)
    pretty(t,sys.stdout,1,1)

