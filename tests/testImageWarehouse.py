#!/usr/bin/env python
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

import unittest
import logging
import uuid
import time
import os
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageWarehouse import ImageWarehouse

class testImageWarehouse(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.NOTSET, format='%(asctime)s %(levelname)s %(name)s pid(%(process)d) Message: %(message)s', filename='/tmp/imagefactory-unittests.log')
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
        self.metadata = dict(key1="value1", key2="value2", key3="value3")

    def tearDown(self):
        del self.warehouse
        del self.metadata

    def testImageWarehouseMethods(self):
        """Tests CRUD operations on target images, templates, icicles, and metadata on those objects..."""
        # TARGET IMAGE
        # store a target image
        target_image_id = str(uuid.uuid4())
        file_content = "This is just to test storing a target image in warehouse.  There is not much to see here."
        file_path = "/tmp/testImageWarehouse_testStoreAndFetchTargetImage.%s" % (target_image_id, )
        with open(file_path, 'w') as test_file:
            test_file.write(file_content)
            test_file.close()
        self.warehouse.store_target_image(target_image_id, file_path, metadata=self.metadata)
        # now fetch that target image
        target_image, metadata = self.warehouse.target_image_with_id(target_image_id, metadata_keys=self.metadata.keys())
        # now make the assertions
        self.assertEqual(file_content, target_image)
        self.assertEqual(self.metadata, metadata)

        # TEMPLATE
        template_content = "<template>This is a test template. There is not much to see here.</template>"
        # store the template and let an id get assigned
        template_id = self.warehouse.store_template(template_content)
        self.assertIsNotNone(template_id)
        # store the template with a specified id
        template_id_known = str(uuid.uuid4())
        template_id2 = self.warehouse.store_template(template_content, template_id_known)
        self.assertEqual(template_id_known, template_id2)
        # fetch the templates
        fetched_template_content, template_metadata1 = self.warehouse.template_with_id(template_id)
        self.assertEqual(template_content, fetched_template_content)
        fetched_template_content2, template_metadata2 = self.warehouse.template_with_id(template_id_known)
        self.assertEqual(template_content, fetched_template_content2)
        # set the template id for a target image and fetch it back
        self.warehouse.set_metadata_for_id_of_type(dict(template=template_id), target_image_id, "target_image")
        template_id3, fetched_template_content3, template_metadata3 = self.warehouse.template_for_target_image_id(target_image_id)
        self.assertEqual(template_id, template_id3)
        self.assertEqual(template_content, fetched_template_content3)

        # ICICLE
        icicle_content = "<icicle>This is a test icicle. There is not much to see here.</icicle>"
        # store the icicle and let an id get assigned
        icicle_id = self.warehouse.store_icicle(icicle_content)
        self.assertIsNotNone(icicle_id)
        # store the icicle with a specified id
        icicle_id_known = str(uuid.uuid4())
        icicle_id2 = self.warehouse.store_icicle(icicle_content, icicle_id_known)
        self.assertEqual(icicle_id_known, icicle_id2)
        # fetch the icicles
        fetched_icicle_content, icicle_metadata1 = self.warehouse.icicle_with_id(icicle_id)
        self.assertEqual(icicle_content, fetched_icicle_content)
        fetched_icicle_content2, icicle_metadata2 = self.warehouse.icicle_with_id(icicle_id_known)
        self.assertEqual(icicle_content, fetched_icicle_content2)
        # set the icicle id for a target image and fetch it back
        self.warehouse.set_metadata_for_id_of_type(dict(icicle=icicle_id), target_image_id, "target_image")
        icicle_id3, fetched_icicle_content3, icicle_metadata3 = self.warehouse.icicle_for_target_image_id(target_image_id)
        self.assertEqual(icicle_id, icicle_id3)
        self.assertEqual(icicle_content, fetched_icicle_content3)

        self.assertTrue(self.warehouse.remove_target_image_with_id(target_image_id))
        self.assertTrue(self.warehouse.remove_template_with_id(template_id))
        self.assertTrue(self.warehouse.remove_template_with_id(template_id2))
        self.assertTrue(self.warehouse.remove_icicle_with_id(icicle_id))
        self.assertTrue(self.warehouse.remove_icicle_with_id(icicle_id2))

        os.remove(file_path)

    def testImageAndBuildMethods(self):
        """Tests CRUD operations on images, builds and metadata on those objects..."""
        image_xml = '<image/>'

        image_id = self.warehouse.store_image(None, image_xml, self.metadata)

        self.assertIsNotNone(image_id)

        image_body, metadata = self.warehouse.object_with_id_of_type(image_id, 'image', self.metadata.keys())

        self.assertEqual(image_xml, image_body)
        self.assertEqual(self.metadata, metadata)

        build_id = self.warehouse.store_build(None, self.metadata)

        build_body, metadata = self.warehouse.object_with_id_of_type(build_id, 'build', self.metadata.keys())

        self.assertEqual('', build_body)
        self.assertEqual(self.metadata, metadata)

        ids = self.warehouse.query('build', '$object_type == "build" && $key1 == "value1"')

        self.assertIn(build_id, ids)

    def testBucketCreation(self):
        # self.assert_(self.warehouse.create_bucket_at_url("%s/unittests-create_bucket/%s" % (self.warehouse.url, str(uuid.uuid4()))))
        self.warehouse.create_bucket_at_url("%s/unittests-create_bucket" % (self.warehouse.url, ))
        self.assert_(self.warehouse.create_bucket_at_url("%s/unittests-create_bucket/%s" % (self.warehouse.url, time.asctime().replace(' ', '-'))))



if __name__ == '__main__':
    unittest.main()
