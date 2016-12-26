from setuptools import setup
from os import path
import re

here = path.abspath(path.dirname(__file__))


# Parse version
with open(path.join(here, 'easyquizz', '__init__.py')) as f:
    m = re.search('^__version_info__ *= *\(([0-9]+), *([0-9]+)\)', f.read(), re.MULTILINE)
    version = '.'.join(m.groups())

install_requires = ['tornado']
description = 'Interactive quizz engine using websockets'

setup(
    name='easyquizz',
    packages=['easyquizz'],
    # Do not filter out packages because we need the whole thing during `sdist`.

    install_requires=install_requires,

    package_data =
    {'':['static/*/*','static/*','static/*/*/*', 'static/*/*/*/*']},

    version=version,


    description=description,

    long_description=description,

    url='https://github.com/folfure/easyquizz',

    author='Olivier Feys',
    author_email='olivier.feys@gmail.com',

    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: End Users/Desktop',
        'Topic :: Games/Entertainment',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2.7',
    ],

    keywords='easyquizz websocket tornado',
)