# Copyright 2019 The Oppia Authors. All Rights Reserved.
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

"""Python execution for running e2e tests."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import argparse
import os
import re
import subprocess
import sys

from constants import constants
import python_utils
from scripts import build
from scripts import common
from scripts import flake_checker
from scripts import install_third_party_libs


MAX_RETRY_COUNT = 3
RERUN_NON_FLAKY = True
OPPIA_SERVER_PORT = 8181
GOOGLE_APP_ENGINE_PORT = 9001
ELASTICSEARCH_SERVER_PORT = 9200
PORTS_USED_BY_OPPIA_PROCESSES = [
    OPPIA_SERVER_PORT, GOOGLE_APP_ENGINE_PORT, ELASTICSEARCH_SERVER_PORT]
PROTRACTOR_BIN_PATH = os.path.join(
    common.NODE_MODULES_PATH, 'protractor', 'bin', 'protractor')

PROTRACTOR_CONFIG_FILE_PATH = os.path.join(
    'core', 'tests', 'protractor.conf.js')

_PARSER = argparse.ArgumentParser(
    description="""
Run this script from the oppia root folder:
   python -m scripts.run_e2e_tests

The root folder MUST be named 'oppia'.

NOTE: You can replace 'it' with 'fit' or 'describe' with 'fdescribe' to run a
single test or test suite.
""")


_PARSER.add_argument(
    '--skip-install',
    help='If true, skips installing dependencies. The default value is false.',
    action='store_true')
_PARSER.add_argument(
    '--skip-build',
    help='If true, skips building files. The default value is false.',
    action='store_true')
_PARSER.add_argument(
    '--sharding-instances', type=int, default=3,
    help='Sets the number of parallel browsers to open while sharding. '
         'Sharding must be disabled (either by passing in false to --sharding '
         'or 1 to --sharding-instances) if running any tests in isolation '
         '(fit or fdescribe).')
_PARSER.add_argument(
    '--prod_env',
    help='Run the tests in prod mode. Static resources are served from '
         'build directory and use cache slugs.',
    action='store_true')
_PARSER.add_argument(
    '--suite', default='full',
    help='Performs test for different suites, here suites are the '
         'name of the test files present in core/tests/protractor_desktop/ and '
         'core/test/protractor/ dirs. e.g. for the file '
         'core/tests/protractor/accessibility.js use --suite=accessibility. '
         'For performing a full test, no argument is required. ')
_PARSER.add_argument(
    '--chrome_driver_version',
    help='Uses the specified version of the chrome driver')
_PARSER.add_argument(
    '--debug_mode',
    help='Runs the protractor test in debugging mode. Follow the instruction '
         'provided in following URL to run e2e tests in debugging mode: '
         'https://www.protractortest.org/#/debugging#disabled-control-flow',
    action='store_true')
_PARSER.add_argument(
    '--deparallelize_terser',
    help='Disable parallelism on terser plugin in webpack. Use with prod_env. '
         'This flag is required for tests to run on CircleCI, since CircleCI '
         'sometimes flakes when parallelism is used. It is not required in the '
         'local dev environment. See https://discuss.circleci.com/t/'
         'build-fails-with-error-spawn-enomem/30537/10',
    action='store_true')
_PARSER.add_argument(
    '--server_log_level',
    help='Sets the log level for the appengine server. The default value is '
         'set to error.',
    default='error',
    choices=['critical', 'error', 'warning', 'info'])
_PARSER.add_argument(
    '--source_maps',
    help='Build webpack with source maps.',
    action='store_true')


def is_oppia_server_already_running():
    """Check if the ports are taken by any other processes. If any one of
    them is taken, it may indicate there is already one Oppia instance running.

    Returns:
        bool. Whether there is a running Oppia instance.
    """
    for port in PORTS_USED_BY_OPPIA_PROCESSES:
        if common.is_port_in_use(port):
            python_utils.PRINT(
                'There is already a server running on localhost:%s. '
                'Please terminate it before running the end-to-end tests. '
                'Exiting.' % port)
            return True
    return False


def run_webpack_compilation(source_maps=False):
    """Runs webpack compilation."""
    max_tries = 5
    webpack_bundles_dir_name = 'webpack_bundles'
    for _ in python_utils.RANGE(max_tries):
        try:
            managed_webpack_compiler = (
                common.managed_webpack_compiler(use_source_maps=source_maps))
            with managed_webpack_compiler as proc:
                proc.wait()
        except subprocess.CalledProcessError as error:
            python_utils.PRINT(error.output)
            sys.exit(error.returncode)
            return
        if os.path.isdir(webpack_bundles_dir_name):
            break
    else:
        # We didn't break out of the loop (all attempts have failed).
        python_utils.PRINT('Failed to complete webpack compilation, exiting...')
        sys.exit(1)


def install_third_party_libraries(skip_install):
    """Run the setup and installation scripts."""
    if not skip_install:
        install_third_party_libs.main()


def build_js_files(
        dev_mode_setting, deparallelize_terser=False, source_maps=False):
    """Build the javascript files.

    Args:
        dev_mode_setting: bool. Represents whether to run the related commands
            in dev mode.
        deparallelize_terser: bool. Represents whether to use webpack
            compilation config that disables parallelism on terser plugin.
        source_maps: bool. Represents whether to use source maps while
            building webpack.
    """
    if not dev_mode_setting:
        python_utils.PRINT('  Generating files for production mode...')
        build_args = ['--prod_env']

        if deparallelize_terser:
            build_args.append('--deparallelize_terser')
        if source_maps:
            build_args.append('--source_maps')

        build.main(args=build_args)
    else:
        build.main(args=[])
        run_webpack_compilation(source_maps=source_maps)


def get_parameter_for_sharding(sharding_instances):
    """Return the parameter for sharding, based on the given number of
    sharding instances.

    Args:
        sharding_instances: int. How many sharding instances to be running.

    Returns:
        list(str). A list of parameters to represent the sharding configuration.
    """
    if sharding_instances <= 0:
        raise ValueError('Sharding instance should be larger than 0')
    if sharding_instances == 1:
        return []
    else:
        return ['--capabilities.shardTestFiles=True',
                '--capabilities.maxInstances=%s' % sharding_instances]


def get_parameter_for_dev_mode(dev_mode_setting):
    """Return parameter for whether the test should be running on dev_mode.

    Args:
        dev_mode_setting: bool. Whether the test is running on dev_mode.

    Returns:
        str. A string for the testing mode command line parameter.
    """
    return '--params.devMode=%s' % dev_mode_setting


def get_parameter_for_suite(suite_name):
    """Return a parameter for which suite to run the tests for.

    Args:
        suite_name: str. The suite name whose tests should be run. If the value
            is `full`, all tests will run.

    Returns:
        list(str). A list of command line parameters for the suite.
    """
    return ['--suite', suite_name]


def get_e2e_test_parameters(
        sharding_instances, suite_name, dev_mode_setting):
    """Return parameters for the end-2-end tests.

    Args:
        sharding_instances: str. Sets the number of parallel browsers to open
            while sharding.
        suite_name: str. Performs test for different suites.
        dev_mode_setting: bool. Represents whether run the related commands in
            dev mode.

    Returns:
        list(str). Parameters for running the tests.
    """
    sharding_parameters = get_parameter_for_sharding(sharding_instances)
    dev_mode_parameters = get_parameter_for_dev_mode(dev_mode_setting)
    suite_parameter = get_parameter_for_suite(suite_name)

    cmd_args = [PROTRACTOR_CONFIG_FILE_PATH]
    cmd_args.extend(sharding_parameters)
    cmd_args.extend(suite_parameter)
    cmd_args.append(dev_mode_parameters)

    return cmd_args


def get_chrome_driver_version():
    """Fetches the latest supported version of chromedriver depending on the
    Chrome version.
    This method follows the steps mentioned here:
    https://chromedriver.chromium.org/downloads/version-selection
    """
    cmd_args = (
        # Although there are spaces between Google and Chrome in the path, they
        # don't need to be escaped outside of the terminal, i.e. shell=False for
        # Popen, by default.
        ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
         '--version']
        if common.is_mac_os() else ['google-chrome', '--version'])

    try:
        with common.managed_process(cmd_args, stdout=subprocess.PIPE) as proc:
            output = proc.stdout.readline()
    except OSError:
        # For the error message for the mac command, we need to add the
        # backslashes in. This is because it is likely that a user will try to
        # run the command on their terminal and, as mentioned above, the mac
        # get chrome version command has spaces in the path which need to be
        # escaped for successful terminal use.
        raise Exception(
            'Failed to execute "%s" command. This is used to determine the '
            'chromedriver version to use. Please set the chromedriver version '
            'manually using --chrome_driver_version flag. To determine the '
            'chromedriver version to be used, please follow the instructions '
            'mentioned in the following URL:\n'
            'https://chromedriver.chromium.org/downloads/version-selection' % (
                ' '.join(arg.replace(' ', r'\ ') for arg in cmd_args)))

    chrome_version = ''.join(re.findall(r'([0-9]|\.)', output))
    chrome_version = '.'.join(chrome_version.split('.')[:-1])
    response = python_utils.url_open(
        'https://chromedriver.storage.googleapis.com/LATEST_RELEASE_%s'
        % chrome_version)
    chrome_driver_version = response.read()
    python_utils.PRINT('\n\nCHROME VERSION: %s' % chrome_version)
    return chrome_driver_version


def run_tests(args):
    """Run the scripts to start end-to-end tests."""
    # TODO(#11549): Move this to top of the file.
    import contextlib2

    if is_oppia_server_already_running():
        sys.exit(1)

    install_third_party_libraries(args.skip_install)

    with contextlib2.ExitStack() as stack:
        dev_mode = not args.prod_env

        if args.skip_build:
            build.modify_constants(prod_env=args.prod_env)
        else:
            build_js_files(
                dev_mode, deparallelize_terser=args.deparallelize_terser,
                source_maps=args.source_maps)
        stack.callback(build.set_constants_to_default)

        python_utils.PRINT('Waiting for servers to come up...')

        stack.enter_context(common.managed_redis_server())
        stack.enter_context(common.managed_elasticsearch_dev_server())
        if constants.EMULATOR_MODE:
            stack.enter_context(common.managed_firebase_auth_emulator())

        stack.enter_context(common.managed_dev_appserver(
            'app.yaml' if args.prod_env else 'app_dev.yaml',
            port=GOOGLE_APP_ENGINE_PORT, log_level=args.server_log_level,
            clear_datastore=True, skip_sdk_update_check=True,
            env={'PORTSERVER_ADDRESS': common.PORTSERVER_SOCKET_FILEPATH}))

        version = args.chrome_driver_version or get_chrome_driver_version()
        stack.enter_context(common.managed_webdriver(version))

        # Wait for the servers to come up.
        python_utils.PRINT('Servers have come up.')
        python_utils.PRINT(
            'Note: If ADD_SCREENSHOT_REPORTER is set to true in '
            'core/tests/protractor.conf.js, you can view screenshots '
            'of the failed tests in ../protractor-screenshots/')

        cmd_args = [common.NODE_BIN_PATH]
        if args.debug_mode:
            cmd_args.append('--inspect-brk')
        # This flag ensures tests fail if waitFor calls time out.
        cmd_args.append('--unhandled-rejections=strict')
        cmd_args.append(PROTRACTOR_BIN_PATH)
        cmd_args.extend(get_e2e_test_parameters(
            args.sharding_instances, args.suite, dev_mode))

        output_lines = []
        with common.managed_process(cmd_args, stdout=subprocess.PIPE) as p:
            # Keep reading until an empty string is returned (process ends).
            for line in iter(p.stdout.readline, b''):
                if isinstance(line, str):
                    # This is a failsafe line in case we get non-unicode
                    # input. Our unit tests always provide unicode strings,
                    # however.
                    line = line.decode('utf-8') # pragma: nocover
                output_lines.append(line.rstrip())
                # Replaces non-ASCII characters with '?'.
                sys.stdout.write(line.encode('ascii', errors='replace'))
        return output_lines, p.returncode


def main(args=None):
    """Run tests, rerunning at most MAX_RETRY_COUNT times if they flake."""
    parsed_args = _PARSER.parse_args(args=args)

    with common.managed_portserver():
        for attempt_num in python_utils.RANGE(MAX_RETRY_COUNT):
            python_utils.PRINT('***Attempt %s.***' % (attempt_num + 1))
            output, return_code = run_tests(parsed_args)
            # Don't rerun off of CI.
            if not flake_checker.check_if_on_ci():
                python_utils.PRINT('No reruns because not running on CI.')
                break
            # Don't rerun passing tests.
            if return_code == 0:
                flake_checker.report_pass(parsed_args.suite)
                break
            flaky = flake_checker.is_test_output_flaky(
                output, parsed_args.suite)
            # Don't rerun if the test was non-flaky and we are not rerunning
            # non-flaky tests.
            if not flaky and not RERUN_NON_FLAKY:
                break

    sys.exit(return_code)


if __name__ == '__main__':  # pragma: no cover
    main()
