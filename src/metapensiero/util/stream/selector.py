# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Selector class
# :Created:   mer 17 gen 2018 20:09:20 CET
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import asyncio
import collections
import contextlib
import enum
import functools


SELECTOR_STATUS = enum.IntEnum('SelectorStatus',
                               'INITIAL STARTED STOPPED CLOSED')
STOPPED_TOKEN = object()


class FutureValue:
    """An awaitable containing a discrete value. The interface it's the
    same as asyncio.Event but `.set()`:meth: supports an optional ``value``
    parameter. `.wait()`:meth: will return the set value.

    :param loop: optional *asyncio* event loop
    """

    def __init__(self, loop=None):
        if loop is None:
            self.loop = loop = asyncio.get_event_loop()
        self._event = asyncio.Event(loop=loop)
        self._value = None

    def clear(self):
        self._value = None
        self._event.clear()

    def is_set(self):
        return self._event.is_set()

    def set(self, value=None):
        """Set the instance value.

        :param value: the value to set the instance to, defaults to None
        """
        self._value = value
        self._event.set()

    async def wait(self):
        """Wait for the value. It will return immediately if `.set()`:meth:
        has been called already."""
        await self._event.wait()
        return self._value


class Selector:
    """An object that accepts multiple async iterables and *merges*
    them. It is itself an async iterable.  It supports ``.asend()`` by
    forwarding that value to the source that has provided the last
    value.

    The sources can be async generators or callables returning one.

    :param bool yield_source: If True, instead of yielding just the
      values, the selector will yield a tuple (source, values)
    """

    def __init__(self, *sources, loop=None, yield_source=False):
        self.loop = loop or asyncio.get_event_loop()
        self._status = SELECTOR_STATUS.INITIAL
        self._sources = set(sources)
        self._result_avail = asyncio.Event(loop=self.loop)
        self._results = collections.deque()
        self._source_data = collections.defaultdict(dict)
        self._yield_source = yield_source
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
            data['send_value'].clear()
        all_stopped = all(sd['status'] is SELECTOR_STATUS.STOPPED for sd in
                          self._source_data.values())
        if all_stopped:
            self._push(None, STOPPED_TOKEN)

    async def _iterate_source(self, source, agen, send_value_cont=None):
        self._source_status(source, SELECTOR_STATUS.STARTED)
        send_capable = send_value_cont is not None
        send_value = None
        try:
            while True:
                if send_capable:
                    el = await agen.asend(send_value)
                else:
                    el = await agen.__anext__()
                self._push(source, el)
                if send_capable:
                    send_value = await send_value_cont.wait()
                    send_value_cont.clear()
        except StopAsyncIteration:
            pass
        except asyncio.CancelledError:
            await agen.aclose()
            raise
        except GeneratorExit:
            pass
        except Exception as e:
            self._push(source, e)
        finally:
            self._cleanup(source)

    def _push(self, source, el):
        """Check the result of the future. If the exception is an instance of
        ``StopAsyncIteration`` it means that the corresponding source
        is exhausted.

        The exception is not raised here because it will be
        swallowed. Instead it is raised on the :meth:`gen` method."""
        self._results.append((source, el))
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

    def _send(self, source, value):
        sd = self._source_data[source]
        send_value_cont = sd['send_value']
        if send_value_cont is not None:
            send_value_cont.set(value)

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
                send_value_cont = FutureValue(loop=self.loop)
            else:
                send_value_cont = None
            self._source_data[source]['send_value'] = send_value_cont
        else:
            send_value_cont = self._source_data[source]['send_value']

        source_fut = asyncio.ensure_future(
            self._iterate_source(source, agen, send_value_cont),
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
            if data['status'] is SELECTOR_STATUS.STARTED:
                data['task'].cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await data['task']
            data['task'] = None

    def add(self, source):
        """Add a new source to the group of those followed."""
        if source not in self._sources:
            self._sources.add(source)
            if self._status is SELECTOR_STATUS.STARTED:
                self._start_source_loop(source)

    async def gen(self):
        """Produce the values iterated by the consumer of the Selector
        instance."""
        assert self._status is SELECTOR_STATUS.STARTED
        try:
            while await self._result_avail.wait():
                if len(self._results):
                    source, v = self._results.popleft()
                    if v == STOPPED_TOKEN:
                        break
                    elif isinstance(v, Exception):
                        raise v
                    else:
                        if self._yield_source:
                            sent_value = yield (source, v)
                        else:
                            sent_value = yield v
                        self._send(source, sent_value)
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
