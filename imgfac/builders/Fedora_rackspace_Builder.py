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

import zope
import oz.Fedora
import oz.TDL
import libxml2
import traceback
import gzip
from cloudservers import CloudServers
import ConfigParser
from time import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageFactoryException import ImageFactoryException
from IBuilder import IBuilder
from BaseBuilder import BaseBuilder

# This allows us to use the utility methods in Oz without errors due to lack of libvirt
class FedoraRemoteGuest(oz.Fedora.FedoraGuest):
    def __init__(self, tdl, config, auto, nicmodel, haverepo, diskbus,
                 brokenisomethod):
        # The debug output in the Guest parent class needs this property to exist
        self.host_bridge_ip = "0.0.0.0"
        oz.Fedora.FedoraGuest.__init__(self, tdl, config, auto, nicmodel, haverepo, diskbus,
                 brokenisomethod)

    def connect_to_libvirt(self):
        pass

class Fedora_rackspace_Builder(BaseBuilder):
    """docstring for Fedora_rackspace_Builder"""
    zope.interface.implements(IBuilder)

    def __init__(self, template, target):
        super(Fedora_rackspace_Builder, self).__init__(template, target)
        self.app_config = ApplicationConfiguration().configuration
        self.warehouse_url = self.app_config['warehouse']
        # May not be necessary to do both of these
        self.tdlobj = oz.TDL.TDL(xmlstring=self.template.xml)
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        # 18-Jul-2011 - Moved to constructor and modified to change TDL object name itself
        #   Oz now uses the tdlobject name property directly in several places so we must change it
        self.tdlobj.name = self.tdlobj.name + "-" + self.new_image_id

        # populate a config object to pass to OZ; this allows us to specify our
        # own output dir but inherit other Oz behavior
        self.oz_config = ConfigParser.SafeConfigParser()
        self.oz_config.read("/etc/oz/oz.cfg")
        self.oz_config.set('paths', 'output_dir', self.app_config["imgdir"])

    def init_guest(self):
        self.guest = FedoraRemoteGuest(self.tdlobj, self.oz_config, None,
                                       "virtio", True, "virtio", True)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"

    def log_exc(self):
        self.log.debug("Exception caught in ImageFactory")
        self.log.debug(traceback.format_exc())

    def build_image(self, build_id=None):
        try:
            self.build_snapshot(build_id)
        except:
            self.log_exc()
            self.status="FAILED"
            raise

    def build_snapshot(self, build_id):
        # All we need do here is store the relevant bits in the Warehouse
        self.log.debug("Building Linux for non-upload cloud (%s)" % (self.target))
        self.image = "%s/placeholder-linux-image-%s" % (self.app_config['imgdir'], self.new_image_id)
        image_file = open(self.image, 'w')
        image_file.write("Placeholder for non upload cloud Linux image")
        image_file.close()
        self.output_descriptor = None
        self.log.debug("Storing placeholder object for non upload cloud image")
        self.store_image(build_id)
        self.percent_complete = 100
        self.status = "COMPLETED"
        self.log.debug("Completed placeholder warehouse object for linux non-upload image...")
        sleep(5)

    def push_image(self, target_image_id, provider, credentials):
        try:
            self.init_guest()
            self.push_image_snapshot_rackspace(target_image_id, provider,
                                               credentials)
        except:
            self.log_exc()
            self.status="FAILED"

    def push_image_snapshot_rackspace(self, target_image_id, provider, credentials):
        doc = libxml2.parseDoc(credentials)

        rack_username = doc.xpathEval("//provider_credentials/rackspace_credentials/username")[0].content
        rack_access_key = doc.xpathEval("//provider_credentials/rackspace_credentials/access_key")[0].content

        cloudservers = CloudServers(rack_username, rack_access_key)
	cloudservers.authenticate()

        # TODO: Config file
        rack_jeos = {'Fedora': { '14' : { 'x86_64': 71},
                                 '13' : { 'x86_64': 53} } }

        jeos_id = None
        try:
            jeos_id = rack_jeos[self.tdlobj.distro][self.tdlobj.update][self.tdlobj.arch]
        except KeyError:
            raise ImageFactoryException("Unable to find Rackspace JEOS for desired distro - ask Rackspace")


	jeos_image = cloudservers.images.get(jeos_id)
        # Hardcode to use a modest sized server
	onegig_flavor = cloudservers.flavors.get(3)

        # This is the Rackspace version of key injection
	mypub = open("/etc/oz/id_rsa-icicle-gen.pub")
	server_files = { "/root/.ssh/authorized_keys":mypub }

        instance_name = "factory-build-%s" % (self.new_image_id, )
        jeos_instance = cloudservers.servers.create(instance_name, jeos_image,
                                                    onegig_flavor,
                                                    files=server_files)

        for i in range(300):
            if jeos_instance.status == "ACTIVE":
                self.log.debug("JEOS instance now active - moving to customize")
                break
            if i % 10 == 0:
                self.log.debug("Waiting for Rackspace instance to start access: %d/300" % (i))
            sleep(1)
            # There is no query or update method, we simply recreate
            jeos_instance = cloudservers.servers.get(jeos_instance.id)

        # As with EC2 put this all in a try block and then terminate at the end to avoid long running
        # instances which cost users money
        try:
            self.guest.sshprivkey = "/etc/oz/id_rsa-icicle-gen"
            guestaddr = jeos_instance.public_ip

            # TODO: Make this loop so we can take advantage of early availability
            # Ugly ATM because failed access always triggers an exception
            self.log.debug("Waiting up to 300 seconds for ssh to become available on %s" % (guestaddr))
            retcode = 1
            for i in range(300):
                if i % 10 == 0:
                    self.log.debug("Waiting for Rackspace ssh access: %d/300" % (i))

                try:
                    stdout, stderr, retcode = self.guest.guest_execute_command(guestaddr, "/bin/true")
                    break
                except:
                    pass

                sleep(1)

            if retcode:
                raise ImageFactoryException("Unable to gain ssh access after 300 seconds - aborting")

            # There are a handful of additional boot tasks after SSH starts running
            # Give them an additional 20 seconds for good measure
            self.log.debug("Waiting 20 seconds for remaining boot tasks")
            sleep(20)

	    self.log.debug("Doing Rackspace Customize")
	    self.guest.mkdir_p(self.guest.icicle_tmp)
	    self.guest.do_customize(guestaddr)
	    self.log.debug("Done!")

            self.log.debug("Generating ICICLE for Rackspace image")
            self.output_descriptor = self.guest.do_icicle(guestaddr)
            self.log.debug("Done!")

            image_name = "factory-image-%s" % (self.new_image_id, )
	    snap_image = cloudservers.images.create(image_name, jeos_instance)

	    self.log.debug("New Rackspace image created with ID: %s" % (snap_image.id))

            for i in range(300):
                if snap_image.status == "ACTIVE":
                    self.log.debug("Snapshot Completed")
                    break
                if i % 10 == 0:
                    self.log.debug("Image status: %s - Waiting for completion: %d/300" % (snap_image.status, i))
                sleep(1)
                # There is no query or update method, we simply recreate
                snap_image = cloudservers.images.get(snap_image.id)

            self.log.debug("Storing Rackspace image ID (%s) and details in Warehouse" % (snap_image.id))
            icicle_id = self.warehouse.store_icicle(self.output_descriptor)
            metadata = dict(target_image=target_image_id, provider=provider, icicle=icicle_id, target_identifier=snap_image.id)
            self.warehouse.create_provider_image(self.new_image_id, metadata=metadata)

        finally:
            self.log.debug("Shutting down Rackspace server")
            cloudservers.servers.delete(jeos_instance.id)

        self.percent_complete=100
        self.status = "COMPLETED"

    def abort(self):
        pass
