#!/usr/bin/env python

"""A CircularBuffer used to hold elements by value: the end the front
can inserted/deleted in constant time: it can request infinite
Circular buffer (meaning that puts will never over-write read
data)."""

class CircularBuffer(object) :

    def __init__ (self, initial_length=4, infinite=False) :
        """Construct a circular buffer (with buffer length)"""
        # Array<T> buff_;
        # int nextPut_;          // Points where next put will occur
        # int nextGet_;          // Points to where next get will occur
        # bool empty_;           // nextPut_==nextGet is either empty or full
        # bool infinite_;        // Puts into empty cause a doubling
  
        self.buff_ = [None for x in xrange(initial_length)]
        self.nextPut_ = 0
        self.nextGet_ = 0
        self.empty_   = True
        self.infinite_ = infinite


    def empty (self): return self.empty_
    def full (self): return not self.empty_ and self.nextGet_==self.nextPut_
    def infinite (self): return self.infinite_
    def capacity (self): return len(self.buff_)
    def __len__ (self) : 
        if (self.empty()) :
            return 0
        elif (self.full()):
            return self.capacity()
        elif (self.nextGet_>self.nextPut_) :
            return self.capacity()-(self.nextGet_-self.nextPut_)
        else :
            return self.nextPut_-self.nextGet_

    def put (self, c) :
        """Put a single element into the buffer.  If in infinite mode, a put
        into a "full" buffer will cause it to re-expand and double the
        size.  If in finite mode, it will throw a runtime_error."""
        self._checkFullness()
        # Space available, just plop it in
        retval = self.buff_[self.nextPut_] = c
        self.nextPut_ = (self.nextPut_+1) % self.capacity()
        self.empty_ = False
        return retval
    
    def get (self) :
        """Get a single element out of the circular buffer.  If the buffer
        is empty, throw a runtime_error"""
        if (self.empty()) :  # Empty, can't get anything
            raise Exception("Circular Buffer Empty")
        else :       # nextGet always tells us where we are
            c = self.buff_[self.nextGet_];
            self.nextGet_ = (self.nextGet_+1) % self.capacity()
            self.empty_ = (self.nextGet_ == self.nextPut_)
        return c

    def peek (self, where=0) :
        """Peek at the nth element (element 0 would be the first thing "get"
        would return, element 1 would be the next).  Throws the
        runtime_error exception if try to peek beyond what the buffer
        has.  This does NOT advance the circular buffer: it only looks
        inside."""
        if (where<0 or where>=len(self)) :
            m = "Trying to peek beyond the end of the Circ. Buff"
            raise Exception(m)
        index = (self.nextGet_+where) % self.capacity()
        return self.buff_[index]
    


    def consume (self, n) :
        """This implements performing "n" gets, but in O(1) time.  If asked
        to consume more elements that the CircularBuffer contains, a
        runtime_error will be thrown."""
        if (n<0 or n>len(self)) :
            m = "Trying to consume more data than in Circ. Buff"
            raise Exception(m)
    
        self.empty_ = (n==len(self))
        self.nextGet_ = (self.nextGet_+n) % self.capacity()
  

    def pushback (self, pushback_val) :
        """The "get()" always pulls from one side of the circular buffer:
        Sometimes, you want to be able to pushback some entry
        you just got as if it were never "get()" ed.   This is
        very similar to "put", but it is simply doing it on the other
        side of the circular buffer.  The pushback can fail if the
        queue is full (not infinite mode) with a runtime_error.
        If it is an infiite queue, it will simply re-expand."""

        self._checkFullness()
        # Space available, just plop it in
        self.nextGet_ = (self.nextGet_+self.capacity()-1) % self.capacity()
        retval = self.buff_[self.nextGet_] = pushback_val
        self.empty_ = False
        return retval


    def drop (self) :
        """ Drop the last "put()" as if it never went in: this can throw
        an exception if the buffer is empty."""
        if (self.empty()) : # Empty, can't get anything
            raise Exception("Circular Buffer Empty")
        else :      # nextPut always tells us where we are
            self.nextPut_ = (self.nextPut_+self.capacity()-1) % self.capacity()
            c = self.buff_[self.nextPut_]
            self.empty_ = (self.nextGet_ == self.nextPut_)
        return c
    
    def __str__ (self) :
        """Stringize from front to back"""
        a = []
        next_get = self.nextGet_
        buffer   = self.buff_
        length   = self.capacity()
        for x in xrange(len(self)) :
            a.append(str(buffer[next_get]))
            a.append(" ")
            next_get = (next_get+1) % length
    
        return "".join(a)


    def _checkFullness (self) :
        # Centralize fullness check and re-expansion code
        if (self.full()) : # Circ Buffer Full, expand and remake
            if (not self.infinite()) : 
                raise Exception("Circular Buffer full")
            else :
                # Create a new Circ. Buffer of twice the size
                length = self.buff_.capacity()
                temp = [None for x in xrange(length*2)]

                buffer = self.buffer_
                next_get = self.nextGet_
                for x in xrange(length) :
                    
                    temp[x] =  buffer[next_get]
                    next_get = (next_get+1) % length

                # Install new buffer
                self.buff_    = temp
                self.nextPut_ = length
                self.nextGet_ = 0
                
        # Assertion: new buffer that is no longer full (has space to grow)
        return

    

if __name__ == "__main__" :
    # testing harness
    CB = CircularBuffer
    
    import sys
    if len(sys.argv)>1 :
        temp = sys.stdout
    else :
        import StringIO
        temp = StringIO.StringIO()
    
    def CBstat(c, temp) :
        print >> temp, "empty:", c.empty(), " full:", c.full(), " len(c):", len(c), " capacity:", c.capacity()
        print >> temp, c

    # Below is the output as you'd cut and patse it: for difflib purposes,
    # we want this to be a list of things
    expected_output_as_cut_and_paste = """\
empty: True  full: False  len(c): 0  capacity: 3

empty: False  full: False  len(c): 1  capacity: 3
100 
100
empty: True  full: False  len(c): 0  capacity: 3

empty: False  full: True  len(c): 3  capacity: 3
1 2 3 
Circular Buffer full
empty: False  full: True  len(c): 3  capacity: 3
1 2 3 
empty: False  full: False  len(c): 2  capacity: 3
2 3 
empty: True  full: False  len(c): 0  capacity: 1

empty: False  full: True  len(c): 1  capacity: 1
4 
Circular Buffer full
empty: False  full: True  len(c): 1  capacity: 1
4 
4
empty: True  full: False  len(c): 0  capacity: 1

empty: True  full: False  len(c): 0  capacity: 2

empty: False  full: False  len(c): 1  capacity: 2
8 
empty: False  full: True  len(c): 2  capacity: 2
8 9 
Circular Buffer full
empty: False  full: True  len(c): 2  capacity: 2
8 9 
8
empty: False  full: False  len(c): 1  capacity: 2
9 
9
empty: True  full: False  len(c): 0  capacity: 2

"""
    expected_output = expected_output_as_cut_and_paste.split('\n')

    a = CB(3)
    CBstat(a, temp)
    a.put(100)
    CBstat(a,temp)
    print >> temp, a.get()
    CBstat(a,temp)

    a.put(1)
    a.put(2)
    a.put(3)
    CBstat(a,temp)

    try :
        a.put(666)
    except Exception, e :
        print >> temp, e
    CBstat(a,temp)

    a.get()
    CBstat(a,temp)


    b = CB(1)
    CBstat(b, temp)
    b.put(4)
    CBstat(b, temp)
    try :
        b.put(666)
    except Exception, e :
        print >> temp, e
    CBstat(b, temp)
    print >> temp, b.get()
    CBstat(b, temp)

    
    b = CB(2)
    CBstat(b, temp)
    b.put(8)
    CBstat(b, temp)
    b.put(9)
    CBstat(b, temp)
    try :
        b.put(666)
    except Exception, e :
        print >> temp, e
    CBstat(b, temp)
    print >> temp, b.get()
    CBstat(b, temp)
    print >> temp, b.get()
    CBstat(b, temp)


    # Finish up early if we just want the output: if we
    # have any argument
    if temp == sys.stdout :
        sys.exit(0)

    # Otherwise, show the diff
    actual_output = temp.getvalue().split('\n')
    temp.close()
    if (expected_output == actual_output) :
        print 'All tests PASSED'
        sys.exit(0) # good!
    else :
        import difflib 
        for line in difflib.context_diff(expected_output, actual_output, fromfile="expected_output", tofile="actual_output", lineterm="") :
            # sys.stdout.write(line)
            print line
        sys.exit(1)  # bad
        
