# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- ABCs
# :Created:   mer 17 gen 2018 20:01:23 CET
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import abc
import inspect


class ExecPossibleAwaitable(abc.ABC):

    async def _exec_possible_awaitable(self, func, *args, **kwargs):
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result


class Pluggable(abc.ABC):
    """An ABC useful to recognize components that can be plugged
    together."""

    def __lshift__(self, other):
        self.plug(other)
        return other

    def plug(self, other):
        self._add_plugged(other)
        return self

    @abc.abstractmethod
    def _add_plugged(self, other):
        """Per class implementation of the plug behavior"""
