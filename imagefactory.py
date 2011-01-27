#!/usr/bin/env python
# encoding: utf-8

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

import os
import sys
import signal
import argparse
import json
import logging
from qmfagent.ImageFactoryAgent import *


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
    
    def configuration():
        doc = "The configuration property."
        def fget(self):
            return self._configuration
        def fset(self, value):
            self._configuration = value
        def fdel(self):
            del self._configuration
        return locals()
    configuration = property(**configuration())
    
    def arguments():
        doc = "The arguments property."
        def fget(self):
            return self._arguments
        def fset(self, value):
            self._arguments = value
        def fdel(self):
            del self._arguments
        return locals()
    arguments = property(**arguments())
    
   
    def __new__(cls, *p, **k):
    	if cls.instance is None:
    		cls.instance = object.__new__(cls, *p, **k)
    	return cls.instance
    
    def __init__(self):
        super(Application, self).__init__()        
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/var/log/imagefactory.log')
                        
        self.configuration = {}
        self.arguments = self.parse_arguments()
                
        if (self.arguments):
            config_file_path = self.arguments.config
            if (os.path.isfile(config_file_path)):
                try:
                    config_file = open(config_file_path)
                    self.configuration = json.load(config_file)
                except IOError, e:
                    logging.exception(e)
            argdict = self.arguments.__dict__
            for key in argdict.keys():
                self.configuration[key] = argdict[key]
                        
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def parse_arguments(self):
        argparser = argparse.ArgumentParser(description='System image creation tool...', prog='imagefactory')
        argparser.add_argument('--version', action='version', version='%(prog)s 0.1', help='Version info')
        argparser.add_argument('-v', '--verbose', action='store_true', default=False, help='Set verbose logging.')
        argparser.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
        argparser.add_argument('--config', default='/etc/imagefactory.conf', help='Configuration file to use. (default: %(default)s)')
        argparser.add_argument('--output', default='/tmp', help='Store built images in location specified. (default: %(default)s)')
        subparsers = argparser.add_subparsers(dest='command', title='commands')
        command_qmf = subparsers.add_parser('qmf', help='Provide a QMFv2 agent interface.')
        command_qmf.add_argument('--broker', default='localhost', help='URL of qpidd to connect to. (default: %(default)s)')
        command_build = subparsers.add_parser('build', help='NOT YET IMPLEMENTED: Build specified system and exit.')
        command_build.add_argument('--template', help='Template file to build from.')
        return argparser.parse_args()
    
    def setup_logging(self):
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/var/log/imagefactory.log')
        if (self.arguments and self.arguments.debug):
            logging.getLogger('').setLevel(logging.DEBUG)
        elif (self.arguments and self.arguments.verbose):
            logging.getLogger('').setLevel(logging.INFO)
    
    def signal_handler(self, signum, stack):
        """docstring for sigterm_handler"""
        if (signum == signal.SIGTERM):
            logging.warn('caught signal SIGTERM, stopping...')
            if (self.qmf_agent):
                self.qmf_agent.shutdown()
            sys.exit(0)
    
    
    # TODO: sloranz@redhat.com - add code here to set the user:group we're running as and drop privileges
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
        if (self.configuration['command'] == 'qmf'):
            if (self.daemonize()):
                self.setup_logging()
                logging.info("Launching daemon...")
                self.qmf_agent = ImageFactoryAgent(self.configuration['broker'])
                self.qmf_agent.run()
    


if __name__ == "__main__":
    application = Application()
    sys.exit(application.main())
