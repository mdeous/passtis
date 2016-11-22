#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup

import passtis

CURDIR = os.path.realpath(os.path.dirname(__file__))

with open(os.path.join(CURDIR, 'README.md')) as ifile:
    README = ifile.read()

with open(os.path.join(CURDIR, 'requirements.txt')) as ifile:
    REQUIREMENTS = []
    for line in ifile:
        line = line.strip()
        if line:
            REQUIREMENTS.append(line)

setup(
    name='Passtis',
    version=passtis.__version__,
    description=' GnuPG-based command line password manager',
    long_description=README,
    author='Mathieu D. (MatToufoutu)',
    author_email='mattoufootu@gmail.com',
    url='TBD',
    zip_safe=False,
    license='GPLv3',
    keywords='pass passwd password password-manager gpg gnupg',
    install_requires=REQUIREMENTS,
    py_modules=['passtis'],
    entry_points={
        'console_scripts': ['passtis = passtis:main']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: Unix',
        'Operating System :: MacOS',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ]
)
