# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Transform class
# :Created:   mar 24 lug 2018 15:38:32 CEST
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import asyncio

from .abc import ExecPossibleAwaitable
from .single import SingleSourced


class Transformer(SingleSourced, ExecPossibleAwaitable):
    """A small utility class to alter a stream of values generated or sent
    to an async iterator."""

    def __init__(self, fyield=None, fsend=None, source=None):
        self._agen = None
        super().__init__(source)
        self.yield_func = fyield
        self.send_func = fsend

    def __aiter__(self):
        self.check_source()
        if self._agen is not None:
            raise RuntimeError("Already itered on")
        self._agen = self._gen(self.yield_func, self.send_func)
        return self._agen

    async def _gen(self, fyield=None, fsend=None):
        agen = self.get_source_agen()
        send_value = None
        try:
            while True:
                value = await agen.asend(send_value)
                if fyield is not None:
                    value = await self._exec_possible_awaitable(fyield, value)
                send_value = yield value
                if fsend and send_value is not None:
                    send_value = await self._exec_possible_awaitable(fsend,
                                                                     send_value)
        except StopAsyncIteration:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            self._agen = None

    @property
    def active(self):
        return self._agen is not None
