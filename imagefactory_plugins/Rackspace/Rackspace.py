#
#   Copyright 2013 Red Hat, Inc.
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
import libxml2
import traceback
import ConfigParser
from time import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from novaclient.v1_1 import client
from novaclient.exceptions import NotFound
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
    return stdout, stderr, retcode


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
            self.rackspace_jeos_amis = config_obj.jeos_images['rackspace']
        else:
            self.log.warning("No JEOS images defined for Rackspace.  Snapshot builds will not be possible.")
            self.rackspace_jeos_amis = {}

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())
        self.active_image.status_detail['error'] = traceback.format_exc()

    def wait_for_rackspace_ssh_access(self, guestaddr):
        self.activity("Waiting for SSH access to Rackspace instance")
        for index in range(300):
            if index % 10 == 0:
                self.log.debug("Waiting for Rackspace ssh access: %d/300" % index)

            try:
                self.guest.guest_execute_command(guestaddr, "/bin/true", timeout=10)
                break
            except Exception, e:
                self.log.exception('Caught exception waiting for ssh access: %s' % e)
                #import pdb
                #pdb.set_trace()
                #pass

            sleep(1)

            if index == 299:
                raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

    def wait_for_rackspace_instance_start(self, instance):
        self.activity("Waiting for Rackspace instance to become active")
        for i in range(600):
            if i % 10 == 0:
                try:
                    instance.get()
                    self.log.debug("Waiting %d more seconds for Rackspace instance to start, %d%% complete..." %
                                   ((600-i), instance.progress))
                except NotFound:
                    # We occasionally get errors when querying an instance that has just started.
                    # Ignore & hope for the best
                    self.log.warning(
                        "NotFound exception encountered when querying Rackspace instance (%s) - trying to continue" % (
                            instance.id), exc_info=True)
                except:
                    self.log.error("Exception encountered when updating status of instance (%s)" % instance.id,
                                   exc_info=True)
                    self.status = "FAILED"
                    try:
                        self.terminate_instance(instance)
                    except:
                        self.log.warning(
                            "WARNING: Instance (%s) failed to start and will not terminate - it may still be running" % (
                                instance.id), exc_info=True)
                        raise ImageFactoryException(
                            "Instance (%s) failed to fully start or terminate - it may still be running" % instance.id)
                    raise ImageFactoryException(
                        "Exception encountered when waiting for instance (%s) to start" % instance.id)
                if instance.status == u'ACTIVE':
                    break
            sleep(1)
        if instance.status != u'ACTIVE':
            self.status = "FAILED"
            try:
                self.terminate_instance(instance)
            except:
                self.log.warning(
                    "WARNING: Instance (%s) failed to start and will not terminate - it may still be running" % (
                        instance.id), exc_info=True)
                raise ImageFactoryException(
                    "Instance (%s) failed to fully start or terminate - it may still be running" % instance.id)
            raise ImageFactoryException("Instance failed to start after 300 seconds - stopping")

    def terminate_instance(self, instance):
        self.activity("Deleting Rackspace instance.")
        try:
            instance.delete()
        except Exception, e:
            self.log.info("Failed to delete Rackspace instance. %s" % e)

    def snapshot_image_on_provider(self, builder, provider, credentials, target, template, parameters):
        self.log.info('snapshot_image_on_provider() called in Rackspace')

        self.builder = builder
        self.active_image = self.builder.provider_image

        # TODO: This is a convenience variable for refactoring - rename
        self.new_image_id = builder.provider_image.identifier
        # TODO: so is this
        self.target = target

        # Template must be defined for snapshots
        self.tdlobj = oz.TDL.TDL(xmlstring=str(template), rootpw_required=True)

        # Create a name combining the TDL name and the UUID for use when tagging Rackspace Images
        self.longname = self.tdlobj.name + "-" + self.new_image_id

        self.log.debug("Being asked to push for provider %s" % provider)
        self.log.debug(
            "distro: %s - update: %s - arch: %s" % (self.tdlobj.distro, self.tdlobj.update, self.tdlobj.arch))
        self.rackspace_decode_credentials(credentials)
        self.log.debug("acting as Rackspace user: %s" % (str(self.rackspace_username)))

        self.status = "PUSHING"
        self.percent_complete = 0

        region = provider

        auth_url = 'https://identity.api.rackspacecloud.com/v2.0/'

        rackspace_client = client.Client(self.rackspace_username, self.rackspace_password,
                                         self.rackspace_account_number, auth_url, service_type="compute",
                                         region_name=region)
        rackspace_client.authenticate()

        mypub = open("/etc/oz/id_rsa-icicle-gen.pub")
        server_files = {"/root/.ssh/authorized_keys": mypub}

        # Now launch it
        self.activity("Launching Rackspace JEOS image")
        rackspace_image_id = self.rackspace_jeos_amis[region][self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]['img_id']
        instance_type = '512MB Standard Instance'
        image = rackspace_client.images.find(id=rackspace_image_id)
        small = rackspace_client.flavors.find(name=instance_type)
        self.log.debug("Starting build server %s with instance_type %s" % (rackspace_image_id, instance_type))
        reservation_name = 'imagefactory-snapshot-%s' % self.active_image.identifier
        reservation = rackspace_client.servers.create(reservation_name, image, small, files=server_files)

        if not reservation:
            self.status = "FAILED"
            raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

        self.instance = reservation

        self.wait_for_rackspace_instance_start(self.instance)

        # From this point on we must be sure to terminate the instance when we are done
        # so wrap in a try/finally
        # Accidentally running a 64 bit instance doing nothing costs 56 USD week
        try:
            while self.instance.accessIPv4 == '':
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

            self.activity("Customizing running Rackspace JEOS instance")
            self.log.debug("Stopping cron and killing any updatedb process that may be running")
            # updatedb interacts poorly with the bundle step - make sure it isn't running
            self.guest.guest_execute_command(guestaddr, "/sbin/service crond stop")
            self.guest.guest_execute_command(guestaddr, "killall -9 updatedb || /bin/true")
            self.log.debug("Done")

            # Not all JEOS images contain this - redoing it if already present is harmless
            self.log.info("Creating cloud-info file indicating target (%s)" % self.target)
            self.guest.guest_execute_command(guestaddr,
                                             'echo CLOUD_TYPE=\\\"%s\\\" > /etc/sysconfig/cloud-info' % self.target)

            self.log.debug("Customizing guest: %s" % guestaddr)
            self.guest.mkdir_p(self.guest.icicle_tmp)
            self.guest.do_customize(guestaddr)
            self.log.debug("Customization step complete")

            self.log.debug("Generating ICICLE from customized guest")
            self.output_descriptor = self.guest.do_icicle(guestaddr)
            self.log.debug("ICICLE generation complete")

            self.log.debug("Re-de-activate firstboot just in case it has been revived during customize")
            self.guest.guest_execute_command(guestaddr,
                                             "[ -f /etc/init.d/firstboot ] && /sbin/chkconfig firstboot off || /bin/true")
            self.log.debug("De-activation complete")

            image_name = str(self.longname)
            #image_desc = "%s - %s" % (asctime(localtime()), self.tdlobj.description)

            self.log.debug("Creating a snapshot of our running Rackspace instance")
            #TODO: give proper name??
            new_image_id = self.instance.create_image(image_name)
            new_image = rackspace_client.images.find(id=new_image_id)
            while True:
                new_image.get()
                self.log.info("Saving image: %d percent complete" % new_image.progress)
                if new_image.progress == 100:
                    break
                else:
                    sleep(20)

            self.builder.provider_image.icicle = self.output_descriptor
            self.builder.provider_image.identifier_on_provider = new_image_id
            self.builder.provider_image.provider_account_identifier = self.rackspace_account_number
        except Exception, e:
            self.log.warning("Exception while executing commands on guest: %s" % e)
        finally:
            self.terminate_instance(self.instance)

    def delete_from_provider(self, builder, provider, credentials, target, parameters):
        self.builder = builder
        self.active_image = self.builder.provider_image
        rackspace_image_id = self.active_image.identifier_on_provider
        try:
            self.log.debug("Deleting Rackspace image (%s)" % self.active_image.identifier_on_provider)
            self.rackspace_decode_credentials(credentials)
            self.log.debug("acting as Rackspace user: %s" % (str(self.rackspace_username)))

            auth_url = 'https://identity.api.rackspacecloud.com/v2.0/'
            rackspace_client = client.Client(self.rackspace_username, self.rackspace_password,
                                             self.rackspace_account_number, auth_url, service_type="compute",
                                             region_name=provider)
            rackspace_client.authenticate()
            image = rackspace_client.images.find(id=rackspace_image_id)
            if image:
                rackspace_client.images.delete(rackspace_image_id)
                self.log.debug('Successfully deleted Rackspace image (%s)' % rackspace_image_id)
        except Exception, e:
            raise ImageFactoryException('Failed to delete Rackspace image (%s) with error (%s)' % (rackspace_image_id,
                                                                                                   str(e)))

    def abort(self):
        # TODO: Make this progressively more robust
        # In the near term, the most important thing we can do is terminate any EC2 instance we may be using
        if self.instance:
            try:
                self.log.debug('Attempting to abort instance: %s' % self.instance)
                self.terminate_instance(self.instance)
            except Exception, e:
                self.log.exception(e)
                self.log.warning("** WARNING ** Instance MAY NOT be terminated ******** ")

    def _rackspace_get_xml_node(self, doc, credtype):
        nodes = doc.xpathEval("//provider_credentials/rackspace_credentials/%s" % credtype)
        if len(nodes) < 1:
            raise ImageFactoryException("No Rackspace %s available" % credtype)

        return nodes[0].content

    def rackspace_decode_credentials(self, credentials):
        self.activity("Preparing Rackspace credentials")
        doc = libxml2.parseDoc(credentials.strip())

        self.rackspace_account_number = self._rackspace_get_xml_node(doc, "account_number")
        self.rackspace_username = self._rackspace_get_xml_node(doc, "username")
        self.rackspace_password = self._rackspace_get_xml_node(doc, "password")

        doc.freeDoc()