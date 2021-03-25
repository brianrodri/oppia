# coding: utf-8
#
# Copyright 2016 The Oppia Authors. All Rights Reserved.
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

"""Tests for query MR job."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import datetime

from constants import constants
from core.domain import exp_domain
from core.domain import exp_services
from core.domain import user_query_jobs_one_off
from core.domain import user_services
from core.platform import models
from core.tests import test_utils

(user_models,) = models.Registry.import_models([models.NAMES.user])


class UserQueryJobOneOffTests(test_utils.EmailTestBase):
    EXP_ID_1 = 'exp_id_1'
    EXP_ID_2 = 'exp_id_2'
    EXP_ID_3 = 'exp_id_3'
    EXP_ID_4 = 'exp_id_4'
    USER_A_EMAIL = 'a@example.com'
    USER_A_USERNAME = 'a'
    USER_B_EMAIL = 'b@example.com'
    USER_B_USERNAME = 'b'
    USER_C_EMAIL = 'c@example.com'
    USER_C_USERNAME = 'c'
    USER_D_EMAIL = 'd@example.com'
    USER_D_USERNAME = 'd'
    USER_E_EMAIL = 'e@example.com'
    USER_E_USERNAME = 'e'
    USER_F_EMAIL = 'f@example.com'
    USER_F_USERNAME = 'f'
    USER_SUBMITTER_EMAIL = 'submit@example.com'
    USER_SUBMITTER_USERNAME = 'submit'

    def setUp(self):
        super(UserQueryJobOneOffTests, self).setUp()
        # User A has no created or edited explorations.
        # User B has one created exploration.
        # User C has one edited exploration.
        # User D has created an exploration and then edited it.
        # User E has created an exploration 10 days before.
        # User F has one created exploration but is not subscribed to emails.
        # Submitter is the user who submits the query.
        self.signup(self.USER_A_EMAIL, self.USER_A_USERNAME)
        self.user_a_id = self.get_user_id_from_email(self.USER_A_EMAIL)
        user_services.update_email_preferences(
            self.user_a_id, True, True, True, True)
        self.signup(self.USER_B_EMAIL, self.USER_B_USERNAME)
        self.user_b_id = self.get_user_id_from_email(self.USER_B_EMAIL)
        user_services.update_email_preferences(
            self.user_b_id, True, True, True, True)
        self.signup(self.USER_C_EMAIL, self.USER_C_USERNAME)
        self.user_c_id = self.get_user_id_from_email(self.USER_C_EMAIL)
        user_services.update_email_preferences(
            self.user_c_id, True, True, True, True)
        self.signup(self.USER_D_EMAIL, self.USER_D_USERNAME)
        self.user_d_id = self.get_user_id_from_email(self.USER_D_EMAIL)
        user_services.update_email_preferences(
            self.user_d_id, True, True, True, True)
        self.signup(self.USER_E_EMAIL, self.USER_E_USERNAME)
        self.user_e_id = self.get_user_id_from_email(self.USER_E_EMAIL)
        user_services.update_email_preferences(
            self.user_e_id, True, True, True, True)
        self.signup(self.USER_F_EMAIL, self.USER_F_USERNAME)
        self.user_f_id = self.get_user_id_from_email(self.USER_F_EMAIL)
        user_services.update_email_preferences(
            self.user_f_id, False, True, True, True)
        self.signup(self.USER_SUBMITTER_EMAIL, self.USER_SUBMITTER_USERNAME)
        self.submitter_id = self.get_user_id_from_email(
            self.USER_SUBMITTER_EMAIL)
        user_services.update_email_preferences(
            self.submitter_id, True, True, True, True)

        self.save_new_valid_exploration(
            self.EXP_ID_1, self.user_b_id, end_state_name='End')

        exp_services.update_exploration(
            self.user_c_id, self.EXP_ID_1, [exp_domain.ExplorationChange({
                'cmd': 'edit_exploration_property',
                'property_name': 'objective',
                'new_value': 'the objective'
            })], 'Test edit')

        self.save_new_valid_exploration(
            self.EXP_ID_2, self.user_d_id, end_state_name='End')

        exp_services.update_exploration(
            self.user_d_id, self.EXP_ID_2, [exp_domain.ExplorationChange({
                'cmd': 'edit_exploration_property',
                'property_name': 'objective',
                'new_value': 'the objective'
            })], 'Test edit')
        user_d_settings = user_services.get_user_settings(self.user_d_id)
        user_d_settings.last_edited_an_exploration = (
            datetime.datetime.utcnow() - datetime.timedelta(days=2))

        self.save_new_valid_exploration(
            self.EXP_ID_3, self.user_e_id, end_state_name='End')
        user_e_settings = user_services.get_user_settings(self.user_e_id)
        user_e_settings.last_created_an_exploration = (
            user_e_settings.last_created_an_exploration -
            datetime.timedelta(days=10))
        # Last edited time also changes when user creates an exploration.
        user_e_settings.last_edited_an_exploration = (
            datetime.datetime.utcnow() - datetime.timedelta(days=10))
        user_services.update_last_logged_in(
            user_e_settings,
            user_e_settings.last_logged_in - datetime.timedelta(days=10))

        self.save_new_valid_exploration(
            self.EXP_ID_4, self.user_f_id, end_state_name='End')

        user_a_settings = user_services.get_user_settings(self.user_a_id)
        user_services.update_last_logged_in(
            user_a_settings,
            user_a_settings.last_logged_in - datetime.timedelta(days=3))

        # Set tmpsuperadm1n as admin in ADMIN_USERNAMES config property.
        self.set_admins(['tmpsuperadm1n'])

    def test_predicate_functions(self):
        predicates = constants.EMAIL_DASHBOARD_PREDICATE_DEFINITION
        job_class = user_query_jobs_one_off.UserQueryOneOffJob
        for predicate in predicates:
            predicate_function = getattr(
                job_class, '_is_%s_query_satisfied' % predicate['backend_id'])
            self.assertIsNotNone(predicate_function)
