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

"""One-off jobs for explorations."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import ast
import datetime
import logging
import re

from constants import constants
from core import jobs
from core.domain import exp_domain
from core.domain import exp_fetchers
from core.domain import exp_services
from core.domain import fs_domain
from core.domain import html_validation_service
from core.domain import rights_domain
from core.domain import rights_manager
from core.platform import models
import feconf
import python_utils
import utils

(
    base_models,
    exp_models,
    feedback_models,
    improvements_models,
    skill_models,
    stats_models,
    story_models,
) = models.Registry.import_models([
    models.NAMES.base_model,
    models.NAMES.exploration,
    models.NAMES.feedback,
    models.NAMES.improvements,
    models.NAMES.skill,
    models.NAMES.statistics,
    models.NAMES.story,
])


class ExplorationValidityJobManager(jobs.BaseMapReduceOneOffJobManager):
    """Job that checks that all explorations have appropriate validation
    statuses.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @staticmethod
    def map(item):
        if item.deleted:
            return

        exploration = exp_fetchers.get_exploration_from_model(item)
        exp_rights = rights_manager.get_exploration_rights(item.id)

        try:
            if exp_rights.status == rights_domain.ACTIVITY_STATUS_PRIVATE:
                exploration.validate()
            else:
                exploration.validate(strict=True)
        except utils.ValidationError as e:
            yield (item.id, python_utils.convert_to_bytes(e))

    @staticmethod
    def reduce(key, values):
        yield (key, values)


class ExplorationMigrationAuditJob(jobs.BaseMapReduceOneOffJobManager):
    """A reusable one-off job for testing exploration migration from any
    exploration schema version to the latest. This job runs the state
    migration, but does not commit the new exploration to the store.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @classmethod
    def enqueue(cls, job_id, additional_job_params=None):
        super(ExplorationMigrationAuditJob, cls).enqueue(
            job_id, shard_count=64)

    @staticmethod
    def map(item):
        if item.deleted:
            return

        current_state_schema_version = feconf.CURRENT_STATE_SCHEMA_VERSION

        states_schema_version = item.states_schema_version
        versioned_exploration_states = {
            'states_schema_version': states_schema_version,
            'states': item.states
        }
        while states_schema_version < current_state_schema_version:
            try:
                exp_domain.Exploration.update_states_from_model(
                    versioned_exploration_states,
                    states_schema_version,
                    item.id)
                states_schema_version += 1
            except Exception as e:
                error_message = (
                    'Exploration %s failed migration to states v%s: %s' %
                    (item.id, states_schema_version + 1, e))
                logging.exception(error_message)
                yield ('MIGRATION_ERROR', error_message.encode('utf-8'))
                break

            if states_schema_version == current_state_schema_version:
                yield ('SUCCESS', 1)

    @staticmethod
    def reduce(key, values):
        if key == 'SUCCESS':
            yield (key, len(values))
        else:
            yield (key, values)


class ExplorationMigrationJobManager(jobs.BaseMapReduceOneOffJobManager):
    """A reusable one-time job that may be used to migrate exploration schema
    versions. This job will load all existing explorations from the data store
    and immediately store them back into the data store. The loading process of
    an exploration in exp_services automatically performs schema updating. This
    job persists that conversion work, keeping explorations up-to-date and
    improving the load time of new explorations.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @classmethod
    def enqueue(cls, job_id, additional_job_params=None):
        super(ExplorationMigrationJobManager, cls).enqueue(
            job_id, shard_count=64)

    @staticmethod
    def map(item):
        if item.deleted:
            return

        # Do not upgrade explorations that fail non-strict validation.
        old_exploration = exp_fetchers.get_exploration_by_id(item.id)
        try:
            old_exploration.validate()
        except Exception as e:
            logging.error(
                'Exploration %s failed non-strict validation: %s' %
                (item.id, e))
            return

        # If the exploration model being stored in the datastore is not the
        # most up-to-date states schema version, then update it.
        if (item.states_schema_version !=
                feconf.CURRENT_STATE_SCHEMA_VERSION):
            # Note: update_exploration does not need to apply a change list in
            # order to perform a migration. See the related comment in
            # exp_services.apply_change_list for more information.
            #
            # Note: from_version and to_version really should be int, but left
            # as str to conform with legacy data.
            commit_cmds = [exp_domain.ExplorationChange({
                'cmd': exp_domain.CMD_MIGRATE_STATES_SCHEMA_TO_LATEST_VERSION,
                'from_version': python_utils.UNICODE(
                    item.states_schema_version),
                'to_version': python_utils.UNICODE(
                    feconf.CURRENT_STATE_SCHEMA_VERSION)
            })]
            exp_services.update_exploration(
                feconf.MIGRATION_BOT_USERNAME, item.id, commit_cmds,
                'Update exploration states from schema version %d to %d.' % (
                    item.states_schema_version,
                    feconf.CURRENT_STATE_SCHEMA_VERSION))
            yield ('SUCCESS', item.id)

    @staticmethod
    def reduce(key, values):
        yield (key, len(values))


class ExplorationRteMathContentValidationOneOffJob(
        jobs.BaseMapReduceOneOffJobManager):
    """Job that checks the html content of an exploration and validates the
    Math content object for each math rich-text components.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @staticmethod
    def map(item):
        if item.deleted:
            return

        exploration = exp_fetchers.get_exploration_from_model(item)
        invalid_tags_info_in_exp = []
        for state_name, state in exploration.states.items():
            html_string = ''.join(state.get_all_html_content_strings())
            error_list = (
                html_validation_service.
                validate_math_content_attribute_in_html(html_string))
            if len(error_list) > 0:
                invalid_tags_info_in_state = {
                    'state_name': state_name,
                    'error_list': error_list,
                    'no_of_invalid_tags': len(error_list)
                }
                invalid_tags_info_in_exp.append(invalid_tags_info_in_state)
        if len(invalid_tags_info_in_exp) > 0:
            yield ('Found invalid tags', (item.id, invalid_tags_info_in_exp))

    @staticmethod
    def reduce(key, values):
        final_values = [ast.literal_eval(value) for value in values]
        no_of_invalid_tags = 0
        invalid_tags_info = {}
        for exp_id, invalid_tags_info_in_exp in final_values:
            invalid_tags_info[exp_id] = []
            for value in invalid_tags_info_in_exp:
                no_of_invalid_tags += value['no_of_invalid_tags']
                del value['no_of_invalid_tags']
                invalid_tags_info[exp_id].append(value)

        final_value_dict = {
            'no_of_explorations_with_no_svgs': len(final_values),
            'no_of_invalid_tags': no_of_invalid_tags,
        }
        yield ('Overall result.', final_value_dict)
        yield ('Detailed information on invalid tags.', invalid_tags_info)


class ViewableExplorationsAuditJob(jobs.BaseMapReduceOneOffJobManager):
    """Job that outputs a list of private explorations which are viewable."""

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @staticmethod
    def map(item):
        if item.deleted:
            return

        exploration_rights = rights_manager.get_exploration_rights(
            item.id, strict=False)
        if exploration_rights is None:
            return

        if (exploration_rights.status == constants.ACTIVITY_STATUS_PRIVATE
                and exploration_rights.viewable_if_private):
            yield (item.id, item.title.encode('utf-8'))

    @staticmethod
    def reduce(key, values):
        yield (key, values)


class RTECustomizationArgsValidationOneOffJob(
        jobs.BaseMapReduceOneOffJobManager):
    """One-off job for validating all the customizations arguments of
    Rich Text Components.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @staticmethod
    def map(item):
        if item.deleted:
            return
        err_dict = {}

        try:
            exploration = exp_fetchers.get_exploration_from_model(item)
        except Exception as e:
            yield (
                'Error %s when loading exploration'
                % python_utils.UNICODE(e), [item.id])
            return

        html_list = exploration.get_all_html_content_strings()
        err_dict = html_validation_service.validate_customization_args(
            html_list)
        for key in err_dict:
            err_value_with_exp_id = err_dict[key]
            err_value_with_exp_id.append('Exp ID: %s' % item.id)
            yield (key, err_value_with_exp_id)

    @staticmethod
    def reduce(key, values):
        final_values = [ast.literal_eval(value) for value in values]
        flattened_values = [
            item for sublist in final_values for item in sublist]

        # Errors produced while loading exploration only contain exploration id
        # in error message, so no further formatting is required. For errors
        # from validation the output is in format [err1, expid1, err2, expid2].
        # So, we further format it as [(expid1, err1), (expid2, err2)].
        if 'loading exploration' in key:
            yield (key, flattened_values)
            return

        output_values = []
        index = 0
        while index < len(flattened_values):
            # flattened_values[index] = error message.
            # flattened_values[index + 1] = exp id in which error message
            # is present.
            output_values.append((
                flattened_values[index + 1], flattened_values[index]))
            index += 2
        output_values.sort()
        yield (key, output_values)


def regenerate_exp_commit_log_model(exp_model, version):
    """Helper function to regenerate a commit log model for an
    exploration model.

    NOTE TO DEVELOPERS: Do not delete this function until issue #10808 is fixed.

    Args:
        exp_model: ExplorationModel. The exploration model for which
            commit log model is to be generated.
        version: int. The commit log version to be generated.

    Returns:
        ExplorationCommitLogEntryModel. The regenerated commit log model.
    """
    metadata_model = (
        exp_models.ExplorationSnapshotMetadataModel.get_by_id(
            '%s-%s' % (exp_model.id, version)))

    required_rights_model = exp_models.ExplorationRightsModel.get(
        exp_model.id, strict=True, version=1)
    for rights_version in python_utils.RANGE(2, version + 1):
        rights_model = exp_models.ExplorationRightsModel.get(
            exp_model.id, strict=False, version=rights_version)
        if rights_model is None:
            break
        if rights_model.created_on <= metadata_model.created_on:
            required_rights_model = rights_model
        else:
            break
    commit_log_model = (
        exp_models.ExplorationCommitLogEntryModel.create(
            exp_model.id, version, metadata_model.committer_id,
            metadata_model.commit_type,
            metadata_model.commit_message,
            metadata_model.commit_cmds,
            required_rights_model.status,
            required_rights_model.community_owned))
    commit_log_model.exploration_id = exp_model.id
    commit_log_model.created_on = metadata_model.created_on
    commit_log_model.last_updated = metadata_model.last_updated
    return commit_log_model


class RegenerateMissingExpCommitLogModels(jobs.BaseMapReduceOneOffJobManager):
    """Job that regenerates missing commit log models for an exploration.

    NOTE TO DEVELOPERS: Do not delete this job until issue #10808 is fixed.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @staticmethod
    def map(item):
        if item.deleted:
            return

        for version in python_utils.RANGE(1, item.version + 1):
            commit_log_model = (
                exp_models.ExplorationCommitLogEntryModel.get_by_id(
                    'exploration-%s-%s' % (item.id, version)))
            if commit_log_model is None:
                commit_log_model = regenerate_exp_commit_log_model(
                    item, version)
                commit_log_model.update_timestamps(
                    update_last_updated_time=False)
                commit_log_model.put()
                yield (
                    'Regenerated Exploration Commit Log Model: version %s' % (
                        version), item.id)

    @staticmethod
    def reduce(key, values):
        yield (key, values)


class ExpCommitLogModelRegenerationValidator(
        jobs.BaseMapReduceOneOffJobManager):
    """Job that validates the process of regeneration of commit log
    models for an exploration.

    NOTE TO DEVELOPERS: Do not delete this job until issue #10808 is fixed.
    """

    @classmethod
    def entity_classes_to_map_over(cls):
        return [exp_models.ExplorationModel]

    @staticmethod
    def map(item):
        if item.deleted:
            return

        # This is done to ensure that all explorations are not checked and
        # a random sample of the explorations is checked.
        last_char_in_id = item.id[-1]
        if last_char_in_id < 'a' or last_char_in_id > 'j':
            return

        for version in python_utils.RANGE(1, item.version + 1):
            commit_log_model = (
                exp_models.ExplorationCommitLogEntryModel.get_by_id(
                    'exploration-%s-%s' % (item.id, version)))
            if commit_log_model is None:
                continue
            regenerated_commit_log_model = regenerate_exp_commit_log_model(
                item, version)

            fields = [
                'user_id', 'commit_type', 'commit_message', 'commit_cmds',
                'version', 'post_commit_status', 'post_commit_community_owned',
                'post_commit_is_private', 'exploration_id'
            ]

            for field in fields:
                commit_model_field_val = getattr(commit_log_model, field)
                regenerated_commit_log_model_field_val = getattr(
                    regenerated_commit_log_model, field)
                if commit_model_field_val != (
                        regenerated_commit_log_model_field_val):
                    yield (
                        'Mismatch between original model and regenerated model',
                        '%s in original model: %s, in regenerated model: %s' % (
                            field, commit_model_field_val,
                            regenerated_commit_log_model_field_val))

            time_fields = ['created_on', 'last_updated']
            for field in time_fields:
                commit_model_field_val = getattr(commit_log_model, field)
                regenerated_commit_log_model_field_val = getattr(
                    regenerated_commit_log_model, field)
                max_allowed_val = regenerated_commit_log_model_field_val + (
                    datetime.timedelta(minutes=1))
                min_allowed_val = regenerated_commit_log_model_field_val - (
                    datetime.timedelta(minutes=1))
                if commit_model_field_val > max_allowed_val or (
                        commit_model_field_val < min_allowed_val):
                    yield (
                        'Mismatch between original model and regenerated model',
                        '%s in original model: %s, in regenerated model: %s' % (
                            field, commit_model_field_val,
                            regenerated_commit_log_model_field_val))

    @staticmethod
    def reduce(key, values):
        yield (key, values)
