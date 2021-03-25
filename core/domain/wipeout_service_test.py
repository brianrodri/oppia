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

from core.domain import user_services
from core.domain import wipeout_domain
from core.domain import wipeout_service
from core.platform import models
from core.tests import test_utils

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
