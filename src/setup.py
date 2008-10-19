#!/usr/bin/python
"""
usage: /usr/bin/python setup.py py2app
"""

from distutils.core import setup
import py2app

setup(
	app=['mkvtops3mp4.py'],
	name="MKV to PS3 MP4",
)

