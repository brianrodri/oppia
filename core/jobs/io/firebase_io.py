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

"""Provides PTransforms for operating on Firebase records."""

from __future__ import annotations

from collections import abc

from core.jobs.io import ndb_io
from core.jobs.types import firebase_adapters
from core.platform import models
from core.platform.auth import firebase_auth_services

import apache_beam as beam
import firebase_admin.auth as firebase_auth
from apache_beam import pvalue

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import auth_models, user_models

auth_models, user_models = models.Registry.import_models(
    [models.Names.AUTH, models.Names.USER]
)


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class GetStrongRecords(beam.PTransform):  # type: ignore[misc]
    """Gets the collection of "strong" records directly from Firebase.

    These records are considered to be "strong" because they are based on
    Firebase's _real_ data. In other words, this collection represents the
    source of truth.
    """

    def setup(self) -> None:
        """Establishes a Firebase connection just before running `process`."""

        firebase_auth_services.establish_firebase_connection()

    def expand(
        self, pbegin: pvalue.PBegin
    ) -> beam.PCollection[firebase_adapters.StrongRecord]:
        """Returns all of the records directly from Firebase."""

        return (
            pbegin
            | 'Use Exactly One Worker' >> beam.Create([None])
            | beam.FlatMap(self._yield_strong_records_from_firebase)
        )

    def _yield_strong_records_from_firebase(
        self, _: None
    ) -> abc.Iterable[firebase_adapters.StrongRecord]:
        """Yields all of the records directly from Firebase."""

        yield from (
            firebase_adapters.StrongRecord.from_export(user)
            for user in firebase_auth.list_users().iterate_all()
        )


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class GetWeakRecords(beam.PTransform):  # type: ignore[misc]
    """Gets the collection of "weak" records from Oppia's user & auth models.

    These records are considered to be "weak" because they are NOT based on real
    data. Instead, they are built using Oppia's internal association models,
    under the assumption that they are consistent with "strong" (real) records.
    """

    def expand(
        self, pbegin: pvalue.PBegin
    ) -> beam.PCollection[firebase_adapters.WeakRecord]:
        """Returns all of the "weak" records from Oppia's user & auth models."""

        user_settings_model_pcoll = (
            pbegin
            | 'Get UserSettingsModels'
            >> ndb_io.GetModels(
                user_models.UserSettingsModel.get_all(include_deleted=True)
            )
            | 'Key UserSettingsModels by id'
            >> beam.Map(lambda model: (model.id, model))
        )

        user_auth_details_model_pcoll = (
            pbegin
            | 'Get UserAuthDetailsModels'
            >> ndb_io.GetModels(
                auth_models.UserAuthDetailsModel.get_all(include_deleted=True)
            )
            | 'Key UserAuthDetailsModels by id'
            >> beam.Map(lambda model: (model.id, model))
        )

        return (
            (user_settings_model_pcoll, user_auth_details_model_pcoll)
            | 'Group User Models by id' >> beam.CoGroupByKey()
            | 'Rebuild Records from User Models'
            >> beam.FlatMapTuple(
                GetWeakRecords._rebuild_fields_from_oppia_models
            )
        )

    @staticmethod
    def _rebuild_fields_from_oppia_models(
        user_id: str,
        group_of_models: tuple[
            abc.Iterable[user_models.UserSettingsModel],
            abc.Iterable[auth_models.UserAuthDetailsModel],
        ],
    ) -> abc.Iterable[firebase_adapters.WeakRecord]:
        """Yields a WeakRecord for the given user_id if possible."""

        user_settings_model_iter, user_auth_details_model_iter = group_of_models
        user_settings_models = tuple(user_settings_model_iter)
        user_auth_details_models = tuple(user_auth_details_model_iter)

        try:
            [(user_settings_model, user_auth_details_model)] = zip(
                user_settings_models, user_auth_details_models, strict=True
            )
        except ValueError as e:
            raise ValueError(
                f'{user_id=!r} needs exactly one UserSettingsModel '
                f'(found {len(user_settings_models)}) and exactly one '
                f'UserAuthDetailsModel (found {len(user_auth_details_models)})'
            ) from e

        try:
            fields = firebase_adapters.WeakRecord.from_oppia_models(
                user_settings_model, user_auth_details_model
            )
        except ValueError as e:
            raise ValueError(f'Failed to resolve fields from {user_id=}') from e

        if fields:
            yield fields
