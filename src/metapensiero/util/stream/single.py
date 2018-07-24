# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- single source base class
# :Created:   mar 24 lug 2018 14:40:33 CEST
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import collections

from .abc import Pluggable


class SingleSourced(Pluggable):
    """A base class for stream classes that have only one source."""

    active = False
    _source = None

    def __init__(self, source=None):
        self.source = source

    def _add_plugged(self, other):
        self.source = other

    def check_source(self):
        if self._source is None:
            raise RuntimeError("Undefined source")

    def get_source_agen(self):
        return self.get_agen(self._source)

    def get_agen(self, factory):
        self.check_source()
        if isinstance(factory, collections.abc.AsyncIterable):
            result = factory.__aiter__()
        else:
            result = factory()
        assert isinstance(result, collections.abc.AsyncGenerator)
        return result

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        if value is self._source:
            return
        if self.active:
            raise RuntimeError("Cannot set the source while active")
        if not (isinstance(value, collections.abc.AsyncIterable) or
                callable(value)):
            raise RuntimeError("The source must be and async iterable or a "
                               "callable returning an async generator")
        self._source = value
