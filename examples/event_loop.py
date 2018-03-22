# osmo_gsm_tester: Event loop
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time
import logging

poll_funcs = []

def register_poll_func(func):
    global poll_funcs
    poll_funcs.append(func)

def unregister_poll_func(func):
    global poll_funcs
    poll_funcs.remove(func)

def poll():
    global poll_funcs
    for func in poll_funcs:
        func()

def wait_no_raise(condition, condition_args, condition_kwargs, timeout, timestep):
    if not timeout or timeout < 0:
        raise RuntimeError('wait() *must* time out at some point.', timeout=timeout)
    if timestep < 0.1:
        timestep = 0.1

    started = time.time()
    while True:
        poll()
        if condition(*condition_args, **condition_kwargs):
            return True
        waited = time.time() - started
        if waited > timeout:
            return False
        time.sleep(timestep)

def wait(condition, *condition_args, timeout=300, timestep=1, **condition_kwargs):
    if not wait_no_raise(condition, condition_args, condition_kwargs, timeout, timestep):
        raise RuntimeError('Wait timeout')

def sleep(seconds):
    assert seconds > 0.
    wait_no_raise(lambda: False, [], {}, timeout=seconds, timestep=min(seconds, 1))


# vim: expandtab tabstop=4 shiftwidth=4
