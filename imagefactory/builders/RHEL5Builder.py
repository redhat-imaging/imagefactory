import oz.RHEL_5
import ConfigParser
from FedoraBuilder import FedoraBuilder


class RHEL5RemoteGuest(oz.RHEL_5.RHEL5Guest):
    def __init__(self, tdl, config, auto):
        # The debug output in the Guest parent class needs this property to exist
        self.host_bridge_ip = "0.0.0.0"
        # Add virtio as dummy arguments below - doesn't actually matter what we put
        oz.RHEL_5.RHEL5Guest.__init__(self, tdl, config, auto, "virtio", "virtio")

    def connect_to_libvirt(self):
        pass

class RHEL5Builder(FedoraBuilder):
    def init_guest(self, guesttype):
        # populate a config object to pass to OZ
        # This allows us to specify our own output dir but inherit other Oz behavior
        # TODO: Messy?
        config_file = "/etc/oz/oz.cfg"
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)
        config.set('paths', 'output_dir', self.app_config["imgdir"])
        if guesttype == "local":
            self.guest = oz.RHEL_5.get_class(self.tdlobj, config, None)
        else:
            self.guest = RHEL5RemoteGuest(self.tdlobj, config, None)
        self.guest.diskimage = self.app_config["imgdir"] + "/base-image-" + self.new_image_id + ".dsk"
        # Oz assumes unique names - TDL built for multiple backends guarantees they are not unique
        # We don't really care about the name so just force uniqueness
        self.guest.name = self.guest.name + "-" + self.new_image_id
