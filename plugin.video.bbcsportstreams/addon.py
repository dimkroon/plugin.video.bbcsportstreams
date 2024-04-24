
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams

import sys

from xbmcplugin import endOfDirectory
from codequick import support
from resources.lib import applog
from resources.lib import main
from resources.lib import cc_patch


cc_patch.patch_cc_route()
cc_patch.patch_label_prop()


if __name__ == '__main__':
    if isinstance(main.run(), Exception):
        endOfDirectory(int(sys.argv[1]), False)
    applog.shutdown_log()
