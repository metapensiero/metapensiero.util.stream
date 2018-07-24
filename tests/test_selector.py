# -*- coding: utf-8 -*-
# :Project:   metapensiero.reactive -- selector tests
# :Created:   lun 30 gen 2017 16:28:18 CET
# :Author:    Alberto Berti <alberto@metapensiero.it>,
#             James Stidard <jamesstidard@gmail.com>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2016, 2017, 2018 Alberto Berti, James Stidard
#

from functools import partial

import pytest

from metapensiero.util.stream import Selector
from metapensiero.util.stream.testing import (
    gen, echo_gen, make_async_gen, profile)


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
    s = Selector(echo_gen, partial(echo_gen))
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
        v = await ch.asend('done')
        data.append(v)

    assert data == ['initial', 1, 'a', None, None]


@pytest.mark.asyncio
async def test_selector_order():
    source_1 = make_async_gen([1, 2, 3], step_delay=0.2)
    source_2 = make_async_gen([4, 5, 6], initial_delay=0.1, step_delay=0.2)
    expected = [1, 4, 2, 5, 3, 6]

    async for value in Selector(source_1(), source_2()):
        assert value == expected.pop(0)


@pytest.mark.asyncio
@pytest.mark.timeout()
async def test_selector_blocking():
    source_1 = make_async_gen([1, 2, 3], step_delay=1)
    source_2 = make_async_gen([1, 2, 3], step_delay=1)

    with profile(max_duration=3.1):
        async for _ in Selector(source_1(), source_2()):
            pass


@pytest.mark.asyncio
async def test_yielded_source_with_values():
    source_values = [
        [object(), object(), object()],
        [object(), object(), object()],
        [object(), object(), object()],
    ]
    source_values = {make_async_gen(vs)(): vs.copy() for vs in source_values}
    sel = Selector(*source_values.keys(), yield_source=True)
    async for source, value in sel:
        source_values[source].remove(value)
    else:
        assert all(len(vs) == 0 for vs in source_values.values())


@pytest.mark.asyncio
async def test_exception_handling():
    class AnException(Exception):
        pass
    exc1 = AnException()
    exc2 = AnException()
    src1 = [0, 1, 2, 3, exc1, 4]
    src2 = [0, 1, exc2, 3, 4, 5]
    source_1 = make_async_gen(src1, initial_delay=0.2)
    source_2 = make_async_gen(src2)
    expected = [0, 1, exc2]
    result = []

    sel = Selector(source_1, source_2)
    sel_agen = sel.__aiter__()
    while True:
        try:
            result.append(await sel_agen.__anext__())
        except AnException as e:
            result.append(e)
        except StopAsyncIteration:
            break

    assert result == expected

@pytest.mark.asyncio
async def test_agen_source_works():
    class AnException(Exception):
        pass
    exc1 = AnException()
    exc2 = AnException()
    src1 = [0, 1, 2, 3, exc1, 4]
    src2 = [0, 1, exc2, 3, 4, 5]
    source_1 = make_async_gen(src1, initial_delay=0.2)
    source_2 = make_async_gen(src2)
    expected = [0, 1, exc2]
    result = []

    sel = Selector(source_1(), source_2())
    sel_agen = sel.__aiter__()
    while True:
        try:
            result.append(await sel_agen.__anext__())
        except AnException as e:
            result.append(e)
        except StopAsyncIteration:
            break

    assert result == expected


@pytest.mark.asyncio
async def test_non_raised_exception_passes():
    class AnException(Exception):
        pass
    exc1 = AnException()
    exc2 = AnException()
    src1 = [0, 1, 2, 3, exc1, 4]
    src2 = [0, 1, exc2, 3, 4, 5]
    source_1 = make_async_gen(src1, initial_delay=0.2)
    source_2 = make_async_gen(src2, raise_exc=False)
    expected = [0, 1, exc2, 3, 4, 5, 0, 1, 2, 3, exc1]
    result = []

    sel = Selector(source_1, source_2)
    sel_agen = sel.__aiter__()
    while True:
        try:
            result.append(await sel_agen.__anext__())
        except AnException as e:
            result.append(e)
        except StopAsyncIteration:
            break

    assert result == expected
