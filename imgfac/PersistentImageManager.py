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

from ApplicationConfiguration import ApplicationConfiguration


class PersistentImageManager(object):
    """ Abstract base class for the Persistence managers  """


    _default_manager = None

    @classmethod
    def default_manager(cls):
        if not cls._default_manager:
            appconfig = ApplicationConfiguration().configuration
            class_name = appconfig['image_manager'].capitalize() + "PersistentImageManager"
            kwargs = appconfig['image_manager_args'] 
            # The current defaults are 'file' for class name and 
            # { "storage_location": "/var/lib/imagefactory/storage" } for the args
            pim_module = __import__(class_name, globals(), locals(), [ class_name ], -1)
            pim_class = getattr(pim_module, class_name)
            cls._default_manager = pim_class(**kwargs)
        return cls._default_manager

    def __init__(self, storage_path = None):
        raise NotImplementedError("PersistentImageManager is an abstract class.  You must instantiate a real manager.")

    def image_with_id(self, image_id):
        """
        TODO: Docstring for image_with_id

        @param image_id TODO 

        @return TODO
        """
        raise NotImplementedError("image_with_id() not implemented - cannot continue")

    def images_from_query(self, query):
        """
        TODO: Docstring for images_from_query

        @param image_id TODO 

        @return TODO
        """
        raise NotImplementedError("images_from_query() not implemented - cannot continue")


    def add_image(self, image):
        """
        TODO: Docstring for add_image

        @param image TODO 

        @return TODO
        """
        raise NotImplementedError("add_image() not implemented - cannot continue")

    def save_image(self, image):
        """
        TODO: Docstring for save_image

        @param image TODO

        @return TODO
        """
        raise NotImplementedError("save_image() not implemented - cannot continue")

    def delete_image_with_id(self, image_id):
        """
        TODO: Docstring for delete_image_with_id

        @param image_id TODO 

        @return TODO
        """
        raise NotImplementedError("delete_image_with_id() not implemented - cannot continue")
