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

"""Unit tests for jobs.batch_jobs.index_all_activities_jobs."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import itertools
import multiprocessing

from core.domain import activity_jobs_one_off
from core.domain import collection_domain
from core.domain import collection_services
from core.domain import exp_domain
from core.domain import exp_services
from core.domain import rights_manager
from core.domain import search_services
from core.domain import taskqueue_services
from core.domain import user_services
from core.platform import models
from core.tests import test_utils
from jobs import job_test_utils
from jobs.batch_jobs import index_all_activities_jobs
from jobs.types import job_run_result
import python_utils
import utils

platform_search_services = models.Registry.import_search_services()


class IndexAllActivitiesJobTests(
        job_test_utils.JobTestBase, test_utils.GenericTestBase):

    JOB_CLASS = index_all_activities_jobs.IndexAllActivitiesJob

    def setUp(self):
        super(IndexAllActivitiesJobTests, self).setUp()

        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.owner = user_services.get_user_actions_info(self.owner_id)

    def test_standard_operation(self):
        multiprocessing_manager = multiprocessing.Manager()
        multiprocessing_dict = multiprocessing_manager.dict()

        for i in python_utils.RANGE(3):
            exp_id = '%s' % i
            exp = exp_domain.Exploration.create_default_exploration(
                exp_id,
                title='title %s' % exp_id,
                category='category %s' % exp_id)
            exp_services.save_new_exploration(self.owner_id, exp)
            rights_manager.publish_exploration(self.owner, exp_id)
            multiprocessing_dict[exp_id] = False

        for i in python_utils.RANGE(3, 6):
            collection_id = '%s' % i
            collection = collection_domain.Collection.create_default_collection(
                collection_id,
                title='title %s' % collection_id,
                category='category %s' % collection_id)
            collection_services.save_new_collection(self.owner_id, collection)
            rights_manager.publish_collection(self.owner, collection_id)
            multiprocessing_dict[collection_id] = False

        def mock_index_activity_summaries(models):
            for model in models:
                multiprocessing_dict[model.id] = True

        swap_exp_indexer = self.swap(
            search_services, 'index_exploration_summaries',
            mock_index_activity_summaries)
        swap_collection_indexer = self.swap(
            search_services, 'index_collection_summaries',
            mock_index_activity_summaries)

        with swap_exp_indexer, swap_collection_indexer:
            self.assert_job_output_is([
                job_run_result.JobRunResult(stdout='6 models indexed'),
            ])

        self.assertEqual(dict(multiprocessing_dict), {
            '0': True,
            '1': True,
            '2': True,
            '3': True,
            '4': True,
            '5': True,
        })
