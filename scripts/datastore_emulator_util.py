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

import os
import re
import subprocess

import contextlib2
import feconf
import psutil
import python_utils

from scripts import common # isort:skip  pylint: disable=wrong-import-position, wrong-import-order


def _terminate_proc_tree(root_proc):
    """Recursively terminate the given process and its children.

    If terminating takes too long, the processes will be forcibly killed.

    Args:
        root_proc: psutil.Process. The root process.
    """
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


def _set_up_emulator_environ():
    """Sets up emulator-specific configuration in os.environ."""
    exports = subprocess.check_output(
        [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-init'])
    for match in re.finditer(r'export (\w*)=(.*)', exports):
        os.environ[match.group(1)] = match.group(2)
    os.environ['DATASTORE_USE_PROJECT_ID_AS_APP_ID'] = 'true'


def _tear_down_emulator_environ():
    """Tears down emulator-specific configuration in os.environ."""
    unsets = subprocess.check_output(
        [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-unset'])
    for match in re.finditer(r'unset (\w*)', unsets):
        del os.environ[match.group(1)]
    del os.environ['DATASTORE_USE_PROJECT_ID_AS_APP_ID']


def emulator_context():
    """Returns a context manager that sets up and tears down a datastore
    emulator.

    Returns:
        contextlib2.ExitStack. A context manager with necessary clean-up pushed
        onto it.
    """
    with contextlib2.ExitStack() as stack:
        devnull = stack.enter_context(python_utils.open_file(os.devnull, 'w'))

        datastore_emulator_host_port = '%s:%d' % (
            feconf.DATASTORE_EMULATOR_HOST, feconf.DATASTORE_EMULATOR_PORT)
        proc = subprocess.Popen(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'start',
             '--project', feconf.OPPIA_PROJECT_ID,
             '--host-port', datastore_emulator_host_port,
             '--no-store-on-disk', '--consistency=1.0', '--quiet'],
            stdout=devnull, stderr=devnull)
        stack.callback(lambda: _terminate_proc_tree(psutil.Process(proc.pid)))

        common.wait_for_port_to_be_open(feconf.DATASTORE_EMULATOR_PORT)

        _set_up_emulator_environ()
        stack.callback(_tear_down_emulator_environ)

        return stack.pop_all()
