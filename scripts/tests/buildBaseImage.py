#!/usr/bin/env python

import argparse
import tempfile
import subprocess
import json
from time import sleep
import sys

# Required for Python 2.6 backwards compat
def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    stdout, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = ' '.join(*popenargs)
        raise Exception("'%s' failed(%d): %s" % (cmd, retcode, stdout))
    return (stdout, stderr, retcode)


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

template = tempfile.NamedTemporaryFile(mode='w', delete=False)
template.write(TDL)
template.close()

(output, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw base_image %s' % template.name, shell=True)
outputd = json.loads(output)

image_id = outputd['identifier']

interval = 5
seconds = interval
msg = ''
while(outputd['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
    msg = '%s - %ss' % (outputd['status_detail']['activity'], seconds)
    sys.stdout.write('\r' + msg)
    sleep(interval)
    seconds = seconds + interval
    (output, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw images \'{"identifier":"%s"}\'' % image_id, shell=True)
    outputd = json.loads(output)

sys.stdout.write('\r' + ' ' * len(msg))
sys.stdout.write('\r' + output)
