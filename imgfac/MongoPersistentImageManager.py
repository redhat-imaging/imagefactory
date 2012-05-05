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
import os
import os.path
import json
import pymongo
from copy import copy
from props import prop
from ImageFactoryException import ImageFactoryException
from PersistentImageManager import PersistentImageManager

STORAGE_PATH = '/var/lib/imagefactory/storage'
METADATA_EXT = '.meta'
BODY_EXT = '.body'
DB_NAME = "factory_db"
COLLECTION_NAME = "factory_collection"


class MongoPersistentImageManager(PersistentImageManager):
    """ TODO: Docstring for PersistentImageManager  """

    storage_path = prop("_storage_path")

    def __init__(self, storage_path=STORAGE_PATH):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        if not os.path.exists(storage_path):
            self.log.debug("Creating directory (%s) for persistent storage" % (storage_path))
            os.makedirs(storage_path)
        elif not os.path.isdir(storage_path):
            raise ImageFactoryException("Storage location (%s) already exists and is not a directory - cannot init persistence" % (storage_path))
        else:
            # TODO: verify that we can write to this location
            pass
        self.storage_path = storage_path
        self.con = pymongo.Connection()
        self.db = self.con[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]

    def _to_mongo_meta(self, meta):
        # Take our view of the metadata and make the mongo view
        # Use our "identifier" as the mongo "_id"
        # Explicitly recommended here: http://www.mongodb.org/display/DOCS/Object+IDs
        # TODO: Pack UUID into BSON representation
        mongometa = copy(meta)
        mongometa['_id'] = meta['identifier']
        return mongometa

    def _from_mongo_meta(self, mongometa):
        # Take mongo metadata and return the internal view
        meta = copy(mongometa)
        # This is just a duplicate
        del meta['_id']
        return meta

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

        #I don't think we want this as it will overwrite the "data" element
        #read from the store.
        #self.add_image(image)

        #just set ourselves as the manager
        image.persistent_manager = self

        return image


    def image_with_id(self, image_id):
        """
        TODO: Docstring for image_with_id

        @param image_id TODO 

        @return TODO
        """
        try:
            metadata = self._from_mongo_meta(self.collection.find_one( { "_id": image_id } ))
        except Exception as e:
            self.log.debug('Exception caught: %s' % e)
            return None

        if not metadata:
            raise ImageFactoryException("Unable to retrieve object metadata in Mongo for ID (%s)" % (image_id))

        return self._image_from_metadata(metadata)


    def images_from_query(self, query):
        images = [ ]
        for image_meta in self.collection.find(query):
            if "type" in image_meta:
                images.append(self._image_from_metadata(image_meta))
            else:
                self.log.warn("Found mongo record with no 'type' key - id (%s)" % (image_meta['_id']))
        return images 

    def add_image(self, image):
        """
        Add a PersistentImage-type object to this PersistenImageManager
        This should only be called with an image that has not yet been added to the store.
        To retrieve a previously persisted image use image_with_id() or image_query()

        @param image TODO 

        @return TODO
        """
        metadata = self.collection.find_one( { "_id": image.identifier } )
        if metadata:
            raise ImageFactoryException("Image %s already managed, use image_with_id() and save_image()" % (image.identifier))

        image.persistent_manager = self
        basename = self.storage_path + '/' + str(image.identifier)
        body_path = basename + BODY_EXT
        image.data = body_path
        try:
            if not os.path.isfile(body_path):
                open(body_path, 'w').close()
                self.log.debug('Created file %s' % body_path)
        except IOError as e:
            self.log.debug('Exception caught: %s' % e)

        self._save_image(image)

    def save_image(self, image):
        """
        TODO: Docstring for save_image

        @param image TODO

        @return TODO
        """
        image_id = str(image.identifier)
        metadata = self._from_mongo_meta(self.collection.find_one( { "_id": image_id } ))
        if not metadata:
            raise ImageFactoryException('Image %s not managed, use "add_image()" first.' % image_id)
        self._save_image(image)

    def _save_image(self, image):
        try:
            meta = {'type': type(image).__name__}
            for mdprop in image.metadata():
                meta[mdprop] = getattr(image, mdprop, None)
            # Set upsert to true - allows this function to do the initial insert for add_image
            # We check existence for save_image() already
            self.collection.update( { '_id': image.identifier}, self._to_mongo_meta(meta), upsert=True )
            self.log.debug("Saved metadata for image (%s): %s" % (image.identifier, meta))
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
        body_path = basename + BODY_EXT
        try:
            os.remove(body_path)
        except Exception as e:
            self.log.warn('Unable to delete file: %s' % e)

        try:
            self.collection.remove(image_id)
        except Exception as e:
            self.log.warn('Unable to remove mongo record: %s' % e)
