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

"""Environment setup for scripts that require the Cloud Datastore Emulator."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import logging
import os
import re
import subprocess
import time

import contextlib2
import feconf
import psutil
import python_utils

from scripts import common # isort:skip  pylint: disable=wrong-import-position, wrong-import-order


def _terminate_proc_tree(pid):
    """Recursively terminate the given process and its children by ID.

    If terminating takes too long, the processes will be forcibly killed.

    Args:
        pid: int. The process ID of the root process.
    """
    root_proc = psutil.Process(pid)

    child_procs = root_proc.children(recursive=True)
    for proc in child_procs:
        proc.terminate()

    _, still_alive = psutil.wait_procs(child_procs, timeout=5)
    for proc in still_alive:
        proc.kill()

    try:
        root_proc.terminate()
        root_proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        root_proc.kill()


def _set_up_datastore_environ(exports):
    """Configures the environment to interact with the Cloud Datastore."""
    os.environ['DATASTORE_USE_PROJECT_ID_AS_APP_ID'] = 'true'
    for match in re.finditer(r'export (\w*)=(.*)', exports):
        os.environ[match.group(1)] = match.group(2)


def _tear_down_datastore_environ(unsets):
    """Removes configurations made by the set up function."""
    del os.environ['DATASTORE_USE_PROJECT_ID_AS_APP_ID']
    for match in re.finditer(r'unset (\w*)', unsets):
        del os.environ[match.group(1)]


def emulator_context():
    """Returns a context manager that sets up and tears down a datastore
    emulator.

    Returns:
        contextlib2.ExitStack. A context manager with necessary clean-up pushed
        onto it.
    """
    with contextlib2.ExitStack() as stack:
        devnull = stack.enter_context(python_utils.open_file(os.devnull, 'w'))

        datastore_emulator_hostport = '%s:%d' % (
            feconf.DATASTORE_EMULATOR_HOST, feconf.DATASTORE_EMULATOR_PORT)
        proc = subprocess.Popen(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'start',
             '--project', feconf.OPPIA_PROJECT_ID,
             '--host-port', datastore_emulator_hostport,
             '--no-store-on-disk', '--consistency=1.0'])
        stack.callback(lambda: _terminate_proc_tree(proc.pid))

        common.wait_for_port_to_be_open(feconf.DATASTORE_EMULATOR_PORT)

        exports = subprocess.check_output(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-init'])
        unsets = subprocess.check_output(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-unset'])

        _set_up_datastore_environ(exports)
        stack.callback(lambda: _tear_down_datastore_environ(unsets))

        return stack.pop_all()
