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

"""Tests for the admin page."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import logging

from constants import constants
from core.domain import collection_services
from core.domain import config_domain
from core.domain import config_services
from core.domain import exp_services
from core.domain import opportunity_services
from core.domain import question_fetchers
from core.domain import rights_manager
from core.domain import skill_services
from core.domain import story_domain
from core.domain import story_fetchers
from core.domain import story_services
from core.domain import topic_domain
from core.domain import topic_fetchers
from core.domain import topic_services
from core.platform import models
from core.tests import test_utils

(
    audit_models, exp_models, job_models,
    opportunity_models, user_models
) = models.Registry.import_models([
    models.NAMES.audit, models.NAMES.exploration, models.NAMES.job,
    models.NAMES.opportunity, models.NAMES.user
])

BOTH_MODERATOR_AND_ADMIN_EMAIL = 'moderator.and.admin@example.com'
BOTH_MODERATOR_AND_ADMIN_USERNAME = 'moderatorandadm1n'


class AdminIntegrationTest(test_utils.GenericTestBase):
    """Server integration tests for operations on the admin page."""

    def setUp(self):
        """Complete the signup process for self.ADMIN_EMAIL."""
        super(AdminIntegrationTest, self).setUp()
        self.signup(self.ADMIN_EMAIL, self.ADMIN_USERNAME)
        self.signup(self.EDITOR_EMAIL, self.EDITOR_USERNAME)
        self.admin_id = self.get_user_id_from_email(self.ADMIN_EMAIL)

    def test_admin_page_rights(self):
        """Test access rights to the admin page."""

        self.get_html_response('/admin', expected_status_int=302)

        # Login as a non-admin.
        self.login(self.EDITOR_EMAIL)
        self.get_html_response('/admin', expected_status_int=401)
        self.logout()

        # Login as an admin.
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        self.get_html_response('/admin')
        self.logout()

    def test_change_configuration_property(self):
        """Test that configuration properties can be changed."""

        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()
        new_config_value = False

        response_dict = self.get_json('/adminhandler')
        response_config_properties = response_dict['config_properties']
        self.assertDictContainsSubset({
            'value': False,
        }, response_config_properties[
            config_domain.IS_IMPROVEMENTS_TAB_ENABLED.name])

        payload = {
            'action': 'save_config_properties',
            'new_config_property_values': {
                config_domain.IS_IMPROVEMENTS_TAB_ENABLED.name: (
                    new_config_value),
            }
        }
        self.post_json('/adminhandler', payload, csrf_token=csrf_token)

        response_dict = self.get_json('/adminhandler')
        response_config_properties = response_dict['config_properties']
        self.assertDictContainsSubset({
            'value': new_config_value,
        }, response_config_properties[
            config_domain.IS_IMPROVEMENTS_TAB_ENABLED.name])

        self.logout()

    def test_cannot_reload_exploration_in_production_mode(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        prod_mode_swap = self.swap(constants, 'DEV_MODE', False)
        assert_raises_regexp_context_manager = self.assertRaisesRegexp(
            Exception, 'Cannot reload an exploration in production.')
        with assert_raises_regexp_context_manager, prod_mode_swap:
            self.post_json(
                '/adminhandler', {
                    'action': 'reload_exploration',
                    'exploration_id': '2'
                }, csrf_token=csrf_token)

        self.logout()

    def test_cannot_load_new_structures_data_in_production_mode(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        prod_mode_swap = self.swap(constants, 'DEV_MODE', False)
        assert_raises_regexp_context_manager = self.assertRaisesRegexp(
            Exception, 'Cannot load new structures data in production.')
        with assert_raises_regexp_context_manager, prod_mode_swap:
            self.post_json(
                '/adminhandler', {
                    'action': 'generate_dummy_new_structures_data'
                }, csrf_token=csrf_token)
        self.logout()

    def test_non_admins_cannot_load_new_structures_data(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()
        assert_raises_regexp = self.assertRaisesRegexp(
            Exception, 'User does not have enough rights to generate data.')
        with assert_raises_regexp:
            self.post_json(
                '/adminhandler', {
                    'action': 'generate_dummy_new_structures_data'
                }, csrf_token=csrf_token)
        self.logout()

    def test_cannot_generate_dummy_skill_data_in_production_mode(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        prod_mode_swap = self.swap(constants, 'DEV_MODE', False)
        assert_raises_regexp_context_manager = self.assertRaisesRegexp(
            Exception, 'Cannot generate dummy skills in production.')
        with assert_raises_regexp_context_manager, prod_mode_swap:
            self.post_json(
                '/adminhandler', {
                    'action': 'generate_dummy_new_skill_data'
                }, csrf_token=csrf_token)
        self.logout()

    def test_non_admins_cannot_generate_dummy_skill_data(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()
        assert_raises_regexp = self.assertRaisesRegexp(
            Exception, 'User does not have enough rights to generate data.')
        with assert_raises_regexp:
            self.post_json(
                '/adminhandler', {
                    'action': 'generate_dummy_new_skill_data'
                }, csrf_token=csrf_token)
        self.logout()

    def test_cannot_reload_collection_in_production_mode(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        prod_mode_swap = self.swap(constants, 'DEV_MODE', False)
        assert_raises_regexp_context_manager = self.assertRaisesRegexp(
            Exception, 'Cannot reload a collection in production.')
        with assert_raises_regexp_context_manager, prod_mode_swap:
            self.post_json(
                '/adminhandler', {
                    'action': 'reload_collection',
                    'collection_id': '2'
                }, csrf_token=csrf_token)

        self.logout()

    def test_reload_collection(self):
        observed_log_messages = []

        def _mock_logging_function(msg, *args):
            """Mocks logging.info()."""
            observed_log_messages.append(msg % args)

        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        collection_services.load_demo('0')
        collection_rights = rights_manager.get_collection_rights('0')

        self.assertFalse(collection_rights.community_owned)

        with self.swap(logging, 'info', _mock_logging_function):
            self.post_json(
                '/adminhandler', {
                    'action': 'reload_collection',
                    'collection_id': '0'
                }, csrf_token=csrf_token)

        collection_rights = rights_manager.get_collection_rights('0')

        self.assertTrue(collection_rights.community_owned)
        self.assertEqual(
            observed_log_messages,
            [
                '[ADMIN] %s reloaded collection 0' % self.admin_id,
                'Collection with id 0 was loaded.'
            ]
        )

        self.logout()

    def test_load_new_structures_data(self):
        self.set_admins([self.ADMIN_USERNAME])
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()
        self.post_json(
            '/adminhandler', {
                'action': 'generate_dummy_new_structures_data'
            }, csrf_token=csrf_token)
        topic_summaries = topic_fetchers.get_all_topic_summaries()
        self.assertEqual(len(topic_summaries), 2)
        for summary in topic_summaries:
            if summary.name == 'Dummy Topic 1':
                topic_id = summary.id
        story_id = (
            topic_fetchers.get_topic_by_id(
                topic_id).canonical_story_references[0].story_id)
        self.assertIsNotNone(
            story_fetchers.get_story_by_id(story_id, strict=False))
        skill_summaries = skill_services.get_all_skill_summaries()
        self.assertEqual(len(skill_summaries), 3)
        questions, _, _ = (
            question_fetchers.get_questions_and_skill_descriptions_by_skill_ids(
                10, [
                    skill_summaries[0].id, skill_summaries[1].id,
                    skill_summaries[2].id], '')
        )
        self.assertEqual(len(questions), 3)
        # Testing that there are 3 hindi translation opportunities
        # available on the Contributor Dashboard. Hindi was picked arbitrarily,
        # any language code other than english (what the dummy explorations
        # were written in) can be tested here.
        translation_opportunities, _, _ = (
            opportunity_services.get_translation_opportunities('hi', None))
        self.assertEqual(len(translation_opportunities), 3)
        self.logout()

    def test_generate_dummy_skill_and_questions_data(self):
        self.set_admins([self.ADMIN_USERNAME])
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()
        self.post_json(
            '/adminhandler', {
                'action': 'generate_dummy_new_skill_data'
            }, csrf_token=csrf_token)
        skill_summaries = skill_services.get_all_skill_summaries()
        self.assertEqual(len(skill_summaries), 1)
        questions, _, _ = (
            question_fetchers.get_questions_and_skill_descriptions_by_skill_ids(
                20, [skill_summaries[0].id], '')
        )
        self.assertEqual(len(questions), 15)
        self.logout()

    def test_regenerate_topic_related_opportunities_action(self):
        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)

        owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.set_admins([self.ADMIN_USERNAME])

        topic_id = 'topic'
        story_id = 'story'
        self.save_new_valid_exploration(
            '0', owner_id, title='title', end_state_name='End State',
            correctness_feedback_enabled=True)
        self.publish_exploration(owner_id, '0')

        topic = topic_domain.Topic.create_default_topic(
            topic_id, 'topic', 'abbrev', 'description')
        topic.thumbnail_filename = 'thumbnail.svg'
        topic.thumbnail_bg_color = '#C6DCDA'
        topic.subtopics = [
            topic_domain.Subtopic(
                1, 'Title', ['skill_id_1'], 'image.svg',
                constants.ALLOWED_THUMBNAIL_BG_COLORS['subtopic'][0],
                'dummy-subtopic-three')]
        topic.next_subtopic_id = 2
        topic_services.save_new_topic(owner_id, topic)
        topic_services.publish_topic(topic_id, self.admin_id)

        story = story_domain.Story.create_default_story(
            story_id, 'A story', 'Description', topic_id, 'story')
        story_services.save_new_story(owner_id, story)
        topic_services.add_canonical_story(
            owner_id, topic_id, story_id)
        topic_services.publish_story(topic_id, story_id, self.admin_id)
        story_services.update_story(
            owner_id, story_id, [story_domain.StoryChange({
                'cmd': 'add_story_node',
                'node_id': 'node_1',
                'title': 'Node1',
            }), story_domain.StoryChange({
                'cmd': 'update_story_node_property',
                'property_name': 'exploration_id',
                'node_id': 'node_1',
                'old_value': None,
                'new_value': '0'
            })], 'Changes.')

        all_opportunity_models = list(
            opportunity_models.ExplorationOpportunitySummaryModel.get_all())

        self.assertEqual(len(all_opportunity_models), 1)

        old_creation_time = all_opportunity_models[0].created_on

        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        result = self.post_json(
            '/adminhandler', {
                'action': 'regenerate_topic_related_opportunities',
                'topic_id': 'topic'
            }, csrf_token=csrf_token)

        self.assertEqual(
            result, {
                'opportunities_count': 1
            })

        all_opportunity_models = list(
            opportunity_models.ExplorationOpportunitySummaryModel.get_all())

        self.assertEqual(len(all_opportunity_models), 1)

        new_creation_time = all_opportunity_models[0].created_on

        self.assertLess(old_creation_time, new_creation_time)

    def test_regenerate_missing_exploration_stats_action(self):
        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)

        self.set_admins([self.ADMIN_USERNAME])

        self.save_new_default_exploration('ID', 'owner_id')

        self.assertEqual(
            exp_services.regenerate_missing_stats_for_exploration('ID'), (
                [], [], 1, 1))

        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        result = self.post_json(
            '/adminhandler', {
                'action': 'regenerate_missing_exploration_stats',
                'exp_id': 'ID'
            }, csrf_token=csrf_token)

        self.assertEqual(
            result, {
                'missing_exp_stats': [],
                'missing_state_stats': [],
                'num_valid_exp_stats': 1,
                'num_valid_state_stats': 1
            })

    def test_admin_topics_csv_download_handler(self):
        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        response = self.get_custom_response(
            '/admintopicscsvdownloadhandler', 'text/csv')

        self.assertEqual(
            response.headers['Content-Disposition'],
            'attachment; filename=topic_similarities.csv')

        self.assertIn(
            'Architecture,Art,Biology,Business,Chemistry,Computing,Economics,'
            'Education,Engineering,Environment,Geography,Government,Hobbies,'
            'Languages,Law,Life Skills,Mathematics,Medicine,Music,Philosophy,'
            'Physics,Programming,Psychology,Puzzles,Reading,Religion,Sport,'
            'Statistics,Welcome',
            response.body)

        self.logout()

    def test_revert_config_property(self):
        observed_log_messages = []

        def _mock_logging_function(msg, *args):
            """Mocks logging.info()."""
            observed_log_messages.append(msg % args)

        self.login(self.ADMIN_EMAIL, is_super_admin=True)
        csrf_token = self.get_new_csrf_token()

        config_services.set_property(self.admin_id, 'promo_bar_enabled', True)
        self.assertTrue(config_domain.PROMO_BAR_ENABLED.value)

        with self.swap(logging, 'info', _mock_logging_function):
            self.post_json(
                '/adminhandler', {
                    'action': 'revert_config_property',
                    'config_property_id': 'promo_bar_enabled'
                }, csrf_token=csrf_token)

        self.assertFalse(config_domain.PROMO_BAR_ENABLED.value)
        self.assertEqual(
            observed_log_messages,
            ['[ADMIN] %s reverted config property: promo_bar_enabled'
             % self.admin_id])

        self.logout()
