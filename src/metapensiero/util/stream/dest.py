# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- end-of-the-stream base class
# :Created:   mar 24 lug 2018 16:51:22 CEST
# :Author:     <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import abc
import asyncio
import contextlib
import logging

from .abc import ExecPossibleAwaitable
from .single import SingleSourced


logger = logging.getLogger(__name__)


class Destination(SingleSourced, ExecPossibleAwaitable):

    def __init__(self, source=None):
        super().__init__(source)
        self._run_fut = None
        self.started = None

    @abc.abstractmethod
    async def _destination(self, element):
        """Do something with each value pulled by the source."""

    async def _run(self):
        send_value = None
        try:
            agen = self.get_source_agen()
            self.started.set_result(None)
        except Exception as e:
            self.started.set_exception(e)
        try:
            while True:
                value = await agen.asend(send_value)
                send_value = await self._destination(value)
        except StopAsyncIteration:
            pass
        except asyncio.CancelledError:
            await agen.aclose()
        except Exception:
            logger.exception('Error in agen stream')
            raise
        finally:
            self.active = False

    async def start(self):
        self.check_source()
        if not self.active and not self._run_fut:
            self.active = True
            loop = asyncio.get_event_loop()
            self.started = loop.create_future()
            self._run_fut = asyncio.ensure_future(self._run())
            await self.started

    async def stop(self):
        if self.active and self._run_fut:
            self._run_fut.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._run_fut
