#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2010-2011 Red Hat, Inc.
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

import sys
import os
import signal
import logging
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.qmfagent.ImageFactoryAgent import *

class Application(object):
    instance = None
    
    def qmf_agent():
        doc = "The qmf_agent property."
        def fget(self):
            return self._qmf_agent
        def fset(self, value):
            self._qmf_agent = value
        def fdel(self):
            del self._qmf_agent
        return locals()
    qmf_agent = property(**qmf_agent())
    
    
    def __new__(cls, *p, **k):
    	if cls.instance is None:
    		cls.instance = object.__new__(cls, *p, **k)
    	return cls.instance
    
    def __init__(self):
        super(Application, self).__init__()        
        # logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s')
        self.daemon = False
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.app_config = ApplicationConfiguration().configuration
    
    def setup_logging(self):
        if (self.app_config['foreground']):
            logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s')
        else:
            logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/var/log/imagefactory.log')
        if (self.app_config['debug']):
            logging.getLogger('').setLevel(logging.DEBUG)
        elif (self.app_config['verbose']):
            logging.getLogger('').setLevel(logging.INFO)
    
    def signal_handler(self, signum, stack):
        """docstring for sigterm_handler"""
        if (signum == signal.SIGTERM):
            logging.warn('caught signal SIGTERM, stopping...')
            if (self.qmf_agent):
                self.qmf_agent.shutdown()
            sys.exit(0)
    
    
    # TODO: (redmine 273) - add code here to set the user:group we're running as and drop privileges
    def daemonize(self): #based on Python recipe 278731
        UMASK = 0
        WORKING_DIRECTORY = '/'
        IO_REDIRECT = os.devnull
                
        try:
            pid = os.fork()
        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)
                
        if (pid == 0):
            os.setsid()
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
            try:
                pid = os.fork()
            except OSError, e:
                raise Exception, "%s [%d]" % (e.strerror, e.errno)
            
            if (pid == 0):
                os.chdir(WORKING_DIRECTORY)
                os.umask(UMASK)
            else:
                os._exit(0)
        else:
            os._exit(0)
                
        for file_descriptor in range(0, 2): # close stdin, stdout, stderr
            try:
                os.close(file_descriptor)
            except OSError:
                pass # The file descriptor wasn't open to begin with, just ignore
                
        os.open(IO_REDIRECT, os.O_RDWR)
        os.dup2(0, 1)
        os.dup2(0, 2)
                
        return(True)
    
    
    def main(self):
        if (self.app_config['qmf']):
            if (not self.app_config['foreground']):
                self.daemon = self.daemonize()
            
            self.setup_logging()
            if(self.daemon):
                logging.info("Launched as daemon...")
            elif(self.app_config['foreground']):
                logging.info("Launching in foreground...")
            else:
                logging.warning("Failed to launch as daemon...")
            
            self.qmf_agent = ImageFactoryAgent(self.app_config['broker'])
            self.qmf_agent.run()
        else:
            self.setup_logging()
    


if __name__ == "__main__":
    application = Application()
    sys.exit(application.main())
