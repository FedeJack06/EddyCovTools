#!/usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import setup

__author__ = ['Federico Giacobbe']
__email__ = ['giacobbefederico6@gmail.com']

PACKAGE_NAME = 'EddyCovTools'
PACKAGE_VERSION = '0.0.1'
DESCRIPTION = 'Python tools to analyze and filter high sampling rate Sonic Anemometer and Thermohygrometer measurements. A clean way to build a database directly from station files and look at your data. Convert Campbell TOB3 file. Despiking method. Rotation-to-streamline methods. '
AUTHOR = 'Federico Giacobbe'
EMAIL = 'fedejek06@gmail.com'
REQUIRES_PYTHON = '>=3'
URL = 'https://github.com/FedeJack06/EddyCovariance_tools'
DOWNLOAD_URL = URL

setup(
  name=PACKAGE_NAME,
  version=PACKAGE_VERSION,
  description=DESCRIPTION,
  author=AUTHOR,
  author_email=EMAIL,
  python_requires=REQUIRES_PYTHON,
  install_requires=[],
  url=URL,
  download_url=DOWNLOAD_URL,
  setup_requires=[],
  packages=[
    PACKAGE_NAME,
  ],
  package_data={
    PACKAGE_NAME: [],
  },
  include_package_data=True,
  platforms='any',
  classifiers=[
    'Natural Language :: English',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: POSIX',
    'Operating System :: POSIX :: Linux',
    'Operating System :: Microsoft :: Windows',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: Implementation :: CPython',
    'Programming Language :: Python :: Implementation :: PyPy'
  ],
  entry_points={'console_scripts': [
    'mlboh = mlboh.__main__:main',
    ],
  },
)