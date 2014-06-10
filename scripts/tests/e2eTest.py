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
import requests
from requests_oauthlib import OAuth1

client_key = 'mock-key'
client_secret = 'mock-secret'

oauth = OAuth1(client_key, client_secret=client_secret)


description = 'Attempts an end to end test of the imagefactory command line interface\
        by creating base images, building a target image from each of the successfully\
        built base images, pushing the target images to each of the providers defined\
        for a target, and finally deleting the provider images. What is done at each\
        step is controlled by the datafile you supply this script. The e2eTest-ExampleData.json\
        file can be found in the scripts/tests/ directory of the imagefactory source\
        tree for you to customize to your own testing.\
        To execute the test via REST api (the default) you need to disable ssl and oauth\
        launching the daemon with --no_ssl and --no_oauth.'
argparser = argparse.ArgumentParser()
argparser.add_argument('datafile', type=argparse.FileType('r'))
argparser.add_argument('--cmd', default='/usr/bin/imagefactory', help='Path to the imagefactory command. (default: %(default)s)')
argparser.add_argument('--url', default='http://localhost:8075/imagefactory', help='URL of the imagefactory instance to test. (default: %(default)s)')
argparser.add_argument('-L', help='uses the local CLI to run the tests instead of the REST api interface. (default: %(default)s)', action='store_false', dest='remote')

args = argparser.parse_args()
test_data = json.load(args.datafile)
args.datafile.close()
builds = test_data['jeos']
targets = test_data['targets']
providers = test_data['providers']
requests_headers = {'accept': 'application/json', 'content-type': 'application/json'}

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
proc_chk_interval = 10
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
    print "Building base image"
    build_queue.acquire()
    try:
        TDL = "<template><name>buildbase_image</name><os><name>%s</name><version>%s\
</version><arch>%s</arch><install type='url'><url>%s</url></install><rootpw>password</rootpw></os>\
<description>Tests building a base_image</description></template>" % (template_args['os'],
                                                                     template_args['version'],
                                                                     template_args['arch'],
                                                                     template_args['url'])

        template = tempfile.NamedTemporaryFile(mode='w', delete=False)
        template.write(TDL)
        template.close()

        if args.remote:
            payload = {'base_image': {'template': TDL}}
            r = requests.post(args.url+'/base_images', data=json.dumps(payload), headers=requests_headers, auth=oauth, verify=False)
            base_image_output_str = r.text
        else:
            (base_image_output_str, ignore, ignore) = subprocess_check_output('%s --output json --raw base_image %s' % (args.cmd, template.name), shell=True)
        base_image_output_dict = json.loads(base_image_output_str)['base_image']
        base_image_id = base_image_output_dict['id']
        while(base_image_output_dict['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
            sleep(proc_chk_interval)
            if args.remote:
                r = requests.get(args.url+'/base_images/'+base_image_id, auth=oauth, verify=False)
                base_image_output_str = r.text
                print "Checking status of %s" % (base_image_id,)
            else:
                (base_image_output_str, ignore, ignore) = subprocess_check_output('%s --output json --raw images \'{"identifier":"%s"}\'' % (args.cmd, base_image_id), shell=True)
            base_image_output_dict = json.loads(base_image_output_str)['base_image']

        if(base_image_output_dict['status'] == 'FAILED'):
            with f_lock:
                failures.append(base_image_output_dict)
        else:
            with b_lock:
                base_images.append(base_image_output_dict)
    finally:
        build_queue.release()

def build_push_delete(target, index):
    global test_index
    build_queue.acquire()
    try:
        if(index < len(base_images)):
            base_image = base_images[index]
            if args.remote:
                payload = {'target_image': {'target': target}}
                print "Creating a target image"
                r = requests.post(args.url+'/base_images/'+base_image['id']+'/target_images', data=json.dumps(payload), headers=requests_headers, auth=oauth, verify=False)
                target_image_output_str = r.text
            else:
                (target_image_output_str, ignore, ignore) = subprocess_check_output('%s --output json --raw target_image --id %s %s' % (args.cmd, base_image['id'], target), shell=True)
            target_image_output_dict = json.loads(target_image_output_str)['target_image']
            target_image_id = target_image_output_dict['id']
            while(target_image_output_dict['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
                sleep(proc_chk_interval)
                if args.remote:
                    r = requests.get(args.url+'/target_images/'+target_image_id, auth=oauth, verify=False)
                    target_image_output_str = r.text
                else:
                    (target_image_output_str, ignore, ignore) = subprocess_check_output('%s --output json --raw images \'{"identifier":"%s"}\'' % (args.cmd, target_image_id), shell=True)
                target_image_output_dict = json.loads(target_image_output_str)['target_image']

            if(target_image_output_dict['status'] == 'FAILED'):
                with f_lock:
                    failures.append(target_image_output_dict)
            else:
                with t_lock:
                    target_images.append(target_image_output_dict)
                for provider in providers:
                    if((not provider['name'].startswith('example')) and (provider['target'] == target)):
                        try:
                            if 'ec2' in provider['target']:
                                f = open(provider['credentials'], 'r')
                                provider['credentials'] = f.read()
                                f.close()
                            credentials_file = NamedTemporaryFile()
                            credentials_file.write(provider['credentials'])
                            provider_file = NamedTemporaryFile()
                            provider_file.write(str(provider['definition']))
                            if args.remote:
                                payload = {'provider_image': {'target': target, 'provider': provider['name'], 'credentials': provider['credentials']}}
                                r = requests.post(args.url+'/target_images/'+target_image_id+'/provider_images', data=json.dumps(payload), headers=requests_headers, auth=oauth, verify=False)
                                provider_image_output_str = r.text
                            else:
                                (provider_image_output_str, ignore, ignore) = subprocess_check_output('%s --output json --raw provider_image --id %s %s %s %s' % (args.cmd, target_image_id, provider['target'], provider_file.name, credentials_file.name), shell=True)
                            provider_image_output_dict = json.loads(provider_image_output_str)['provider_image']
                            provider_image_id = provider_image_output_dict['id']
                            while(provider_image_output_dict['status'] not in ('COMPLETE', 'COMPLETED', 'FAILED')):
                                sleep(proc_chk_interval)
                                if args.remote:
                                    r = requests.get(args.url+'/provider_images/'+provider_image_id, auth=oauth, verify=False)
                                    provider_image_output_str = r.text
                                else:
                                    (provider_image_output_str, ignore, ignore) = subprocess_check_output('%s --output json --raw images \'{"identifier":"%s"}\'' % (args.cmd, provider_image_id), shell=True)
                                provider_image_output_dict = json.loads(provider_image_output_str)['provider_image']

                            if(provider_image_output_dict['status'] == 'FAILED'):
                                with f_lock:
                                    failures.append(provider_image_output_dict)
                            else:
                                with p_lock:
                                    provider_images.append(provider_image_output_dict)
                                if args.remote:
                                    
                                    print "Checking status of %s" % (base_image_id,)
                                    r = requests.delete(args.url+'/provider_images/'+provider_image_id, auth=oauth, verify=False)
                                else:
                                    subprocess_check_output('%s --output json --raw delete %s --target %s --provider %s --credentials %s' % (args.cmd, provider_image_id, provider['target'], provider_file.name, credentials_file.name), shell=True)
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
    sleep(proc_chk_interval)
for target_image in target_images:
    if args.remote:
        r = requests.delete(args.url+'/target_images/'+target_image['id'], auth=oauth, verify=False)
    else:
        subprocess_check_output('%s --output json --raw delete %s' % (args.cmd, target_image['id']), shell=True)

for base_image in base_images:
    if args.remote:
        print "About to delete base image: %s" % (base_image['id'],)
        r = requests.delete(args.url+'/base_images/'+base_image['id'], auth=oauth, verify=False)
    else:
        subprocess_check_output('%s --output json --raw delete %s' % (args.cmd, base_image['id']), shell=True)

print json.dumps({"failures":failures, "base_images":base_images, "target_images":target_images}, indent=2)
if len(failures) > 0:
    sys.exit(1)
sys.exit(0)
