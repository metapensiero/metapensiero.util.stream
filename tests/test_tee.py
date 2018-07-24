# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Tee class tests
# :Created:   mar 24 lug 2018 15:18:00 CEST
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

from functools import partial

import pytest

from metapensiero.util.stream import Tee, TEE_STATUS
from metapensiero.util.stream.testing import gen, echo_gen


@pytest.mark.asyncio
async def test_tee(event_loop):

    tee = Tee(partial(gen, 10, lambda i: i, 0.1))
    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()
    data1 = [e async for e in ch1]
    data2 = [e async for e in ch2]

    assert len(data1) == len(data2) == 10
    assert len(tee._queues) == 0
    assert tee._status == TEE_STATUS.STOPPED

    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()
    data1 = [e async for e in ch1]
    data2 = [e async for e in ch2]

    assert len(data1) == len(data2) == 10

    tee = Tee(gen(10, lambda i: i, 0.1, gen_exc=True))
    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()
    with pytest.raises(ZeroDivisionError):
        data1 = [e async for e in ch1]
    with pytest.raises(ZeroDivisionError):
        data2 = [e async for e in ch2]


@pytest.mark.asyncio
async def test_tee_send(event_loop):

    tee = Tee(echo_gen, remove_none=True, await_send=True)
    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()

    # setup
    v1 = await ch1.asend(None)
    v2 = await ch2.asend(None)

    assert v1 == v2 == 'initial'

    data1 = []
    data2 = []
    data1.append(await ch1.asend(1))
    data2.append(await ch2.asend('a'))
    data1.append(await ch1.asend('done'))
    data2.append(await ch2.asend('done'))

    with pytest.raises(StopAsyncIteration):
        data1.append(await ch1.asend(None))
    with pytest.raises(StopAsyncIteration):
        data1.append(await ch2.asend(None))

    assert data1 == data2 == [1, 'a']

    assert tee._status == TEE_STATUS.STOPPED


@pytest.mark.asyncio
async def test_tee_push_mode(event_loop):

    tee = Tee(push_mode=True)
    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()

    tee.push('a')
    tee.push('b')
    tee.close()

    data1 = [e async for e in ch1]
    data2 = [e async for e in ch2]

    assert len(data1) == len(data2) == 2
    assert data1 == data2 == ['a', 'b']
    assert tee._status == TEE_STATUS.CLOSED

    tee = Tee(push_mode=True)
    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()

    tee.push('a')
    tee.push('b')
    tee.push(ZeroDivisionError())
    tee.close()

    with pytest.raises(ZeroDivisionError):
        data1 = [e async for e in ch1]
    with pytest.raises(ZeroDivisionError):
        data2 = [e async for e in ch2]

    sent_values = []

    async def sent(value):
        sent_values.append(value)

    tee = Tee(push_mode=sent)
    ch1 = tee.__aiter__()
    ch2 = tee.__aiter__()

    tee.push('a')
    v1 = await ch1.asend(None)
    v2 = await ch2.asend(None)

    assert v1 == v2 == 'a'

    data1 = []
    data2 = []
    tee.push('b')
    data1.append(await ch1.asend(1))
    data2.append(await ch2.asend('c'))

    assert data1 == data2 == ['b']
    assert sent_values == [1, 'c']
    tee.close()
