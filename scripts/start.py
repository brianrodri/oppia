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

"""This script starts up a development server running Oppia. It installs any
missing third-party dependencies and starts up a local GAE development
server.
"""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import argparse
import os
import re
import time

from constants import constants

from . import install_third_party_libs
# This installs third party libraries before importing other files or importing
# libraries that use the builtins python module (e.g. build, python_utils).
install_third_party_libs.main()

from . import build # isort:skip  pylint: disable=wrong-import-position, wrong-import-order
from . import common # isort:skip  pylint: disable=wrong-import-position, wrong-import-order

import python_utils # isort:skip  pylint: disable=wrong-import-position, wrong-import-order


_PARSER = argparse.ArgumentParser(
    description="""
Run the script from the oppia root folder:
    python -m scripts.start
Note that the root folder MUST be named 'oppia'.
""")

_PARSER.add_argument(
    '--save_datastore',
    help='optional; if specified, does not clear the datastore.',
    action='store_true')
_PARSER.add_argument(
    '--enable_console',
    help='optional; if specified, enables console.',
    action='store_true')
_PARSER.add_argument(
    '--disable_host_checking',
    help=(
        'optional; if specified, disables host checking so that the dev '
        'server can be accessed by any device on the same network using the '
        'host device\'s IP address. DO NOT use this flag if you\'re running '
        'on an untrusted network.'),
    action='store_true')
_PARSER.add_argument(
    '--prod_env',
    help='optional; if specified, runs Oppia in a production environment.',
    action='store_true')
_PARSER.add_argument(
    '--maintenance_mode',
    help='optional; if specified, puts Oppia into maintenance mode.',
    action='store_true')
_PARSER.add_argument(
    '--no_browser',
    help='optional; if specified, does not open a browser.',
    action='store_true')
_PARSER.add_argument(
    '--no_auto_restart',
    help=(
        'optional; if specified, does not automatically restart when files are '
        'changed.'),
    action='store_true')
_PARSER.add_argument(
    '--source_maps',
    help=(
        'optional; if specified, build webpack with source maps.'),
    action='store_true')

PORT_NUMBER_FOR_GAE_SERVER = 8181


def main(args=None):
    """Starts up a development server running Oppia."""
    # TODO(#11549): Move this to top of the file.
    import contextlib2

    parsed_args = _PARSER.parse_args(args=args)

    # Check that there isn't a server already running.
    if common.is_port_open(PORT_NUMBER_FOR_GAE_SERVER):
        common.print_each_string_after_two_new_lines([
            'WARNING',
            'Could not start new server. There is already an existing server '
            'running at port %d.' % PORT_NUMBER_FOR_GAE_SERVER])

    build_args = ['--prod_env'] if parsed_args.prod_env else []
    if parsed_args.maintenance_mode:
        build_args.append('--maintenance_mode')
    if parsed_args.source_maps:
        build_args.append('--source_maps')

    with contextlib2.ExitStack() as exit_stack:
        build.main(args=build_args)
        exit_stack.callback(build.set_constants_to_default)

        if not parsed_args.prod_env:
            python_utils.PRINT('Compiling webpack...')
            exit_stack.enter_context(common.managed_webpack_compiler(
                use_source_maps=parsed_args.source_maps))
            # Give webpack few seconds to do the initial compilation.
            time.sleep(10)

        python_utils.PRINT('Starting Redis server.')
        exit_stack.enter_context(common.managed_redis_server())

        python_utils.PRINT('Starting ElasticSearch development server.')
        exit_stack.enter_context(common.managed_elasticsearch_dev_server())

        if constants.EMULATOR_MODE:
            python_utils.PRINT('Starting Firebase emulators')
            exit_stack.enter_context(common.managed_firebase_auth_emulator())

        python_utils.PRINT('Starting GAE development server')
        app_yaml_filepath = (
            'app.yaml' if parsed_args.prod_env else 'app_dev.yaml')
        exit_stack.enter_context(common.managed_dev_appserver(
            app_yaml_filepath,
            clear_datastore=not parsed_args.save_datastore,
            enable_console=parsed_args.enable_console,
            enable_host_checking=not parsed_args.disable_host_checking,
            automatic_restart=not parsed_args.no_auto_restart,
            skip_sdk_update_check=True,
            port=PORT_NUMBER_FOR_GAE_SERVER))

        # Launch a browser window.
        if common.is_linux_os() and not parsed_args.no_browser:
            if any(re.match('.*VBOX.*', d)
                   for d in os.listdir('/dev/disk/by-id/')):
                common.print_each_string_after_two_new_lines([
                    'INFORMATION',
                    'Setting up a local development server. You can access '
                    'this server by navigating to localhost:%d in a browser '
                    'window.' % PORT_NUMBER_FOR_GAE_SERVER,
                ])
            else:
                common.print_each_string_after_two_new_lines([
                    'INFORMATION',
                    'Setting up a local development server at localhost:%d.' % (
                        PORT_NUMBER_FOR_GAE_SERVER),
                    'Opening a default browser window pointing to this server',
                ])
                time.sleep(5)
                exit_stack.enter_context(common.managed_process([
                    'xdg-open',
                    'http://localhost:%d/' % PORT_NUMBER_FOR_GAE_SERVER
                ]))
        elif common.is_mac_os() and not parsed_args.no_browser:
            common.print_each_string_after_two_new_lines([
                'INFORMATION',
                'Setting up a local development server at localhost:%d.' % (
                    PORT_NUMBER_FOR_GAE_SERVER),
                'Opening a default browser window pointing to this server.',
            ])
            time.sleep(5)
            exit_stack.enter_context(common.managed_process([
                'open', 'http://localhost:%d/' % PORT_NUMBER_FOR_GAE_SERVER,
            ]))
        else:
            common.print_each_string_after_two_new_lines([
                'INFORMATION',
                'Setting up a local development server. You can access this '
                'server by navigating to localhost:%d in a browser window.' % (
                    PORT_NUMBER_FOR_GAE_SERVER),
            ])

        python_utils.PRINT('Done!')

        while common.is_port_open(PORT_NUMBER_FOR_GAE_SERVER):
            time.sleep(1)

        common.print_each_string_after_two_new_lines(
            ['INFORMATION', 'Cleaning up the servers.'])


if __name__ == '__main__':
    main()
