# -*- coding: utf-8 -*-
# :Project:   metapensiero.reactive -- selector tests
# :Created:   lun 30 gen 2017 16:28:18 CET
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2016, 2017, 2018 Alberto Berti
#

import asyncio
from functools import partial

import pytest

from metapensiero.util.stream import Selector
from metapensiero.util.stream.testing import gen, echo_gen


@pytest.mark.asyncio
async def test_selector(event_loop):

    # results = []
    # async for el in partial(gen, 10, lambda i: i, 0.1)():
    #     results.append(el)

    # assert len(results) == 10

    # results = []
    # async for el in partial(gen, 10, lambda i: i*2, 0.1)():
    #     results.append(el)

    # assert len(results) == 10

    s = Selector(
        partial(gen, 10, lambda i: i, 0.1),
        partial(gen, 10, lambda i: chr(i+64), 0.1),
    )

    results = []
    async for el in s:
        results.append(el)
    assert len(results) == 20

    # test generator restart

    results = []
    async for el in s:
        results.append(el)
    assert len(results) == 20

    s = Selector(
        partial(gen, 10, lambda i: i, 0.1),
        partial(gen, 10, lambda i: chr(i+64), 0.1, gen_exc=True),
    )

    with pytest.raises(ZeroDivisionError):
        results = []
        async for el in s:
            results.append(el)


@pytest.mark.asyncio
async def test_selector_send(event_loop):

    # use partial here just to differentiate the two sources
    s = Selector(echo_gen, partial(echo_gen), remove_none=True,
                 await_send=True)
    ch = s.__aiter__()

    # setup
    v = await ch.asend(None)

    assert v == 'initial'

    data = []

    data.append(await ch.asend(1))
    data.append(await ch.asend('a'))
    data.append(await ch.asend('done'))
    data.append(await ch.asend(None))
    data.append(await ch.asend(None))

    with pytest.raises(StopAsyncIteration):
        v = await ch.asend(None)
        data.append(v)

    assert data == ['initial', 1, 'a', 1, 'a']
