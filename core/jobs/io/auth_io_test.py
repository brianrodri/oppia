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

"""Unit tests for jobs.io.auth_io."""

from __future__ import annotations

import builtins

from core.domain import auth_domain, auth_services
from core.jobs import job_test_utils
from core.jobs.io import auth_io
from core.platform import models
from core.platform.auth import firebase_auth_services_test

import apache_beam as beam

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import auth_models, user_models

auth_models, user_models = models.Registry.import_models(
    [models.Names.AUTH, models.Names.USER]
)


class AuthIoTestBase(
    job_test_utils.JobTestBase,
    firebase_auth_services_test.FirebaseAuthServicesTestBase,
):
    """Base class for auth_io tests."""

    pass


class GetStrongRecordsTests(AuthIoTestBase):

    def test_returns_empty_when_no_records_exist(self) -> None:
        self.assert_pcoll_empty(
            self.pipeline | auth_io.GetStrongRecords('Firebase')
        )

    def test_returns_all_records(self) -> None:
        self.firebase_sdk_stub.create_user(
            uid='uid_a', email='a@a.com', disabled=False
        )
        self.firebase_sdk_stub.create_user(
            uid='uid_b', email='b@b.com', disabled=False
        )
        self.firebase_sdk_stub.create_user(
            uid='uid_c', email='c@c.com', disabled=True
        )

        self.assert_pcoll_equal(
            self.pipeline | auth_io.GetStrongRecords('Firebase'),
            [
                auth_domain.AuthProviderRecord(
                    'uid_a', 'Firebase', 'a@a.com', disabled=False
                ),
                auth_domain.AuthProviderRecord(
                    'uid_b', 'Firebase', 'b@b.com', disabled=False
                ),
                auth_domain.AuthProviderRecord(
                    'uid_c', 'Firebase', 'c@c.com', disabled=True
                ),
            ],
        )


class GetWeakRecordsTests(AuthIoTestBase):

    def test_returns_empty_when_no_models_exist(self) -> None:
        self.assert_pcoll_empty(
            self.pipeline | auth_io.GetWeakRecords('Firebase')
        )

    def test_returns_record(self) -> None:
        self.put_multi(
            [
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_a',
                    firebase_auth_id='fb_a',
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_a',
                    email='a@a.com',
                ),
            ]
        )

        self.assert_pcoll_equal(
            self.pipeline | auth_io.GetWeakRecords('Firebase'),
            [
                (
                    'uid_a',
                    auth_domain.AuthProviderRecord(
                        'fb_a', 'Firebase', 'a@a.com'
                    ),
                )
            ],
        )

    def test_returns_deleted_record(self) -> None:
        self.put_multi(
            [
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_a',
                    firebase_auth_id='fb_a',
                    deleted=True,
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_a',
                    email='a@a.com',
                    deleted=True,
                ),
            ]
        )

        self.assert_pcoll_equal(
            self.pipeline | auth_io.GetWeakRecords('Firebase'),
            [
                (
                    'uid_a',
                    auth_domain.AuthProviderRecord(
                        'fb_a', 'Firebase', 'a@a.com', disabled=True
                    ),
                )
            ],
        )

    def test_returns_multiple_records(self) -> None:
        self.put_multi(
            [
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_a',
                    firebase_auth_id='fb_a',
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_a',
                    email='a@a.com',
                ),
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_b',
                    firebase_auth_id='fb_b',
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_b',
                    email='b@b.com',
                ),
            ]
        )

        self.assert_pcoll_equal(
            self.pipeline | auth_io.GetWeakRecords('Firebase'),
            [
                (
                    'uid_a',
                    auth_domain.AuthProviderRecord(
                        'fb_a', 'Firebase', 'a@a.com'
                    ),
                ),
                (
                    'uid_b',
                    auth_domain.AuthProviderRecord(
                        'fb_b', 'Firebase', 'b@b.com'
                    ),
                ),
            ],
        )

    def test_ignores_profile_users(self) -> None:
        self.put_multi(
            [
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_a',
                    firebase_auth_id='fb_a',
                    parent_user_id=None,
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_a',
                    email='a@a.com',
                ),
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_b',
                    firebase_auth_id=None,
                    parent_user_id='uid_a',
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_b',
                    email='b@b.com',
                ),
            ]
        )

        self.assert_pcoll_equal(
            self.pipeline | auth_io.GetWeakRecords('Firebase'),
            [
                (
                    'uid_a',
                    auth_domain.AuthProviderRecord(
                        'fb_a', 'Firebase', 'a@a.com'
                    ),
                ),
            ],
        )

    def test_raises_when_zip_encounters_invalid_state(self) -> None:
        self.put_multi(
            [
                self.create_model(
                    auth_models.UserAuthDetailsModel,
                    id='uid_a',
                    firebase_auth_id='fb_a',
                ),
                self.create_model(
                    user_models.UserSettingsModel,
                    id='uid_a',
                    email='a@a.com',
                ),
            ]
        )

        def fail() -> None:
            """Always raises a ValueError.

            Raises:
                ValueError. Always raised.
            """
            raise ValueError('uh-oh!')

        real_zip = builtins.zip
        mock_zip = lambda *args, strict=False: (
            fail() if strict else real_zip(*args)
        )

        with (
            self.swap(builtins, 'zip', mock_zip),
            self.assertRaisesRegex(
                ValueError,
                'user_id=\'uid_a\' must have EXACTLY ONE auth_id, email, and '
                'deleted status',
            ),
        ):
            self.assert_pcoll_empty(
                self.pipeline | auth_io.GetWeakRecords('Firebase')
            )


class UploadRecordsTests(AuthIoTestBase):

    def test_imports_records(self) -> None:
        imported_records = [
            auth_domain.AuthProviderRecord(
                'uid_a', 'Firebase', 'a@a.com', disabled=False
            ),
            auth_domain.AuthProviderRecord(
                'uid_b', 'Firebase', 'b@b.com', disabled=False
            ),
            auth_domain.AuthProviderRecord(
                'uid_c', 'Firebase', 'c@c.com', disabled=True
            ),
        ]

        self.assertItemsEqual(
            auth_services.get_all_auth_provider_records('Firebase'),
            [],
        )

        self.assert_pcoll_empty(
            self.pipeline
            | beam.Create(imported_records)
            | auth_io.UploadRecords()
        )

        self.assertItemsEqual(
            auth_services.get_all_auth_provider_records('Firebase'),
            imported_records,
        )


class DeleteRecordsTests(AuthIoTestBase):

    def test_deletes_records(self) -> None:
        self.firebase_sdk_stub.create_user(uid='uid_a', email='a@a.com')
        self.firebase_sdk_stub.create_user(uid='uid_b', email='b@b.com')
        self.firebase_sdk_stub.create_user(uid='uid_c', email='c@c.com')

        self.assertItemsEqual(
            auth_services.get_all_auth_provider_records('Firebase'),
            [
                auth_domain.AuthProviderRecord('uid_a', 'Firebase', 'a@a.com'),
                auth_domain.AuthProviderRecord('uid_b', 'Firebase', 'b@b.com'),
                auth_domain.AuthProviderRecord('uid_c', 'Firebase', 'c@c.com'),
            ],
        )

        self.assert_pcoll_empty(
            self.pipeline
            | beam.Create(
                [
                    auth_domain.AuthProviderRecord(
                        'uid_a', 'Firebase', 'a@a.com'
                    ),
                    auth_domain.AuthProviderRecord(
                        'uid_b', 'Firebase', 'b@b.com'
                    ),
                ]
            )
            | auth_io.DeleteRecords()
        )

        self.assertItemsEqual(
            auth_services.get_all_auth_provider_records('Firebase'),
            [
                auth_domain.AuthProviderRecord(
                    'uid_c', 'Firebase', 'c@c.com', False
                ),
            ],
        )
