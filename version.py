# -*- coding: utf-8 -*-
"""The version number, in one place.

⚠️ It used to live in build.py alone, which meant the running program did
not know its own version -- and a program that cannot say which version it
is cannot tell whether a newer one exists. build.py, the Windows resource,
the installer and the update check all read it from here.
"""
from __future__ import unicode_literals

VERSION = "1.2.1"
