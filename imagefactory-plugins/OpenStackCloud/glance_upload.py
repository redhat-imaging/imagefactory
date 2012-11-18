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

from glance import client as glance_client
from pprint import pprint

def glance_upload(image_filename, creds = {'auth_url': None, 'password': None, 'strategy': 'noauth', 'tenant': None, 'username': None},
                  host = "0.0.0.0", port = "9292", token = None):

    image_meta = {'container_format': 'bare',
     'disk_format': 'qcow2',
     'is_public': True,
     'min_disk': 0,
     'min_ram': 0,
     'name': 'Factory Test Image',
     'properties': {'distro': 'rhel'}}


    c = glance_client.Client(host=host, port=port,
                             auth_tok=token, creds=creds)

    image_data = open(image_filename, "r")

    image_meta = c.add_image(image_meta, image_data)

    image_data.close()

    return image_meta['id']


image_id = glance_upload("/root/base-image-f19e3f9b-5905-4b66-acb2-2e25395fdff7.qcow2")

print image_id

