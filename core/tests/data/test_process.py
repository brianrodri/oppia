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

"""A simple Python program for testing process management.

By default, does nothing for 10 seconds and then exits.
"""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import argparse
import os
import signal
import time


def main():
    parser = argparse.ArgumentParser(
        description='A simple Python program for testing process management.')
    parser.add_argument(
        '-u', '--unresponsive', help='ignore SIGTERM signals',
        action='store_true')
    parser.add_argument(
        '-d', '--delay_secs', help='seconds to wait before exiting',
        type=int, default=10)
    parser.add_argument(
        '-n', '--num_children', help='number of child processes to create',
        type=int, default=0)
    parser.add_argument(
        '-o', '--outputs', help='strings to print to stdout',
        type=str, default=(), nargs='*')

    parsed_args = parser.parse_args()

    for output in parsed_args.outputs:
        print(output) # pylint: disable=superfluous-parens

    for _ in range(parsed_args.num_children): # pylint: disable=replace-disallowed-function-calls
        # The child process will return a value of 0 from os.fork().
        if os.fork() == 0:
            break

    if parsed_args.unresponsive:
        # Register an unresponsive function as the SIGTERM handler.
        signal.signal(
            signal.SIGTERM, lambda *_: time.sleep(parsed_args.delay_secs))

    time.sleep(parsed_args.delay_secs)


if __name__ == '__main__':
    main()
