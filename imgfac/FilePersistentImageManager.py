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

import logging
import re
import os
import os.path
import stat
import json
from props import prop
from ImageFactoryException import ImageFactoryException
from PersistentImageManager import PersistentImageManager
from threading import BoundedSemaphore

STORAGE_PATH = '/var/lib/imagefactory/storage'
METADATA_EXT = '.meta'
BODY_EXT = '.body'

class FilePersistentImageManager(PersistentImageManager):
    """ TODO: Docstring for PersistentImageManager  """

    storage_path = prop("_storage_path")

    def __init__(self, storage_path=STORAGE_PATH):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        if not os.path.exists(storage_path):
            self.log.debug("Creating directory (%s) for persistent storage" % (storage_path))
            os.makedirs(storage_path)
            os.chmod(storage_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        elif not os.path.isdir(storage_path):
            raise ImageFactoryException("Storage location (%s) already exists and is not a directory - cannot init persistence" % (storage_path))
        else:
            # TODO: verify that we can write to this location
            pass
        self.storage_path = storage_path
        self.metadata_lock = BoundedSemaphore()


    def _image_from_metadata(self, metadata):
        # Given the retrieved metadata from mongo, return a PersistentImage type object
        # with us as the persistent_manager.

        image_module = __import__(metadata['type'], globals(), locals(), [metadata['type']], -1)
        image_class = getattr(image_module, metadata['type'])
        image = image_class(metadata['identifier'])

        # We don't actually want a 'type' property in the resulting PersistentImage object
        del metadata['type']

        for key in image.metadata().union(metadata.keys()):
            setattr(image, key, metadata.get(key))

        #set ourselves as the manager
        image.persistent_manager = self

        return image


    def _metadata_from_file(self, metadatafile):
        self.metadata_lock.acquire()
        try:
            mdf = open(metadatafile, 'r')
            metadata = json.load(mdf)
            mdf.close()
        finally:
            self.metadata_lock.release()
        return metadata


    def image_with_id(self, image_id):
        """
        TODO: Docstring for image_with_id

        @param image_id TODO 

        @return TODO
        """
        metadatafile = self.storage_path + '/' + image_id + METADATA_EXT
        try:
            metadata = self._metadata_from_file(metadatafile)
        except Exception as e:
            self.log.debug('Exception caught: %s' % e)
            return None

        return self._image_from_metadata(metadata)


    def images_from_query(self, query):
        images = [ ]
        for storefileshortname in os.listdir(self.storage_path):
            storefilename = self.storage_path + '/' + storefileshortname
            if re.search(METADATA_EXT, storefilename):
                try:
                    metadata = self._metadata_from_file(storefilename)
                    match = True
                    for querykey in query:
                        if metadata[querykey] != query[querykey]:
                            match = False
                            break
                    if match:
                        images.append(self._image_from_metadata(metadata))
                except:
                    self.log.warn("Could not extract image metadata from file (%s)" % (storefilename))

        return images              


    def add_image(self, image):
        """
        TODO: Docstring for add_image

        @param image TODO 

        @return TODO
        """
        image.persistent_manager = self
        basename = self.storage_path + '/' + str(image.identifier)
        metadata_path = basename + METADATA_EXT
        body_path = basename + BODY_EXT
        image.data = body_path
        try:
            if not os.path.isfile(metadata_path):
                open(metadata_path, 'w').close()
                self.log.debug('Created file %s' % metadata_path)
            if not os.path.isfile(body_path):
                open(body_path, 'w').close()
                self.log.debug('Created file %s' % body_path)
        except IOError as e:
            self.log.debug('Exception caught: %s' % e)

        self.save_image(image)

    def save_image(self, image):
        """
        TODO: Docstring for save_image

        @param image TODO

        @return TODO
        """
        image_id = str(image.identifier)
        metadata_path = self.storage_path + '/' + image_id + METADATA_EXT
        if not os.path.isfile(metadata_path):
            raise ImageFactoryException('Image %s not managed, use "add_image()" first.' % image_id)
        try:
            meta = {'type': type(image).__name__}
            for mdprop in image.metadata():
                meta[mdprop] = getattr(image, mdprop, None)
 
            self.metadata_lock.acquire()
            try:
                mdf = open(metadata_path, 'w')
                json.dump(meta, mdf)
                mdf.close()
            finally:
                self.metadata_lock.release()

            self.log.debug("Saved metadata for image (%s): %s" % (image_id, meta))
        except Exception as e:
            self.log.debug('Exception caught: %s' % e)
            raise ImageFactoryException('Unable to save image metadata: %s' % e)

    def delete_image_with_id(self, image_id):
        """
        TODO: Docstring for delete_image_with_id

        @param image_id TODO 

        @return TODO
        """
        basename = self.storage_path + '/' + image_id
        metadata_path = basename + METADATA_EXT
        body_path = basename + BODY_EXT
        try:
            os.remove(metadata_path)
            os.remove(body_path)
        except Exception as e:
            self.log.warn('Unable to delete file: %s' % e)
