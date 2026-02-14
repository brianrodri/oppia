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

from core.domain import auth_domain
from core.jobs.io import auth_io
from core.jobs import base_jobs
from core.jobs.transforms import job_result_transforms
from core.jobs.types import job_run_result

import apache_beam as beam
from apache_beam import pvalue
import result
from typing import Iterable, TypedDict


class AuditAuthProviderRecordsJob(base_jobs.JobBase):
    """Audits accounts in our Auth Provider against Oppia's registered users."""

    def run(self) -> beam.PCollection[job_run_result.JobRunResult]:
        weak_records = (
            self.pipeline
            | 'Create weak records from Oppia user models'
            >> auth_io.GetWeakRecords()
            | 'Create key/value pairs for weak records'
            >> beam.Map(self._create_group_entry_from_weak_record_result)
        )

        strong_records = (
            self.pipeline
            | 'Fetch strong records from Auth Provider'
            >> auth_io.GetStrongRecords()
            | 'Create key/value pairs for strong records'
            >> beam.Map(self._create_group_entry_from_strong_record)
        )

        audit_result = (
            {'from_oppia': weak_records, 'from_provider': strong_records}
            | 'Group records by emails' >> beam.CoGroupByKey()
            | 'Audit groups'
            >> beam.ParDo(AuditFn()).with_outputs(
                AuditFn.TAG_CONSISTENT,
                AuditFn.TAG_MISSING_FROM_OPPIA,
                AuditFn.TAG_MISSING_FROM_PROVIDER,
                AuditFn.TAG_COLLISION_IN_OPPIA,
                AuditFn.TAG_COLLISION_IN_PROVIDER,
            )
        )

        job_run_results: list[beam.PCollection[job_run_result.JobRunResult]] = [
            audit_result[AuditFn.TAG_CONSISTENT]
            | 'Format consistent records'
            >> job_result_transforms.CountObjectsToJobRunResult(
                prefix='Oppia users consistent with Auth Provider accounts'
            ),
            audit_result[AuditFn.TAG_MISSING_FROM_OPPIA]
            | 'Format records missing from Oppia'
            >> job_result_transforms.ResultsToJobRunResults(
                prefix='Oppia is missing users for Auth Provider accounts'
            ),
            audit_result[AuditFn.TAG_MISSING_FROM_PROVIDER]
            | 'Format records missing from provider'
            >> job_result_transforms.ResultsToJobRunResults(
                prefix='Auth Provider is missing accounts for Oppia users'
            ),
            audit_result[AuditFn.TAG_COLLISION_IN_OPPIA]
            | 'Format records with email collisions in Oppia'
            >> job_result_transforms.ResultsToJobRunResults(
                prefix='Oppia users are sharing the same email'
            ),
            audit_result[AuditFn.TAG_COLLISION_IN_PROVIDER]
            | 'Format records with email collisions in Auth Provider'
            >> job_result_transforms.ResultsToJobRunResults(
                prefix='Auth Provider accounts are sharing the same email'
            ),
        ]

        return job_run_results | 'Flatten audit results' >> beam.Flatten()

    def _create_group_entry_from_weak_record_result(
        self,
        pair: tuple[str, auth_domain.AuthProviderRecord],
    ) -> tuple[str, tuple[str, auth_domain.AuthProviderRecord]]:
        return (pair[1].email, pair)

    def _create_group_entry_from_strong_record(
        self, record: auth_domain.AuthProviderRecord
    ) -> tuple[str, auth_domain.AuthProviderRecord]:
        return (record.email, record)


# TODO(#15613): Here we use MyPy ignore because Apache Beam lacks type hints.
class AuditFn(beam.DoFn):  # type: ignore[misc]

    TAG_CONSISTENT = 'consistent'
    TAG_MISSING_FROM_OPPIA = 'missing_from_oppia'
    TAG_MISSING_FROM_PROVIDER = 'missing_from_provider'
    TAG_COLLISION_IN_OPPIA = 'collision_in_oppia'
    TAG_COLLISION_IN_PROVIDER = 'collision_in_provider'

    def process(
        self, email_and_grouped_records: tuple[str, _GroupedRecords]
    ) -> Iterable[pvalue.TaggedOutput]:
        """Audits the records in the given group and yields tagged outputs.

        Args:
            email_and_grouped_records: tuple[str, _GroupedRecords]. A pair where
                the first element is the email shared by all records in the
                second element.

        Yields:
            pvalue.TaggedOutput. The result of the audit with appropriate tags.
        """
        email, group = email_and_grouped_records
        collisions_found = False

        if len(from_oppia := {record for _, record in group['from_oppia']}) > 1:
            collisions_found = True
            # NOTE: Sorted to ensure deterministic output for testing purposes.
            user_ids = sorted(user_id for user_id, _ in group['from_oppia'])
            yield pvalue.TaggedOutput(
                self.TAG_COLLISION_IN_OPPIA,
                result.Err(f'{email=}: {user_ids=}'),
            )

        if len(from_provider := set(group['from_provider'])) > 1:
            collisions_found = True
            # NOTE: Sorted to ensure deterministic output for testing purposes.
            auth_ids = sorted(record.auth_id for record in from_provider)
            yield pvalue.TaggedOutput(
                self.TAG_COLLISION_IN_PROVIDER,
                result.Err(f'{email=}: {auth_ids=}'),
            )

        if collisions_found:
            return

        if from_oppia & from_provider:
            yield pvalue.TaggedOutput(self.TAG_CONSISTENT, result.Ok(1))

        if from_oppia - from_provider:
            yield pvalue.TaggedOutput(
                self.TAG_MISSING_FROM_PROVIDER, result.Err(f'{email=}')
            )

        if from_provider - from_oppia:
            yield pvalue.TaggedOutput(
                self.TAG_MISSING_FROM_OPPIA, result.Err(f'{email=}')
            )

    class _GroupedRecords(TypedDict):
        from_oppia: Iterable[tuple[str, auth_domain.AuthProviderRecord]]
        from_provider: Iterable[auth_domain.AuthProviderRecord]
