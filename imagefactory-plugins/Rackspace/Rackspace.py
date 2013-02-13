#
#   Copyright 2011 Red Hat, Inc.
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

import logging
import zope
import oz.Fedora
import oz.TDL
import subprocess
import os
import re
import guestfs
import string
import libxml2
import traceback
import ConfigParser
import boto.ec2
import sys
import json
from time import *
from tempfile import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.ReservationManager import ReservationManager
from imgfac.CloudDelegate import CloudDelegate

import novaclient
from novaclient.v1_1 import client
from novaclient.exceptions import NotFound
import httplib2
httplib2.debuglevel = 0
import oz.Fedora

def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    stdout, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = ' '.join(*popenargs)
        raise ImageFactoryException("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)


class Rackspace(object):
    zope.interface.implements(CloudDelegate)

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def __init__(self):
        # Note that we are now missing ( template, target, config_block = None):
        super(Rackspace, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        config_obj = ApplicationConfiguration()
        self.app_config = config_obj.configuration
        self.oz_config = ConfigParser.SafeConfigParser()
        self.oz_config.read("/etc/oz/oz.cfg")
        self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])
        
        if "rackspace" in config_obj.jeos_images:
            self.ec2_jeos_amis = config_obj.jeos_images['ec2']
        else:
            self.log.warning("No JEOS images defined for Rackspace.  Snapshot builds will not be possible.")
            self.ec2_jeos_amis = {}


    def _get_os_helper(self):
        # For now we are adopting a 'mini-plugin' approach to OS specific code within the EC2 plugin
        # In theory, this could live in the OS plugin - however, the code in question is very tightly
        # related to the EC2 plugin, so it probably should stay here
        try:
            # Change RHEL-6 to RHEL6, etc.
            os_name = self.tdlobj.distro.translate(None, '-')
            class_name = "%s_ec2_Helper" % (os_name)
            module_name = "imagefactory_plugins.EC2Cloud.EC2CloudOSHelpers"
            __import__(module_name)
            os_helper_class = getattr(sys.modules[module_name], class_name)
            self.os_helper = os_helper_class(self)
        except:
            self.log_exc()
            raise ImageFactoryException("Unable to create EC2 OS helper object for distro (%s) in TDL" % (self.tdlobj.distro) )

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        self.log.info('push_image_to_provider() called in Rackspace')

        self.builder = builder
        self.active_image = self.builder.provider_image

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier

        self.tdlobj = oz.TDL.TDL(xmlstring=builder.target_image.template, rootpw_required=True)
        self._get_os_helper()
        self.push_image_upload(target_image, provider, credentials)


    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())
        self.active_image.status_detail['error'] = traceback.format_exc()


    def wait_for_rackspace_ssh_access(self, guestaddr):
        self.activity("Waiting for SSH access to Rackspace instance")
        for i in range(300):
            if i % 10 == 0:
                self.log.debug("Waiting for Rackspace ssh access: %d/300" % (i))

            try:
                stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, "/bin/true", timeout = 10)
                break
            except:
		import pdb;pdb.set_trace()
                pass

            sleep(1)

        if i == 299:
            raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

    def wait_for_rackspace_instance_start(self, instance):
        self.activity("Waiting for EC2 instance to become active")
        for i in range(600):
            if i % 10 == 0:
                self.log.debug("Waiting for Rackspace instance to start: %d/600" % (i))
            try:
                instance.get()
                self.log.debug("Progress: %d" % (instance.progress))
            except NotFound, e:
                # We occasionally get errors when querying an instance that has just started - ignore them and hope for the best
                self.log.warning("NotFound exception encountered when querying Rackspace instance (%s) - trying to continue" % (instance.id), exc_info = True)
            except:
                self.log.error("Exception encountered when updating status of instance (%s)" % (instance.id), exc_info = True)
                self.status="FAILED"
                try:
                    self.terminate_instance(instance)
                except:
                    log.warning("WARNING: Instance (%s) failed to start and will not terminate - it may still be running" % (instance.id), exc_info = True)
                    raise ImageFactoryException("Instance (%s) failed to fully start or terminate - it may still be running" % (instance.id))
                raise ImageFactoryException("Exception encountered when waiting for instance (%s) to start" % (instance.id))
            if instance.status == u'ACTIVE':
                break
            sleep(1)
        if instance.status != u'ACTIVE':
            self.status="FAILED"
            try:
                self.terminate_instance(instance)
            except:
                log.warning("WARNING: Instance (%s) failed to start and will not terminate - it may still be running" % (instance.id), exc_info = True)
                raise ImageFactoryException("Instance (%s) failed to fully start or terminate - it may still be running" % (instance.id))
            raise ImageFactoryException("Instance failed to start after 300 seconds - stopping")

    def terminate_instance(self, instance):
	self.activity("Deleting Rackspace instance")
	try:
  	    self.instance.delete()
	except Exception, e:
	    import pdb; pdb.set_trace()
            self.log.info("Failed to delete Rackspace instance.")

    def snapshot_image_on_provider(self, builder, provider, credentials, target, template, parameters):
        self.log.info('snapshot_image_on_provider() called in Rackspace')
	print "\n\n\n\n\n\n\n\n\n\n\n"

        self.builder = builder
        self.active_image = self.builder.provider_image

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier
        # TODO: so is this
        self.target = target


        # Template must be defined for snapshots
        self.tdlobj = oz.TDL.TDL(xmlstring=str(template), rootpw_required=True)
        self._get_os_helper()
        self.os_helper.init_guest()

        # Create a name combining the TDL name and the UUID for use when tagging EC2 AMIs
        self.longname = self.tdlobj.name + "-" + self.new_image_id

        def replace(item):
            if item in [self.rackspace_username, self.rackspace_password]:
                return "REDACTED"
            return item

        self.log.debug("Being asked to push for provider %s" % (provider))
        self.log.debug("distro: %s - update: %s - arch: %s" % (self.tdlobj.distro, self.tdlobj.update, self.tdlobj.arch))
        self.rackspace_decode_credentials(credentials)
        self.log.debug("acting as Rackspace user: %s" % (str(self.rackspace_username)))

        self.status="PUSHING"
        self.percent_complete=0

        region=provider
        
	auth_url = 'https://identity.api.rackspacecloud.com/v2.0/'

	rackspace_client = client.Client(self.rackspace_username, self.rackspace_password, self.rackspace_account_number, auth_url, service_type="compute", region_name=region)
	rackspace_client.authenticate()


	mypub = open("/etc/oz/id_rsa-icicle-gen.pub")
        server_files = { "/root/.ssh/authorized_keys":mypub }

        # Now launch it
        self.activity("Launching Rackspace JEOS image")
        #self.log.debug("Starting ami %s with instance_type %s" % (ami_id, instance_type))
	f17 = rackspace_client.images.find(name='Fedora 17 (Beefy Miracle)')
	small = rackspace_client.flavors.find(name='512MB Standard Instance')
	reservation = rackspace_client.servers.create('testing', f17, small, files=server_files)



        if not reservation:
            self.status="FAILED"
            raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

        self.instance = reservation

        self.wait_for_rackspace_instance_start(self.instance)

        # From this point on we must be sure to terminate the instance when we are done
        # so wrap in a try/finally
        # Accidentally running a 64 bit instance doing nothing costs 56 USD week
        try:
	    while (self.instance.accessIPv4 == ''):
                self.log.debug("Waiting to get public IP address")
		sleep(1)
	    	self.instance.get()
            guestaddr = self.instance.accessIPv4
	    self.guest = oz.Fedora.FedoraGuest(self.tdlobj, self.oz_config, None, "virtio", True, "virtio", True)

            # Ugly ATM because failed access always triggers an exception
            self.wait_for_rackspace_ssh_access(guestaddr)

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 60 seconds for remaining boot tasks")
            sleep(60)

            self.activity("Customizing running EC2 JEOS instance")
            self.log.debug("Stopping cron and killing any updatedb process that may be running")
            # updatedb interacts poorly with the bundle step - make sure it isn't running
	    try:
                self.guest.guest_execute_command(guestaddr, "/sbin/service crond stop")
                self.guest.guest_execute_command(guestaddr, "killall -9 updatedb || /bin/true")
	    except Exception, e:
		import pdb; pdb.set_trace()
            self.log.debug("Done")

            # Not all JEOS images contain this - redoing it if already present is harmless
            self.log.info("Creating cloud-info file indicating target (%s)" % (self.target))
            self.guest.guest_execute_command(guestaddr, 'echo CLOUD_TYPE=\\\"%s\\\" > /etc/sysconfig/cloud-info' % (self.target))

            self.log.debug("Customizing guest: %s" % (guestaddr))
            self.guest.mkdir_p(self.guest.icicle_tmp)
            self.guest.do_customize(guestaddr)
            self.log.debug("Customization step complete")

            self.log.debug("Generating ICICLE from customized guest")
            self.output_descriptor = self.guest.do_icicle(guestaddr)
            self.log.debug("ICICLE generation complete")

            self.log.debug("Re-de-activate firstboot just in case it has been revived during customize")
            self.guest.guest_execute_command(guestaddr, "[ -f /etc/init.d/firstboot ] && /sbin/chkconfig firstboot off || /bin/true")
            self.log.debug("De-activation complete")

            new_image_id = None
            image_name = str(self.longname)
            image_desc = "%s - %s" % (asctime(localtime()), self.tdlobj.description)

            self.log.debug("Creating a snapshot of our running Rackspace instance")
	    #TODO: give proper name??
	    new_image_id = self.instance.create_image(image_name)
       	    new_image = rackspace_client.images.find(id=new_image_id)
	    while(True):
	        new_image.get()
		self.log.info("Saving image: %d percent complete" % (new_image.progress))
		if new_image.progress == 100:
		    break
                else:
		    sleep(20)

	    # This replaces our Warehouse calls
            self.builder.provider_image.icicle = self.output_descriptor
            self.builder.provider_image.identifier_on_provider = new_image_id
            self.builder.provider_account_identifier = self.rackspace_account_number
        finally:
            self.terminate_instance(self.instance)    

    def _rackspace_get_xml_node(self, doc, credtype):
        nodes = doc.xpathEval("//provider_credentials/rackspace_credentials/%s" % (credtype))
        if len(nodes) < 1:
            raise ImageFactoryException("No Rackspace %s available" % (credtype))

        return nodes[0].content

    def rackspace_decode_credentials(self, credentials):
        self.activity("Preparing Rackspace credentials")
        doc = libxml2.parseDoc(credentials.strip())

        self.rackspace_account_number = self._rackspace_get_xml_node(doc, "account_number")
        self.rackspace_username = self._rackspace_get_xml_node(doc, "username")
        self.rackspace_password = self._rackspace_get_xml_node(doc, "password")

        doc.freeDoc()

    def abort(self):
        # TODO: Make this progressively more robust

        # In the near term, the most important thing we can do is terminate any EC2 instance we may be using
        if self.instance:
            instance_id = self.instance.id
            try:
                self.terminate_instance(self.instance)
            except Exception, e:
                self.log.warning("Warning, encountered - Instance %s may not be terminated ******** " % (instance_id))
                self.log.exception(e)

    # This file content is tightly bound up with our mod code above
    # I've inserted it as class variables for convenience


    def add_target_content(self):
        """Merge in target specific package and repo content.
        TDL object must already exist as self.tdlobj"""
        doc = None
# TODONOW: Fix
#        if self.config_block:
        import os.path
        if None:
            doc = libxml2.parseDoc(self.config_block)
        elif os.path.isfile("/etc/imagefactory/target_content.xml"):
            doc = libxml2.parseFile("/etc/imagefactory/target_content.xml")
        else:
            self.log.debug("Found neither a call-time config nor a config file - doing nothing")
            return

        # Purely to make the xpath statements below a tiny bit shorter
        target = self.target
        os=self.tdlobj.distro
        version=self.tdlobj.update
        arch=self.tdlobj.arch

        # We go from most to least specific in this order:
        #   arch -> version -> os-> target
        # Note that at the moment we even allow an include statment that covers absolutely everything.
        # That is, one that doesn't even specify a target - this is to support a very simple call-time syntax
        include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and @arch='%s']" %
                                (target, os, version, arch))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and @version='%s' and not(@arch)]" %
                                    (target, os, version))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and @os='%s' and not(@version) and not(@arch)]" %
                                        (target, os))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[@target='%s' and not(@os) and not(@version) and not(@arch)]" %
                                            (target))
        if len(include) == 0:
            include = doc.xpathEval("/template_includes/include[not(@target) and not(@os) and not(@version) and not(@arch)]")
        if len(include) == 0:
            self.log.debug("cannot find a config section that matches our build details - doing nothing")
            return

        # OK - We have at least one config block that matches our build - take the first one, merge it and be done
        # TODO: Merge all of them?  Err out if there is more than one?  Warn?
        include = include[0]

        packages = include.xpathEval("packages")
        if len(packages) > 0:
            self.tdlobj.merge_packages(str(packages[0]))

        repositories = include.xpathEval("repositories")
        if len(repositories) > 0:
            self.tdlobj.merge_repositories(str(repositories[0]))

