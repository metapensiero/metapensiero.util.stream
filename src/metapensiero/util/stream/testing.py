# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Some common fixtures and tools
# :Created:   sab 21 lug 2018 20:42:00 CEST
# :Author:     <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import asyncio


async def gen(count, func, delay, initial_delay=None, gen_exc=False):
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
