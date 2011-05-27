#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2010-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import logging
import pycurl
import httplib2
import urllib
import uuid
import os
from imagefactory.ApplicationConfiguration import ApplicationConfiguration


class ImageWarehouse(object):

    # Properties
    def url():
        doc = "The url property."
        def fget(self):
            return self._url
        def fset(self, value):
            self._url = value
        def fdel(self):
            del self._url
        return locals()
    url = property(**url())

    def image_bucket():
        doc = "The image_bucket property."
        def fget(self):
            return self._image_bucket
        def fset(self, value):
            self._image_bucket = value
        def fdel(self):
            del self._image_bucket
        return locals()
    image_bucket = property(**image_bucket())

    def template_bucket():
        doc = "The template_bucket property."
        def fget(self):
            return self._template_bucket
        def fset(self, value):
            self._template_bucket = value
        def fdel(self):
            del self._template_bucket
        return locals()
    template_bucket = property(**template_bucket())

    def icicle_bucket():
        doc = "The icicle_bucket property."
        def fget(self):
            return self._icicle_bucket
        def fset(self, value):
            self._icicle_bucket = value
        def fdel(self):
            del self._icicle_bucket
        return locals()
    icicle_bucket = property(**icicle_bucket())

    def provider_image_bucket():
        doc = "The provider_image_bucket property."
        def fget(self):
            return self._provider_image_bucket
        def fset(self, value):
            self._provider_image_bucket = value
        def fdel(self):
            del self._provider_image_bucket
        return locals()
    provider_image_bucket = property(**provider_image_bucket())

    # Properties end

    def __repr__(self):
        return "%s - %r" % (super(ImageWarehouse, self).__repr__(), self.__dict__)

    def __str__(self):
        return "%s - buckets(%s, %s, %s, %s)" % (self.url, self.image_bucket, self.template_bucket, self.icicle_bucket, self.provider_image_bucket)

    def __init__(self, url=None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.http = httplib2.Http()

        if(not url):
            url = ApplicationConfiguration().configuration['warehouse']
            self.log.debug("Property (url) not specified.  Pulling from application configuration: %s" % (url, ))

        self.image_bucket = ApplicationConfiguration().configuration['image_bucket']
        self.template_bucket = ApplicationConfiguration().configuration['template_bucket']
        self.icicle_bucket = ApplicationConfiguration().configuration['icicle_bucket']
        self.provider_image_bucket = ApplicationConfiguration().configuration['provider_bucket']

        if (url.endswith('/')):
             self.url = url[0:len(url)-1]
        else:
            self.url = url

        self.log.debug("Created Image Warehouse instance %s" % (self, ))

    def create_bucket_at_url(self, url):
        try:
            response_headers, response = self.http.request(url, "PUT", headers={'content-type':'text/plain'})
            status = int(response_headers["status"])
            if(399 < status < 600):
                # raise RuntimeError("Could not create bucket: %s" % url)
                self.log.info("Creating a bucket returned status %s.  If only iwhd would provide a sane way to know if a bucket exists so we wouldn't have to try and create one every time..." % (status, ))
                return False
            else:
                return True
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def __url_for_id_of_type(self, object_id, object_type, create=True):
        bucket = getattr(self, "_%s_bucket" % (object_type, ))
        if(bucket):
            if(create):
                self.create_bucket_at_url("%s/%s" % (self.url, bucket))
            object_url = "%s/%s/%s" % (self.url, bucket, object_id)
        else:
            object_url ="%s/%s" % (self.url, object_id)

        return object_url

    def post_on_object_with_id_of_type(self, object_id, object_type, post_data):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        try:
            response_headers, response = self.http.request(object_url, "POST", urllib.urlencode(post_data), headers={'Content-Type': 'application/x-www-form-urlencoded'})
            return response
        except Exception, e:
            raise WarehouseError("Problem encountered trying to POST to image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def object_with_id_of_type(self, object_id, object_type, metadata_keys=()):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        try:
            response_headers, response = self.http.request(object_url, "GET", headers={'content-type':'text/plain'})
            if(len(metadata_keys) > 0):
                metadata = self.metadata_for_id_of_type(metadata_keys, object_id, object_type)
            else:
                metadata = {}
            return response, metadata
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def object_for_image_id(self, image_id, object_type, metadata_keys=()):
        object_url = self.__url_for_id_of_type(image_id, "image", create=False)
        try:
            response_headers, object_id = self.http.request("%s/%s" % (object_url, object_type), "GET", headers={'content-type':'text/plain'})
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

        the_object, metadata = self.object_with_id_of_type(object_id, object_type, metadata_keys)
        return object_id, the_object, metadata

    def delete_object_at_url(self, object_url):
        try:
            response_headers, response = self.http.request(object_url, "DELETE", headers={'content-type':'text/plain'})
            status = int(response_headers["status"])
            if(status == 200):
                return True
            else:
                self.log.error("Unable to delete object from %s.  Warehouse returned status %s." % (object_url, status))
                return False
        except Exception, e:
            raise WarehouseError("Problem encountered trying to delete object at %s.\nPlease check that iwhd is running and reachable.\nException text: %s" % (object_url, e))

    def delete_object_with_id_of_type(self, object_id, object_type):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        return self.delete_object_at_url(object_url)

    def set_metadata_for_id_of_type(self, metadata, object_id, object_type):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        self.set_metadata_for_object_at_url(metadata, object_url)

    def set_metadata_for_object_at_url(self, metadata, object_url):
        try:
            self.log.debug("Setting metadata (%s) for %s" % (metadata, object_url))
            for item in metadata:
                response_header, response = self.http.request("%s/%s" % (object_url, item), "PUT", body=str(metadata[item]), headers={'content-type':'text/plain'})
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def metadata_for_id_of_type(self, metadata_keys, object_id, object_type):
        object_url = self.__url_for_id_of_type(object_id, object_type, create=False)
        return self.metadata_for_object_at_url(metadata_keys, object_url)

    def metadata_for_object_at_url(self, metadata_keys, object_url):
        try:
            self.log.debug("Getting metadata (%s) from %s" % (metadata_keys, object_url))
            metadata = dict()
            for item in metadata_keys:
                response_header, response = self.http.request("%s/%s" % (object_url, item), "GET", headers={'content-type':'text/plain'})
                metadata.update( { item : response } )
            return metadata
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

    def store_image(self, image_id, image_file_path, metadata=None):
        object_url = self.__url_for_id_of_type(image_id, "image")
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

        meta_data = dict(uuid=str(image_id), object_type="image")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

    def create_provider_image(self, image_id, txt=None, metadata=None):
        object_url = self.__url_for_id_of_type(image_id, object_type="provider_image")
        if(not txt):
            if(metadata):
                txt = "This object has the following metadata keys: %s" % (metadata.keys(), )
            else:
                txt = "This object only exists to hold metadata."

        try:
            response_headers, response = self.http.request(object_url, "PUT", body=txt, headers={'content-type':'text/plain'})
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

        meta_data = dict(uuid=str(image_id), object_type="provider_image")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

    def store_template(self, template, template_id=None, metadata=None):
        if(not template_id):
            template_id = uuid.uuid4()
        object_url = self.__url_for_id_of_type(template_id, object_type="template")

        try:
            response_headers, response = self.http.request(object_url, "PUT", body=template, headers={'content-type':'text/plain'})
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

        meta_data = dict(uuid=str(template_id), object_type="template")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return template_id

    def store_icicle(self, icicle, icicle_id=None, metadata=None):
        if(not icicle_id):
            icicle_id = uuid.uuid4()
        object_url = self.__url_for_id_of_type(icicle_id, object_type="icicle")

        try:
            response_headers, response = self.http.request(object_url, "PUT", body=icicle, headers={'content-type':'text/plain'})
        except Exception, e:
            raise WarehouseError("Problem encountered trying to reach image warehouse. Please check that iwhd is running and reachable.\nException text: %s" % (e, ))

        meta_data = dict(uuid=str(icicle_id), object_type="icicle")
        if(metadata):
            meta_data.update(metadata)
        self.set_metadata_for_object_at_url(meta_data, object_url)

        return icicle_id

    def icicle_with_id(self, icicle_id, metadata_keys=()):
        return self.object_with_id_of_type(icicle_id, "icicle", metadata_keys)

    def icicle_for_image_id(self, image_id, metadata_keys=()):
        return self.object_for_image_id(image_id, "icicle", metadata_keys)

    def template_with_id(self, template_id, metadata_keys=()):
        return self.object_with_id_of_type(template_id, "template", metadata_keys)

    def template_for_image_id(self, image_id, metadata_keys=()):
        return self.object_for_image_id(image_id, "template", metadata_keys)

    def image_with_id(self, image_id, metadata_keys=()):
        return self.object_with_id_of_type(image_id, "image", metadata_keys)

    def remove_template_with_id(self, template_id):
        return self.delete_object_with_id_of_type(template_id, "template")

    def remove_icicle_with_id(self, icicle_id):
        return self.delete_object_with_id_of_type(icicle_id, "icicle")

    def remove_image_with_id(self, image_id):
        return self.delete_object_with_id_of_type(image_id, "image")


class WarehouseError(Exception):
    """Error related to image warehouse interactions."""
    def __init__(self, value):
        super(WarehouseError, self).__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)
