# Copyright 2020 The Oppia Authors. All Rights Reserved.
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

"""Tests for wipeout service."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

from constants import constants
from core.domain import rights_manager
from core.domain import topic_domain
from core.domain import topic_services
from core.domain import user_domain
from core.domain import user_services
from core.domain import wipeout_domain
from core.domain import wipeout_service
from core.platform import models
from core.tests import test_utils
import feconf

(
    auth_models, collection_models, config_models,
    email_models, exp_models, feedback_models,
    improvements_models, question_models, skill_models,
    story_models, subtopic_models, suggestion_models,
    topic_models, user_models
) = models.Registry.import_models([
    models.NAMES.auth, models.NAMES.collection, models.NAMES.config,
    models.NAMES.email, models.NAMES.exploration, models.NAMES.feedback,
    models.NAMES.improvements, models.NAMES.question, models.NAMES.skill,
    models.NAMES.story, models.NAMES.subtopic, models.NAMES.suggestion,
    models.NAMES.topic, models.NAMES.user
])

datastore_services = models.Registry.import_datastore_services()


class WipeoutServiceHelpersTests(test_utils.GenericTestBase):
    """Provides testing of the pre-deletion part of wipeout service."""

    USER_1_EMAIL = 'some@email.com'
    USER_1_USERNAME = 'username1'
    USER_2_EMAIL = 'some-other@email.com'
    USER_2_USERNAME = 'username2'

    def setUp(self):
        super(WipeoutServiceHelpersTests, self).setUp()
        self.signup(self.USER_1_EMAIL, self.USER_1_USERNAME)
        self.user_1_id = self.get_user_id_from_email(self.USER_1_EMAIL)
        self.user_1_role = user_services.get_user_settings(self.user_1_id).role
        self.signup(self.USER_2_EMAIL, self.USER_2_USERNAME)
        self.user_2_id = self.get_user_id_from_email(self.USER_2_EMAIL)
        self.user_2_role = user_services.get_user_settings(self.user_2_id).role

    def test_gets_pending_deletion_request(self):
        wipeout_service.save_pending_deletion_requests(
            [
                wipeout_domain.PendingDeletionRequest.create_default(
                    self.user_1_id, self.USER_1_EMAIL, self.user_1_role)
            ]
        )

        pending_deletion_request = (
            wipeout_service.get_pending_deletion_request(self.user_1_id))
        self.assertEqual(pending_deletion_request.user_id, self.user_1_id)
        self.assertEqual(pending_deletion_request.email, self.USER_1_EMAIL)
        self.assertEqual(pending_deletion_request.deletion_complete, False)
        self.assertEqual(
            pending_deletion_request.pseudonymizable_entity_mappings, {})

    def test_get_number_of_pending_deletion_requests_returns_correct_number(
            self):
        number_of_pending_deletion_requests = (
            wipeout_service.get_number_of_pending_deletion_requests())
        self.assertEqual(number_of_pending_deletion_requests, 0)

        wipeout_service.save_pending_deletion_requests(
            [
                wipeout_domain.PendingDeletionRequest.create_default(
                    self.user_1_id, self.USER_1_EMAIL, self.user_1_role),
                wipeout_domain.PendingDeletionRequest.create_default(
                    self.user_2_id, self.USER_2_EMAIL, self.user_2_role)
            ]
        )
        number_of_pending_deletion_requests = (
            wipeout_service.get_number_of_pending_deletion_requests())
        self.assertEqual(number_of_pending_deletion_requests, 2)

    def test_saves_pending_deletion_request_when_new(self):
        pending_deletion_request = (
            wipeout_domain.PendingDeletionRequest.create_default(
                self.user_1_id, self.USER_1_EMAIL, self.user_1_role))
        wipeout_service.save_pending_deletion_requests(
            [pending_deletion_request])

        pending_deletion_request_model = (
            user_models.PendingDeletionRequestModel.get_by_id(self.user_1_id))

        self.assertEqual(pending_deletion_request_model.id, self.user_1_id)
        self.assertEqual(
            pending_deletion_request_model.email, self.USER_1_EMAIL)
        self.assertEqual(
            pending_deletion_request_model.deletion_complete, False)
        self.assertEqual(
            pending_deletion_request_model.pseudonymizable_entity_mappings, {})

    def test_saves_pending_deletion_request_when_already_existing(self):
        pending_deletion_request_model_old = (
            user_models.PendingDeletionRequestModel(
                id=self.user_1_id,
                email=self.USER_1_EMAIL,
                role=self.user_1_role,
                deletion_complete=False,
                pseudonymizable_entity_mappings={}
            )
        )
        pending_deletion_request_model_old.put()

        pending_deletion_request = (
            wipeout_domain.PendingDeletionRequest.create_default(
                self.user_1_id, self.USER_1_EMAIL, self.user_1_role)
        )
        pending_deletion_request.deletion_complete = True
        pending_deletion_request.pseudonymizable_entity_mappings = {
            'story': {'story_id': 'user_id'}
        }
        wipeout_service.save_pending_deletion_requests(
            [pending_deletion_request])

        pending_deletion_request_model_new = (
            user_models.PendingDeletionRequestModel.get_by_id(self.user_1_id))

        self.assertEqual(pending_deletion_request_model_new.id, self.user_1_id)
        self.assertEqual(
            pending_deletion_request_model_new.email, self.USER_1_EMAIL)
        self.assertEqual(
            pending_deletion_request_model_new.deletion_complete, True)
        self.assertEqual(
            pending_deletion_request_model_new.pseudonymizable_entity_mappings,
            {'story': {'story_id': 'user_id'}})
        self.assertEqual(
            pending_deletion_request_model_old.created_on,
            pending_deletion_request_model_new.created_on)


class WipeoutServicePreDeleteTests(test_utils.GenericTestBase):
    """Provides testing of the pre-deletion part of wipeout service."""

    USER_1_EMAIL = 'some@email.com'
    USER_1_USERNAME = 'username1'
    USER_2_EMAIL = 'some-other@email.com'
    USER_2_USERNAME = 'username2'
    USER_3_EMAIL = 'other@email.com'
    USER_3_USERNAME = 'username3'

    def setUp(self):
        super(WipeoutServicePreDeleteTests, self).setUp()
        self.signup(self.USER_1_EMAIL, self.USER_1_USERNAME)
        self.user_1_id = self.get_user_id_from_email(self.USER_1_EMAIL)
        self.set_user_role(self.USER_1_USERNAME, feconf.ROLE_ID_TOPIC_MANAGER)
        self.user_1_auth_id = self.get_auth_id_from_email(self.USER_1_EMAIL)
        self.user_1_actions = user_services.get_user_actions_info(
            self.user_1_id)

        self.signup(self.USER_2_EMAIL, self.USER_2_USERNAME)
        self.user_2_id = self.get_user_id_from_email(self.USER_2_EMAIL)
        self.user_1_auth_id = self.get_auth_id_from_email(self.USER_1_EMAIL)
        user_data_dict = {
            'schema_version': 1,
            'display_alias': 'display_alias',
            'pin': '12345',
            'preferred_language_codes': [constants.DEFAULT_LANGUAGE_CODE],
            'preferred_site_language_code': None,
            'preferred_audio_language_code': None,
            'user_id': self.user_1_id,
        }
        new_user_data_dict = {
            'schema_version': 1,
            'display_alias': 'display_alias3',
            'pin': '12345',
            'preferred_language_codes': [constants.DEFAULT_LANGUAGE_CODE],
            'preferred_site_language_code': None,
            'preferred_audio_language_code': None,
            'user_id': None,
        }
        self.modifiable_user_data = (
            user_domain.ModifiableUserData.from_raw_dict(user_data_dict))
        self.modifiable_new_user_data = (
            user_domain.ModifiableUserData.from_raw_dict(new_user_data_dict))

        user_services.update_multiple_users_data(
            [self.modifiable_user_data])
        self.modifiable_user_data.display_alias = 'name'
        self.modifiable_user_data.pin = '123'
        self.profile_user_id = user_services.create_new_profiles(
            self.user_1_auth_id, self.USER_1_EMAIL,
            [self.modifiable_new_user_data]
        )[0].user_id

    def tearDown(self):
        pending_deletion_request_models = (
            user_models.PendingDeletionRequestModel.get_all())
        for pending_deletion_request_model in pending_deletion_request_models:
            pending_deletion_request = (
                wipeout_service.get_pending_deletion_request(
                    pending_deletion_request_model.id))
            self.assertEqual(
                wipeout_service.run_user_deletion(pending_deletion_request),
                wipeout_domain.USER_DELETION_SUCCESS)
            self.assertEqual(
                wipeout_service.run_user_deletion_completion(
                    pending_deletion_request),
                wipeout_domain.USER_VERIFICATION_SUCCESS)


class WipeoutServiceDeleteCollectionModelsTests(test_utils.GenericTestBase):
    """Provides testing of the deletion part of wipeout service."""

    USER_1_EMAIL = 'some@email.com'
    USER_1_USERNAME = 'username1'
    USER_2_EMAIL = 'some-other@email.com'
    USER_2_USERNAME = 'username2'
    COL_1_ID = 'col_1_id'
    COL_2_ID = 'col_2_id'

    def setUp(self):
        super(WipeoutServiceDeleteCollectionModelsTests, self).setUp()
        self.signup(self.USER_1_EMAIL, self.USER_1_USERNAME)
        self.signup(self.USER_2_EMAIL, self.USER_2_USERNAME)
        self.user_1_id = self.get_user_id_from_email(self.USER_1_EMAIL)
        self.user_2_id = self.get_user_id_from_email(self.USER_2_EMAIL)
        self.save_new_valid_collection(self.COL_1_ID, self.user_1_id)
        self.publish_collection(self.user_1_id, self.COL_1_ID)
        rights_manager.assign_role_for_collection(
            user_services.get_user_actions_info(self.user_1_id),
            self.COL_1_ID,
            self.user_2_id,
            feconf.ROLE_OWNER)


class WipeoutServiceDeleteTopicModelsTests(test_utils.GenericTestBase):
    """Provides testing of the deletion part of wipeout service."""

    USER_1_EMAIL = 'some@email.com'
    USER_1_USERNAME = 'username1'
    USER_2_EMAIL = 'some-other@email.com'
    USER_2_USERNAME = 'username2'
    TOP_1_ID = 'top_1_id'
    TOP_2_ID = 'top_2_id'

    def setUp(self):
        super(WipeoutServiceDeleteTopicModelsTests, self).setUp()
        self.signup(self.USER_1_EMAIL, self.USER_1_USERNAME)
        self.signup(self.USER_2_EMAIL, self.USER_2_USERNAME)
        self.user_1_id = self.get_user_id_from_email(self.USER_1_EMAIL)
        self.user_2_id = self.get_user_id_from_email(self.USER_2_EMAIL)
        user_services.update_user_role(
            self.user_1_id, feconf.ROLE_ID_ADMIN)
        user_services.update_user_role(
            self.user_2_id, feconf.ROLE_ID_TOPIC_MANAGER)
        self.user_1_actions = user_services.get_user_actions_info(
            self.user_1_id)
        self.user_2_actions = user_services.get_user_actions_info(
            self.user_2_id)
        self.save_new_topic(self.TOP_1_ID, self.user_1_id)
        topic_services.assign_role(
            self.user_1_actions,
            self.user_1_actions,
            topic_domain.ROLE_MANAGER,
            self.TOP_1_ID)
        topic_services.assign_role(
            self.user_1_actions,
            self.user_2_actions,
            topic_domain.ROLE_MANAGER,
            self.TOP_1_ID)


class WipeoutServiceDeleteUserModelsTests(test_utils.GenericTestBase):
    """Provides testing of the deletion part of wipeout service."""

    USER_1_EMAIL = 'some@email.com'
    USER_1_USERNAME = 'username1'
    USER_2_EMAIL = 'some-other@email.com'
    USER_2_USERNAME = 'username2'
    COLLECTION_1_ID = 'col_1_id'
    COLLECTION_2_ID = 'col_2_id'
    EXPLORATION_1_ID = 'exp_1_id'
    EXPLORATION_2_ID = 'exp_2_id'

    def setUp(self):
        super(WipeoutServiceDeleteUserModelsTests, self).setUp()
        self.signup(self.USER_1_EMAIL, self.USER_1_USERNAME)
        self.signup(self.USER_2_EMAIL, self.USER_2_USERNAME)
        self.user_1_id = self.get_user_id_from_email(self.USER_1_EMAIL)
        self.user_2_id = self.get_user_id_from_email(self.USER_2_EMAIL)
        user_models.CompletedActivitiesModel(
            id=self.user_2_id, exploration_ids=[], collection_ids=[]
        ).put()
        user_models.IncompleteActivitiesModel(
            id=self.user_2_id, exploration_ids=[], collection_ids=[]
        ).put()
        user_models.LearnerPlaylistModel(
            id=self.user_2_id, exploration_ids=[], collection_ids=[]
        ).put()
        self.user_1_auth_id = self.get_auth_id_from_email(self.USER_1_EMAIL)
        user_data_dict = {
            'schema_version': 1,
            'display_alias': 'display_alias',
            'pin': '12345',
            'preferred_language_codes': [constants.DEFAULT_LANGUAGE_CODE],
            'preferred_site_language_code': None,
            'preferred_audio_language_code': None,
            'user_id': self.user_1_id,
        }
        new_user_data_dict = {
            'schema_version': 1,
            'display_alias': 'display_alias3',
            'pin': '12345',
            'preferred_language_codes': [constants.DEFAULT_LANGUAGE_CODE],
            'preferred_site_language_code': None,
            'preferred_audio_language_code': None,
            'user_id': None,
        }
        self.modifiable_user_data = (
            user_domain.ModifiableUserData.from_raw_dict(user_data_dict))
        self.modifiable_new_user_data = (
            user_domain.ModifiableUserData.from_raw_dict(new_user_data_dict))

        user_services.update_multiple_users_data(
            [self.modifiable_user_data])

        self.modifiable_new_user_data.display_alias = 'name'
        self.modifiable_new_user_data.pin = '123'
        self.profile_user_id = user_services.create_new_profiles(
            self.user_1_auth_id, self.USER_1_EMAIL,
            [self.modifiable_new_user_data]
        )[0].user_id

        user_models.CompletedActivitiesModel(
            id=self.profile_user_id, exploration_ids=[], collection_ids=[]
        ).put()
        user_models.IncompleteActivitiesModel(
            id=self.profile_user_id, exploration_ids=[], collection_ids=[]
        ).put()
        user_models.LearnerPlaylistModel(
            id=self.profile_user_id, exploration_ids=[], collection_ids=[]
        ).put()
