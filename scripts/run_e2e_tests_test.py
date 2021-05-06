# -*- coding: UTF-8 -*-
# Copyright 2019 The Oppia Authors. All Rights Reserved.
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

"""Unit tests for scripts/run_e2e_tests.py."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import os
import signal
import subprocess
import sys
import time

from core.tests import test_utils
import python_utils

from scripts import build
from scripts import common
from scripts import flake_checker
from scripts import install_third_party_libs
from scripts import run_e2e_tests

import contextlib2
import psutil


CHROME_DRIVER_VERSION = '77.0.3865.40'


class MockProcessClass(python_utils.OBJECT):
    """Mocks a process to make unit testing less expensive.

    Attributes:
        pid: int. The ID of the process.
        pname: str. The name of the process.
        return_code: int. The return code of the process.
        poll_count: int. The number of times poll() has been called.
        signals_received: list(int). List of received signals (as ints) in order
            of receipt.
        kill_count: int. Number of times kill() has been called.
        alive: bool. Whether the process should be considered to be alive.
        clean_shutdown: bool. Whether to shut down when signal.SIGINT signal is
            received.
        stdout: str. The text written to standard output by the process.
        stdout: str. The text written to standard error output by the process.
        accept_signal: bool. Whether to raise OSError in send_signal().
        accept_terminate: bool. Whether to raise OSError in terminate().
        accept_kill: bool. Whether to raise OSError in kill().
        child_procs: list(MockProcessClass). Child processes (processes spawned
            by self).
    """

    def __init__(
            self, pid=1, name='process', stdout='', stderr='', return_code=0,
            accept_signal=True, accept_terminate=True, accept_kill=True,
            clean_shutdown=True):
        """Create a mock process object.

        Args:
            pid: int. The ID of the process.
            name: str. The name of the process.
            stdout: str. The text written to standard output by the process.
            stderr: str. The text written to standard error output by the
                process.
            return_code: int. The return code of the process.
            accept_signal: bool. Whether to raise OSError in send_signal().
            accept_terminate: bool. Whether to raise OSError in terminate().
            accept_kill: bool. Whether to raise OSError in kill().
            clean_shutdown: bool. Whether to shut down when SIGINT received.
        """
        self.pid = pid
        self.pname = name
        self.return_code = return_code
        self.poll_count = 0
        self.signals_received = []
        self.terminate_count = 0
        self.kill_count = 0
        self.alive = True
        self.clean_shutdown = clean_shutdown
        self.accept_signal = accept_signal
        self.accept_terminate = accept_terminate
        self.accept_kill = accept_kill
        self.child_procs = []

        self.stdout = python_utils.string_io(buffer_value=stdout)
        self.stderr = python_utils.string_io(buffer_value=stderr)

    @property
    def returncode(self):
        """Returns the return code of the process.

        Returns:
            int. The return code of the process.
        """
        return self.return_code

    def name(self):
        """Returns the name of the process.

        Returns:
            str. The name of the process.
        """
        return self.pname

    def children(self, recursive=False):
        """Returns the children spawned by this process.

        Args:
            recursive: bool. Whether to also return non-direct decendants from
                self (i.e. children of children).

        Returns:
            list(MockProcessClass). A list of the child processes.
        """
        children = []
        for child in self.child_procs:
            children.append(child)
            if recursive:
                children.extend(child.children(recursive=True))
        return children

    def terminate(self):
        """Increment terminate_count.

        Mocks the process being terminated.
        """
        self.terminate_count += 1
        if not self.accept_terminate:
            raise OSError()

    def kill(self):
        """Increment kill_count.

        Mocks the process being killed.
        """
        self.kill_count += 1
        if not self.accept_kill:
            raise OSError()

    def is_running(self):
        """Returns whether the process is running.

        Returns:
            bool. The value of self.alive, which mocks whether the process is
            still alive.
        """
        return self.alive

    def poll(self):
        """Increment poll_count.

        Mocks checking whether the process is still alive.

        Returns:
            bool. The value of self.alive, which mocks whether the process is
            still alive.
        """
        self.poll_count += 1
        return None if self.alive else self.return_code

    def send_signal(self, signal_number):
        """Append signal to self.signals_received.

        Mocks receiving a process signal. If a SIGINT signal is received (e.g.
        from ctrl-C) and self.clean_shutdown is True, then we set self.alive to
        False to mimic the process shutting down.

        Args:
            signal_number: int. The number of the received signal.
        """
        self.signals_received.append(signal_number)
        if not self.accept_signal:
            raise OSError()
        if signal_number == signal.SIGINT and self.clean_shutdown:
            self.alive = False

    def wait(self, timeout=0): # pylint: disable=unused-argument
        """Wait for the process completion.

        Mocks the process waiting for completion before it continues execution.

        Args:
            timeout: int. Unused because wait() returns immediately.
        """
        return

    def communicate(self, input=None): # pylint: disable=unused-argument, redefined-builtin
        """Mocks interaction with the process.

        Args:
            input: str|None. Unused because the process isn't real.

        Returns:
            tuple(str, str). The stdout and stderr of the process, respectively.
        """
        return self.stdout.getvalue(), self.stderr.getvalue()


class RunE2ETestsTests(test_utils.GenericTestBase):
    """Test the run_e2e_tests methods."""

    def setUp(self):
        super(RunE2ETestsTests, self).setUp()

        self.exit_stack = contextlib2.ExitStack()

        def mock_run_cmd(unused_commands):
            pass

        self.mock_run_cmd = mock_run_cmd

        def mock_build_main(args):  # pylint: disable=unused-argument
            pass

        self.mock_build_main = mock_build_main

        def mock_managed_process(*unused_args, **unused_kwargs):
            """Mock method for replacing the managed_process() functions.

            Args:
                *unused_args: tuple(*). Unused arguments.
                **unused_kwargs: dict(str: *). Unused keyword arguments.

            Returns:
                Context manager. A context manager that always yields a mock
                process.
            """
            return contextlib2.nullcontext(enter_result=self.mock_process)

        self.mock_process = MockProcessClass()
        self.mock_managed_process = mock_managed_process

    def tearDown(self):
        try:
            self.exit_stack.close()
        finally:
            super(RunE2ETestsTests, self).tearDown()

    def test_is_oppia_server_already_running_when_ports_closed(self):
        self.exit_stack.enter_context(self.swap_to_always_return(
            common, 'is_port_in_use', value=False))

        self.assertFalse(run_e2e_tests.is_oppia_server_already_running())

    def test_is_oppia_server_already_running_when_a_port_is_open(self):
        running_port = run_e2e_tests.GOOGLE_APP_ENGINE_PORT
        def mock_is_port_in_use(port):
            if port == running_port:
                return True
            return False

        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'is_port_in_use', mock_is_port_in_use))

        self.assertTrue(run_e2e_tests.is_oppia_server_already_running())

    def test_wait_for_port_to_be_in_use_when_port_successfully_opened(self):
        def mock_is_port_in_use(unused_port):
            mock_is_port_in_use.wait_time += 1
            if mock_is_port_in_use.wait_time > 10:
                return True
            return False
        mock_is_port_in_use.wait_time = 0

        def mock_sleep(unused_time):
            mock_sleep.called_times += 1
            return
        mock_sleep.called_times = 0

        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'is_port_in_use', mock_is_port_in_use))
        self.exit_stack.enter_context(
            self.swap_with_checks(time, 'sleep', mock_sleep))

        common.wait_for_port_to_be_in_use(1)

        self.assertEqual(mock_is_port_in_use.wait_time, 11)
        self.assertEqual(mock_sleep.called_times, 10)

    def test_wait_for_port_to_be_in_use_when_port_failed_to_open(self):
        def mock_is_port_in_use(unused_port):
            return False

        def mock_sleep(unused_time):
            mock_sleep.sleep_time += 1

        def mock_exit(unused_exit_code):
            return

        mock_sleep.sleep_time = 0

        self.exit_stack.enter_context(self.swap(
            common, 'is_port_in_use', mock_is_port_in_use))
        self.exit_stack.enter_context(
            self.swap_with_checks(time, 'sleep', mock_sleep))
        self.exit_stack.enter_context(
            self.swap_with_checks(sys, 'exit', mock_exit))

        common.wait_for_port_to_be_in_use(1)

        self.assertEqual(
            mock_sleep.sleep_time,
            common.MAX_WAIT_TIME_FOR_PORT_TO_OPEN_SECS)

    def test_run_webpack_compilation_success(self):
        # The webpack compilation processes will be called 4 times as mock_isdir
        # will return true after 4 calls.
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webpack_compiler',
            self.mock_managed_process))

        run_e2e_tests.run_webpack_compilation()

    def test_get_chrome_driver_version(self):
        def mock_os_popen(unused_arg, shell=False): # pylint: disable=unused-argument
            class Ret(python_utils.OBJECT):
                """Return object with required attributes."""

                def read(self):
                    """Return required method."""
                    return '77.0.3865'
            return Ret()

        self.exit_stack.enter_context(self.swap(os, 'popen', mock_os_popen))
        def mock_url_open(unused_arg):
            class Ret(python_utils.OBJECT):
                """Return object with required attributes."""

                def read(self):
                    """Return required method."""
                    return CHROME_DRIVER_VERSION
            return Ret()

        self.exit_stack.enter_context(
            self.swap(python_utils, 'url_open', mock_url_open))

        version = run_e2e_tests.get_chrome_driver_version()

        self.assertEqual(version, CHROME_DRIVER_VERSION)

    def test_run_webpack_compilation_failed(self):

        def mock_isdir(unused_port):
            return False

        def mock_exit(unused_exit_code):
            return

        # The webpack compilation processes will be called five times.
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webpack_compiler',
            self.mock_managed_process))

        self.exit_stack.enter_context(self.swap(os.path, 'isdir', mock_isdir))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(1,)]))

        run_e2e_tests.run_webpack_compilation()

    def test_install_third_party_libraries_without_skip(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            install_third_party_libs, 'main', lambda: None))

        run_e2e_tests.install_third_party_libraries(False)

    def test_install_third_party_libraries_with_skip(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            install_third_party_libs, 'main', lambda: None, called=False))

        run_e2e_tests.install_third_party_libraries(True)

    def test_build_js_files_in_dev_mode_with_hash_file_exists(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webpack_compiler', self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'main', self.mock_build_main,
            expected_kwargs=[{'args': []}]))

        run_e2e_tests.build_js_files(True)

    def test_build_js_files_in_dev_mode_with_exception_raised(self):
        def mock_error(**_):
            raise subprocess.CalledProcessError(
                returncode=2, cmd=[], output='ERROR')

        def mock_exit(unused_code):
            pass

        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webpack_compiler', mock_error))
        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'main', self.mock_build_main,
            expected_kwargs=[{'args': []}]))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(2,)]))

        run_e2e_tests.build_js_files(True)

    def test_build_js_files_in_prod_mode(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'run_cmd', self.mock_run_cmd, called=False))

        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'main', self.mock_build_main,
            expected_kwargs=[{'args': ['--prod_env']}]))


        run_e2e_tests.build_js_files(False)

    def test_build_js_files_in_prod_mode_with_deparallelize_terser(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'run_cmd', self.mock_run_cmd, called=False))

        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'main', self.mock_build_main,
            expected_kwargs=[{'args': [
                '--prod_env', '--deparallelize_terser']}]))


        run_e2e_tests.build_js_files(
            False, deparallelize_terser=True)

    def test_build_js_files_in_prod_mode_with_source_maps(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'run_cmd', self.mock_run_cmd, called=False))

        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'main', self.mock_build_main,
            expected_kwargs=[{'args': [
                '--prod_env', '--source_maps']}]))


        run_e2e_tests.build_js_files(
            False, source_maps=True)

    def test_webpack_compilation_in_dev_mode_with_source_maps(self):
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'run_cmd', self.mock_run_cmd, called=False))

        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'main', self.mock_build_main,
            expected_kwargs=[{'args': []}]))

        def mock_run_webpack_compilation(source_maps=False):
            self.assertEqual(source_maps, True)

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'run_webpack_compilation',
            mock_run_webpack_compilation))


        run_e2e_tests.build_js_files(
            True, source_maps=True)

    def test_get_parameter_for_one_sharding_instance(self):
        result = run_e2e_tests.get_parameter_for_sharding(1)
        self.assertEqual([], result)

    def test_get_parameter_for_three_sharding_instances(self):
        result = run_e2e_tests.get_parameter_for_sharding(3)
        self.assertEqual(
            ['--capabilities.shardTestFiles=True',
             '--capabilities.maxInstances=3'], result)

    def test_get_parameter_for_negative_sharding_instances(self):
        with self.assertRaisesRegexp(
            ValueError, 'Sharding instance should be larger than 0'):
            run_e2e_tests.get_parameter_for_sharding(-3)

    def test_get_parameter_for_dev_mode(self):
        result = run_e2e_tests.get_parameter_for_dev_mode(True)
        self.assertEqual(result, '--params.devMode=True')

    def test_get_parameter_for_prod_mode(self):
        result = run_e2e_tests.get_parameter_for_dev_mode(False)
        self.assertEqual(result, '--params.devMode=False')

    def test_get_parameter_for_suite(self):
        result = run_e2e_tests.get_parameter_for_suite('Full')
        self.assertEqual(result, ['--suite', 'Full'])

    def test_get_e2e_test_parameters(self):
        result = run_e2e_tests.get_e2e_test_parameters(3, 'Full', False)
        self.assertEqual(result, [
            run_e2e_tests.PROTRACTOR_CONFIG_FILE_PATH,
            '--capabilities.shardTestFiles=True',
            '--capabilities.maxInstances=3',
            '--suite', 'Full', '--params.devMode=False',
        ])

    def test_start_tests_when_other_instances_not_stopped(self):
        def mock_exit(unused_exit_code):
            raise Exception('sys.exit(1)')
        def mock_is_oppia_server_already_running(*unused_args):
            return True

        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'is_oppia_server_already_running',
            mock_is_oppia_server_already_running))
        self.exit_stack.enter_context(self.swap(sys, 'exit', mock_exit))

        with self.assertRaisesRegexp(Exception, r'sys\.exit\(1\)'):
            run_e2e_tests.main(args=[])

    def test_start_tests_when_no_other_instance_running(self):

        def mock_is_oppia_server_already_running(*unused_args):
            return False

        def mock_install_third_party_libraries(unused_arg):
            return

        def mock_exit(unused_exit_code):
            return

        def mock_build_js_files(
                unused_arg, deparallelize_terser=False, source_maps=False): # pylint: disable=unused-argument
            return

        def mock_get_e2e_test_parameters(
                unused_sharding_instances, unused_suite, unused_dev_mode):
            return ['commands']

        def mock_managed_process(unused_commands, stdout=None, shell=False): # pylint: disable=unused-argument
            return contextlib2.nullcontext(
                enter_result=MockProcessClass(stdout='sample output\n'))

        def mock_get_chrome_driver_version():
            return CHROME_DRIVER_VERSION

        def mock_check_if_on_ci():
            return True

        def mock_report_pass(unused_suite_name):
            return

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'get_chrome_driver_version',
            mock_get_chrome_driver_version))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'is_oppia_server_already_running',
            mock_is_oppia_server_already_running))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'install_third_party_libraries',
            mock_install_third_party_libraries, expected_args=[(False,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'build_js_files', mock_build_js_files,
            expected_args=[(True,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_elasticsearch_dev_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_firebase_auth_emulator',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_dev_appserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_redis_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_portserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webdriver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'get_e2e_test_parameters',
            mock_get_e2e_test_parameters,
            expected_args=[(3, 'full', True)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_process', mock_managed_process, expected_args=[
                (
                    [common.NODE_BIN_PATH, '--unhandled-rejections=strict',
                     run_e2e_tests.PROTRACTOR_BIN_PATH, 'commands'],
                ),
            ]))
        self.exit_stack.enter_context(
            self.swap(flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'report_pass', mock_report_pass,
            expected_args=[('full',)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(0,)]))

        run_e2e_tests.main(args=[])

    def test_work_with_non_ascii_chars(self):

        def mock_is_oppia_server_already_running(*unused_args):
            return False

        def mock_install_third_party_libraries(unused_arg):
            return

        def mock_build_js_files(
                unused_arg, deparallelize_terser=False, source_maps=False): # pylint: disable=unused-argument
            return

        def mock_get_e2e_test_parameters(
                unused_sharding_instances, unused_suite, unused_dev_mode):
            return ['commands']

        def mock_managed_process(unused_commands, stdout=None, shell=False): # pylint: disable=unused-argument
            return contextlib2.nullcontext(
                enter_result=MockProcessClass(stdout='sample\n✓\noutput\n'))

        def mock_get_chrome_driver_version():
            return CHROME_DRIVER_VERSION

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'get_chrome_driver_version',
            mock_get_chrome_driver_version))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'is_oppia_server_already_running',
            mock_is_oppia_server_already_running))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'install_third_party_libraries',
            mock_install_third_party_libraries, expected_args=[(False,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'build_js_files', mock_build_js_files,
            expected_args=[(True,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_elasticsearch_dev_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_firebase_auth_emulator',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_dev_appserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_redis_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webdriver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'get_e2e_test_parameters',
            mock_get_e2e_test_parameters,
            expected_args=[(3, 'full', True)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_process', mock_managed_process, expected_args=[
                (
                    [common.NODE_BIN_PATH, '--unhandled-rejections=strict',
                     run_e2e_tests.PROTRACTOR_BIN_PATH, 'commands'],
                ),
            ]))
        args = run_e2e_tests._PARSER.parse_args(args=[])  # pylint: disable=protected-access

        lines, _ = run_e2e_tests.run_tests(args)

        self.assertEqual(lines, ['sample', u'✓', 'output'])

    def test_rerun_when_tests_fail(self):

        def mock_check_if_on_ci():
            return True

        def mock_exit(unused_exit_code):
            return

        def mock_run_tests(unused_args):
            return 'sample\noutput', 1

        def mock_is_test_output_flaky(
                unused_output, unused_suite_name):
            return False

        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_portserver', self.mock_managed_process))
        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'run_tests', mock_run_tests))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'is_test_output_flaky',
            mock_is_test_output_flaky,
            expected_args=[
                ('sample\noutput', 'mySuite'),
                ('sample\noutput', 'mySuite'),
                ('sample\noutput', 'mySuite'),
            ]))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(1,)]))

        run_e2e_tests.main(args=['--suite', 'mySuite'])

    def test_do_not_rerun_when_tests_fail(self):

        def mock_check_if_on_ci():
            return True

        def mock_exit(unused_exit_code):
            return

        def mock_run_tests(unused_args):
            return 'sample\noutput', 1

        def mock_is_test_output_flaky(
                unused_output, unused_suite_name):
            return False

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'run_tests', mock_run_tests))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'is_test_output_flaky',
            mock_is_test_output_flaky,
            expected_args=[
                ('sample\noutput', 'mySuite')]))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(1,)]))
        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'RERUN_NON_FLAKY', False))

        run_e2e_tests.main(args=['--suite', 'mySuite'])

    def test_rerun_when_tests_flake(self):

        def mock_check_if_on_ci():
            return True

        def mock_exit(unused_exit_code):
            return

        def mock_run_tests(unused_args):
            return 'sample\noutput', 1

        def mock_is_test_output_flaky(
                unused_output, unused_suite_name):
            return True

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'run_tests', mock_run_tests))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'is_test_output_flaky',
            mock_is_test_output_flaky,
            expected_args=[
                ('sample\noutput', 'mySuite'),
                ('sample\noutput', 'mySuite'),
                ('sample\noutput', 'mySuite'),
            ]))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(1,)]))

        run_e2e_tests.main(args=['--suite', 'mySuite'])

    def test_no_reruns_off_ci_fail(self):

        def mock_check_if_on_ci():
            return False

        def mock_exit(unused_exit_code):
            return

        def mock_run_tests(unused_args):
            return 'sample\noutput', 1

        def mock_is_test_output_flaky(
                unused_output, unused_suite_name):
            raise AssertionError('Tried to Check Flakiness.')

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'run_tests', mock_run_tests))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'is_test_output_flaky',
            mock_is_test_output_flaky))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(1,)]))

        run_e2e_tests.main(args=['--suite', 'mySuite'])

    def test_no_reruns_off_ci_pass(self):

        def mock_check_if_on_ci():
            return False

        def mock_exit(unused_exit_code):
            return

        def mock_run_tests(unused_args):
            return 'sample\noutput', 0

        def mock_report_pass(unused_suite_name):
            raise AssertionError('Tried to Report Pass')

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'run_tests', mock_run_tests))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'report_pass', mock_report_pass))
        self.exit_stack.enter_context(self.swap(
            flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(0,)]))

        run_e2e_tests.main(args=['--suite', 'mySuite'])

    def test_start_tests_skip_build(self):

        def mock_is_oppia_server_already_running(*unused_args):
            return False

        def mock_install_third_party_libraries(unused_arg):
            return

        def mock_exit(unused_exit_code):
            return

        def mock_modify_constants(prod_env, maintenance_mode=False):  # pylint: disable=unused-argument
            return

        def mock_set_constants_to_default():
            return

        def mock_get_e2e_test_parameters(
                unused_sharding_instances, unused_suite, unused_dev_mode):
            return ['commands']

        def mock_managed_process(unused_commands, stdout=None, shell=False):  # pylint: disable=unused-argument
            return contextlib2.nullcontext(enter_result=MockProcessClass())

        def mock_get_chrome_driver_version():
            return CHROME_DRIVER_VERSION

        def mock_check_if_on_ci():
            return True

        def mock_report_pass(unused_suite_name):
            return

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'get_chrome_driver_version',
            mock_get_chrome_driver_version))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'is_oppia_server_already_running',
            mock_is_oppia_server_already_running))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'install_third_party_libraries',
            mock_install_third_party_libraries, expected_args=[(True,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'modify_constants', mock_modify_constants,
            expected_kwargs=[{'prod_env': False}]))
        self.exit_stack.enter_context(self.swap_with_checks(
            build, 'set_constants_to_default', mock_set_constants_to_default))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_elasticsearch_dev_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_firebase_auth_emulator',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_dev_appserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_redis_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webpack_compiler',
            self.mock_managed_process, called=False))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_portserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webdriver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'get_e2e_test_parameters',
            mock_get_e2e_test_parameters,
            expected_args=[(3, 'full', True)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_process', mock_managed_process, expected_args=[
                (
                    [common.NODE_BIN_PATH, '--unhandled-rejections=strict',
                     run_e2e_tests.PROTRACTOR_BIN_PATH, 'commands'],
                ),
            ]))
        self.exit_stack.enter_context(
            self.swap(flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'report_pass', mock_report_pass,
            expected_args=[('full',)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(0,)]))

        run_e2e_tests.main(args=['--skip-install', '--skip-build'])

    def test_linux_chrome_version_command_not_found_failure(self):
        self.exit_stack.enter_context(self.swap(common, 'OS_NAME', 'Linux'))

        def mock_popen(unused_commands, stdout, shell=False): # pylint: disable=unused-argument
            self.assertEqual(stdout, -1)
            raise OSError('google-chrome not found')

        self.exit_stack.enter_context(self.swap_with_checks(
            psutil, 'Popen', mock_popen,
            expected_args=[(['google-chrome', '--version'],)]))
        expected_message = (
            'Failed to execute "google-chrome --version" command. This is '
            'used to determine the chromedriver version to use. Please set '
            'the chromedriver version manually using --chrome_driver_version '
            'flag. To determine the chromedriver version to be used, please '
            'follow the instructions mentioned in the following URL:\n'
            'https://chromedriver.chromium.org/downloads/version-selection')

        with self.assertRaisesRegexp(Exception, expected_message):
            run_e2e_tests.get_chrome_driver_version()

    def test_mac_chrome_version_command_not_found_failure(self):
        self.exit_stack.enter_context(self.swap(common, 'OS_NAME', 'Darwin'))

        def mock_popen(unused_commands, stdout, shell=False): # pylint: disable=unused-argument
            self.assertEqual(stdout, -1)
            raise OSError(
                r'/Applications/Google\ Chrome.app/Contents/MacOS/Google\ '
                'Chrome not found')

        self.exit_stack.enter_context(self.swap_with_checks(
            psutil, 'Popen', mock_popen,
            expected_args=[
                (
                    ['/Applications/Google Chrome.app/Contents/MacOS/'
                     'Google Chrome', '--version'],
                ),
            ]))
        expected_message = (
            r'Failed to execute "/Applications/Google\\ '
            r'Chrome.app/Contents/MacOS/Google\\ Chrome --version" command. '
            'This is used to determine the chromedriver version to use. '
            'Please set the chromedriver version manually using '
            '--chrome_driver_version flag. To determine the chromedriver '
            'version to be used, please follow the instructions mentioned '
            'in the following URL:\n'
            'https://chromedriver.chromium.org/downloads/version-selection')

        with self.assertRaisesRegexp(Exception, expected_message):
            run_e2e_tests.get_chrome_driver_version()

    def test_start_tests_in_debug_mode(self):

        def mock_is_oppia_server_already_running(*unused_args):
            return False

        def mock_install_third_party_libraries(unused_arg):
            return

        def mock_exit(unused_exit_code):
            return

        def mock_build_js_files(
                unused_arg, deparallelize_terser=False, source_maps=False): # pylint: disable=unused-argument
            return

        def mock_get_e2e_test_parameters(
                unused_sharding_instances, unused_suite, unused_dev_mode):
            return ['commands']

        def mock_managed_process(unused_commands, stdout=None, shell=False):  # pylint: disable=unused-argument
            return contextlib2.nullcontext(enter_result=MockProcessClass())

        def mock_get_chrome_driver_version():
            return CHROME_DRIVER_VERSION

        def mock_check_if_on_ci():
            return True

        def mock_report_pass(unused_suite_name):
            return

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'get_chrome_driver_version',
            mock_get_chrome_driver_version))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'is_oppia_server_already_running',
            mock_is_oppia_server_already_running))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'install_third_party_libraries',
            mock_install_third_party_libraries, expected_args=[(False,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'build_js_files', mock_build_js_files,
            expected_args=[(True,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_elasticsearch_dev_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_firebase_auth_emulator',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_dev_appserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_redis_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_portserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webdriver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'get_e2e_test_parameters',
            mock_get_e2e_test_parameters,
            expected_args=[(3, 'full', True)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_process', mock_managed_process, expected_args=[
                (
                    [common.NODE_BIN_PATH, '--inspect-brk',
                     '--unhandled-rejections=strict',
                     run_e2e_tests.PROTRACTOR_BIN_PATH, 'commands'],
                ),
            ]))
        self.exit_stack.enter_context(
            self.swap(flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'report_pass', mock_report_pass,
            expected_args=[('full',)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(0,)]))

        run_e2e_tests.main(args=['--debug_mode'])

    def test_start_tests_in_with_chromedriver_flag(self):

        def mock_is_oppia_server_already_running(*unused_args):
            return False

        def mock_install_third_party_libraries(unused_arg):
            return

        def mock_exit(unused_exit_code):
            return

        def mock_build_js_files(
                unused_arg, deparallelize_terser=False, source_maps=False): # pylint: disable=unused-argument
            return

        def mock_get_e2e_test_parameters(
                unused_sharding_instances, unused_suite, unused_dev_mode):
            return ['commands']

        def mock_popen(unused_commands, stdout=None, shell=False):  # pylint: disable=unused-argument
            return MockProcessClass()

        def mock_get_chrome_driver_version():
            return CHROME_DRIVER_VERSION

        def mock_check_if_on_ci():
            return True

        def mock_report_pass(unused_suite_name):
            return

        self.exit_stack.enter_context(self.swap(
            run_e2e_tests, 'get_chrome_driver_version',
            mock_get_chrome_driver_version))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'is_oppia_server_already_running',
            mock_is_oppia_server_already_running))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'install_third_party_libraries',
            mock_install_third_party_libraries, expected_args=[(False,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'build_js_files', mock_build_js_files,
            expected_args=[(True,)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_elasticsearch_dev_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_firebase_auth_emulator',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_dev_appserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_redis_server',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_portserver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            common, 'managed_webdriver',
            self.mock_managed_process))
        self.exit_stack.enter_context(self.swap_with_checks(
            run_e2e_tests, 'get_e2e_test_parameters',
            mock_get_e2e_test_parameters,
            expected_args=[(3, 'full', True)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            psutil, 'Popen', mock_popen, expected_args=[
                (
                    [common.NODE_BIN_PATH, '--unhandled-rejections=strict',
                     run_e2e_tests.PROTRACTOR_BIN_PATH, 'commands'],
                ),
            ]))
        self.exit_stack.enter_context(
            self.swap(flake_checker, 'check_if_on_ci', mock_check_if_on_ci))
        self.exit_stack.enter_context(self.swap_with_checks(
            flake_checker, 'report_pass', mock_report_pass,
            expected_args=[('full',)]))
        self.exit_stack.enter_context(self.swap_with_checks(
            sys, 'exit', mock_exit, expected_args=[(0,)]))

        run_e2e_tests.main(
            args=['--chrome_driver_version', CHROME_DRIVER_VERSION])
