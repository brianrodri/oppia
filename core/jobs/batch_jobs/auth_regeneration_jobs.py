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

"""Jobs for regenerating auth provider records."""

from __future__ import annotations

from core.jobs import base_jobs
from core.jobs.io import auth_io
from core.jobs.transforms import job_result_transforms
from core.jobs.types import job_run_result

import apache_beam as beam
from apache_beam.transforms.util import WaitOn


class RegenerateAuthProviderRecordsJob(base_jobs.JobBase):
    """Job that regenerates auth provider records by deleting all existing
    records from Firebase, then uploading rebuilt records from Oppia's models.

    The sequential ordering is critical: UploadRecords has no duplicate
    protection, so it must only run against an empty server.
    """

    def run(self) -> beam.PCollection[job_run_result.JobRunResult]:
        records_to_delete = (
            self.pipeline | 'Get "strong" records' >> auth_io.GetStrongRecords()
        )
        records_to_upload = (
            self.pipeline
            | 'Get "weak" records' >> auth_io.GetWeakRecords()
            | 'Discard keys (Oppia ID associated with record)' >> beam.Values()
        )

        delete_result = (
            records_to_delete
            | 'Delete records from our Auth Provider' >> auth_io.DeleteRecords()
        )
        upload_result = (
            records_to_upload
            | 'Wait for delete to end before uploading' >> WaitOn(delete_result)
            | 'Upload records into our Auth Provider' >> auth_io.UploadRecords()
        )

        delete_count = (
            records_to_delete
            | 'Wait for delete to end before counting' >> WaitOn(delete_result)
            | 'Count the deleted records'
            >> job_result_transforms.CountObjectsToJobRunResult()
        )
        upload_count = (
            records_to_upload
            | 'Wait for upload to end before counting' >> WaitOn(upload_result)
            | 'Count the uploaded records'
            >> job_result_transforms.CountObjectsToJobRunResult('UPLOADED')
        )

        return [delete_count, upload_count] | 'Merge outputs' >> beam.Flatten()
