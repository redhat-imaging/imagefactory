# encoding: utf-8

#   Copyright 2012 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import json
import logging
import os.path
from xml.etree.ElementTree import fromstring


########## THIS IS TEMPORARY 
# These functions were moved from being methods on BuildDispatcher
# to avoid a circular import in Builder.py. There may be a better
# place for these, but I could see us having Target and Provider
# clases in thhe future, so I created this module as a placeholder.
#
# TODO This is *UGLY* and should get cleaned up.
###################################################################


# FIXME: this is a hack; conductor is the only one who really
#        knows this mapping, so perhaps it should provide it?
#        e.g. pass a provider => target dict into push_image
#        rather than just a list of providers. Perhaps just use
#        this heuristic for the command line?
#
# provider semantics, per target:
#  - ec2: region, one of ec2-us-east-1, ec2-us-west-1, ec2-ap-southeast-1, ec2-ap-northeast-1, ec2-eu-west-1
#  - condorcloud: ignored
#  - mock: any provider with 'mock' prefix
#  - rackspace: provider is rackspace
# UPDATE - Sept 13, 2011 for dynamic providers
#  - vpshere: encoded in provider string or a key in /etc/vmware.json
#  - rhevm: encoded in provider string or a key in /etc/rhevm.json
#
def map_provider_to_target(provider):
    # TODO: Add to the cloud plugin delegate interface a method to allow the plugin to "claim"
    #       a provider name.  Loop through the clouds, find ones that claim it.  Warn if more
    #       than one.  Error if none.  Success if only one.
    log = logging.getLogger(__name__)
    # Check for dynamic providers first
    provider_data = get_dynamic_provider_data(provider)
    if provider_data:
        try:
            return provider_data['target']
        except KeyError as e:
            log.debug('Provider data does not specify target!\n%s' % provider_data)
            log.exception(e)
            raise Exception('Provider data does not specify target!\n%s' % provider_data)
    elif provider.startswith('ec2-'):
        return 'ec2'
    elif provider == 'rackspace':
        return 'rackspace'
    elif provider.startswith('mock'):
        return 'mock'
    elif provider.startswith('MockCloud'):
        return 'MockCloud'
    else:
        log.warn('No matching provider found for %s, using "condorcloud" by default.' % (provider))
        return 'condorcloud' # condorcloud ignores provider

def get_dynamic_provider_data(provider):
    log = logging.getLogger(__name__)
    # Get provider details for RHEV-M or VSphere
    # First try to interpret this as an ad-hoc/dynamic provider def
    # If this fails, try to find it in one or the other of the config files
    # If this all fails return None
    # We use this in the builders as well so I have made it "public"

    try:
        xml_et = fromstring(provider)
        return xml_et.attrib
    except Exception as e:
        log.debug('Testing provider for XML: %s' % e)
        pass

    try:
        jload = json.loads(provider)
        return jload
    except ValueError as e:
        log.debug('Testing provider for JSON: %s' % e)
        pass

    rhevm_data = _return_dynamic_provider_data(provider, "rhevm")
    if rhevm_data:
        rhevm_data['target'] = "rhevm"
        rhevm_data['name'] = provider
        return rhevm_data

    vsphere_data = _return_dynamic_provider_data(provider, "vsphere")
    if vsphere_data:
        vsphere_data['target'] = "vsphere"
        vsphere_data['name'] = provider
        return vsphere_data

    # It is not there
    return None

def _return_dynamic_provider_data(provider, filebase):
    provider_json = '/etc/imagefactory/%s.json' % (filebase)
    if not os.path.exists(provider_json):
        return False

    provider_sites = {}
    f = open(provider_json, 'r')
    try:
        provider_sites = json.loads(f.read())
    finally:
        f.close()

    if provider in provider_sites:
        return provider_sites[provider]
    else:
        return None
