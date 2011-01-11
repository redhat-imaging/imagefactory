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

import sys
import getopt
from qmfagent.ImageFactoryAgent import *
import time
import logging
import math


help_message = '''
The help message goes here.
'''

class Usage(Exception):
	def __init__(self, msg):
		self.msg = msg


def main(argv=None):
    verbose = False
    qmfagent = False
    url = "localhost"
    template = None
    output = None
    loglevel = logging.WARNING
    log = logging.getLogger('imagefactory')
    
    logging.info("Starting imagefactory...")
    
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "ho:v", ["verbose", "help", "qmf", "url=", "template=", "output=", "loglevel="])
        except getopt.error, msg:
            raise Usage(msg)
        # option processing
        for option, value in opts:
            if option in ("-v", "--verbose"):
                verbose = True
            if option in ("-h", "--help"):
                raise Usage(help_message)
            if option in ("--qmf"):
                qmfagent = True
            if option in ("--url"):
                url = value
            if option in ("--template"):
                # template = value
                print "Not implemented yet... use oz directly."
            if option in ("-o", "--output"):
                # output = value
                print "Not implemented yet... use oz directly."
            if option in ("--loglevel"):
                loglevel = int(math.fabs((int(value) * 10) - 60))
    except Usage, err:
        print >> sys.stderr, sys.argv[0].split("/")[-1] + ": " + str(err.msg)
        print >> sys.stderr, "\t for help use --help"
        return 2
        
    logging.getLogger('').setLevel(loglevel)
        
    if (qmfagent):
        img_fac_agent = ImageFactoryAgent(url)
        img_fac_agent.run()
        logging.info("connecting to qmf agent on %s" % url)
        # TODO: sloranz@redhat.com - replace this with proper daemon code
        while True:
            time.sleep(1000)


if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(message)s', filename='/var/log/imagefactory.log')
    sys.exit(main())
