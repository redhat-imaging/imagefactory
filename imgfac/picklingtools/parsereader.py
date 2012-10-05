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


from circularbuffer import * # used for context

class Context_(object) :
    """
     A helper class that keeps track of where we are within the parsing:
     allows us to return better error messages from parsing the tabs.
     """

    def __init__(self, keep_last_n_lines=5) :
        """Create a Parsing Context and remember the last n lines for when
        error messages happen"""
        self.contextLines_ = keep_last_n_lines
        self.data_ = CircularBuffer(1024)
        self.lineNumber_ = 1
        self.charNumber_ = 0

    # // When holding the data, we make the "keeping context" operations
    # // cheap, but when we need to actually supply the information, it's
    # // a little more expensive, as we have to look for line breaks, etc.
    #
    # int contextLines_;  // how lines of context to hold (i.e., how much do we
    #                     // buffer)
    # CircularBuffer<char> data_;  
    #                     // The current "context", i.e., that last few lines 
    # int lineNumber_;    // Current line number we are on
    # int charNumber_;   // current character within that line

  
    def addChar (self, c) :
        """ Add a character to the context """
        #  Notice the \n so we can notice when new lines begin
        if (c=='\n') :
            self.lineNumber_ += 1
            self.charNumber_  = 0
            
        # Keep the last 1024 or so characters
        if (self.data_.full()) :
            self.data_.get()
        self.data_.put(c)
        self.charNumber_ += 1
        

    def deleteLastChar (self) :
        """Delete a character from the context"""
        c = self.data_.drop();
        # Notice the \n so we can notice when new lines begin
        if (c=='\n') :
            self.lineNumber_ -= 1
            # Find last \n ... if we can
            index_of_last_newline = -1
            for ii in xrange(0, len(self.data_)) :
                if (self.data_.peek(len(self.data_)-ii-1)=='\n') :
                    index_of_last_newline = ii
                    break   
      
            self.charNumber_ = index_of_last_newline
            if (index_of_last_newline==-1) : self.charNumber = 80
        else :
            self.charNumber_-=1;


    # Add from this buffer, the amount of data
    def addData (self, buffer, len) :
        for ii in xrange(0,len) :
            self.addChar(buffer[ii])
            

    # Generate a string which has the full context (the last n lines)
    def generateReport (self) :
      
        report = ""

        # Post processing: Create an array of the lines of input.  The
        # last line probably won't end with an newline because the error
        # probably happened in the middle of the line.
        lines = []
        current_line = ""
        for ii in xrange(0, len(self.data_)) :
            c = self.data_.peek(ii)
            current_line = current_line + c
            if (c=='\n') :
                lines.append(current_line)
                current_line = ""
                
        if (current_line != "") :
            current_line = current_line + '\n'
            lines.append(current_line)


        # Only take the last few lines for error reporting
        context_lines = self.contextLines_
        if (len(lines) < self.contextLines_) : context_lines = len(lines)

        if (context_lines) :
            start_line = len(lines)-context_lines

            report = "****Syntax Error on line:"+str(self.lineNumber_)+\
                     " Last "+str(context_lines)+ " line"
            if (context_lines!=1) :
                report = report + "s"
            report = report + " of input (lines "+ \
                     str(start_line+1)+"-"+str(start_line+context_lines)+") "\
                     "shown below****\n"

            for ii in xrange(0, context_lines) :
                report = report + "  " + lines[start_line+ii]
      
            # Show, on last line, where!
            cursor = "-"*(self.charNumber_+1) + "^\n"
            report = report + cursor

        # All done
        return report
  

    def syntaxError (self, s) :
        """Have everything do a syntax error the same way"""
        report = self.generateReport() + s
        raise Exception, report

# A meta-object that is not a string so we can compare against it
EOF = "" # None 
        
class ReaderA(object) :
    """Interface for all Readers parsing ASCII streams.  They all have a
    context for holding the current line numbers for error reporting
    purposes."""

    def __init__ (self) :
        self.context_ = Context_()
        
    def syntaxError (self, s) : self.context_.syntaxError(s)
    def EOFComing (self) :      return self._peekNWSChar()==EOF
    
    def _getNWSChar (self)  : pass
    def _peekNWSChar (self) : pass
    def _getChar (self)     : pass
    def _peekChar (self)    : pass
    def _consumeWS (self)   : pass
    def _pushback (self, pushback_char) : pass

    
class StringReader (ReaderA) :
    """A class to read directly from strings (or any class that supports
    [] and len)"""

    def __init__ (self, input) :
        """Allows to read and parse around anything that can be indexed"""
        ReaderA.__init__(self) # call parent
        # print '************************* input = ', input, type(input)
        self.buffer_ = input   # this is any thing that can be indexed
        self.current_ = 0
    
    # Return the index of the next Non-White Space character.  This is
    # where comments are handled: comments are counted as white space.
    # The default implementation treats # and \n as comments
    def _indexOfNextNWSChar (self) :
        length=len(self.buffer_)
        cur = self.current_
        if (cur==length) : return cur
        # Look for WS or comments that start with #
        comment_mode = False
        while cur<len :
            if (comment_mode) :
                if (self.buffer_[cur]=='\n') : comment_mode = False
                continue
            else :
                if (self.buffer_[cur].isspace()) : continue
                elif (self.buffer_[cur]=='#') :
                    comment_mode = True
                    continue
                else :
                    break
        # All done
        return cur

  
    # Get a the next non-white character from input
    def _getNWSChar(self) :
        index = self._indexOfNextNWSChar()

        # Save all chars read into 
        old_current = self.current_
        self.current_ = index
        self.context_.addData(self.buffer_[old_current:],
                              self.current_-old_current)

        return self._getChar()
  
    # Peek at the next non-white character
    def _peekNWSChar(self) :
        index = self._indexOfNextNWSChar()
        if (index>=len(self.buffer_)) : return EOF
        c = self.buffer_[index]
        return c

    # get the next character
    def _getChar(self) :
        length=len(self.buffer_)
        if (self.current_==length) : return EOF
        
        c = self.buffer_[self.current_] # avoid EOF/int-1 weirdness
        self.current_ += 1
        self.context_.addChar(c)

        # Next char
        return c
  
    # look at the next char without getting it
    def _peekChar(self) : 
        length=len(self.buffer_)
        if (self.current_==length) : return EOF
        c = self.buffer_[self.current_] # avoid EOF/int-1 weirdness
        return c

    # Consume the next bit of whitespace
    def _consumeWS(self) :
        index = self._indexOfNextNWSChar()
        
        old_current = self.current_
        self.current_ = index
        self.context_.addData(self.buffer_[old_current:],
                              self.current_-old_current)
        
        if (index==len(self.buffer_)): return EOF
        c = self.buffer_[index]  # avoid EOF/int-1 weirdness
        return c


    # The pushback allows just a little extra flexibility in parsing:
    # Note that we can only pushback chracters that were already there!
    def _pushback(self, pushback_char) :
        # EOF pushback
        if (pushback_char==EOF) :
            if (self.current_!=len(self.buffer_)) :
                self.syntaxError("Internal Error: Attempt to pushback EOF when not at end")
            else :
                return

        if (self.current_<=0) :
            print "*********************current is", self.current_, self.buffer_
            self.syntaxError("Internal Error: Attempted to pushback beginning of file")
        # Normal char pushback
        else :
            self.current_ -= 1
            if (self.buffer_[self.current_]!=pushback_char) :
                # print "** pushback_char", pushback_char, " buffer", buffer_[current_]
                self.syntaxError("Internal Error: Attempt to pushback diff char")

        self.context_.deleteLastChar()





class StreamReader (ReaderA) :
    """A StreamReader exists to read in data from an input stream  """

    def __init__ (self, istream) :
        """ Open the given file, and attempt to read Vals out of it"""
        ReaderA.__init__(self) # call parent
        self.is_ = istream
        self.cached_ = CircularBuffer(132, True) 


    # istream& is_;
    # CircularBuffer<int> cached_;

    # This routines buffers data up until the next Non-White space
    # character, ands returns what the next ws char is _WITHOUT
    # GETTING IT_.  It returns (c, "peek_ahead") where peek_ahead to
    # indicate how many characters into the stream you need to be to
    # get it.

    # This is the default implementation that treats # and \n as comments
    def _peekIntoNextNWSChar (self) :
        peek_ahead = 0  # This marks how many characters into the stream we need to consume
        start_comment = False
        while (1) :
            # Peek at a character either from the cache, or grab a new char
            # of the stream and cache it "peeking" at it.
            c = ''
            if (peek_ahead >= len(self.cached_)) :
                c = self.is_.read(1)
                self.cached_.put(c);
            else :
                c = self.cached_.peek(peek_ahead)

            # Look at each character individually
            if (c==EOF) :  # EOF
                # We never consume the EOF once we've seen it
                return (c, peek_ahead)
            elif (start_comment) : 
                peek_ahead+=1
                start_comment = (c!='\n')
                continue
            elif (c=='#') : 
                peek_ahead+=1
                start_comment = True
                continue
            elif (c.isspace()) : # white and comments
                peek_ahead+=1
                continue
            else :
                return (c, peek_ahead)


    # Get the next Non White Space character
    def _getNWSChar (self) :
        (_, peek_ahead) = self._peekIntoNextNWSChar()
      
        for ii in xrange(0, peek_ahead) :
            cc_ii = self.cached_.peek(ii);
            if (cc_ii != EOF) :  # Strange EOF char NOT in context!
                self.context_.addChar(cc_ii)
      
        self.cached_.consume(peek_ahead)
  
        return self._getChar() # This will handle syntax error message buffer for char
  

    # Look at but do not consume the next NWS Char
    def _peekNWSChar (self) : 
        (c, _) = self._peekIntoNextNWSChar()
        return c

    # get a char
    def _getChar (self) : 
        if (self.cached_.empty()) :
            cc = self.is_.read(1)
        else :
            cc = self.cached_.get()
    
        if (cc!=EOF) :
            self.context_.addChar(cc)
        return cc
  
  
    def _peekChar (self) :
        if (self.cached_.empty()) :
            c = self.is_.read(1)
            self.cached_.put(c)
        return self.cached_.peek()


    def _consumeWS (self) :
        (c,peek_ahead) = self._peekIntoNextNWSChar()
        for ii in xrange(0,peek_ahead) :
            cc_ii = self.cached_.peek(ii)
            if (cc_ii != EOF) :  # Strange EOF char NOT in context!
                self.context_.addChar(cc_ii)
        self.cached_.consume(peek_ahead)
        return c

    def _pushback (self, pushback_char) :
        if (pushback_char != EOF) : self.context_.deleteLastChar()
        self.cached_.pushback(pushback_char)


