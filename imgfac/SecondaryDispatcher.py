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
import os.path
import json
import shutil
from imgfac.Singleton import Singleton
from imgfac.NotificationCenter import NotificationCenter
from threading import BoundedSemaphore, Thread
from PersistentImageManager import PersistentImageManager
from ReservationManager import ReservationManager
from TargetImage import TargetImage
from SecondaryHelper import SecondaryHelper
import uuid

SECONDARIES = "/etc/imagefactory/secondaries.json"

class SecondaryDispatcher(Singleton):

    def _singleton_init(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.pending_uploads = dict()
        self.pending_uploads_lock = BoundedSemaphore()
        self.pim = PersistentImageManager.default_manager()
        self.res = ReservationManager()
        self.secondaries = { } 
        if os.path.isfile(SECONDARIES):
            try:
                secs = open(SECONDARIES, "r")
                self.secondaries = json.load(secs)
                secs.close()
            except:
                self.log.warning("Unable to load JSON for secondaries from %s", SECONDARIES)
        if not 'targets' in self.secondaries:
            self.secondaries['targets'] = { }
        if not 'providers' in self.secondaries:
            self.secondaries['providers'] = { }

    def queue_pending_upload(self, target_image_uuid):
        # Create a UUID - map it to the target_image_uuid and return it
        # TODO: Expire these somehow
        upload_uuid = str(uuid.uuid4())
        self.pending_uploads_lock.acquire()
        try:
            self.pending_uploads[upload_uuid] = target_image_uuid
        finally:
            self.pending_uploads_lock.release()
        return upload_uuid

    def target_image_for_upload_uuid(self, upload_uuid):
        # Return the target_image UUID for a given upload UUID if it exists
        # and remove it from the dict.  Return None if the UUID is not in the dict.
        self.pending_uploads_lock.acquire()
        target_image_uuid = None
        try:
            if upload_uuid in self.pending_uploads:
                target_image_uuid = self.pending_uploads[upload_uuid]
                del self.pending_uploads[upload_uuid]
        finally:
            self.pending_uploads_lock.release()

        return target_image_uuid
                
    def update_target_image_body(self, target_image, new_body):
        # Called during the clone process - we background the actual copy
        # and update the target_image in question to COMPLETED when the copy is finished
        # This allows the HTTP transaction to complete - in testing some upload clients
        # timed out waiting for the local copy to complete
        # (bottle.py internally processes all uploaded files to completion, storing them as unnamed temporary
        # files)
        target_update_thread = Thread(target=self._update_target_image_body, args=(target_image, new_body))
        target_update_thread.start()

    def _update_target_image_body(self, target_image, new_body):
        try:
            self.log.debug("Copying incoming file to %s" % (target_image.data))
            dest = open(target_image.data,"w")
            shutil.copyfileobj(new_body, dest, 16384)
            self.log.debug("Finished copying incoming file to %s" % (target_image.data))
            target_image.status="COMPLETE"
        except Exception as e:
            self.log.debug("Exception encountered when attempting to update target_image body")
            self.log.exception(e)
            target_image.status="FAILED"
        finally:
            self.pim.save_image(target_image)

    def prep_target_image_clone(self, request_data, target_image_id):
        # Request data should contain all target_image metadata to be cloned
        # If target_image with this ID doest not exist, create it and establish an
        # upload UUID and return both.
        # If taget_image already exists, return just the existing target_image

        upload_id = None
        self.res.get_named_lock(target_image_id)
        # At this point no other thread, either remote or local, can operate on this ID
        # The image either already exists or it doesn't.  If it doesn't we can safely create
        # it without worrying about concurrency problems.
        try:
            target_image = self.pim.image_with_id(target_image_id)
            if not target_image:
                upload_id = self.queue_pending_upload(target_image_id)
                target_image = TargetImage(image_id=target_image_id)
                metadata_keys = target_image.metadata()
                for data_element in request_data.keys():
                    if not (data_element in metadata_keys):
                        self.log.warning("Metadata field (%s) in incoming target_image clone request is non-standard - skipping" % (data_element))
                    else:
                         setattr(target_image, data_element, request_data[data_element])
                # The posted image will, of course, be complete, so fix status here
                target_image.status = "PENDING"
                target_image.percent_complete = 0
                target_image.status_detail = { 'activity': 'Image being cloned from primary factory - initial metadata set', 'error':None }
                self.pim.add_image(target_image)
                self.pim.save_image(target_image)
                self.log.debug("Completed save of target_image (%s)" % target_image.identifier)
        finally:
            self.res.release_named_lock(target_image_id)

        return (target_image, upload_id)

    def get_secondary(self, target, provider):
        if provider in self.secondaries['providers']:
            return self.secondaries['providers'][provider]
        elif target in self.secondaries['targets']:
            return self.secondaries['targets'][target]
        else:
            return None

    def get_helper(self, secondary):
        try:
            helper = SecondaryHelper(**secondary)
            return helper
        except Exception as e:
            self.log.error("Exception encountered when trying to create secondary helper object")
            self.log.error("Secondary details: %s" % (secondary))
            self.log.exception(e) 
