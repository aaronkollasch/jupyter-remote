#!/usr/bin/env python
from __future__ import unicode_literals

# Execute with
# $ python jupyter_remote/__main__.py (2.6+)
# $ python -m jupyter_remote          (2.7+)

import sys

if __package__ is None and not hasattr(sys, 'frozen'):
    # direct call of __main__.py
    import os.path
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))

from jupyter_remote import main

if __name__ == '__main__':
    sys.exit(main())
