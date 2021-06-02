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

"""Provides an Apache Beam API for operating on NDB models."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import feconf
from jobs import job_utils

import apache_beam as beam
from apache_beam.io.gcp.datastore.v1new import datastoreio


class GetModels(beam.PTransform):
    """Reads NDB models from the datastore using a query."""

    def __init__(self, query, label=None):
        """Initializes the GetModels PTransform.

        Args:
            query: datastore_services.Query. The query used to fetch models.
            label: str|None. The label of the PTransform.
        """
        super(GetModels, self).__init__(label=label)
        self.query = query

    def expand(self, pbegin):
        """Returns a PCollection with models matching the corresponding query.

        Args:
            pbegin: PValue. The initial PValue of the pipeline, used to anchor
                the models to its underlying pipeline.

        Returns:
            PCollection. The PCollection of models.
        """
        query = job_utils.get_beam_query_from_ndb_query(
            self.query, namespace=pbegin.pipeline.options.namespace)
        return (
            pbegin.pipeline
            | 'Reading %r from the datastore' % self.query >> (
                datastoreio.ReadFromDatastore(query))
            | 'Transforming %r into NDB models' % self.query >> (
                beam.Map(job_utils.get_ndb_model_from_beam_entity))
        )


class PutModels(beam.PTransform):
    """Writes NDB models to the datastore."""

    def expand(self, model_pcoll):
        """Writes the given models to the datastore.

        Args:
            model_pcoll: PCollection. A PCollection of NDB models.

        Returns:
            PCollection. An empty PCollection.
        """
        return (
            model_pcoll
            | 'Transforming the NDB models into Apache Beam entities' >> (
                beam.Map(job_utils.get_beam_entity_from_ndb_model))
            | 'Writing the NDB models to the datastore' >> (
                datastoreio.WriteToDatastore(feconf.OPPIA_PROJECT_ID))
        )


class DeleteModels(beam.PTransform):
    """Deletes NDB models from the datastore."""

    def expand(self, model_key_pcoll):
        """Deletes the given models from the datastore.

        Args:
            model_key_pcoll: PCollection. The PCollection of NDB keys to delete.

        Returns:
            PCollection. An empty PCollection.
        """
        return (
            model_key_pcoll
            | 'Transforming the NDB keys into Apache Beam keys' >> (
                beam.Map(job_utils.get_beam_key_from_ndb_key))
            | 'Deleting the NDB keys from the datastore' >> (
                datastoreio.DeleteFromDatastore(feconf.OPPIA_PROJECT_ID))
        )
