

from unittest.mock import patch

import xbmc
import sys


def global_setup():
    xbmc.getInfoLabel = lambda label: '31.3.5' if label == 'System.BuildVersionShort' else ''
    if len(sys.argv) == 1:
        sys.argv.extend(('1', ))
