# coding: utf-8
#
# Copyright 2026 The Oppia Authors. All Rights Reserved.
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

"""Unit tests for the firebase_adapters module."""

from __future__ import annotations

import unittest
from unittest import mock

from core.jobs.types import firebase_adapters
from core.platform import models

auth_models, user_models = models.Registry.import_models(
    [models.Names.AUTH, models.Names.USER]
)


class FirebaseRecordTests(unittest.TestCase):
    def test_init_with_valid_args_sets_fields(self) -> None:
        record = firebase_adapters.FirebaseRecord(
            auth_id='aid', email='a@a.com', disabled=False
        )
        self.assertEqual(record.auth_id, 'aid')
        self.assertEqual(record.email, 'a@a.com')
        self.assertFalse(record.disabled)

    def test_from_export_with_exported_record_sets_fields(self) -> None:
        export_record = mock.Mock(uid='uid', email='a@a.com', disabled=False)
        record = firebase_adapters.FirebaseRecord.from_export(export_record)
        self.assertEqual(record.auth_id, 'uid')
        self.assertEqual(record.email, 'a@a.com')
        self.assertFalse(record.disabled)

    def test_from_export_with_disabled_record_sets_disabled_to_true(
        self,
    ) -> None:
        export_record = mock.Mock(uid='uid', email='a@a.com', disabled=True)
        record = firebase_adapters.FirebaseRecord.from_export(export_record)
        self.assertEqual(record.auth_id, 'uid')
        self.assertEqual(record.email, 'a@a.com')
        self.assertTrue(record.disabled)

    def test_to_import_returns_matching_import_user_record(self) -> None:
        record = firebase_adapters.FirebaseRecord(
            auth_id='aid', email='a@a.com', disabled=False
        )
        import_record = record.to_import()
        self.assertEqual(import_record.uid, 'aid')
        self.assertEqual(import_record.email, 'a@a.com')
        self.assertFalse(import_record.disabled)

    def test_to_import_with_disabled_record_preserves_disabled(self) -> None:
        record = firebase_adapters.FirebaseRecord(
            auth_id='aid', email='a@a.com', disabled=True
        )
        import_record = record.to_import()
        self.assertEqual(import_record.uid, 'aid')
        self.assertEqual(import_record.email, 'a@a.com')
        self.assertTrue(import_record.disabled)
