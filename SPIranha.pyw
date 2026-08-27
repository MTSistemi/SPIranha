# -*- coding: utf-8 -*-
"""Avvio senza finestra nera: doppio clic su questo file.

Start without a console window: double-click this file.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
