# -*- coding: utf-8 -*-
# :Project:   metapensiero.util.stream -- Utility classes for asynchronous streams
# :Created:   Wed 17 Jan 2018 19:44:33 CET
# :Author:    Alberto Berti <alberto@metapensiero.it>
# :License:   GNU General Public License version 3 or later
# :Copyright: © 2018 Alberto Berti
#

import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.rst'), encoding='utf-8') as f:
    CHANGES = f.read()
with open(os.path.join(here, 'version.txt'), encoding='utf-8') as f:
    VERSION = f.read().strip()

setup(
    name="metapensiero.util.stream",
    version=VERSION,
    url="https://gitlab.com/metapensiero/metapensiero.util.stream",

    description="Utility classes for asynchronous streams",
    long_description=README + '\n\n' + CHANGES,

    author="Alberto Berti",
    author_email="alberto@metapensiero.it",

    license="GPLv3+",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        ],
    keywords="",

    packages=['metapensiero.util.' + pkg
              for pkg in find_packages('src/metapensiero/util')],
    package_dir={'': 'src'},
    namespace_packages=['metapensiero', 'metapensiero.util'],

    install_requires=['setuptools'],
    extras_require={
        'dev': [
            'metapensiero.tool.bump_version',
            'readme_renderer',
        ]
    },
)
