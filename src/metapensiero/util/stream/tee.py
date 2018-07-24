# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Tee class
# :Created:   mar 24 lug 2018 15:02:16 CEST
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import asyncio
import collections
import enum

from . import STOPPED_TOKEN
from .single import SingleSourced

TEE_STATUS = enum.IntEnum('TeeStatus', 'INITIAL STARTED STOPPED CLOSED')
TEE_MODE = enum.IntEnum('TeeMode', 'PULL PUSH')


class Tee(SingleSourced):
    """An object clones an asynchronous iterator. It is not meant to give
    each consumer the same stream of values no matter when the
    consumer starts the iteration like the tee in itertools. Here
    *when* matters: each consumer will receive any value collected
    **after** it started iterating over the Tee object.

    Another feature is that this object will start consuming its
    source only when consumers start iterating over. This is to lower
    the price in terms of task switches.

    It can also work in *push* mode, where it doesn't iterates over
    any source but any value is passed in using the :meth:`push`
    method and the Tee is permanently stopped using the :meth:`close`
    method.

    :param aiterable source: The object to async iterate. Can be a
      direct async-iterable (which should implement an ``__aiter__``
      method) or a callable that should return an async-iterable.
    :param bool push_mode: ``True`` if the Tee should operate in push mode.
      If it's a callable it will be used as an async callback.
    :param bool remove_none: Remove occurring ``None`` values from the
      stream.
    :param bool await_send: Await the availability of a sent value before
      consuming another value from the source.
    :param loop: The optional loop.
    :type loop: `asyncio.BaseEventLoop`"""

    # Remove the need for the loop
    def __init__(self, source=None, *, push_mode=False, loop=None,
                 remove_none=False, await_send=False):
        self.loop = loop or asyncio.get_event_loop()
        self._mode = TEE_MODE.PUSH if push_mode else TEE_MODE.PULL
        if self._mode == TEE_MODE.PULL:
            self._status = TEE_STATUS.INITIAL
        else:
            self._status = TEE_STATUS.STARTED
        super().__init__(source)
        self._queues = {}
        self._run_fut = None
        self._send_queue = collections.deque()
        self._send_cback = push_mode
        self._send_avail = asyncio.Event(loop=self.loop)
        self._remove_none = remove_none
        self._await_send = await_send

    def __aiter__(self):
        return self._setup()

    def _add_queue(self):
        """Add a queue to the group that will receive the incoming values."""
        q = collections.deque()
        e = asyncio.Event(loop=self.loop)
        self._queues[e] = q
        return e, q

    def _cleanup(self):
        """Sent to the queues a marker value that means that ther will be no
        more values after that."""
        self._push(STOPPED_TOKEN)
        self._send_queue.clear()

    async def _del_queue(self, ev):
        """Remove a queue, called by the generator instance that is driven by
        a consumer when it gets garbage collected. Also, if there are
        no more queues to fill, halt the source consuming task."""
        queue = self._queues.pop(ev)
        queue.clear()
        if len(self._queues) == 0:
            if self._run_fut is not None:
                if self._status == TEE_STATUS.STARTED:
                    self._run_fut.cancel()
                await self._run_fut
                self._run_fut = None

    def _push(self, element):
        """Push a new value into the queues and signal that a value is
        waiting."""
        for event, queue in self._queues.items():
            queue.append(element)
            event.set()

    async def _run(self, source):
        """Private coroutine that consumes the source."""
        self._status = TEE_STATUS.STARTED
        try:
            send_value = None
            while True:
                el = await source.asend(send_value)
                self._push(el)
                if self._await_send:
                    await self._send_avail.wait()
                if len(self._send_queue) > 0:
                    send_value = self._send_queue.popleft()
                    if self._await_send and len(self._send_queue) == 0:
                        self._send_avail.clear()
                else:
                    send_value = None
        except StopAsyncIteration:
            pass
        except asyncio.CancelledError:
            await source.aclose()
            raise
        except GeneratorExit:
            pass
        except Exception as e:
            self.push(e)
            self._status = TEE_STATUS.STOPPED
        finally:
            self._status = TEE_STATUS.STOPPED
            self._cleanup()

    async def _send(self, value):
        """Send a value coming from one of the consumers."""
        assert value is not None
        if self._mode == TEE_MODE.PUSH and callable(self._send_cback):
            await self._send_cback(value)
        else:
            self._send_queue.append(value)
            self._send_avail.set()

    def _setup(self):
        if self._status in [TEE_STATUS.INITIAL, TEE_STATUS.STOPPED]:
            self.run()
        next_value_avail, queue = self._add_queue()
        return self.gen(next_value_avail, queue)

    @property
    def active(self):
        return self._status == TEE_STATUS.STARTED

    def close(self):
        """Close a started tee and mark it as depleted, used in ``push``
        mode."""
        assert self._status == TEE_STATUS.STARTED
        self._status = TEE_STATUS.CLOSED
        self._cleanup()

    async def gen(self, next_value_avail, queue):
        """An async generator instantiated per consumer."""
        if self._status == TEE_STATUS.CLOSED and len(queue) == 0:
            return
        try:
            while await next_value_avail.wait():
                if len(queue):
                    v = queue.popleft()
                    if v == STOPPED_TOKEN:
                        break
                    elif isinstance(v, Exception):
                        raise v
                    else:
                        sent_value = yield v
                    if sent_value is not None:
                        await self._send(sent_value)
                else:
                    next_value_avail.clear()
        except GeneratorExit:
            pass
        finally:
            await self._del_queue(next_value_avail)

    def push(self, value):
        """Public api to push a value."""
        assert self._status == TEE_STATUS.STARTED
        if self._remove_none:
            if value is not None:
                self._push(value)
        else:
            self._push(value)

    def run(self):
        """Starts the source-consuming task."""
        agen = self.get_source_agen()
        self._run_fut = asyncio.ensure_future(self._run(agen), loop=self.loop)
        self._status = TEE_STATUS.STARTED
