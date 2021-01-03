# coding: utf-8
#
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

"""Service layer for handling user-authentication with GAE's built-in system."""

from core.domain import auth_domain

from google.appengine.api import users


def authenticate_request(unused_request):
    """Returns Claims for the user currently signed-in and sending requests."""
    gae_user = users.get_current_user()
    if gae_user is not None:
        return auth_domain.AuthClaims(gae_user.user_id(), gae_user.email())
    return None


def delete_auth_associations(user_id):
    """Deletes associations referring to the given user_id."""
    pass


def are_auth_associations_deleted(user_id):
    """Returns whether the Firebase account of the given user ID is deleted."""
    return True


def get_user_id_from_auth_id(auth_id):
    """Returns the user ID associated with the given auth ID."""
    return None


def get_multi_user_ids_from_auth_ids(auth_ids):
    """Returns the user IDs associated with the given auth IDs."""
    return [None for _ in auth_ids]


def associate_auth_id_to_user_id(auth_id_user_id_pair):
    """Commits the association between auth ID and user ID."""
    pass


def associate_multi_auth_ids_to_user_ids(auth_id_user_id_pairs):
    """Commits the associations between auth IDs and user IDs."""
    pass
