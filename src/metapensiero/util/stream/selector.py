# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Selector class
# :Created:   mer 17 gen 2018 20:09:20 CET
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import asyncio
import collections
from contextlib import suppress
import enum
import functools


SELECTOR_STATUS = enum.IntEnum('SelectorStatus',
                               'INITIAL STARTED STOPPED CLOSED')
STOPPED_TOKEN = object()


class Selector:
    """An object that accepts multiple async iterables and *unifies*
    them. It is itself an async iterable.

    :param bool await_send: optional boolean used to signal if the
      selector machinery will always wait for a ``send`` value to be
      available from the consuming context when iterating over a
      source. By default if no value is available,``None`` will be
      sent in
    :param bool remove_none: optional boolean used to remove ``None``
      value from the stream
    """

    def __init__(self, *sources, loop=None, await_send=False,
                 remove_none=False):
        self.loop = loop or asyncio.get_event_loop()
        self._status = SELECTOR_STATUS.INITIAL
        self._sources = set(sources)
        self._result_avail = asyncio.Event(loop=self.loop)
        self._results = collections.deque()
        self._await_send = await_send
        self._remove_none = remove_none
        self._source_data = collections.defaultdict(dict)
        self._gen = None

    def __aiter__(self):
        """Async generator main interface, it isn't a coroutine, """
        if self._gen:
            raise RuntimeError('This Selector already has a consumer, there can'
                               ' be only one.')
        else:
            self._run()
            self._gen = g = self.gen()
        return g

    def _cleanup(self, source):
        self._source_status(source, SELECTOR_STATUS.STOPPED)
        data = self._source_data[source]
        if data['send_capable']:
            data['queue'].clear()
            data['send_event'].clear()
        all_stopped = all(sd['status'] == SELECTOR_STATUS.STOPPED for sd in
                          self._source_data.values())
        if all_stopped:
            self._push(STOPPED_TOKEN)

    async def _iterate_source(self, source, agen, send_value_avail=None,
                              queue=None):
        self._source_status(source, SELECTOR_STATUS.STARTED)
        send_capable = queue is not None
        send_value = None
        try:
            while True:
                if send_capable:
                    el = await agen.asend(send_value)
                else:
                    el = await agen.__anext__()
                self._push(el)
                if send_capable:
                    if self._await_send:
                        await send_value_avail.wait()
                        send_value = queue.popleft()
                        if len(queue) == 0:
                            send_value_avail.clear()
                    else:
                        if len(queue) > 0:
                            send_value = queue.popleft()
                        else:
                            send_value = None
        except StopAsyncIteration:
            pass
        except asyncio.CancelledError:
            await agen.aclose()
            raise
        except GeneratorExit:
            pass
        except Exception as e:
            self._push(e)
        finally:
            self._cleanup(source)

    def _push(self, el):
        """Check the result of the future. If the exception is an instance of
        ``StopAsyncIteration`` it means that the corresponding source
        is exhausted.

        The exception is not raised here because it will be
        swallowed. Instead it is raised on the :meth:`gen` method."""
        if self._remove_none:
            if el is not None:
                self._results.append(el)
                self._result_avail.set()
        else:
            self._results.append(el)
            self._result_avail.set()

    def _remove_stopped_source(self, source,  stop_fut):
        if source in self._source_data:
            del self._source_data[source]
        self._sources.remove(source)

    def _run(self):
        """For every registered source, start a pulling coroutine."""
        for s in self._sources:
            self._start_source_loop(s)
        self._status = SELECTOR_STATUS.STARTED

    def _send(self, value):
        assert value is not None
        for sd in self._source_data.values():
            queue = sd['queue']
            event = sd['send_event']
            if queue is not None:
                queue.append(value)
                event.set()

    def _source_status(self, source, status=None):
        if status:
            self._source_data[source]['status'] = status
        else:
            status = self._source_data[source]['status']
        return status

    def _start_source_loop(self, source):
        """Start a coroutine that will pull (and send, if it's the case) data
        from (and into) a given source using async iteration protocol.
        """
        if hasattr(source, '__aiter__'):
            agen = source.__aiter__()
        else:
            assert callable(source)
            agen = source()
        is_new = source not in self._source_data
        self._source_status(source, SELECTOR_STATUS.INITIAL)
        if is_new:
            send_capable = hasattr(agen, 'asend')
            self._source_data[source]['send_capable'] = send_capable
            if send_capable:
                queue = collections.deque()
                send_value_avail = asyncio.Event(loop=self.loop)
            else:
                send_value_avail, queue = None, None
            self._source_data[source]['queue'] = queue
            self._source_data[source]['send_event'] = send_value_avail
        else:
            queue = self._source_data[source]['queue']
            send_value_avail = self._source_data[source]['send_event']

        source_fut = asyncio.ensure_future(
            self._iterate_source(source, agen, send_value_avail, queue),
            loop=self.loop)
        self._source_data[source]['task'] = source_fut

    async def _stop(self):
        """Stop pulling data from every registered source."""
        for s, data in self._source_data.items():
            await self._stop_iteration_on(s)
        self._gen = None
        self._results.clear()
        self._result_avail.clear()
        self._status = SELECTOR_STATUS.STOPPED

    async def _stop_iteration_on(self, source):
        """Stop pulling from a single source."""
        if self._status > SELECTOR_STATUS.INITIAL:
            data = self._source_data[source]
            if data['status'] == SELECTOR_STATUS.STARTED:
                data['task'].cancel()
            with suppress(asyncio.CancelledError):
                await data['task']
            data['task'] = None

    def add(self, source):
        """Add a new source to the group of those followed."""
        if source not in self._sources:
            self._sources.add(source)
            if self._status == SELECTOR_STATUS.STARTED:
                self._start_source_loop(source)

    async def gen(self):
        assert self._status == SELECTOR_STATUS.STARTED
        """Produce the values iterated by the consumer of the Selector
        instance."""
        try:
            while await self._result_avail.wait():
                if len(self._results):
                    v = self._results.popleft()
                    if v == STOPPED_TOKEN:
                        break
                    elif isinstance(v, Exception):
                        raise v
                    else:
                        sent_value = yield v
                    if sent_value is not None:
                        self._send(sent_value)
                else:
                    self._result_avail.clear()
        finally:
            await self._stop()

    def remove(self, source):
        if source in self._sources:
            stop_fut = asyncio.ensure_future(self._stop_iteration_on(source),
                                             loop=self.loop)
            stop_fut.add_done_callback(
                functools.partial(self._remove_stopped_source, source))
