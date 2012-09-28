#!/bin/env python

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
  The tools here allow us to 
  (1) translate from XML to Val/Tar/Arr using xmlreader.h
  (2) translate from Val/Tab/Arr to XML using xmldumper.h
 
  The basic premise of these tools is that you are using
  XML as key-value pairs, and thus translating between
  dictionaries and XML is straight-forward.  In the
  following example, there is an obvious mapping between 
  dictionaries and XML:
 
    <book attr1="1" attr2="2">
       <chapter>text chap 1</chapter>
       <chapter>text chap 2</chapter>
    </book>
  
  ----------------------------------
  
   { 'book' = {
         '__attrs__' = { 'attr1':"1", 'attr2':"2" }
         'chapter' = [ 'text chap1', 'text chap2']
   }
 
  Adding attributes complicates the issues: many of the options
  below help control how the attributes in XML gets translated.
  The examples below showing UNFOLDING (or not) of attributes
  
  <html>
    <book attr1="1" attr2="2">
      <chapter> chapter 1 </chapter>
      <chapter> chapter 2 </chapter>
    </book>
  </html>
  ----------------------------------------
  { 'html': {           
       'book': {
          '_attr1':"1",     <!--- Attributes UNFOLDED -->
          '_attr2':"2",
          'chapter': [ 'chapter1', 'chapter2' ]
       }
  }
   or
  { 'html' : {
       'book': {
          '__attrs__': { 'attr1'="1", 'attr2'="2" },  <!-- DEFAULT way -->
          'chapter' : [ 'chapter1', 'chapter2' ]
       }
    }
  }


  ** Example where XML really is better:
  ** This is more of a "document", where HTML is better (text and
  key-values are interspersed)
  <html>
    <book attr1="1" attr2="2">
      This is the intro
      <chapter> chapter 1 </chapter>
      This is the extro
    </book>
  </html>
  
  {
    'book': { 
       'chapter': { ???
       }
    }
  }
  
  ???? ['book'] -> "This is the intro" or "This is the outro?"
  NEITHER.  It gets dumped, as book is a dictionary.
  This is an example where converting from XML to Dictionaries
  may be a bad idea and just may not be a good correspondance.


  Options are formed by 'or'ing together. 
"""

from xmlloader import *
from xmldumper import *
