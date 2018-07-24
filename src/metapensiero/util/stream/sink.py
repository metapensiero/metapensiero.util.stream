# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- End-of-the-stream classes
# :Created:   mar 24 lug 2018 15:50:57 CEST
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import collections

from .dest import Destination


class Sink(Destination):
    """Given a source, it will pull any value out of it when its
    `.start()`:meth: is executed. The collected values are appended to
    the `.data`:attr: instance member.

    :param source: an *async generator* or a *callable* returning an *async
      generator* when called with no arguments
    """

    def __init__(self, source=None):
        super().__init__(source)
        """The recipient of the collected values"""
        self.data = collections.deque()

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    async def _destination(self, element):
        self.data.append(element)

    def clear(self):
        """Clear the data container."""
        self.data.clear()
