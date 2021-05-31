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

    def test_create_copy_creates_separate_instance_with_same_values(self):
        orig_blob = cloud_storage_emulator.Blob('name', 'string', 'png')
        copy_blob = cloud_storage_emulator.Blob.create_copy(orig_blob)
        self.assertNotEqual(orig_blob, copy_blob)
        self.assertEqual(orig_blob.name, copy_blob.name)
        self.assertEqual(
            orig_blob.download_as_bytes(), copy_blob.download_as_bytes())
        self.assertEqual(orig_blob.content_type, copy_blob.content_type)


class CloudStorageEmulatorUnitTests(test_utils.TestBase):
    """Tests for CloudStorageEmulator."""

    def setUp(self):
        super(CloudStorageEmulatorUnitTests, self).setUp()
        self.emulator = cloud_storage_emulator.CloudStorageEmulator()

    def test_get_blob_returns_correct_blob(self, filepath):
        return self._blob_dict.get(filepath)

    def upload_blob(self, filepath, blob):
        self._blob_dict[filepath] = blob

    def delete_blob(self, filepath):
        del self._blob_dict[filepath]

    def copy_blob(self, blob, new_name):
        self._blob_dict[new_name] = Blob.create_copy(blob)

    def list_blobs(self, prefix):
        return [
            value for key, value in self._blob_dict.items()
            if key.startswith(prefix)
        ]

    def reset(self):
        self._blob_dict = {}

