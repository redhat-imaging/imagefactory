#!/usr/bin/env python

import argparse
import tempfile
import subprocess
import json
from time import sleep
import threading
import os
import sys


argparser = argparse.ArgumentParser()
argparser.add_argument('--builds', default='[{"os":"Fedora","version":"16","arch":"x86_64","url":"http://download.fedoraproject.org/pub/fedora/linux/releases/16/Fedora/x86_64/os/"},\
                                             {"os":"Fedora","version":"17","arch":"x86_64","url":"http://download.fedoraproject.org/pub/fedora/linux/releases/17/Fedora/x86_64/os/"}]')
argparser.add_argument('--targets', default='["rhevm", "ec2", "vsphere"]')

args = argparser.parse_args()
builds = json.loads(args.builds)
targets = json.loads(args.targets)

base_images = []
b_lock = threading.Lock()
target_images = []
t_lock = threading.Lock()
failures = []
f_lock = threading.Lock()
queue = threading.BoundedSemaphore(len(builds))
proc_chk_interval = 5

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
###

def build_base_image(template_args):
    queue.acquire()
    try:
        TDL = "<template><name>buildBaseImage</name><os><name>%s</name><version>%s\
</version><arch>%s</arch><install type='url'><url>%s</url></install></os>\
<description>Tests building a BaseImage</description></template>" % (template_args['os'],
                                                                     template_args['version'],
                                                                     template_args['arch'],
                                                                     template_args['url'])

        template = tempfile.NamedTemporaryFile(mode='w', delete=False)
        template.write(TDL)
        template.close()

        (output, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw base_image %s' % template.name, shell=True)
        outputd = json.loads(output)
        image_id = outputd['identifier']
        while(outputd['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
            sleep(proc_chk_interval)
            (output, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --raw images \'{"identifier":"%s"}\'' % image_id, shell=True)
            outputd = json.loads(output)

        if(outputd['status'] == 'FAILED'):
            with f_lock:
                failures.append(outputd)
        else:
            with b_lock:
                base_images.append(outputd)
    finally:
        queue.release()

def customize_target_image(target, index):
    queue.acquire()
    try:
        if(index < len(base_images)):
            base_image = base_images[index]
            (output, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw target_image --id %s %s' % (base_image.get('identifier'), target), shell=True)
            outputd = json.loads(output)
            image_id = outputd['identifier']
            while(outputd['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
                sleep(proc_chk_interval)
                (output, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --raw images \'{"identifier":"%s"}\'' % image_id, shell=True)
                outputd = json.loads(output)

            if(outputd['status'] == 'FAILED'):
                with f_lock:
                    failures.append(outputd)
            else:
                with t_lock:
                    target_images.append(outputd)
    finally:
        queue.release()

for build in builds:
    thread_name = "%s-%s-%s.%s" % (build['os'], build['version'], build['arch'], os.getpid())
    build_thread = threading.Thread(target=build_base_image, name = thread_name, args=(build,))
    build_thread.start()

for target in targets:
    for index in range(len(builds)):
        thread_name = "%s-%s.%s" % (target, index, os.getpid())
        customize_thread = threading.Thread(target=customize_target_image, name=thread_name, args=(target, index))
        customize_thread.start()

queue.acquire()
print json.dumps({"failures":failures, "base_images":base_images, "target_images":target_images}, indent=2)
queue.release()
sys.exit(0)
