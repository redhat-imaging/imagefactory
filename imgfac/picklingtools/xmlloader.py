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
   The reader will take and translate the XML into appropriate
   Val data structures.  This is appropriate for Key-Value documents,
   where the tags and attributes translate readily to key-value pairs
   of dictionaries.

   Examples:

     <book attr1="1" attr2="2">
        <chapter>text chap 1</chapter>
        <chapter>text chap 2</chapter>
     </book>
   
   becomes
    { 'book' : {
          '__attrs__' : { 'attr1':"1", 'attr2':"2" },
          'chapter' : [ 'text chap 1', 'text chap 2']
    }
"""

import sys
# Not until 2.7, keep as plain dict then
try :
    from collections import OrderedDict
except :
    OrderedDict = dict

# We want to use literal_eval, but it may not be available
try :
    from ast import literal_eval  # Safe: just can handle standard literals
    def safe_eval (s) :
        """This does an safe eval(i.e., ast.literal_eval): but literal_eval
        doesn't like whitespace,so this strips the whitespace before"""
        a = s.strip()
        return literal_eval(a)
    some_eval = safe_eval
except :
    # Set XML_NO_WARN in your global to avoid this warning
    # XML_NO_WARN = 1
    # import xmlloader
    if not ("XML_NO_WARN" in globals()) :
        print "*Warning: This version of Python doesn't support ast.literal_eval, so XML_LOAD_EVAL_CONTENT can be an unsafe option in malicious input/XML"
    some_eval = eval   # Warning: May be unsafe if malicious user code

# Parser of single characters
from parsereader import *

# The way to handle POD data
from arraydisposition import *


###################### OPTIONS for XML -> dictionaries

#  ATTRS (attributes on XML nodes) by default becomes
#  separate dictionaries in the table with a 
#  "__attrs__" key.  If you choose to unfold, the attributes
#  become keys at the same level, with an underscore.
#  (thus "unfolding" the attributes to an outer level).
#  
#  For example:
#    <book attr1="1" attr2="2>contents</book>
#  WITHOUT unfolding  (This is the DEFAULT)
#    { 'book' : "contents",
#      '__attrs__' : {'attr1'="1", "attr2"="2"}
#    }
#  WITH unfolding:  (Turning XML_LOAD_UNFOLD_ATTRS on)
#    { 'book' : "contents",
#      '_attr1':"1", 
#      '_attr2':"2", 
#    }
XML_LOAD_UNFOLD_ATTRS = 0x01


#  When unfolding, choose to either use the XML_PREPEND character '_'
#  or no prepend at all.  This only applies if XML_LOAD_UNFOLD_ATTRS is on.
#    <book attr1="1" attr2="2>contents</book>
#  becomes 
#   { 'book': "content", 
#     'attr1':'1',
#     'attr2':'2'
#   }
#  Of course, the problem is you can't differentiate TAGS and ATTRIBUTES 
#  with this option 
XML_LOAD_NO_PREPEND_CHAR = 0x02

#  If XML attributes are being folded up, then you may
#  want to prepend a special character to distinguish attributes
#  from nested tags: an underscore is the usual default.  If
#  you don't want a prepend char, use XML_LOAD_NO_PREPEND_CHAR option
XML_PREPEND_CHAR = '_'


#  Or, you may choose to simply drop all attributes:
#  <book a="1">text<book>
#    becomes
#  { 'book':'1' } #  Drop ALL attributes
XML_LOAD_DROP_ALL_ATTRS = 0x04

#  By default, we use Dictionaries (as we trying to model
#  key-value dictionaries).  Can also use ordered dictionaries
#  if you really truly care about the order of the keys from 
#  the XML
XML_LOAD_USE_OTABS = 0x08

#  Sometimes, for key-value translation, somethings don't make sense.
#  Normally:
#    <top a="1" b="2">content</top>
#  .. this will issue a warning that attributes a and b will be dropped
#  becuase this doesn't translate "well" into a key-value substructure.
#    { 'top':'content' }
# 
#  If you really want the attributes, you can try to keep the content by setting
#  the value below (and this will supress the warning)
#  
#   { 'top': { '__attrs__':{'a':1, 'b':2}, '__content__':'content' } }
#  
#  It's probably better to rethink your key-value structure, but this
#  will allow you to move forward and not lose the attributes
XML_LOAD_TRY_TO_KEEP_ATTRIBUTES_WHEN_NOT_TABLES = 0x10

#  Drop the top-level key: the XML spec requires a "containing"
#  top-level key.  For example: <top><l>1</l><l>2</l></top>
#  becomes { 'top':[1,2] }  (and you need the top-level key to get a 
#  list) when all you really want is the list:  [1,2].  This simply
#  drops the "envelope" that contains the real data.
XML_LOAD_DROP_TOP_LEVEL = 0x20

#  Converting from XML to Tables results in almost everything 
#  being strings:  this option allows us to "try" to guess
#  what the real type is by doing an Eval on each member:
#  Consider: <top> <a>1</a> <b>1.1</b> <c>'string' </top>
#  WITHOUT this option (the default) -> {'top': { 'a':'1','b':'1.1','c':'str'}}
#  WITH this option                  -> {'top': { 'a':1, 'b':1.1, 'c':'str' } }
#  If the content cannot be evaluated, then content simply says 'as-is'.
#  Consider combining this with the XML_DUMP_STRINGS_BEST_GUESS
#  if you go back and forth between Tables and XML a lot.
#  NOTE:  If you are using Python 2.6 and higher, this uses ast.literal_eval,
#         which is much SAFER than eval.  Pre-2.6 has no choice but to use
#         eval.
XML_LOAD_EVAL_CONTENT = 0x40

# Even though illegal XML, allow element names starting with Digits:
# when it does see a starting digit, it turns it into an _digit
# so that it is still legal XML
XML_TAGS_ACCEPTS_DIGITS = 0x80


#  When loading XML, do we require the strict XML header?
#  I.e., <?xml version="1.0"?>
#  By default, we do not.  If we set this option, we get an error
#  thrown if we see XML without a header
XML_STRICT_HDR = 0x10000




class XMLLoaderA(object) :
  """Abstract base class: All the code for parsing the letters one by
     one is here.  The code for actually getting the letters (from a
     string, stream, etc.) defers and uses the same framework as the
     OCValReader and the OpalReader (so that we can handle
     context for syntax errors)."""


  def __init__ (self, reader, options,
                array_disposition=ARRAYDISPOSITION_AS_LIST,
                prepend_char=XML_PREPEND_CHAR,
                suppress_warnings_when_not_key_value_xml=False) : # XMLDumper.CERR_ON_ERROR construct
      # // ///// Data Members
      # ReaderA* reader_;                 // Defer I/O so better syntax errors
      # int options_;                     // | ed options
      # HashTable<char> escapeSeqToSpecialChar_; // XML escape sequences
      # string prependChar_;              // When unfolding, prepend char
      # bool suppressWarning_;            // The warnings can be obnoxious
      
      """*The ReaderA* handles IO (from file, stream or string).
      *The options are or'ed in:  XML_LOAD_CONTENT | XML_STRICT_HDR: 
       see all the options above (this controls most XML loading features).  
      *The array_disposition tells what to do with Numeric arrays: AS_LIST
       turns them into lists, whereas both AS_NUMERIC and AS_PYTHON_ARRAY
       turn them into true POD arrays (there's no difference in this
       context: it makes more sense in Python when there are multiple POD
       array choices).
      *The prepend_char is what to look for if folding attributes (see above).
      *When problems loading, do we output an error to cerr or not."""
      self.reader_ = reader
      self.options_= options
      self.arrayDisp_ = array_disposition
      self.escapeSeqToSpecialChar_ = { }
      self.prependChar_ = prepend_char
      self.suppressWarning_ = suppress_warnings_when_not_key_value_xml

      if array_disposition==ARRAYDISPOSITION_AS_NUMERIC :
          # If we support Numeric, immediately construct and use those
          import Numeric
          self.array_type = type(Numeric.array([],'i'))
          self.array = Numeric.array
      else :
          # Otherwise, use the wrapper which looks like Numeric
          from simplearray import SimpleArray as array
          self.array_type = array
          self.array = array
                    
      # Low over constructor
      self.escapeSeqToSpecialChar_ = { 
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&apos;": "\'",
        "&quot;": "\"", 
      }

  def EOFComing () :
      "Look for EOF"
      return self.reader_.EOFComing()
  

  def expectXML (self) :
      """ Reads some XML and fills in result appropriately.  TODO: Still need
      to handle namespaces."""
      # Initial parsing into simpler IM 
      self._handleXMLDeclaration()
      name_attrs_content = [] 
      self._expectElement(name_attrs_content, False)
      # return name_attrs_content
    
      # Turn name_attrs_content into more "familiar' dicts
      result = self._tableType()
      self._fillInOutput(name_attrs_content, result) # fill in result
      post_result = self._postProcessListsOflist(result)
      final_result = self._dropTop(post_result)
      return final_result
  
  # ###### Helper methods

    # Choose whether we use OTabs or Tabs for dictionaries
  def _tableType (self, attrsp=None) :
      if self.options_ & XML_LOAD_USE_OTABS :
          return OrderedDict()
      else :
          return dict()

  # May or may not have an XML declaration: 
  #  <?xml version="1.0" encoding="UTF-8"?> or
  # <?xml version="1.0"?>
  # Really, all we support is version 1.0 and UTF-8.  And we don't
  # have to have the header.
  def _handleXMLDeclaration (self) :
      cc = self._peekNWSChar()
      if cc!='<':
          self._syntaxError("No top level for XML? Content without tags")
          
      self._getNWSChar()
      cc = self._peekChar()
      if cc==EOF :
          self._syntaxError("Premature EOF")

      # Look for XML Declaration
      if cc=='?' :
          self._expectString("Error during XML declaration", "?xml")
          xml_decl_attrs = { }
          self._getAttributeTable(xml_decl_attrs)
          if "version" in xml_decl_attrs and xml_decl_attrs["version"]!="1.0" :
              self._syntaxError("Can't handle any XML other than version 1.0")
      
          if ("encoding" in xml_decl_attrs and
              xml_decl_attrs["encoding"]!="UTF-8") :
              self._syntaxError("Can't handle any XML encodings other than UTF-8")
      
          self._expectString("Error during XML declaration", "?>")
          self._consumeWS()
    
      # Nope, just saw a < which starts some tag
      else :
          if (self.options_ & XML_STRICT_HDR) :
              self._syntaxError("No XML header (i.e., <?xml ... ?> on XML")
      
          self._pushback('<')

      # handle comments just after
      #while self._peekStream("<!--") :
      #    self._consumeComment()
      #    self._consumeWS()
      while 1 :
          if self._peekStream("<!") :
              if self._peekStream("<!--") :
                  self._consumeComment()
                  self._consumeWS()
              else :
                  self._consumeDTD()
                  self._consumeWS()
          else :
              break

  def _syntaxError (self, s) :
      # centralized syntax error handling
      self.reader_.syntaxError(s)
    
  def _XMLNotKeyValueWarning (self, name, output):
      if self.suppressWarning_ : 
         return
  
      mesg = "Warning: the given input XML has content interspersed\n" \
      "with keys and values:  the last content (and nesting will override\n"\
      "content) seen will become the value, but this kind of XML is not good\n"\
      "for just key-value pairs. Some info may be lost."
      sys.stderr.write(mesg + "\n")
      sys.stderr.write("name:"+name+'\n')
      sys.stderr.write("output:"+repr(output)+'\n')
      sys.stderr.write("... Continuing with best effort ...\n")

  def _XMLAttributesWithPrimitiveContentWarning (self, tag, value, output) :
      if self.suppressWarning_ :
         return
    
      mesg = "Warning: the given input XML has attributes interspersed with\n"\
      "primitive content:  To preserve the primitivenes of the data,\n"\
      "the attributes will been dropped from the data. Please revisit\n"\
      "your data format to avoid this situation so the data is more\n"\
      "key-value centric."
      sys.stderr.write(mesg+'\n')
      sys.stderr.write(" tag:"+tag+'\n')
      sys.stderr.write(" value:"+repr(value)+'\n') 
      sys.stderr.write(" output:"+repr(output)+'\n')
      sys.stderr.write(" ... Continuing with best effort ...\n")

  def _arrayPODWarning (self): 
      if self.suppressWarning_ :
          return  
      mesg = ""\
      "Trying to build an ArrayPOD list, but mismatched type__ attributes:\n" \
      "(or other attributes?) continuing with first definition";
      sys.stderr.write(mesg+'\n') 
      sys.stderr.write(" ... Continuing with best effort ...\n")
      
  # Drop the top level key, if it makes sense
  def _dropTop (self, result) :
      # Drop the top
      if (self.options_ & XML_LOAD_DROP_TOP_LEVEL):
           if ((type(result)==OrderedDict or type(result)==dict) and len(result)==1) :
               # We RETURN the dropped top
               for key,value in result.iteritems() :
                   return value
           else :
               if self.suppressWarning_ : 
                   return result
               mesg = ""\
               "Trying to drop the top-level key, but there is no single-top " \
               "level key that makes sense to drop, so not doing it"
               sys.stderr.write(mesg+"\n")
               sys.stderr.write(" ... Continuing with best effort ...\n")
      
      return result  # No change
    
  ######################################################################
  ## take the IM form and turn it into the final results
    
  # Post-processing: if the table has one entry labelled "listx__",
  # then this was a special way for XML->dict() to occur:
  # Basically:
  # { 'top:' [0,1,2] },
  #   becomes
  # <top>
  #  <list__>0</list__>
  #  <list__>1</list__>
  #  <list__>2</list__>
  # </top>
  #  We see this is as:
  #  { 'top': { 'list__': [0,1,2] } }
  #  .... We want to convert this BACK the right way, so we have to 
  #  find all <listx__ keys> and post-process.
  def _postProcessListsOflist (self, child) :
      # Base case
      if type(child)==self.array_type :
          if self.arrayDisp_ == ARRAYDISPOSITION_AS_LIST :
              return child.tolist()
          elif self.arrayDisp_ == ARRAYDISPOSITION_AS_NUMERIC :
              return child   # Could only do this if we supported Numeric
                             # in constructor
          elif self.arrayDisp_ == ARRAYDISPOSITION_AS_PYTHON_ARRAY :
              return child.asarray()
          elif self.arrayDisp_ == ARRAYDISPOSITION_AS_NUMERIC_WRAPPER :
              return child

          
      if type(child)!=OrderedDict and type(child)!=dict and type(child)!=list : 
          # Eval content instead of just strings
          if (self.options_ & XML_LOAD_EVAL_CONTENT) :
              try :
                  temp = some_eval(child)  # May be eval or ast.literal_eval
                  # Only eval "reversible" operations
                  if type(temp)==str :
                      # Then this was a string: the only
                      # way to get here is to have "" match (some whitespace
                      # at end:  "'123'" and "'123' " is legal
                      return temp

                  else :
                      stringized_temp = repr(temp)
                      
                  if (stringized_temp==child.strip()) : 
                      return temp
                  # So, wasn't reversible:  something prevents from being completely
                  # invertible. For many real-valued entries, this is simply
                  # a precision (one too many or too few digits) or a format
                  # thing (1e6 vs. 100000.0).  The ValReader can handle this
                  # by JUST expecting a real or complex, and we can check if there
                  # is "more stuff" on input after a full complex or real evaluation
                  t = type(temp)
                  if t in [float, long, complex] :
                      # temp is a real-valued datapoint: real values are
                      # problematic because of precision issues.
                      splits = child.split()
                      if len(splits)!=1: 
                          # Extra characters, so really not reversible
                          pass
                      else :
                          # So, got all characters as part, so, really just a precision
                          # issue, let's keep reals
                          if (stringized_temp == repr(t(splits[0]))) :
                              return temp
              
              except :
                  # Just ignore, and leave original as is
                  pass
          return child
    
      # Recursive: table
      elif (type(child)==dict or type(child)==OrderedDict) :
          # Recursively descend
          new_child = child.__class__()   # create new prototype with same type
          for key, value in child.iteritems() :
              new_value = self._postProcessListsOflist(value)
              new_child[key] = new_value
      

          # However, A lone list__ in a table is the target audience
          #  or      A lone dict__ in a table is the target audience
          if (len(new_child)==1) :
              found_lone_container = False
              
              for key, value in new_child.iteritems() : # get one and only item
                  if (key[-1]=='_' and key[-2]=='_') :
                      if (key.find("list")==0 and type(value) in [list, self.array_type] ) :
                          found_lone_container = True
	  
                      if (key.find("dict")==0 and type(value) in [dict, OrderedDict]) :
                          found_lone_container = True

                  # Make sure calls to child are cleaned up
                  if found_lone_container :
                      # child.swap(*vp) leaks because contains
                      new_child = value
                    
          # Processed entire dict, returning new_child
          return new_child

      # Recursive: list
      else : # child.tag=='n' subtype='Z'
          new_child = []
          for entry in child :
              new_entry = self._postProcessListsOflist(entry)
              new_child.append(new_entry)
          return new_child



  # Specialization for Val code ... slightly more efficient
  def _addValToList (self, content, output) :
    # TODO: this is probably tail-recursive, should iterate
    
    # Assertion: Have a list now
    # output is a list
    
    # Recursively fills in: by default it creates Tabs, so we need
    # to fix up into list.  TODO: Warn about non-empty attributes for lists
    temp=self._tableType()
    self._fillInOutput(content, temp);
    v = temp[content[0]]
    output.append(v)

    # All done
    return output


  # helper for fillingNestedList: After we know output is a 
  # list, we fill it in correctly.  This is really only called 
  # when we are doing the long form of Array<POD> types:
  # <l type__='f'>1</l><l type__='f'>/l>
  def _addToList (self, content, output) :
    # TODO: this is probably tail-recursive, should iterate
        
    # Assertion: Have a Numeric array now
    # Array<T>& l = output;   
    
    # Recursively fills in: by default it creates Tabs, so we need
    # to fix up into list.  TODO: Warn about non-empty attributes for lists
    temp=self._tableType()
    self._fillInOutput(content, temp)
    nested = temp[content[0]]
    t = nested  # will be filled in as some number
    if (type(nested) in [list, self.array_type]) :
      if (output.typecode() != nested.typecode()) :
	self._arrayPODWarning()
      t = nested[0]  # Had type__ tag too
    else :
      t = nested     # forgot type tag, but okay, still can process

    if self.arrayDisp_ != ARRAYDISPOSITION_AS_NUMERIC :
        output.append(t) ### NO APPEND on Numeric Arrays??????
    else :
        import Numeric
        # We have to friggin' do concatenate (Ugh, so O(n^2):  TODO: Fix!
    ##print >> sys.stderr, "************* t is ", t, ' nested is ', nested, '   output is', output
        output = Numeric.concatenate((output, Numeric.array([t], output.typecode()))) # YES, has to be a TUPLE as input to concatenate! SUCK!
    return output
   

  
  # The nested_name is already in the dictionary of output: by XML
  # rules, this needs to become a list.  Then either 
  # is already a list or we need to turn it into one
  def _fillingNestedList (self, content, output) :
  
    # Standard case: Not a list: either content or a dictionary: 
    # needs to be listized! (because we have repeated keys!).
    if ( (not (type(output) in [list, self.array_type])) or
         ((type(output)==self.array_type and (not ("type__" in content[1]))))) : # special:  the longer array pod sequence .. don't convert!

      # Assertion: "output" is either content or dictionary
      output = [output]
  
    # Assertion: "output" is a list ... either POD or Arr:
    # Add in the content
    if type(output)==list :
      return self._addValToList(content, output)
    else :
      return self._addToList(content, output)


  
  # Add in the given key-value pair to the output table.  Because the
  # output may not be a table, we handle this consistently by converting
  # (if the user chooses) that to a table.
  def _addAttrs (self, tag, value, output) :

      # Drop all attributes
      if (self.options_ & XML_LOAD_DROP_ALL_ATTRS) :
          return output

      # More complex: if there is some "non-insertable" content,
      # we either (a) ignore the attrs or (b) turn the content
      # into a table and THEN insert it
      new_output = output
      if (not (type(output)==OrderedDict or type(output)==dict)) :
          if (self.options_ & XML_LOAD_TRY_TO_KEEP_ATTRIBUTES_WHEN_NOT_TABLES) :
              # Otherwise, we have to turn content into a table
              # that contains the content
              new_output = self._tableType()
              new_output["__content__"] = output
          else :
              self._XMLAttributesWithPrimitiveContentWarning(tag,value,output)
              return new_output

      # Assertion: Standard table already there in output, 
      # so easy to just plop this in
      new_output[tag] = value
      return new_output

  
  # Taking the options as presented, figure out how to deal with the
  # attributes.  Do they go in as __attrs__?  Each tag as _ members?
  # Dropped entirely?
  def _addInAttrs (self, attrs, output) :
  
    if (len(attrs)==0) : return output
    if ("type__" in attrs) :
        if (len(attrs)!=1) :
            self._arrayPODWarning_() # TODO: Better warning?
        return output

    # Unfold attributes into table
    if (self.options_ & XML_LOAD_UNFOLD_ATTRS) : 
        # Iterate through all attributes, and add each one to the table
        for orig_key, value in attrs.iteritems() :
	
            # Choose what prepend char is
            key = str(orig_key);
            if (not(self.options_ & XML_LOAD_NO_PREPEND_CHAR)) :
                key = self.prependChar_ + key
	
            output = self._addAttrs(key, value, output)
      
     
    # The DEFAULT is as __attrs__: only do this if we haven't
    # set the unfold
    else :
        output = self._addAttrs("__attrs__", attrs, output)
    
    # All done
    return output


  # ... helper function for when processing arraytype__ 
  def _handlePODArraysHelper (self, output, name_attrs_content, typecode) :
    # print >> sys.stderr, '@@@@@@@@@@@@@@@ typecode is', typecode, '  @@@@ output is', output
    # Set the output, and check a few things
    output = self.array([], typecode) # Array<T>();
    if (len(name_attrs_content)<=2) : return output # No content
    content = name_attrs_content[2]
    string_content = ""
    if (type(content) == str) :
      string_content = str(content)
    elif (type(content)==list and len(content)>0 and type(content[0])==str) :
      string_content = str(content[0])
    elif (type(content)==list and len(content)==0) :
      string_content = ""
    else :
      print >> sys.stderr, content 
      raise Exception("Expecting solely string content for array of POD");
      
    # Assertion: We have a string of stuff, hopefully , separated numbers
    list_of_strings = string_content.split(',')
    if list_of_strings[0] == "" :
        intermediate_list = []
    else :
        intermediate_list = map(eval, list_of_strings)
    output = self.array(intermediate_list, typecode)
    return output


  # TOP-LEVEL: Map to map Val typecodes to Numeric typecodes
  typecodes_map = { 's':'1',
                    'S':'b',
                    'i':'s',
                    'I':'w',
                    'l':'i',
                    'L':'u',
                    'x':'l',
                    'X':'l',
                    'f':'f',
                    'd':'d',
                    'F':'F',
                    'D':'D'
                    }

  # If the attsr contain arraytype__, then the content is a POD
  # array:  Turn this into the proper type!
  def _handlePODArrays (self, name_attrs_content, output) :
    attrs = name_attrs_content[1]
    val_tag = attrs["arraytype__"]
    if val_tag in XMLLoader.typecodes_map :
      return self._handlePODArraysHelper(output, name_attrs_content,
                                         XMLLoader.typecodes_map[val_tag])
    else :
      raise Exception("arraytype__ attribute is not recognized")

  
  # Used when we first see an attribute <type__>
  def _createPODArray (self, value, tag, appending) :
    if tag in XMLLoader.typecodes_map :
      typecode = XMLLoader.typecodes_map[tag]
      if appending :
          a = self.array([eval(value)], typecode)
      else :
          a = self.array([], typecode)
      return a
    else :
      raise Exception("Don't support lists of anything but POD")
    
      
  # We have seen attrs("type__") == "list", so we have to be careful
  # parsing this thing
  def _handleAttributeTypeOfList (self, look) :
  
      # Returned with something that SHOULD be a list: most of the
      # time this means turning the nested thing into a list
      #//cout << "Got type list ... here's what I got:" << look << endl;
      if (type(look)==list) :
          # already a list, don't have to do anything
          pass
      elif ((type(look)==dict or type(look)==OrderedDict) and len(look)==0) :
          look = []
      else :
          look = [ look ]
    
      return look

  # helper; check to see if a "type__" tag is a legal one
  def _type__fillIn_ (self, type_tag, content, appending) :
      # Tag so we will create a  BRAND NEW minted Array POD!
      tag = None
      stag = str(type_tag)
      if len(stag)>0 : tag = stag[0]

      if stag=="list" :
          result = []
          if appending :
              result.append(content)
      elif len(stag)!=1 or not (stag[0] in "silxfdSILXFDb") :
          print sys.stderr, "Unknown tag '"+stag+"' .. ignoring "
          result = content
      else :
          result = self._createPODArray(content, tag, appending)
      return result


  # MAIN ENTRY:
  # Centralize all the output options for the given XML here.
  # Once we have parsed all the nessary parsed XML, we want to turn
  # it into a much simpler key-value thingee.  Output is assumed to
  # be the "dictionary" to fill in: it shoudl be set to an empty dict
  # by the caller, and it will be filled in by name_attrs_content
  def _fillInOutput (self, name_attrs_content, output) :
  
      # Parsed work here: need to turn into better vals
      name  = str(name_attrs_content[0])
      attrs = name_attrs_content[1]  # should be a table
      # print "name:", name, " attrs:", attrs 

      # Default of no content
      output[name] = self._tableType()
      look = output[name]

      # Arrays of POD content have some special keys to distinguish them:
      # array_type as an attribute
      if ("arraytype__" in attrs) :
          output[name] = self._handlePODArrays(name_attrs_content, look)
          look = output[name]
          if ("type__" in attrs and attrs["type__"]=="list") :
              output[name] = self._handleAttributeTypeOfList(look)
              look = output[name]
          return # TODO: revisit?  To handle listn__ ?
      
      # Special case: type__ tag, empty content
      if ("type__" in attrs) and \
         (len(name_attrs_content)==2 or \
          len(name_attrs_content)==3 and len(name_attrs_content[2])==0) :
          # <tag type__="something"></tag> or
          # <tag type__="something"/> 
          # NOTE: This needs to become a PODArray of empty
          dud = 666
          output[name] = self._type__fillIn_(attrs["type__"], dud, False)
          look = output[name]


      # Figure out which things will be lists, which will be attrs,
      # which will be nested tags.  
      if (len(name_attrs_content)>2) : # Content may be empty because of />
          contents   = name_attrs_content[2]
          # print >> sys.stderr, '****************CONTENTS', contents
          for content in contents :
	
              # Nested content: either needs to become a list or a dict
              if (type(content) == list) : 
                  nested_name = str(content[0])
	  
                  # If name is already there: then this is from an XML list with
                  # repeated entries, so the entry becomes a list
                  if (type(look)!=type("") and nested_name in look) :
                      look[nested_name] = self._fillingNestedList(content, look[nested_name])
	  
	  
                  # Name not there, so we need to insert a new table
                  else :
                      # Already filled in for something: careful, because
                      # we may have content littering the key-value portions
                      if (type(look) == type("")) : # May destroy content  
                          self._XMLNotKeyValueWarning(nested_name, look) 
	    
                      # Force name to be a table ... may destroy content
                      if (type(look)!=OrderedDict and type(look)!=dict) :
                          output[name] = self._tableType()
                          look = output[name]
                          
                      self._fillInOutput(content, output[name])
	  
  
              # Plain primitive content
              elif (type(content) == type("")) :
                  # print >> sys.stderr,  '****************** primitive content', content
                  if ("type__" in attrs) : # special key means Array<POD>, List
                      output[name] = \
                          self._type__fillIn_(attrs["type__"], content, True)
                      look = output[name]
                      
                  else :
                      # print >> sys.stderr, '**************primitive type: look is ', look, type(look)
                      t_look = type(look)
                      if ((t_look in [list,self.array_type] and len(look)==0) or
                          ((t_look==OrderedDict or t_look==dict) and len(look)>0)) :
                          self._XMLNotKeyValueWarning(name, content)
	    
	              output[name] = content  # TODO: Swap?
	              look = output[name]

              else :
                  self._syntaxError("Internal Error?  Malformed XML");
	

      # print >> sys.stderr,  '************ look is', look, ' ** output[name] is', output[name]
      # print >> sys.stderr,  '       ....  output is', output

      # POST_PROCESSING
      
      # Adding a tag of "type__"="list" means we want to make sure
      # some single element lists are tagged as lists, not tables
      if ("type__" in attrs and attrs["type__"]=="list") :
          output[name] = self._handleAttributeTypeOfList(look)
          look = output[name]

      # We want to do it AFTER we have processed all tags, as we want to
      # always *PREFER* tags so that if there might be an unfold of attributes,
      # we don't step on a real tag.
      output[name] = self._addInAttrs(attrs, look)
      look = output[name]

      # print >> sys.stderr,  '************ look is', look, ' ** output[name] is', output[name]
      # print >> sys.stderr,  '       ....  output is', output
      # done


  ##############################################################
  # Most of the routines from here PARSE the XML into a simpler
  # IM form which we then operate on and turn into more familiar
  # dicts

  # Expect a string of particular chars
  def _expectString (self, error_message_prefix, string_to_expect) :
      # 
      for some_char in string_to_expect :
          xc = self._getChar()
          char_found = xc
          char_look  = some_char
          if (xc==EOF) : 
            self._syntaxError(str(error_message_prefix)+ \
                           ":Premature EOF while looking for '"+char_look+"'")
      
          elif (char_look != char_found) :
            self._syntaxError(str(error_message_prefix)+ \
                              ":Was looking for '"+ \
                              char_look+"' but found '"+char_found+"'")
  

  # Expect some characters in a set: if not, throw error with message
  def _expect (self, message, one_of_set) :      
      # Single character token
      get      = self._getNWSChar()
      expected = -1
      for one in one_of_set :
          if (get==one) : 
              expected = one

      if (get!=expected) :
          get_string = ""
          if (get==EOF) :
              get_string="EOF"
          else :
              get_string=get
          self._syntaxError("Expected one of:'"+one_of_set+ \
                            "', but saw '"+get_string+"' " \
                            "on input during "+message)
      return get


  # Look for the ending character, grabbing everything
  # in between.  Really, these are for XML escapes
  def _expectUntil (self, end_char) :
      ret = []
      while (1) :
          ii = self._getChar()
          if (ii==EOF) :
              cc = end_char
              self._syntaxError("Unexpected EOF before "+str(cc)+" encountered")

          c = ii
          ret.append(c)

          if (c==end_char) :
              name = "".join(ret) # make string from all elements
              if (len(name)>1 and name[1] == '#') : # Numeric char. references
                  if (len(name)>2 and (str.lower(name[2])=='x')) : # hex number
                      if len(name)<=4 : # Not really legal ... &#x;
                          self._syntaxError("Expected some digits for hex escape sequence")
                      if len(name)>19 :
                          self._syntaxError("Too many digits in hex escape sequence")
                      # Every digit must be hex digit
                      hexdigits = "0123456789abcdef"
                      hexme = 0
                      for ii in xrange(3, len(name)-1) :
                          dig = str.lower(name[ii])
                          if not(dig in hexdigits) :
                              self._syntaxError("Expected hex digits only in escape sequence")
                          value = str.find(hexdigits, dig)
                          hexme = hexme* 16 + value
                      # if hexme==0 : syntaxError("Can't have \x0 on input") # ridiculous
                      # all done accumulating hex digits
                      # Since only do UTF-8 for now, truncate
                      return chr(hexme)
                  else : # decimal number
                      #decimal_number = int(name[2:])
                      #unicode = decimal_number
                      #return str(unicode)
                      self._syntaxError("Missing x for escape sequence")
	  
              special_char = '*' # just something to shut up compiler
              if name in self.escapeSeqToSpecialChar_ :
                  return self.escapeSeqToSpecialChar_[name] 
              else :
                  self._syntaxError("Unknown XML escape sequence:"+name)


      
  # Simply get the name, everything up to whitespace
  def _getElementName (self) :
      name = [] # Array appends better than string
    
      # Makes sure starts with 'a..ZA..Z_/'
      ii = self._getChar()
      if (ii==EOF) : self._syntaxError("Unexpected EOF inside element name")
      c = ii
      if (c.isdigit()) :
          if self.options_ & XML_TAGS_ACCEPTS_DIGITS == 0:
              self._syntaxError("element names can't start with '"+str(cc)+"'")
          else :
              name.append('_')
      elif (not(c.isalpha() or ii=='_' or ii=='/')) :
          cc = str(c)
          self._syntaxError("element names can't start with '"+str(cc)+"'")
    
      name.append(c)

      # .. now, make sure rest of name contains _, A..Za..Z, numbers
      while (1) :
          ii = self._peekChar()
          if (ii==EOF) : break
          c = ii
          if (c.isalnum() or c=='_') :
              self._getChar()
              name.append(c)
          else :
              break
      
      return "".join(name) # flatten [] to string


  # Get the attribute="value" names.  Expect "value" to be surrounded
  # by either " or ' quotes.
  def _getKeyValuePair (self) :
      
      # Simple name
      key = self._getElementName()
      self._consumeWS()
      #char the_equals  = 
      self._expect("looking at key:"+key, "=")
      self._consumeWS()
      which_quote = self._expect("looking at key:"+key, "\"'");

      # Follow quotes until see new one.  TODO:  look for escapes?
      value = None
      value_a = []
      while (1) :
          ii = self._getChar()
          if (ii==EOF) : 
              self._syntaxError("Unexpected EOF parsing key:"+key)
          elif (ii==which_quote) :
              value = "".join(value_a)
              break
          elif (ii=='&') : # start XML escape sequence 
              esc = self._expectUntil(';')
              for s in esc: # Most likely single char
                  value_a.append(s)
          else :
              value_a.append(ii)

      return (key, value)



  #  Assumption: We are just after the ELEMENT_NAME in "<ELEMENT_NAME
  #  att1=1, ... >" and we are looking to build a table of attributes.
  #  TODO: Should this be a list?
  def _getAttributeTable (self, attribute_table) :
      
      # The attribute list may be empty
      ii = self._peekNWSChar()
      c = ii
      if ('>'==c or '/'==c or '?'==c or EOF==ii) : return

      # Expecting something there
      while (1) :
          self._consumeWS()
          (key, value) = self._getKeyValuePair()
          attribute_table[key] = value

          self._consumeWS()
          ii = self._peekChar()
          c = ii;
          if ('>'==c or '/'==c or '?'==c or EOF==ii) : return
  

  def _isXMLSpecial (self, c) :
      return c=='<'


  # Expect a tag: starts with a < ends with a >.  If there is an
  # attribute list, will be the second element.  
  def _expectTag (self, a) :
      is_empty_tag = False

      # Expecting '<' to start
      self._expect("looking for start of tag", "<")
    
      # Assumption: Saw and got opening '<'.  Get the name
      element_name = self._getElementName()
      a.append(element_name)
    
      # Assumption: Got the < and NAME.  Now, Get the list of attributes
      # before the end of the '>'
      a.append({})  # attribute table ALWAYS a tab
      attribute_table = a[-1]
      self._getAttributeTable(attribute_table)
    
      # Assumption: End of list, consume the ">" or "/>"
      ii = self._peekNWSChar()
      if (EOF==ii) :
          self._syntaxError("Unexpected EOF inside tag '"+element_name+"'")
    
      if (ii=='/') :
          self._expect("empty content tag", "/")
          is_empty_tag = True
    
      self._expect("looking for end of tag"+element_name, ">")

      # End of list, make sure its well formed
      if (is_empty_tag and len(element_name)>0 and element_name[0]=='/') :
          self._syntaxError(
              "Can't have a tag start with </ and end with"
              "/> for element:"+element_name)

      return is_empty_tag


  # Expect a string of base content.  Collect it until you reach a
  # special character which ends the content ('<' for example).
  def _expectBaseContent (self, content) :
      ret = []
      while (1) :
          c = self._peekChar()
          if (c==EOF) : 
              return
          elif ('&'==c) :
              entity = self._expectUntil(';'); # Handles escapes for us
              for character in entity :
                  ret.append(character)
               
          elif (not self._isXMLSpecial(c)) :
              c = self._getChar()
              ret.append(c)
          else :
              # We have a '<':  is it a comment or start of a tag?
              if self._peekStream("<!--") :
                  self._consumeComment()
                  continue
	
              return_content = content + "".join(ret)
              return return_content


  #  [ 'book',                         // name 
  #    {'attr1': "1", 'attr2'="2"},    // table of attributes
  #    ["content"]                     // actual content
  #  ]                  
  #  
  #  If content is nested:
  #  <book attr1="1" attr2="2">
  #      <chapter>text chap 1</chapter>
  #      <chapter>text chap 2</chapter>
  #  </book>
  # 
  #  becomes
  # 
  #  [ 'book',  
  #    {'attr1'="1" 'attr2'="2"},
  #    [ ... ]
  #  ] 
  #  where [ ... ] is 
  #  [ ['chapter', {}, ["text chap 1"]], ['chapter', {}, ["text chap 2"]] ]
  # 
  #  We are starting with a beginning <tag> and we will return the table
  #  up to the end </tag>.  In other words, the next character we expect
  #  to see is a '<'.  This return the tag for the element, and fills
  #  in the element with some composite container (based on the options).
  def _expectElement (self, element, already_consumed_begin_tag=False) :
      
      # Get '<' NAME optional_attribute_list '>', put NAME, attr_list in
      if (not already_consumed_begin_tag) :
          tag_and_attrs = []
          is_empty_tag = self._expectTag(element)
          if (is_empty_tag): return
          
      tag_name = element[0] # Name always at front element

      # Assumption, consumed < NAME atr_list '>' of ELEMENT.
      # Everything that follow is content until we hit the </theendtag>
    
      # The content is a list of possibly nested ELEMENTs
      element.append([]) 
      content = element[-1]

      while (1) :
      
          whitespace = self._consumeWSWithReturn()  # always a string

          # We immediately see a <, is nested tag or end tag?
          ci = self._peekChar()
          if (ci == EOF) : self._syntaxError("Premature EOF?")
          c = ci
          if ('<' == c) : # Immediately saw <

              # May be comment!
              if (self._peekStream("<!--")) :
                  self._consumeComment()
                  continue
      
              
              # Get next tag 
              new_tag = []
              is_empty_tag = self._expectTag(new_tag)
              new_tag_name = new_tag[0]  # name always at front of list
	
              # Check for / to see if end tag
              if (len(new_tag_name)>0 and new_tag_name[0]=='/') :
                  if (new_tag_name[1:]==tag_name) : # saw end tag
                      return  # all good!
                  else :
                      self._syntaxError(
                          "Was looking for an end tag of '"+tag_name+
                          "' and saw an end tag of '"+new_tag_name+"'")
	  
	

              # This is a nested XML start tag
              else : 
                  content.append(new_tag)
                  nested_element = content[-1]
                  if (not is_empty_tag) : 
                      self._expectElement(nested_element, True) # already consumed tag!
      
          # No <, so it must be some content which we collect
          else :
              base_content = whitespace
              return_content = self._expectBaseContent(base_content)
              content.append(return_content)

  

  # If we see the given string as the next characters on the
  # input, return true.  Otherwise, false.  Note, we leave the
  # stream exactly as it is either way.
  def _peekStream (self, given) :
      # Holding area for stream as we peek it
      hold = [0 for x in xrange(len(given))]

      # Continue peeking and holding each char you see
      peeked_stream_ok = True
      length = len(given)
      ii = 0
      while ii<length :
          ci = self._getChar()
          hold[ii] = ci;
          if ci==EOF or ci!=given[ii] :
              peeked_stream_ok = False
              break
          ii += 1
      
      if peeked_stream_ok: ii-=1 # All the way through .. okay!

      # Restore the stream to its former glory
      jj = ii
      while jj>=0 :
          self._pushback(hold[jj]);
          jj -= 1
  
      return peeked_stream_ok
  


  # Assumes next four characters are <!--: a comment is coming.  
  # When done, stream reads immediately after comment ending -->
  def _consumeComment (self) :
      self._expectString("Expecting <!-- to start comment?", "<!--")
      while 1 :
          ci = self._getChar()
          if ci==EOF: self._syntaxError("Found EOF inside of comment")
          if ci!='-': continue
      
          # Saw a - ... looking for ->
          ci = self._getChar()
          if ci==EOF : self._syntaxError("Found EOF inside of comment")
          if ci!='-' : continue

          # Saw second - ... looking for >
          while 1 :
              ci = self._getChar()
              if ci==EOF : self._syntaxError("Found EOF inside of comment")
              if ci=='-' : continue  # Saw enough --, keep going
              if ci=='>' : return       # All done! Consumed a comment
              break  # Ah, no - or >, start all over looking for comment
          

  # Currently don't handle DTDs; just throw them away
  def _consumeDTD (self) :
      
      self._expectString("Expecting <! to start a DTD", "<!")
      while (1) :
          # You can have comments and NESTED DTDs in these things, ugh
          if (self._peekStream("<!")) :
              if (self._peekStream("<!--")) :
                  self._consumeComment()
              else :
                  self._consumeDTD()
                  
          # End of is just >
          ci = self._getChar()
          if (ci==EOF) : self._syntaxError("Found EOF inside of <!")
          if (ci=='>') : return


  # Plain whitespace, no comments
  def _consumeWSWithReturn (self) :
      retval = ""
      while (1) :
          cc = self._peekChar()
          if (cc==EOF) : break
          if (cc.isspace()) :
              retval = retval + cc
              self._getChar()
              continue
          else :
              break
      
      return retval





  # A derived class implements these methods to read characters from
  # some input source.
  def _getNWSChar(self)    : return self.reader_._getNWSChar() 
  def _peekNWSChar(self)   : return self.reader_._peekNWSChar()
  def _getChar(self)       : return self.reader_._getChar() 
  def _peekChar(self)      : return self.reader_._peekChar() 
  def _consumeWS(self)     : return self.reader_._consumeWS()
  def _pushback(self, pushback_ch) : return self.reader_._pushback(pushback_ch)

# XMLLoaderA



# Helper class to handle reading strings from an XML string
class XMLStringReader_ (StringReader) :

      def __init__(self, seq) :
          StringReader.__init__(self, seq) 

      # Return the index of the next Non-White Space character.
      # The default string reader handles # comments, which is NOT
      # what we want.  In fact, comments in XML are really only in
      # one syntactic place, so actually expect them explicitly when
      # reading them, otherwise, we don't expect them at all.
      # Return the index of the next Non-White Space character.
      def _indexOfNextNWSChar (self) : 
          length = len(self.buffer_)
          cur = self.current_
          if (cur==len) : return cur;
          while (cur<len and self.buffer_[cur].isspace()) :
              cur +=1 
          return cur


class XMLLoader (XMLLoaderA) :
      """ The XMLLoader reads XML from strings """

      def __init__(self, seq, options,
                   array_disposition=ARRAYDISPOSITION_AS_LIST, 
                   prepend_char=XML_PREPEND_CHAR,
                   suppress_warnings_when_not_key_value_xml=False) :
        """Create an XML loader from the given sequence"""
        XMLLoaderA.__init__(self, XMLStringReader_(seq), options,
                            array_disposition,
                            prepend_char, 
                            suppress_warnings_when_not_key_value_xml)



# Helper class for reading XML ASCII streams
class XMLStreamReader_(StreamReader) :
  
  def __init__(self, istream) :
    StreamReader.__init__(self, istream) 
    
  # This routines buffers data up until the next Non-White space
  # character, ands returns what the next ws char is _WITHOUT
  # GETTING IT_.  It returns (c, peek_ahead) where peek_ahead is
  # used to indicate how many characters into the stream you need
  # to be to get it (and c is the char)
  def _peekIntoNextNWSChar (self) :
    peek_ahead = 0   # This marks how many characters into the stream we need to consume
    while (1) :
      # Peek at a character either from the cache, or grab a new char
      # of the stream and cache it "peeking" at it.
      c = '*'
      if (peek_ahead >= len(self.cached_)) :
        c = self.is_.read(1)
        self.cached_.put(c)
      else :
        c = self.cached_.peek(peek_ahead)

      # Look at each character individually
      if (c==EOF) :
        # We never consume the EOF once we've seen it
        return (c, peek_ahead)
      elif (c.isspace()) : # whitespace but NOT comments!
        peek_ahead += 1;
        continue
      else :
        return (c, peek_ahead)
      
class StreamXMLLoader(XMLLoaderA) :
  """ Read an XML table from a stream """

  def __init__(self, istream, options,
               array_disposition = ARRAYDISPOSITION_AS_LIST,
               prepend_char=XML_PREPEND_CHAR,
	       suppress_warnings_when_not_key_value_xml=False) :
    """Open the given stream, and attempt to read Vals out of it"""
    XMLLoaderA.__init__(self, XMLStreamReader_(istream), options,
                        array_disposition,
                        prepend_char, suppress_warnings_when_not_key_value_xml)



def ReadFromXMLStream (istream,
                       options = XML_STRICT_HDR | XML_LOAD_DROP_TOP_LEVEL | XML_LOAD_EVAL_CONTENT, # best option for invertibility 
                       array_disposition = ARRAYDISPOSITION_AS_NUMERIC_WRAPPER,
                       prepend_char=XML_PREPEND_CHAR) :
    """Read XML from a stream and turn it into a dictionary.
    The options below represent the 'best choice' for invertibility:
     options=XML_STRICT_HDR | XML_LOAD_DROP_TOP_LEVEL | XML_LOAD_EVAL_CONTENT
    Although AS_NUMERIC_WRAPPER is less compatible, you are not going to lose
    any information."""
    sv = StreamXMLLoader(istream, options, array_disposition,prepend_char,False)
    return sv.expectXML()


def ReadFromXMLFile (filename,
                     options = XML_STRICT_HDR | XML_LOAD_DROP_TOP_LEVEL | XML_LOAD_EVAL_CONTENT, # best options for invertibility 
                     array_disposition = ARRAYDISPOSITION_AS_NUMERIC_WRAPPER,
                     prepend_char=XML_PREPEND_CHAR) :
    """ Read XML from a file and return it as a dictionary (as approp.)
    The options below represent the 'best choice' for invertibility:
     options=XML_STRICT_HDR | XML_LOAD_DROP_TOP_LEVEL | XML_LOAD_EVAL_CONTENT
    Although AS_NUMERIC_WRAPPER is less compatible, you are not going to lose
    any information."""
    ifstream = file(filename, 'r')
    return ReadFromXMLStream(ifstream, options, array_disposition, prepend_char)

import cStringIO
def ConvertFromXML (given_xml_string) :
    """Convert the given XML string (a text string) to a Python dictionary
    and return that.  This uses the most common options that tend to
    make the conversions fully invertible."""
    stream_thing = cStringIO.StringIO(given_xml_string)
    return ReadFromXMLStream(stream_thing)



if __name__ == "__main__" :  # from UNIX shell
  x = XMLLoader("<top>1</top>", XML_LOAD_DROP_TOP_LEVEL)  
  print x.expectXML()
  #xx = { 'top' : { 'lots':1, 'o':2 } }
  #print xx
  #print x._dropTop(xx)
  #xx = { 'top' : [1,2,3] }
  #print xx
  #print x._dropTop(xx)
  #xx = { 'top' : [1,2,3], 'other':1 }
  #print xx
  #print x._dropTop(xx)
  #xx = { 'top': { 'list0__': Numeric.array([0,1,2],'i') } }
  #yy = x._postProcessListsOflist(xx) 
  #print yy

  
