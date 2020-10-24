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


def _get_emulator_environ():
    """Returns a dict of environment variables the datastore emulator needs."""
    export_cmds = subprocess.check_output(
        [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-init'])
    emulator_environ = {'DATASTORE_USE_PROJECT_ID_AS_APP_ID': 'true'}
    emulator_environ.update(
        m.group(1, 2) for m in re.finditer(r'export (\w*)=(.*)', export_cmds))
    return emulator_environ


def emulator_context(silent=True):
    """Returns a context manager that sets up and tears down a datastore
    emulator.

    Args:
        silent: bool. Whether the emulator should have its output printed.

    Returns:
        contextlib2.ExitStack. A context manager with necessary clean-up pushed
        onto it.
    """
    with contextlib2.ExitStack() as stack:
        if silent:
            stdout = stderr = stack.enter_context(open(os.devnull, 'w'))
        else:
            stdout, stderr = subprocess.STDOUT, subprocess.STDERR

        emulator_host_port = '%s:%d' % (
            feconf.DATASTORE_EMULATOR_HOST, feconf.DATASTORE_EMULATOR_PORT)
        emulator_proc = subprocess.Popen(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'start',
             '--project', feconf.OPPIA_PROJECT_ID,
             '--host-port', emulator_host_port,
             '--consistency=1.0', '--no-store-on-disk', '--quiet'],
            stdout=stdout, stderr=stderr)

        @stack.callback
        def tear_down_emulator_proc(): # pylint: disable=unused-var
            """Tears down the emulator process and all of its children."""
            root_proc = psutil.Process(emulator_proc.pid)
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

        emulator_environ = _get_emulator_environ()
        os.environ.update(emulator_environ)

        @stack.callback
        def tear_down_emulator_environ(): # pylint: disable=unused-var
            """Tears down the emulator-specific environment variables."""
            for var_name in emulator_environ:
                del os.environ[var_name]

        common.wait_for_port_to_be_open(
            feconf.DATASTORE_EMULATOR_PORT, timeout_secs=10)

        return stack.pop_all()
