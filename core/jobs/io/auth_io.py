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

"""Provides PTransforms for operating on the records in our auth provider."""

from __future__ import annotations

from core import feconf
from core.domain import auth_domain, auth_services
from core.jobs.io import ndb_io
from core.platform import models

import apache_beam as beam
from apache_beam import pvalue
from typing import Iterable, TypedDict

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import auth_models, user_models

auth_models, user_models = models.Registry.import_models(
    [models.Names.AUTH, models.Names.USER]
)


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class GetStrongRecords(beam.PTransform):  # type: ignore[misc]
    """Gets the collection of "strong" records directly from our auth provider.

    These records are considered to be "strong" because they are based on our
    auth provider's _real_ data. In other words, this collection represents the
    source of truth.
    """

    AUTH_PROVIDER_ID = feconf.FIREBASE_AUTH_PROVIDER_ID

    def expand(
        self, pbegin: pvalue.PBegin
    ) -> pvalue.PCollection[auth_domain.AuthProviderRecord]:
        """Returns all of the records directly from our auth provider.

        Args:
            pbegin: PBegin. The beginning of the pipeline.

        Returns:
            PCollection[AuthProviderRecord]. All of the records registered with
            our auth provider.
        """
        return (
            pbegin
            | 'Synchronously load and shuffle records for improved parallelism.'
            >> beam.Create(
                auth_services.get_all_auth_provider_records(
                    self.AUTH_PROVIDER_ID
                ),
                reshuffle=True,
            )
        )


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class GetWeakRecords(beam.PTransform):  # type: ignore[misc]
    """Gets the collection of "weak" records based on Oppia's user auth models.

    These records are considered to be "weak" because they are NOT based on real
    data. Instead, they are built from Oppia's internal association models under
    the assumption that they are consistent with the "strong" (real) records.
    """

    AUTH_PROVIDER_ID = feconf.FIREBASE_AUTH_PROVIDER_ID

    def expand(
        self, pbegin: pvalue.PBegin
    ) -> beam.PCollection[tuple[str, auth_domain.AuthProviderRecord]]:
        """Returns all of the records *assumed* to be in our auth provider.

        Args:
            pbegin: PBegin. The beginning of the pipeline.

        Returns:
            tuple[str, PCollection[AuthProviderRecord]]. All of the records
            *assumed* to be registered with our auth provider.
        """
        id_to_user_settings_model = (
            pbegin
            | 'Get UserSettingsModels'
            >> ndb_io.GetModels(
                user_models.UserSettingsModel.get_all(include_deleted=True)
            )
            | 'Key UserSettingsModels by user id'
            >> beam.Map(lambda settings: (settings.id, settings))
        )
        id_to_user_auth_details_model = (
            pbegin
            | 'Get UserAuthDetailsModels'
            >> ndb_io.GetModels(
                auth_models.UserAuthDetailsModel.get_all(include_deleted=True)
            )
            | 'Key UserAuthDetailsModels by user id'
            >> beam.Map(lambda auth_details: (auth_details.id, auth_details))
        )
        return (
            {
                'user_settings_models': id_to_user_settings_model,
                'user_auth_details_models': id_to_user_auth_details_model,
            }
            | 'Group models by user id' >> beam.CoGroupByKey()
            | 'Build weak records from grouped results'
            >> beam.FlatMap(self._build_weak_record_from_user_models)
        )

    def _build_weak_record_from_user_models(
        self, result: tuple[str, _GroupedUserModels]
    ) -> Iterable[tuple[str, auth_domain.AuthProviderRecord]]:
        """Yields an AuthProviderRecord from the provided group of fields.

        Args:
            result: tuple[str, _GroupedUserModels]. A tuple where the first
                element is the user ID and the second element holds the fields
                required to build an AuthProviderRecord.

        Yields:
            tuple[str, AuthProviderRecord]. The user ID and record.

        Raises:
            ValueError. The group does not contain EXACTLY ONE set of fields, or
                the group uses None as the auth_id or email.
        """
        user_id, group = result
        user_settings = group['user_settings_models']
        user_auth_details = group['user_auth_details_models']

        try:
            same_len_groups = zip(user_settings, user_auth_details, strict=True)
            (only_one_group,) = same_len_groups

        except ValueError as unpack_or_zip_error:
            raise ValueError(
                f'{user_id=!r} has '
                f'{len(user_settings)} UserSettingsModels and '
                f'{len(user_auth_details)} UserAuthDetailsModels, '
                'but there must be EXACTLY ONE of each.'
            ) from unpack_or_zip_error
        else:
            user_settings, user_auth_details = only_one_group

        if record := auth_services.get_auth_provider_records_from_models(
            self.AUTH_PROVIDER_ID, user_settings, user_auth_details, strict=True
        ):
            yield (user_id, record)

    class _GroupedUserModels(TypedDict):
        """Typings for the grouped user models used to build weak records."""

        user_settings_models: Iterable[user_models.UserSettingsModel]
        user_auth_details_models: Iterable[auth_models.UserAuthDetailsModel]


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class UploadRecords(beam.PTransform):  # type: ignore[misc]
    """Uploads auth provider records WITHOUT protecting against duplicates."""

    UPLOAD_FN = beam.DoFn.from_callable(
        auth_services.upload_multi_auth_provider_records
    )

    def expand(
        self, records: pvalue.PCollection[auth_domain.AuthProviderRecord]
    ) -> pvalue.PDone:
        """Uploads records into our auth provider WITHOUT safety checks.

        WARNING: This operation DOES NOT protect against duplicate records!
        The ONLY way to guarantee this function is used safely is by running it
        on an empty server, where collisions are impossible.

        Args:
            records: PCollection[AuthProviderRecord]. The records to upload.

        Returns:
            PDone. This is a terminal operation.
        """
        return (
            records
            | 'Batch records into large groups to minimize network calls'
            >> beam.BatchElements(min_batch_size=feconf.FIREBASE_BATCH_SIZE)
            | 'Upload records in batches' >> beam.ParDo(self.UPLOAD_FN)
        )


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class DeleteRecords(beam.PTransform):  # type: ignore[misc]
    """Deletes auth provider records kept in our auth provider."""

    _DELETE_DO_FN = beam.DoFn.from_callable(
        auth_services.delete_multi_auth_provider_records
    )

    def expand(
        self, records: pvalue.PCollection[auth_domain.AuthProviderRecord]
    ) -> pvalue.PDone:
        """Deletes records from our auth provider.

        Args:
            records: PCollection[AuthProviderRecord]. The records to delete.

        Returns:
            PDone. This is a terminal operation.
        """
        return (
            records
            | 'Batch records into large groups to minimize network calls'
            >> beam.BatchElements(min_batch_size=feconf.FIREBASE_BATCH_SIZE)
            | 'Delete records in batches' >> beam.ParDo(self._DELETE_DO_FN)
        )
