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

"""Job for auditing Firebase records against Oppia's user & auth models."""

from __future__ import annotations

from collections import abc

from core.jobs import base_jobs
from core.jobs.io import firebase_io, ndb_io
from core.jobs.types import firebase_adapters, job_run_result
from core.platform import models

import apache_beam as beam

(user_models,) = models.Registry.import_models([models.Names.USER])

TAG_COLLISION = 'COLLISION'
TAG_OK = 'OK'
TAG_ADD = 'ADD'
TAG_DEL = 'DEL'
TAG_COLLISION = 'STDERR'


class FirebaseAuditRecordsJob(base_jobs.JobBase):
    """Audit Firebase records against the records that Oppia claims to exist."""

    def run(self) -> beam.PCollection[job_run_result.JobRunResult]:
        user_id_by_email = (
            self.pipeline
            | 'Get UserSettingsModels'
            >> ndb_io.GetModels(
                user_models.UserSettingsModel.get_all(include_deleted=True)
            )
            | 'Key UserSettingsModels by Email'
            >> beam.Map(lambda model: (model.email, model.id))
        )
        oppia_record_by_email = (
            self.pipeline
            | 'Recreate Records from Oppia Models'
            >> firebase_io.RecreateRecordsFromOppiaModels()
            | 'Key Records from Oppia by Email'
            >> beam.Map(lambda record: (record.email, record))
        )
        firebase_record_by_email = (
            self.pipeline
            | 'Get Records Directly from Firebase'
            >> firebase_io.GetRecordsDirectlyFromFirebase()
            | 'Key Records from Firebase by Email'
            >> beam.Map(lambda record: (record.email, record))
        )

        outputs = (
            (user_id_by_email, oppia_record_by_email, firebase_record_by_email)
            | 'Group Records by Email Key' >> beam.CoGroupByKey()
            | 'Inspect Records'
            >> beam.ParDo(_TagEmailGroup()).with_outputs(
                TAG_OK, TAG_ADD, TAG_DEL, TAG_COLLISION
            )
        )

        return (
            (
                outputs[TAG_OK]
                | beam.combiners.Count.Globally(False)
                | beam.Map(self.format_ok_result)
            ),
            outputs[TAG_ADD] | beam.Map(self.format_add_result),
            outputs[TAG_DEL] | beam.Map(self.format_del_result),
            outputs[TAG_COLLISION] | beam.Map(self.format_collision_result),
        ) | beam.Flatten()

    @classmethod
    def format_ok_result(cls, ok_count: int) -> job_run_result.JobRunResult:
        """Formats the given OK count as a human-readable string."""
        return job_run_result.JobRunResult.as_stdout(f'OK: {ok_count}')

    @classmethod
    def format_add_result(
        cls, record: firebase_adapters.FirebaseRecord
    ) -> job_run_result.JobRunResult:
        """Formats the account to create as a human-readable string."""
        return job_run_result.JobRunResult.as_stdout(f'ADD RECORD: {record}')

    @classmethod
    def format_del_result(
        cls, record: firebase_adapters.FirebaseRecord
    ) -> job_run_result.JobRunResult:
        """Formats the account to deleted as a human-readable string."""
        return job_run_result.JobRunResult.as_stdout(f'DEL RECORD: {record}')

    @classmethod
    def format_collision_result(
        cls, message: str
    ) -> job_run_result.JobRunResult:
        """Formats the given collision message as a human-readable string."""
        return job_run_result.JobRunResult.as_stderr(message)


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class _TagEmailGroup(beam.DoFn):  # type: ignore[misc]
    """Audits records using tagged outputs to group findings by severity."""

    def process(
        self,
        entry: tuple[
            str,
            tuple[
                abc.Iterable[str],
                abc.Iterable[firebase_adapters.FirebaseRecord],
                abc.Iterable[firebase_adapters.FirebaseRecord],
            ],
        ],
    ) -> abc.Iterable[beam.TaggedOutput]:
        """Yields tagged outputs which will group audit findings by severity."""
        email, (user_id_iter, oppia_record_iter, firebase_record_iter) = entry

        if len(user_ids := sorted(set(user_id_iter))) > 1:
            yield beam.TaggedOutput(
                TAG_COLLISION, f'{email=} shared by {user_ids=}'
            )
            return

        oppia_record_set = frozenset(oppia_record_iter)
        firebase_record_set = frozenset(firebase_record_iter)

        if ok_records := oppia_record_set & firebase_record_set:
            yield beam.TaggedOutput(TAG_OK, len(ok_records))

        yield from (
            beam.TaggedOutput(TAG_DEL, record)
            for record in firebase_record_set - oppia_record_set
        )
        yield from (
            beam.TaggedOutput(TAG_ADD, record)
            for record in oppia_record_set - firebase_record_set
        )
