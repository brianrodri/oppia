# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
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

"""Tests for user-related one-off computations."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import ast
import datetime
import re

from core.domain import collection_domain
from core.domain import collection_services
from core.domain import event_services
from core.domain import exp_domain
from core.domain import exp_services
from core.domain import feedback_services
from core.domain import learner_progress_services
from core.domain import rating_services
from core.domain import rights_domain
from core.domain import rights_manager
from core.domain import subscription_services
from core.domain import taskqueue_services
from core.domain import user_jobs_continuous
from core.domain import user_jobs_one_off
from core.domain import user_services
from core.platform import models
from core.tests import test_utils
from core.tests.data import image_constants
import feconf
import python_utils
import utils

auth_models, user_models, feedback_models, exp_models = (
    models.Registry.import_models(
        [models.NAMES.auth, models.NAMES.user, models.NAMES.feedback,
         models.NAMES.exploration]))

datastore_services = models.Registry.import_datastore_services()
search_services = models.Registry.import_search_services()


class MockUserStatsAggregator(
        user_jobs_continuous.UserStatsAggregator):
    """A modified UserStatsAggregator that does not start a new
     batch job when the previous one has finished.
    """

    @classmethod
    def _get_batch_job_manager_class(cls):
        return MockUserStatsMRJobManager

    @classmethod
    def _kickoff_batch_job_after_previous_one_ends(cls):
        pass


class MockUserStatsMRJobManager(
        user_jobs_continuous.UserStatsMRJobManager):

    @classmethod
    def _get_continuous_computation_class(cls):
        return MockUserStatsAggregator


class DashboardStatsOneOffJobTests(test_utils.GenericTestBase):
    """Tests for the one-off dashboard stats job."""

    CURRENT_DATE_AS_STRING = user_services.get_current_date_as_string()
    DATE_AFTER_ONE_WEEK = (
        (datetime.datetime.utcnow() + datetime.timedelta(7)).strftime(
            feconf.DASHBOARD_STATS_DATETIME_STRING_FORMAT))

    USER_SESSION_ID = 'session1'

    EXP_ID_1 = 'exp_id_1'
    EXP_ID_2 = 'exp_id_2'
    EXP_VERSION = 1

    def _run_one_off_job(self):
        """Runs the one-off MapReduce job."""
        job_id = user_jobs_one_off.DashboardStatsOneOffJob.create_new()
        user_jobs_one_off.DashboardStatsOneOffJob.enqueue(job_id)
        self.assertEqual(
            self.count_jobs_in_mapreduce_taskqueue(
                taskqueue_services.QUEUE_NAME_ONE_OFF_JOBS), 1)
        self.process_and_flush_pending_mapreduce_tasks()

    def setUp(self):
        super(DashboardStatsOneOffJobTests, self).setUp()

        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)

    def mock_get_current_date_as_string(self):
        return self.CURRENT_DATE_AS_STRING

    def _rate_exploration(self, user_id, exp_id, rating):
        """Assigns rating to the exploration corresponding to the given
        exploration id.

        Args:
            user_id: str. The user id.
            exp_id: str. The exploration id.
            rating: int. The rating to be assigned to the given exploration.
        """
        rating_services.assign_rating_to_exploration(user_id, exp_id, rating)

    def _record_play(self, exp_id, state):
        """Calls StartExplorationEventHandler and records the 'play' event
        corresponding to the given exploration id.

        Args:
            exp_id: str. The exploration id.
            state: dict(str, *). The state of the exploration corresponding to
                the given id.
        """
        event_services.StartExplorationEventHandler.record(
            exp_id, self.EXP_VERSION, state, self.USER_SESSION_ID, {},
            feconf.PLAY_TYPE_NORMAL)

    def test_weekly_stats_if_continuous_stats_job_has_not_been_run(self):
        exploration = self.save_new_valid_exploration(
            self.EXP_ID_1, self.owner_id)
        exp_id = exploration.id
        init_state_name = exploration.init_state_name
        self._record_play(exp_id, init_state_name)
        self._rate_exploration('user1', exp_id, 5)

        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        self.assertEqual(weekly_stats, None)
        self.assertEqual(
            user_services.get_last_week_dashboard_stats(self.owner_id), None)

        with self.swap(
            user_services,
            'get_current_date_as_string',
            self.mock_get_current_date_as_string):
            self._run_one_off_job()

        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        expected_results_list = [{
            self.mock_get_current_date_as_string(): {
                'num_ratings': 0,
                'average_ratings': None,
                'total_plays': 0
            }
        }]
        self.assertEqual(weekly_stats, expected_results_list)
        self.assertEqual(
            user_services.get_last_week_dashboard_stats(self.owner_id),
            expected_results_list[0])

    def test_weekly_stats_if_no_explorations(self):
        MockUserStatsAggregator.start_computation()
        self.process_and_flush_pending_mapreduce_tasks()

        with self.swap(
            user_services,
            'get_current_date_as_string',
            self.mock_get_current_date_as_string):
            self._run_one_off_job()

        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        self.assertEqual(
            weekly_stats, [{
                self.mock_get_current_date_as_string(): {
                    'num_ratings': 0,
                    'average_ratings': None,
                    'total_plays': 0
                }
            }])

    def test_weekly_stats_for_single_exploration(self):
        exploration = self.save_new_valid_exploration(
            self.EXP_ID_1, self.owner_id)
        exp_id = exploration.id
        init_state_name = exploration.init_state_name
        self._record_play(exp_id, init_state_name)
        self._rate_exploration('user1', exp_id, 5)
        event_services.StatsEventsHandler.record(
            self.EXP_ID_1, 1, {
                'num_starts': 1,
                'num_actual_starts': 0,
                'num_completions': 0,
                'state_stats_mapping': {}
            })

        self.process_and_flush_pending_tasks()

        MockUserStatsAggregator.start_computation()
        self.process_and_flush_pending_mapreduce_tasks()

        with self.swap(
            user_services,
            'get_current_date_as_string',
            self.mock_get_current_date_as_string):
            self._run_one_off_job()

        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        self.assertEqual(
            weekly_stats, [{
                self.mock_get_current_date_as_string(): {
                    'num_ratings': 1,
                    'average_ratings': 5.0,
                    'total_plays': 1
                }
            }])

    def test_weekly_stats_for_multiple_explorations(self):
        exploration_1 = self.save_new_valid_exploration(
            self.EXP_ID_1, self.owner_id)
        exp_id_1 = exploration_1.id
        exploration_2 = self.save_new_valid_exploration(
            self.EXP_ID_2, self.owner_id)
        exp_id_2 = exploration_2.id
        init_state_name_1 = exploration_1.init_state_name
        self._record_play(exp_id_1, init_state_name_1)
        self._rate_exploration('user1', exp_id_1, 5)
        self._rate_exploration('user2', exp_id_2, 4)
        event_services.StatsEventsHandler.record(
            self.EXP_ID_1, 1, {
                'num_starts': 1,
                'num_actual_starts': 0,
                'num_completions': 0,
                'state_stats_mapping': {}
            })

        self.process_and_flush_pending_tasks()
        MockUserStatsAggregator.start_computation()
        self.process_and_flush_pending_mapreduce_tasks()

        with self.swap(
            user_services,
            'get_current_date_as_string',
            self.mock_get_current_date_as_string):
            self._run_one_off_job()

        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        self.assertEqual(
            weekly_stats, [{
                self.mock_get_current_date_as_string(): {
                    'num_ratings': 2,
                    'average_ratings': 4.5,
                    'total_plays': 1
                }
            }])

    def test_stats_for_multiple_weeks(self):
        exploration = self.save_new_valid_exploration(
            self.EXP_ID_1, self.owner_id)
        exp_id = exploration.id
        init_state_name = exploration.init_state_name
        self._rate_exploration('user1', exp_id, 4)
        self._record_play(exp_id, init_state_name)
        self._record_play(exp_id, init_state_name)
        event_services.StatsEventsHandler.record(
            self.EXP_ID_1, 1, {
                'num_starts': 2,
                'num_actual_starts': 0,
                'num_completions': 0,
                'state_stats_mapping': {}
            })

        self.process_and_flush_pending_tasks()
        MockUserStatsAggregator.start_computation()
        self.process_and_flush_pending_mapreduce_tasks()

        with self.swap(
            user_services,
            'get_current_date_as_string',
            self.mock_get_current_date_as_string):
            self._run_one_off_job()

        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        self.assertEqual(
            weekly_stats, [{
                self.mock_get_current_date_as_string(): {
                    'num_ratings': 1,
                    'average_ratings': 4.0,
                    'total_plays': 2
                }
            }])

        MockUserStatsAggregator.stop_computation(self.owner_id)
        self.process_and_flush_pending_mapreduce_tasks()

        self._rate_exploration('user2', exp_id, 2)

        MockUserStatsAggregator.start_computation()
        self.process_and_flush_pending_mapreduce_tasks()

        def _mock_get_date_after_one_week():
            """Returns the date of the next week."""
            return self.DATE_AFTER_ONE_WEEK

        with self.swap(
            user_services,
            'get_current_date_as_string',
            _mock_get_date_after_one_week):
            self._run_one_off_job()

        expected_results_list = [
            {
                self.mock_get_current_date_as_string(): {
                    'num_ratings': 1,
                    'average_ratings': 4.0,
                    'total_plays': 2
                }
            },
            {
                _mock_get_date_after_one_week(): {
                    'num_ratings': 2,
                    'average_ratings': 3.0,
                    'total_plays': 2
                }
            }
        ]
        weekly_stats = user_services.get_weekly_dashboard_stats(self.owner_id)
        self.assertEqual(weekly_stats, expected_results_list)
        self.assertEqual(
            user_services.get_last_week_dashboard_stats(self.owner_id),
            expected_results_list[1])


class CleanupUserSubscriptionsModelUnitTests(test_utils.GenericTestBase):

    def setUp(self):
        super(CleanupUserSubscriptionsModelUnitTests, self).setUp()

        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.signup('user@email', 'user')
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.user_id = self.get_user_id_from_email('user@email')
        self.owner = user_services.UserActionsInfo(self.owner_id)

        explorations = [exp_domain.Exploration.create_default_exploration(
            '%s' % i,
            title='title %d' % i,
            category='category%d' % i
        ) for i in python_utils.RANGE(3)]

        for exp in explorations:
            exp_services.save_new_exploration(self.owner_id, exp)
            rights_manager.publish_exploration(self.owner, exp.id)

        for exp in explorations:
            subscription_services.subscribe_to_exploration(
                self.user_id, exp.id)
        self.process_and_flush_pending_mapreduce_tasks()

    def test_standard_operation(self):
        for exp_id in python_utils.RANGE(3):
            exp_models.ExplorationModel.get('%s' % exp_id).delete(
                self.owner_id, 'deleted exploration')

        owner_subscription_model = user_models.UserSubscriptionsModel.get(
            self.owner_id)
        self.assertEqual(len(owner_subscription_model.exploration_ids), 3)

        user_subscription_model = user_models.UserSubscriptionsModel.get(
            self.user_id)
        self.assertEqual(len(user_subscription_model.exploration_ids), 3)

        job = (
            user_jobs_one_off
            .CleanupExplorationIdsFromUserSubscriptionsModelOneOffJob
        )
        job_id = job.create_new()
        job.enqueue(job_id)
        self.assertEqual(
            self.count_jobs_in_mapreduce_taskqueue(
                taskqueue_services.QUEUE_NAME_ONE_OFF_JOBS), 1)
        self.process_and_flush_pending_mapreduce_tasks()

        owner_subscription_model = user_models.UserSubscriptionsModel.get(
            self.owner_id)
        self.assertEqual(len(owner_subscription_model.exploration_ids), 0)

        user_subscription_model = user_models.UserSubscriptionsModel.get(
            self.user_id)
        self.assertEqual(len(user_subscription_model.exploration_ids), 0)
        actual_output = job.get_output(job_id)
        expected_output = [
            u'[u\'Successfully cleaned up UserSubscriptionsModel %s and '
            'removed explorations 0, 1, 2\', 1]' %
            self.owner_id,
            u'[u\'Successfully cleaned up UserSubscriptionsModel %s and '
            'removed explorations 0, 1, 2\', 1]' %
            self.user_id]
        self.assertEqual(sorted(actual_output), sorted(expected_output))


class MockUserSettingsModelWithGaeUserId(user_models.UserSettingsModel):
    """Mock UserSettingsModel so that it allows to set `gae_user_id`."""

    gae_user_id = (
        datastore_services.StringProperty(indexed=True, required=False))


class MockUserSettingsModelWithGaeId(user_models.UserSettingsModel):
    """Mock UserSettingsModel so that it allows to set `gae_id`."""

    gae_id = (
        datastore_services.StringProperty(indexed=True, required=True))


class MockUserSubscriptionsModelWithActivityIDs(
        user_models.UserSubscriptionsModel):
    """Mock UserSubscriptionsModel so that it allows to set 'activity_ids'. """

    activity_ids = (
        datastore_services.StringProperty(indexed=True, repeated=True))


class RemoveActivityIDsOneOffJobTests(test_utils.GenericTestBase):
    def _run_one_off_job(self):
        """Runs the one-off MapReduce job."""
        job_id = (
            user_jobs_one_off.RemoveActivityIDsOneOffJob.create_new())
        user_jobs_one_off.RemoveActivityIDsOneOffJob.enqueue(job_id)
        self.assertEqual(
            self.count_jobs_in_mapreduce_taskqueue(
                taskqueue_services.QUEUE_NAME_ONE_OFF_JOBS), 1)
        self.process_and_flush_pending_mapreduce_tasks()
        stringified_output = (
            user_jobs_one_off.RemoveActivityIDsOneOffJob
            .get_output(job_id))
        eval_output = [ast.literal_eval(stringified_item) for
                       stringified_item in stringified_output]
        return eval_output

    def test_one_subscription_model_with_activity_ids(self):
        with self.swap(
            user_models, 'UserSubscriptionsModel',
            MockUserSubscriptionsModelWithActivityIDs):
            original_subscription_model = (
                user_models.UserSubscriptionsModel(
                    id='id',
                    activity_ids=['exp_1', 'exp_2', 'exp_3']
                )
            )
            original_subscription_model.update_timestamps()
            original_subscription_model.put()

            self.assertIsNotNone(
                original_subscription_model.activity_ids)
            self.assertIn(
                'activity_ids', original_subscription_model._values)  # pylint: disable=protected-access
            self.assertIn(
                'activity_ids', original_subscription_model._properties)  # pylint: disable=protected-access

            output = self._run_one_off_job()
            self.assertItemsEqual(
                [['SUCCESS_REMOVED - UserSubscriptionsModel', 1]], output)

            migrated_subscription_model = (
                user_models.UserSubscriptionsModel.get_by_id('id'))

            self.assertNotIn(
                'activity_ids', migrated_subscription_model._values)  # pylint: disable=protected-access
            self.assertNotIn(
                'activity_ids', migrated_subscription_model._properties)  # pylint: disable=protected-access
            self.assertEqual(
                original_subscription_model.last_updated,
                migrated_subscription_model.last_updated)

    def test_one_subscription_model_without_activity_ids(self):
        original_subscription_model = (
            user_models.UserSubscriptionsModel(
                id='id'
            )
        )
        original_subscription_model.update_timestamps()
        original_subscription_model.put()

        self.assertNotIn(
            'activity_ids', original_subscription_model._values)  # pylint: disable=protected-access
        self.assertNotIn(
            'activity_ids', original_subscription_model._properties)  # pylint: disable=protected-access

        output = self._run_one_off_job()
        self.assertItemsEqual(
            [['SUCCESS_ALREADY_REMOVED - UserSubscriptionsModel', 1]], output)

        migrated_subscription_model = (
            user_models.UserSubscriptionsModel.get_by_id('id'))
        self.assertNotIn(
            'activity_ids', migrated_subscription_model._values)  # pylint: disable=protected-access
        self.assertNotIn(
            'activity_ids', migrated_subscription_model._properties)  # pylint: disable=protected-access
        self.assertEqual(
            original_subscription_model.last_updated,
            migrated_subscription_model.last_updated)

    def test_rerun(self):
        original_subscription_model = (
            user_models.UserSubscriptionsModel(
                id='id'
            )
        )
        original_subscription_model.update_timestamps()
        original_subscription_model.put()

        self.assertNotIn(
            'activity_ids', original_subscription_model._values)  # pylint: disable=protected-access
        self.assertNotIn(
            'activity_ids', original_subscription_model._properties)  # pylint: disable=protected-access

        output = self._run_one_off_job()
        self.assertItemsEqual(
            [['SUCCESS_ALREADY_REMOVED - UserSubscriptionsModel', 1]], output)

        migrated_subscription_model = (
            user_models.UserSubscriptionsModel.get_by_id('id'))
        self.assertNotIn(
            'activity_ids', migrated_subscription_model._values)  # pylint: disable=protected-access
        self.assertNotIn(
            'activity_ids', migrated_subscription_model._properties)  # pylint: disable=protected-access
        self.assertEqual(
            original_subscription_model.last_updated,
            migrated_subscription_model.last_updated)

        output = self._run_one_off_job()
        self.assertItemsEqual(
            [['SUCCESS_ALREADY_REMOVED - UserSubscriptionsModel', 1]], output)

        migrated_subscription_model = (
            user_models.UserSubscriptionsModel.get_by_id('id'))
        self.assertNotIn(
            'activity_ids', migrated_subscription_model._values)  # pylint: disable=protected-access
        self.assertNotIn(
            'activity_ids', migrated_subscription_model._properties)  # pylint: disable=protected-access
        self.assertEqual(
            original_subscription_model.last_updated,
            migrated_subscription_model.last_updated)


class MockUserSubscriptionsModelWithFeedbackThreadIDs(
        user_models.UserSubscriptionsModel):
    """Mock UserSubscriptionsModel so that it allows to set
    `feedback_thread_ids`.
    """

    feedback_thread_ids = (
        datastore_services.StringProperty(indexed=True, repeated=True))


class CleanUpCollectionProgressModelOneOffJobTests(test_utils.GenericTestBase):

    def setUp(self):
        super(CleanUpCollectionProgressModelOneOffJobTests, self).setUp()

        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.set_admins([self.OWNER_USERNAME])
        self.owner = user_services.UserActionsInfo(self.owner_id)

        explorations = [exp_domain.Exploration.create_default_exploration(
            '%s' % i,
            title='title %d' % i,
            category='category%d' % i
        ) for i in python_utils.RANGE(3)]

        collection = collection_domain.Collection.create_default_collection(
            'col')

        for exp in explorations:
            exp_services.save_new_exploration(self.owner_id, exp)
            rights_manager.publish_exploration(self.owner, exp.id)
            collection.add_node(exp.id)

        collection_services.save_new_collection(self.owner_id, collection)
        rights_manager.publish_collection(self.owner, 'col')

        self.signup('user@email', 'user')
        self.user_id = self.get_user_id_from_email('user@email')

        learner_progress_services.mark_exploration_as_completed(
            self.user_id, '0')
        collection_services.record_played_exploration_in_collection_context(
            self.user_id, 'col', '0')
        learner_progress_services.mark_exploration_as_completed(
            self.user_id, '1')
        collection_services.record_played_exploration_in_collection_context(
            self.user_id, 'col', '1')

        self.model_instance = user_models.CollectionProgressModel.get_by_id(
            '%s.col' % self.user_id)
        self.process_and_flush_pending_mapreduce_tasks()

    def test_standard_operation(self):
        job_id = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpCollectionProgressModelOneOffJob.enqueue(
            job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.get_output(job_id))
        self.assertEqual(output, [])
        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])

    def test_migration_job_skips_deleted_model(self):
        self.model_instance.completed_explorations.append('3')
        self.model_instance.deleted = True
        self.model_instance.update_timestamps()
        self.model_instance.put()

        job_id = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpCollectionProgressModelOneOffJob.enqueue(
            job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.get_output(job_id))
        self.assertEqual(output, [])

    def test_job_cleans_up_exploration_ids_not_present_in_collection(self):
        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '1'])

        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])
        self.model_instance.completed_explorations.append('3')
        self.model_instance.update_timestamps()
        self.model_instance.put()
        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1', '3'])

        job_id = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpCollectionProgressModelOneOffJob.enqueue(
            job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.get_output(job_id))
        expected_output = [(
            '[u\'Added missing exp ids in CompletedActivitiesModel\', '
            '[u\'%s.col\']]' % self.user_id
        ), (
            '[u\'Invalid Exploration IDs cleaned from '
            'CollectionProgressModel\', '
            '[u"Model id: %s.col, Collection id: col, Removed exploration ids: '
            '[u\'3\']"]]' % self.user_id)]
        self.assertEqual(output, expected_output)
        self.model_instance = user_models.CollectionProgressModel.get_by_id(
            '%s.col' % self.user_id)
        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])

        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '1', '3'])

    def test_job_creates_completed_activities_model_if_it_is_missing(self):
        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '1'])
        completed_activities_model.delete()

        self.assertIsNone(
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))

        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])

        job_id = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpCollectionProgressModelOneOffJob.enqueue(
            job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.get_output(job_id))
        self.assertEqual(
            output, [
                '[u\'Regenerated Missing CompletedActivitiesModel\', '
                '[u\'%s.col\']]' % self.user_id])

        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])

        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '1'])

    def test_job_updates_completed_activities_model_if_exp_ids_do_not_match(
            self):
        learner_progress_services.mark_exploration_as_completed(
            self.user_id, '2')
        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '1', '2'])
        completed_activities_model.exploration_ids = ['0', '2']
        completed_activities_model.update_timestamps()
        completed_activities_model.put()

        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '2'])

        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])

        job_id = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpCollectionProgressModelOneOffJob.enqueue(
            job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off
            .CleanUpCollectionProgressModelOneOffJob.get_output(job_id))
        self.assertEqual(
            output, [
                '[u\'Added missing exp ids in CompletedActivitiesModel\', '
                '[u\'%s.col\']]' % self.user_id])

        self.assertEqual(
            self.model_instance.completed_explorations, ['0', '1'])

        completed_activities_model = (
            user_models.CompletedActivitiesModel.get_by_id(self.user_id))
        self.assertEqual(
            completed_activities_model.exploration_ids, ['0', '2', '1'])


class CleanUpUserContributionsModelOneOffJobTests(test_utils.GenericTestBase):

    def setUp(self):
        super(CleanUpUserContributionsModelOneOffJobTests, self).setUp()

        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.signup('user@email', 'user')
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.user_id = self.get_user_id_from_email('user@email')

        self.owner = user_services.UserActionsInfo(self.owner_id)
        self.user = user_services.UserActionsInfo(self.user_id)

        self.save_new_valid_exploration(
            'exp0', self.user_id, end_state_name='End')
        self.save_new_valid_exploration(
            'exp1', self.owner_id, end_state_name='End')
        exp_services.update_exploration(
            self.user_id, 'exp1', [exp_domain.ExplorationChange({
                'cmd': 'edit_exploration_property',
                'property_name': 'objective',
                'new_value': 'the objective'
            })], 'Test edit')

        rights_manager.publish_exploration(self.user, 'exp0')
        rights_manager.publish_exploration(self.owner, 'exp1')

        self.process_and_flush_pending_mapreduce_tasks()

    def test_standard_operation(self):
        job_id = (
            user_jobs_one_off
            .CleanUpUserContributionsModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.get_output(
                job_id))
        self.assertEqual(output, [])

        model_instance_1 = user_models.UserContributionsModel.get_by_id(
            self.user_id)
        self.assertEqual(model_instance_1.created_exploration_ids, ['exp0'])
        self.assertEqual(
            model_instance_1.edited_exploration_ids, ['exp0', 'exp1'])

        model_instance_2 = user_models.UserContributionsModel.get_by_id(
            self.owner_id)
        self.assertEqual(model_instance_2.created_exploration_ids, ['exp1'])
        self.assertEqual(
            model_instance_2.edited_exploration_ids, ['exp1'])

    def test_migration_job_skips_deleted_model(self):
        model_instance = user_models.UserContributionsModel.get_by_id(
            self.user_id)
        model_instance.deleted = True
        model_instance.update_timestamps()
        model_instance.put()
        exp_services.delete_exploration(self.user_id, 'exp0')
        job_id = (
            user_jobs_one_off
            .CleanUpUserContributionsModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.get_output(
                job_id))
        self.assertEqual(output, [])

    def test_job_removes_deleted_exp_from_created_explorations(self):
        exp_services.delete_exploration(self.user_id, 'exp0')
        model_instance_1 = user_models.UserContributionsModel.get_by_id(
            self.user_id)
        self.assertEqual(model_instance_1.created_exploration_ids, ['exp0'])
        self.assertEqual(
            model_instance_1.edited_exploration_ids, ['exp0', 'exp1'])

        model_instance_2 = user_models.UserContributionsModel.get_by_id(
            self.owner_id)
        self.assertEqual(model_instance_2.created_exploration_ids, ['exp1'])
        self.assertEqual(
            model_instance_2.edited_exploration_ids, ['exp1'])

        job_id = (
            user_jobs_one_off
            .CleanUpUserContributionsModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.get_output(
                job_id))
        self.assertEqual(
            output, [
                '[u\'Removed deleted exp ids from UserContributionsModel\', '
                '[u"Model id: %s, Removed exploration ids: [u\'exp0\', '
                'u\'exp0\']"]]' % self.user_id])

        model_instance_1 = user_models.UserContributionsModel.get_by_id(
            self.user_id)
        self.assertEqual(model_instance_1.created_exploration_ids, [])
        self.assertEqual(model_instance_1.edited_exploration_ids, ['exp1'])

        model_instance_2 = user_models.UserContributionsModel.get_by_id(
            self.owner_id)
        self.assertEqual(model_instance_2.created_exploration_ids, ['exp1'])
        self.assertEqual(
            model_instance_2.edited_exploration_ids, ['exp1'])

    def test_job_removes_deleted_exp_from_edited_explorations(self):
        exp_services.delete_exploration(self.owner_id, 'exp1')
        model_instance_1 = user_models.UserContributionsModel.get_by_id(
            self.user_id)
        self.assertEqual(model_instance_1.created_exploration_ids, ['exp0'])
        self.assertEqual(
            model_instance_1.edited_exploration_ids, ['exp0', 'exp1'])

        model_instance_2 = user_models.UserContributionsModel.get_by_id(
            self.owner_id)
        self.assertEqual(model_instance_2.created_exploration_ids, ['exp1'])
        self.assertEqual(
            model_instance_2.edited_exploration_ids, ['exp1'])

        job_id = (
            user_jobs_one_off
            .CleanUpUserContributionsModelOneOffJob.create_new())
        user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_mapreduce_tasks()

        output = (
            user_jobs_one_off.CleanUpUserContributionsModelOneOffJob.get_output(
                job_id))
        removed_exp_list = [
            'Model id: %s, Removed exploration ids: '
            '[u\'exp1\', u\'exp1\']' % self.owner_id,
            'Model id: %s, Removed exploration ids: '
            '[u\'exp1\']' % self.user_id]
        removed_exp_list.sort()
        self.assertEqual(
            output, [
                '[u\'Removed deleted exp ids from UserContributionsModel\', '
                '[u"%s", u"%s"]]' % (removed_exp_list[0], removed_exp_list[1])])

        model_instance_1 = user_models.UserContributionsModel.get_by_id(
            self.user_id)
        self.assertEqual(model_instance_1.created_exploration_ids, ['exp0'])
        self.assertEqual(model_instance_1.edited_exploration_ids, ['exp0'])

        model_instance_2 = user_models.UserContributionsModel.get_by_id(
            self.owner_id)
        self.assertEqual(model_instance_2.created_exploration_ids, [])
        self.assertEqual(
            model_instance_2.edited_exploration_ids, [])


class ProfilePictureAuditOneOffJobTests(test_utils.GenericTestBase):

    def _run_one_off_job(self):
        """Runs the one-off MapReduce job."""
        job_id = user_jobs_one_off.ProfilePictureAuditOneOffJob.create_new()
        user_jobs_one_off.ProfilePictureAuditOneOffJob.enqueue(job_id)
        self.assertEqual(
            self.count_jobs_in_mapreduce_taskqueue(
                taskqueue_services.QUEUE_NAME_ONE_OFF_JOBS), 1)
        self.process_and_flush_pending_mapreduce_tasks()
        stringified_output = (
            user_jobs_one_off.ProfilePictureAuditOneOffJob.get_output(job_id))
        eval_output = [ast.literal_eval(stringified_item) for
                       stringified_item in stringified_output]
        return eval_output

    def setUp(self):
        def empty(*_):
            """Function that takes any number of arguments and does nothing."""
            pass

        # We don't want to sign up the superadmin user.
        with self.swap(
            test_utils.AppEngineTestBase, 'signup_superadmin_user', empty):
            super(ProfilePictureAuditOneOffJobTests, self).setUp()
        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        user_services.generate_initial_profile_picture(self.owner_id)

    def test_correct_profile_picture_has_success_value(self):
        user_services.generate_initial_profile_picture(self.owner_id)
        output = self._run_one_off_job()
        self.assertEqual(output, [['SUCCESS', 1]])

    def test_resized_image_has_profile_picture_non_standard_dimensions_error(
            self):
        user_services.update_profile_picture_data_url(
            self.owner_id, image_constants.PNG_IMAGE_WRONG_DIMENSIONS_BASE64)
        output = self._run_one_off_job()
        self.assertEqual(
            output,
            [[
                'FAILURE - PROFILE PICTURE NON STANDARD DIMENSIONS - 150,160',
                [self.OWNER_USERNAME]
            ]]
        )

    def test_invalid_image_has_cannot_load_picture_error(self):
        user_services.update_profile_picture_data_url(
            self.owner_id, image_constants.PNG_IMAGE_BROKEN_BASE64)
        output = self._run_one_off_job()
        self.assertEqual(
            output,
            [['FAILURE - CANNOT LOAD PROFILE PICTURE', [self.OWNER_USERNAME]]]
        )

    def test_non_png_image_has_profile_picture_not_png_error(self):
        user_services.update_profile_picture_data_url(
            self.owner_id, image_constants.JPG_IMAGE_BASE64)
        output = self._run_one_off_job()
        self.assertEqual(
            output,
            [['FAILURE - PROFILE PICTURE NOT PNG', [self.OWNER_USERNAME]]]
        )

    def test_broken_base64_data_url_has_invalid_profile_picture_data_url_error(
            self):
        user_services.update_profile_picture_data_url(
            self.owner_id, image_constants.BROKEN_BASE64)
        output = self._run_one_off_job()
        self.assertEqual(
            output,
            [[
                'FAILURE - INVALID PROFILE PICTURE DATA URL',
                [self.OWNER_USERNAME]
            ]]
        )

    def test_user_without_profile_picture_has_missing_profile_picture_error(
            self):
        user_services.update_profile_picture_data_url(self.owner_id, None)
        output = self._run_one_off_job()
        self.assertEqual(
            output,
            [['FAILURE - MISSING PROFILE PICTURE', [self.OWNER_USERNAME]]]
        )

    def test_not_registered_user_has_not_registered_value(self):
        user_settings_model = (
            user_models.UserSettingsModel.get_by_id(self.owner_id))
        user_settings_model.username = None
        user_settings_model.update_timestamps()
        user_settings_model.put()
        output = self._run_one_off_job()
        self.assertEqual(output, [['SUCCESS - NOT REGISTERED', 1]])

    def test_deleted_user_has_deleted_value(self):
        user_settings_model = (
            user_models.UserSettingsModel.get_by_id(self.owner_id))
        user_settings_model.deleted = True
        user_settings_model.update_timestamps()
        user_settings_model.put()
        output = self._run_one_off_job()
        self.assertEqual(output, [['SUCCESS - DELETED', 1]])

    def test_zero_users_has_no_output(self):
        user_models.UserSettingsModel.delete_by_id(self.owner_id)
        output = self._run_one_off_job()
        self.assertEqual(output, [])

    def test_multiple_users_have_correct_values(self):
        self.signup(self.NEW_USER_EMAIL, self.NEW_USER_USERNAME)
        new_user_id = self.get_user_id_from_email(self.NEW_USER_EMAIL)
        self.signup(self.EDITOR_EMAIL, self.EDITOR_USERNAME)
        editor_id = self.get_user_id_from_email(self.EDITOR_EMAIL)
        self.signup(self.MODERATOR_EMAIL, self.MODERATOR_USERNAME)
        moderator_id = self.get_user_id_from_email(self.MODERATOR_EMAIL)

        user_services.update_profile_picture_data_url(
            new_user_id, image_constants.JPG_IMAGE_BASE64)
        user_services.update_profile_picture_data_url(editor_id, None)

        user_settings_model = (
            user_models.UserSettingsModel.get_by_id(moderator_id))
        user_settings_model.deleted = True
        user_settings_model.update_timestamps()
        user_settings_model.put()

        output = self._run_one_off_job()
        self.assertItemsEqual(
            output,
            [
                ['SUCCESS', 1],
                ['FAILURE - MISSING PROFILE PICTURE', [self.EDITOR_USERNAME]],
                ['SUCCESS - DELETED', 1],
                ['FAILURE - PROFILE PICTURE NOT PNG', [self.NEW_USER_USERNAME]]
            ]
        )
