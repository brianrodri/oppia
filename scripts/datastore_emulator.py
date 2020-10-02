import logging
import os
import contextlib
import contextlib2
import subprocess

import psutil
import shutil
import tempfile
import common
import time

import python_utils

def _terminate_proc_tree(pid):
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)

    for child in children:
        child.terminate()
    gone, still_alive = psutil.wait_procs(children, timeout=5)
    for child in still_alive:
        child.kill()
    num_terminated, num_killed = len(gone), len(still_alive)

    parent.terminate()
    try:
        parent.wait(5)
        num_terminated += 1
    except psutil.TimeoutExpired:
        parent.kill()
        num_killed += 1

    if num_terminated:
        logging.info('Successfully terminated %d processes' % num_terminated)
    if num_killed:
        logging.warn('Forced to kill %d processes' % num_killed)


def _set_up_datastore_environ(export_cmds):
    for export_cmd in export_cmds:
        if export_cmd.startswith(b'export '):
            var, val = export_cmd[7:].split(b'=')
            os.environ[var.strip()] = val.strip()
            logging.info(export_cmd)


def _tear_down_datastore_environ(unset_cmds):
    for unset_cmd in unset_cmds:
        if unset_cmd.startswith(b'unset '):
            var = unset_cmd[6:].strip()
            del os.environ[var]
            logging.info(unset_cmd)


def datastore_emulator_context():
    with contextlib2.ExitStack() as stack:
        proc = subprocess.Popen(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'start',
             '--project=oppia-dev'])
        stack.callback(lambda: _terminate_proc_tree(proc.pid))

        while not common.is_port_open(8081):
            time.sleep(1)

        env_sets = subprocess.check_output(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-init'])
        env_unsets = subprocess.check_output(
            [common.GCLOUD_PATH, 'beta', 'emulators', 'datastore', 'env-unset'])

        _set_up_datastore_environ(env_sets.split(b'\n'))
        stack.callback(
            lambda: _tear_down_datastore_environ(env_unsets.split(b'\n')))

        return stack.pop_all()
