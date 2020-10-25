# Copyright 2020 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS-IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helpers for maintaining the Google Cloud Datastore Emulator."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import os
import re
import subprocess

import contextlib2
import feconf
import psutil

from scripts import common # isort:skip  pylint: disable=wrong-import-position, wrong-import-order


def emulator_context():
    """Manages the Google Cloud Datastore Emulator within a context.

    Returns:
        contextlib2.ExitStack. An ExitStack with tear-down operations pushed on.
    """
    if not os.path.exists(common.DATASTORE_EMULATOR_DATA_DIR):
        os.makedirs(common.DATASTORE_EMULATOR_DATA_DIR)

    with contextlib2.ExitStack() as exit_stack:
        devnull = exit_stack.enter_context(open(os.devnull, 'w'))

        emulator_host_port = '%s:%d' % (
            feconf.DATASTORE_EMULATOR_HOST, feconf.DATASTORE_EMULATOR_PORT)
        emulator_process = subprocess.Popen(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'start',
             '--data-dir', common.DATASTORE_EMULATOR_DATA_DIR,
             '--project', feconf.OPPIA_PROJECT_ID,
             '--host-port', emulator_host_port,
             '--no-store-on-disk', '--consistency=1.0', '--quiet'],
            stdout=devnull, stderr=devnull)

        @exit_stack.callback
        def tear_down_emulator_process(): # pylint: disable=unused-variable
            """Tears down the emulator process and all of its children."""
            root_process = psutil.Process(emulator_process.pid)
            child_processes = root_process.children(recursive=True)
            for process in child_processes:
                process.terminate()

            _, still_alive = psutil.wait_procs(child_processes, timeout=5)
            for process in still_alive:
                process.kill()

            try:
                root_process.terminate()
                root_process.wait(timeout=5)
            except psutil.TimeoutExpired:
                root_process.kill()

        common.wait_for_port_to_be_open(feconf.DATASTORE_EMULATOR_PORT)

        exports = subprocess.check_output(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-init',
             '--data-dir', common.DATASTORE_EMULATOR_DATA_DIR, '--quiet'])
        emulator_environ = {'DATASTORE_USE_PROJECT_ID_AS_APP_ID': 'true'}
        emulator_environ.update(
            m.group(1, 2) for m in re.finditer(r'export (\w*)=(.*)', exports))
        os.environ.update(emulator_environ)

        @exit_stack.callback
        def tear_down_emulator_environ(): # pylint: disable=unused-variable
            """Tears down the emulator-specific environment variables."""
            for var_name in emulator_environ:
                del os.environ[var_name]

        return exit_stack.pop_all()
