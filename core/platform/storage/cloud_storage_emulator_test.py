# coding: utf-8
#
# Copyright 2021 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for cloud_storage_emulator."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

from core.platform.storage import cloud_storage_emulator
from core.tests import test_utils


class BlobUnitTests(test_utils.TestBase):
    """Tests for Blob."""

    def test_init_blob_with_str_creates_blob(self):
        blob = cloud_storage_emulator.Blob('name', 'string', 'png')
        self.assertEqual(blob.name, 'name')
        self.assertEqual(blob.download_as_bytes(), b'string')
        self.assertEqual(blob.content_type, 'png')

    def test_init_blob_with_bytes_creates_blob(self):
        blob = cloud_storage_emulator.Blob('name', b'string', 'png')
        self.assertEqual(blob.name, 'name')
        self.assertEqual(blob.download_as_bytes(), b'string')
        self.assertEqual(blob.content_type, 'png')

    def test_create_copy(self):
        orig_blob = cloud_storage_emulator.Blob('name', 'string', 'png')
        copy_blob = cloud_storage_emulator.Blob.create_copy(orig_blob)
        self.assertNotEqual(orig_blob, copy_blob)
        self.assertEqual(orig_blob.name, copy_blob.name)
        print(copy_blob.download_as_bytes())
        self.assertEqual(
            orig_blob.download_as_bytes(), copy_blob.download_as_bytes())
        self.assertEqual(orig_blob.content_type, copy_blob.content_type)


class CloudStorageEmulatorUnitTests(test_utils.TestBase):
    """Tests for CloudStorageEmulator."""

    def setUp(self):
        super(CloudStorageEmulatorUnitTests, self).setUp()
        self.emulator = cloud_storage_emulator.CloudStorageEmulator()
        self.blob1 = cloud_storage_emulator.Blob(
            '/file/path.png', b'data', 'png')
        self.blob2 = cloud_storage_emulator.Blob(
            '/file/path2.png', b'data2', 'png')
        self.blob3 = cloud_storage_emulator.Blob(
            '/different/path.png', b'data2', 'png')

    def test_get_blob(self):
        self.emulator._blob_dict['/file/path.png'] = self.blob1

        self.assertEqual(self.emulator.get_blob('/file/path.png'), self.blob1)

    def test_upload_blob(self):
        self.emulator.upload_blob('/file/path.png', self.blob1)

        self.assertEqual(self.emulator._blob_dict['/file/path.png'], self.blob1)

    def test_delete_blob(self):
        self.emulator._blob_dict['/file/path.png'] = self.blob1
        self.emulator.delete_blob('/file/path.png')

        self.assertIsNone(self.emulator.get_blob('/file/path.png'))

    def test_copy_blob(self):
        self.emulator._blob_dict['/file/path.png'] = self.blob1
        self.emulator.copy_blob(
            self.emulator._blob_dict['/file/path.png'], '/different/path2.png')

        orig_blob = self.emulator.get_blob('/file/path.png')
        copy_blob = self.emulator.get_blob('/different/path2.png')
        self.assertEqual(orig_blob.name, copy_blob.name)
        self.assertEqual(
            orig_blob.download_as_bytes(), copy_blob.download_as_bytes())

    def test_list_blobs(self):
        self.emulator._blob_dict['/file/path.png'] = self.blob1
        self.emulator._blob_dict['/file/path2.png'] = self.blob2
        self.emulator._blob_dict['/different/path.png'] = self.blob3
        self.assertItemsEqual(
            self.emulator.list_blobs('/'), [self.blob1, self.blob2, self.blob3])
        self.assertItemsEqual(
            self.emulator.list_blobs('/file'), [self.blob1, self.blob2])
        self.assertItemsEqual(
            self.emulator.list_blobs('/different'), [self.blob3])

    def test_reset(self):
        self.emulator._blob_dict['/file/path.png'] = self.blob1
        self.emulator.reset()

        self.assertEqual(self.emulator._blob_dict, {})


