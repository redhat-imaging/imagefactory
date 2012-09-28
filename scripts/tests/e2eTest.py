#!/usr/bin/env python

import argparse
import tempfile
import subprocess
import json
from time import sleep
import threading
import os
import sys
from tempfile import NamedTemporaryFile


description = 'Attempts an end to end test of the imagefactory command line interface\
        by creating base images, building a target image from each of the successfully\
        built base images, pushing the target images to each of the providers defined\
        for a target, and finally deleting the provider images. What is done at each\
        step is controlled by the datafile you supply this script. The e2eTest-ExampleData.json\
        file can be found in the scripts/tests/ directory of the imagefactory source\
        tree for you to customize to your own testing.'
argparser = argparse.ArgumentParser()
argparser.add_argument('datafile', type=argparse.FileType('r'))

args = argparser.parse_args()
test_data = json.load(args.datafile)
args.datafile.close()

builds = test_data['jeos']
targets = test_data['targets']
providers = test_data['providers']

base_images = []
b_lock = threading.Lock()
target_images = []
t_lock = threading.Lock()
provider_images = []
p_lock = threading.Lock()
failures = []
f_lock = threading.Lock()
build_queue = threading.BoundedSemaphore(len(builds))
test_count = len(builds) * len(targets)
test_index = 0
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

def create_base_image(template_args):
    build_queue.acquire()
    try:
        TDL = "<template><name>buildbase_image</name><os><name>%s</name><version>%s\
</version><arch>%s</arch><install type='url'><url>%s</url></install></os>\
<description>Tests building a base_image</description></template>" % (template_args['os'],
                                                                     template_args['version'],
                                                                     template_args['arch'],
                                                                     template_args['url'])

        template = tempfile.NamedTemporaryFile(mode='w', delete=False)
        template.write(TDL)
        template.close()

        (base_image_output_str, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw base_image %s' % template.name, shell=True)
        base_image_output_dict = json.loads(base_image_output_str)
        base_image_id = base_image_output_dict['identifier']
        while(base_image_output_dict['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
            sleep(proc_chk_interval)
            (base_image_output_str, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --raw images \'{"identifier":"%s"}\'' % base_image_id, shell=True)
            base_image_output_dict = json.loads(base_image_output_str)

        if(base_image_output_dict['status'] == 'FAILED'):
            with f_lock:
                failures.append(base_image_output_dict)
        else:
            with b_lock:
                base_images.append(base_image_output_dict)
    finally:
        build_queue.release()

def build_push_delete(target, index):
    build_queue.acquire()
    try:
        if(index < len(base_images)):
            base_image = base_images[index]
            (target_image_output_str, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw target_image --id %s %s' % (base_image.get('identifier'), target), shell=True)
            target_image_output_dict = json.loads(target_image_output_str)
            target_image_id = target_image_output_dict['identifier']
            while(target_image_output_dict['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
                sleep(proc_chk_interval)
                (target_image_output_str, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --raw images \'{"identifier":"%s"}\'' % target_image_id, shell=True)
                target_image_output_dict = json.loads(target_image_output_str)

            if(target_image_output_dict['status'] == 'FAILED'):
                with f_lock:
                    failures.append(target_image_output_dict)
            else:
                with t_lock:
                    target_images.append(target_image_output_dict)
                for provider in providers:
                    if((not provider.startswith('example')) and (provider['target'] == target)):
                        try:
                            credentials_file = NamedTemporaryFile()
                            credentials_file.write(provider['credentials'])
                            provider_file = NamedTemporaryFile()
                            provider_file.write(provider['definition'])
                            (provider_image_output_str, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --debug --raw provider_image --id %s %s %s %s' % (target_image_id, provider['target'], provider_file.name, credentials_file.name), shell=True)
                            provider_image_output_dict = json.loads(provider_image_output_str)
                            provider_image_id = provider_image_output_dict['identifier']
                            while(provider_image_output_dict['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
                                sleep(proc_chk_interval)
                                (provider_image_output_str, ignore, ignore) = subprocess_check_output('/usr/bin/imagefactory --raw images \'{"identifier":"%s"}\'' % provider_image_id, shell=True)
                                provider_image_output_dict = json.loads(provider_image_output_str)
                                if(provider_image_output_dict['status'] == 'FAILED'):
                                    with f_lock:
                                        failures.append(provider_image_output_dict)
                                else:
                                    with p_lock:
                                        provider_images.append(provider_image_output_dict)
                                    subprocess_check_output('/usr/bin/imagefactory --raw delete %s --target %s --provider %s --credentials %s' % (provider_image_id, provider['target'], provider_file.name, credentials_file.name), shell=True)
                        finally:
                            credentials_file.close()
                            provider_file.close()

    finally:
        build_queue.release()
        test_index += 1

for build in builds:
    thread_name = "%s-%s-%s.%s" % (build['os'], build['version'], build['arch'], os.getpid())
    build_thread = threading.Thread(target=create_base_image, name = thread_name, args=(build,))
    build_thread.start()

for target in targets:
    for index in range(len(builds)):
        thread_name = "%s-%s.%s" % (target, index, os.getpid())
        customize_thread = threading.Thread(target=build_push_delete, name=thread_name, args=(target, index))
        customize_thread.start()

while(test_index < test_count):
    sleep(5)

for target_image in target_images:
    subprocess_check_output('/usr/bin/imagefactory --raw delete %s' % target_image['identifier'], shell=True)

for base_image in base_images:
    subprocess_check_output('/usr/bin/imagefactory --raw delete %s' % base_image['identifier'], shell=True)

print json.dumps({"failures":failures, "base_images":base_images, "target_images":target_images}, indent=2)
sys.exit(0)
