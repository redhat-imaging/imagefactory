# encoding: utf-8

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
import pycurl
import httplib2
import urllib
import uuid
import os
import libxml2
import props
from imgfac.ApplicationConfiguration import ApplicationConfiguration


class ImageWarehouse(object):

    url = props.prop("_url", "The url property.")
    image_bucket = props.prop("_image_bucket", "The image_bucket property.")
    build_bucket = props.prop("_build_bucket", "The build_bucket property.")
    target_image_bucket = props.prop("_target_image_bucket", "The target_image_bucket property.")
    template_bucket = props.prop("_template_bucket", "The template_bucket property.")
    icicle_bucket = props.prop("_icicle_bucket", "The icicle_bucket property.")
    provider_image_bucket = props.prop("_provider_image_bucket", "The provider_image_bucket property.")

    def __repr__(self):
        return "%s - %r" % (super(ImageWarehouse, self).__repr__(), self.__dict__)

    def __str__(self):
        return "%s - buckets(%s, %s, %s, %s)" % (self.url, self.target_image_bucket, self.template_bucket, self.icicle_bucket, self.provider_image_bucket)

    def __init__(self, url=None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.http = httplib2.Http()

        if(not url):
            url = ApplicationConfiguration().configuration['warehouse']
            self.log.debug("Property (url) not specified.  Pulling from application configuration: %s" % (url, ))

        self.image_bucket = ApplicationConfiguration().configuration['image_bucket']
        self.build_bucket = ApplicationConfiguration().configuration['build_bucket']
        self.target_image_bucket = ApplicationConfiguration().configuration['target_bucket']
        self.template_bucket = ApplicationConfiguration().configuration['template_bucket']
        self.icicle_bucket = ApplicationConfiguration().configuration['icicle_bucket']
        self.provider_image_bucket = ApplicationConfiguration().configuration['provider_bucket']

        if (url.endswith('/')):
            self.url = url[0:len(url)-1]
        else:
            self.url = url

        self.log.debug("Created Image Warehouse instance %s" % (self, ))

    def _http_request(self, url, method, body = None, content_type = 'text/plain'):
        try:
            return self.http.request(url, method, body, headers={'content-type': content_type})
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def _http_get(self, url):
        return self._http_request(url, 'GET')[1]

    def _http_post(self, url, body, content_type):
        return self._http_request(url, 'POST', body, content_type)[1]

    def _http_put(self, url, body = None):
        self._http_request(url, 'PUT', body)[1]

    def create_bucket_at_url(self, url):
        response_headers, response = self._http_request(url, 'PUT')
        status = int(response_headers["status"])
        if(399 < status < 600):
            # raise RuntimeError("Could not create bucket: %s" % url)
            self.log.info("Creating a bucket returned status %s." % (status, ))
            return False
        else:
            return True

    def __url_for_id_of_type(self, object_id, object_type, create=True):
        bucket = getattr(self, "_%s_bucket" % (object_type, ))
        if(bucket):
            if(create):
                self.create_bucket_at_url("%s/%s" % (self.url, bucket))
            object_url = "%s/%s/%s" % (self.url, bucket, object_id)
        else:
            object_url ="%s/%s" % (self.url, object_id)

        return object_url

    def query(self, object_type, expression):
        object_url = self.__url_for_id_of_type("_query", object_type, create=False)
        self.log.debug("Querying (%s) with expression (%s)" % (object_url, expression))
        xml = self._http_post(object_url, expression, 'application/x-www-form-urlencoded')
        if not xml:
            return []
        return map(lambda n: n.content, libxml2.parseDoc(xml).xpathEval("/objects/object/key"))

    def post_on_object_with_id_of_type(self, object_id, object_type, post_data):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        return self._http_post(object_url, urllib.urlencode(post_data), 'application/x-www-form-urlencoded')

    def object_with_id_of_type(self, object_id, object_type, metadata_keys=()):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        obj = self._http_get(object_url)
        if(len(metadata_keys) > 0):
            metadata = self.metadata_for_id_of_type(metadata_keys, object_id, object_type)
        else:
            metadata = {}
        return obj, metadata

    def object_for_target_image_id(self, target_image_id, object_type, metadata_keys=()):
        object_url = self.__url_for_id_of_type(target_image_id, "target_image", create=False)
        object_id = self._http_get("%s/%s" % (object_url, object_type))

        the_object, metadata = self.object_with_id_of_type(object_id, object_type, metadata_keys)
        return object_id, the_object, metadata

    def delete_object_at_url(self, object_url):
        response_headers, response = self._http_request(object_url, 'DELETE')
        status = int(response_headers["status"])
        if(status == 200):
            return True
        else:
            self.log.error("Unable to delete object from %s.  Warehouse returned status %s." % (object_url, status))
            return False

    def delete_object_with_id_of_type(self, object_id, object_type):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        return self.delete_object_at_url(object_url)

    def set_metadata_for_id_of_type(self, metadata, object_id, object_type):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        self.set_metadata_for_object_at_url(metadata, object_url)

    def set_metadata_for_object_at_url(self, metadata, object_url):
        self.log.debug("Setting metadata (%s) for %s" % (metadata, object_url))
        for item in metadata:
            self._http_put("%s/%s" % (object_url, item), str(metadata[item]))

    def metadata_for_id_of_type(self, metadata_keys, object_id, object_type):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        return self.metadata_for_object_at_url(metadata_keys, object_url)

    def metadata_for_object_at_url(self, metadata_keys, object_url):
        self.log.debug("Getting metadata (%s) from %s" % (metadata_keys, object_url))
        metadata = dict()
        for item in metadata_keys:
            metadata.update( { item : self._http_get("%s/%s" % (object_url, item)) } )
        return metadata

    def store_image(self, image_id, image_xml, metadata=None):
        if(not image_id):
            image_id = str(uuid.uuid4())
        object_url = self.__url_for_id_of_type(image_id, object_type="image")

        self._http_put(object_url, image_xml)

        meta_data = dict(uuid=str(image_id), object_type="image")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return image_id

    def store_build(self, build_id, metadata=None):
        if(not build_id):
            build_id = str(uuid.uuid4())
        object_url = self.__url_for_id_of_type(build_id, object_type="build")

        self._http_put(object_url)

        meta_data = dict(uuid=str(build_id), object_type="build")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return build_id

    def _upload_image_file(self, object_url, image_file_path):
        try:
            image_file = open(image_file_path)

            # Upload the image itself
            image_size = os.path.getsize(image_file_path)
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, object_url)
            curl.setopt(pycurl.HTTPHEADER, ["User-Agent: Load Tool (PyCURL Load Tool)"])
            curl.setopt(pycurl.PUT, 1)
            curl.setopt(pycurl.INFILE, image_file)
            curl.setopt(pycurl.INFILESIZE, image_size)
            curl.perform()
            curl.close()
            image_file.close()
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def store_target_image(self, target_image_id, image_file_path, metadata=None):
        if(not target_image_id):
            target_image_id = str(uuid.uuid4())
        object_url = self.__url_for_id_of_type(target_image_id, "target_image")

        if image_file_path:
            self._upload_image_file(object_url, image_file_path)
        else:
            self._http_put(object_url)

        meta_data = dict(uuid=target_image_id, object_type="target_image")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return target_image_id

    def create_provider_image(self, image_id, txt=None, metadata=None):
        if(not image_id):
            image_id = str(uuid.uuid4())
        object_url = self.__url_for_id_of_type(image_id, object_type="provider_image")
        if(not txt):
            if(metadata):
                txt = "This object has the following metadata keys: %s" % (metadata.keys(), )
            else:
                txt = "This object only exists to hold metadata."

        self._http_put(object_url, txt)

        meta_data = dict(uuid=image_id, object_type="provider_image")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return image_id

    def store_template(self, template, template_id=None, metadata=None):
        if(not template_id):
            template_id = str(uuid.uuid4())
        object_url = self.__url_for_id_of_type(template_id, object_type="template")

        self._http_put(object_url, template)

        meta_data = dict(uuid=template_id, object_type="template")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return template_id

    def store_icicle(self, icicle, icicle_id=None, metadata=None):
        if(not icicle_id):
            icicle_id = str(uuid.uuid4())
        object_url = self.__url_for_id_of_type(icicle_id, object_type="icicle")

        self._http_put(object_url, icicle)

        meta_data = dict(uuid=icicle_id, object_type="icicle")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return icicle_id

    def icicle_with_id(self, icicle_id, metadata_keys=()):
        return self.object_with_id_of_type(icicle_id, "icicle", metadata_keys)

    def icicle_for_target_image_id(self, target_image_id, metadata_keys=()):
        return self.object_for_target_image_id(target_image_id, "icicle", metadata_keys)

    def template_with_id(self, template_id, metadata_keys=()):
        return self.object_with_id_of_type(template_id, "template", metadata_keys)

    def template_for_target_image_id(self, target_image_id, metadata_keys=()):
        return self.object_for_target_image_id(target_image_id, "template", metadata_keys)

    def target_image_with_id(self, target_image_id, metadata_keys=()):
        return self.object_with_id_of_type(target_image_id, "target_image", metadata_keys)

    def remove_template_with_id(self, template_id):
        return self.delete_object_with_id_of_type(template_id, "template")

    def remove_icicle_with_id(self, icicle_id):
        return self.delete_object_with_id_of_type(icicle_id, "icicle")

    def remove_target_image_with_id(self, target_image_id):
        return self.delete_object_with_id_of_type(target_image_id, "target_image")

class WarehouseError(Exception):
    """Error related to image warehouse interactions."""
    def __init__(self, value):
        super(WarehouseError, self).__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)
