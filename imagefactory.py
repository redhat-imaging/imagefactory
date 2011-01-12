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
import time
import logging
import math
from qmfagent.ImageFactoryAgent import *


img_fac_agent = None


class Arguments(object):
    pass

def signal_handler(signum, stack):
    """docstring for sigterm_handler"""
    if (signum == signal.SIGTERM):
        logging.info('caught signal SIGTERM, stopping...')
        if (img_fac_agent):
            img_fac_agent.shutdown()
        sys.exit(0)


# TODO: sloranz@redhat.com - add code here to set the user:group we're running as and drop privileges
def daemonize(): #based on Python recipe 278731
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


def main(args):
    if (args.qmf):
        daemonize()
    
    logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/var/log/imagefactory.log')
    logging.info("Starting imagefactory...")
    if (args.debug):
        logging.getLogger('').setLevel(logging.DEBUG)
    elif (args.verbose):
        logging.getLogger('').setLevel(logging.INFO)
    else:
        logging.getLogger('').setLevel(logging.WARNING)
    
    signal.signal(signal.SIGTERM, signal_handler)        
        
    if (args.qmf):
        img_fac_agent = ImageFactoryAgent(args.url)
        img_fac_agent.run()
        log.info("connected to qmf agent on %s" % args.url)
        while True:
            time.sleep(60)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description='System image creation tool...')
    argparser.add_argument('-v', '--verbose', action='store_true', default=False, help='Set verbose logging.')
    argparser.add_argument('--debug', action='store_true', default=False, help='Set really verbose logging for debugging.')
    argparser.add_argument('--qmf', action='store_true', default=True, help='Provide QMFv2 agent interface. The default.')
    argparser.add_argument('--url', default='localhost', help='URL of qpidd to connect to.')
    argparser.add_argument('--build-template', help='NOT YET IMPLEMENTED: Build specified system and exit.')
    argparser.add_argument('--build-output', help='NOT YET IMPLEMENTED: Store built image in location specified.')
    argparser.add_argument('--version', action='version', version='%(prog)s 0.1', help='Version info')
    args = Arguments()
    argparser.parse_args(namespace=args)
    
    sys.exit(main(args))
