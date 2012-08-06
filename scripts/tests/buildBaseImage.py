#!/usr/bin/env python

import argparse


argparser = argparse.ArgumentParser()
argparser.add_argument('--os', default='Fedora', help='The OS name. (default: %(default)s)')
argparser.add_argument('--version', default='16', help='The OS version. (default: %(default)s)')
argparser.add_argument('--arch', default='x86_64', help='The OS architecture. (default: %(default)s)')
argparser.add_argument('--url', default='http://download.fedoraproject.org/pub/fedora/linux/releases/16/Fedora/x86_64/os/', help='The installation url. (default: %(default)s)')

options = argparser.parse_args()

TDL = "<template><name>buildBaseImage</name><os><name>%s</name><version>%s\
</version><arch>%s</arch><install type='url'><url>%s</url></install></os>\
<description>Tests building a BaseImage</description></template>" % (options.os,
                                                                     options.version,
                                                                     options.arch,
                                                                     options.url)

print TDL
