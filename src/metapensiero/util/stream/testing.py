# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Some common fixtures and tools
# :Created:   sab 21 lug 2018 20:42:00 CEST
# :Author:    Alberto Berti <alberto@metapensiero.it>,
#             James Stidard <jamesstidard@gmail.com>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti, James Stidard
#

import asyncio
from contextlib import contextmanager
import time


async def gen(count, func, delay, initial_delay=None, gen_exc=False):
    """To be merged with make_async_gen"""
    if initial_delay:
        await asyncio.sleep(initial_delay)
    for i in range(count):
        yield func(i)
        if gen_exc and i > count/2:
            a = 1/0
        await asyncio.sleep(delay)


async def echo_gen():
    v = yield 'initial'
    while v != 'done':
        v = yield v


def make_async_gen(yieldables, *, initial_delay: float=0, step_delay: float=0):
    """
    Returns async generator yielding with delay.

    Exceptions found in yieldables will be raised.
    """
    async def async_gen():
        await asyncio.sleep(initial_delay)
        for yieldable in yieldables:
            await asyncio.sleep(step_delay)
            if isinstance(yieldable, Exception):
                raise yieldable
            else:
                yield yieldable

    return async_gen


@contextmanager
def profile(*, max_duration: float):
    """Raises a TimeoutError when enclosed code exceeds duration."""
    start = time.time()
    yield
    actual_duration = time.time() - start
    if actual_duration > max_duration:
        raise TimeoutError
