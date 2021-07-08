# coding: utf-8
#
# Copyright 2017 The Oppia Authors. All Rights Reserved.
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

"""Batch jobs for indexing activities."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

from core.platform import models
from core.domain import search_services
from jobs import base_jobs
from jobs.io import ndb_io
from jobs.types import job_run_result

import apache_beam as beam

(collection_models, exp_models) = models.Registry.import_models(
    [models.NAMES.collection, models.NAMES.exploration])


class IndexAllActivitiesJob(base_jobs.JobBase):
    """Indexes and ranks all explorations and collections."""

    def run(self):
        exp_summary_query = exp_models.ExpSummaryModel.query(
            exp_models.ExpSummaryModel.deleted == False)
        exp_summary_models = (
            self.pipeline
            | 'Get all ExpSummaryModels' >> ndb_io.GetModels(
                exp_summary_query, self.datastoreio_stub)
        )

        collection_summary_query = (
            collection_models.CollectionSummaryModel.query(
                collection_models.CollectionSummaryModel.deleted == False))
        collection_summary_models = (
            self.pipeline
            | 'Get all CollectionSummaryModels' >> ndb_io.GetModels(
                collection_summary_query, self.datastoreio_stub)
        )

        exp_summary_models | beam.ParDo(IndexExplorationSummary())
        collection_summary_models | beam.ParDo(IndexCollectionSummary())

        return (
            (exp_summary_models, collection_summary_models)
            | 'Flatten models into a list' >> beam.Flatten()
            | 'Count the number of models' >> beam.combiners.Count.Globally()
            | 'Format the count' >> beam.Map(lambda n: '%d models indexed' % n)
            | 'Map to stdout' >> beam.Map(job_run_result.JobRunResult.as_stdout)
        )


class IndexExplorationSummary(beam.DoFn):

    def process(self, exp_summary_model):
        search_services.index_exploration_summaries([exp_summary_model])


class IndexCollectionSummary(beam.DoFn):

    def process(self, collection_summary_model):
        search_services.index_collection_summaries([collection_summary_model])
