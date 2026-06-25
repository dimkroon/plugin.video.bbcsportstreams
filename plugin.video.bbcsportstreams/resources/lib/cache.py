#  Copyright (c) 2026 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams

import time
import json
import os
from typing import Generator
from json import JSONDecodeError
from functools import wraps

from resources.lib import utils


class FileCache:
    def __init__(self, file_name):
        self._data_file = os.path.join(utils.addon_info['profile'], file_name)

    def set(self, data, check_key=None):
        cache_data = (time.time(), data, check_key)
        with open(self._data_file, 'w') as f:
            json.dump(cache_data, f)

    def get(self, max_age, check_key=None):
        try:
            with open(self._data_file, 'r') as f:
                cache_time, data, key = json.load(f)
                if cache_time + max_age > time.time() and check_key == key:
                    return data
        except (OSError, JSONDecodeError, ValueError) as err:
            utils.log_warning('Error reading cache: {!r}', err)
        return None


def file_cache(file_name: str, max_age: int, check_key=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = FileCache(file_name)
            data = cache.get(max_age, check_key)
            if data:
                utils.log_info('Cache HIT')
            else:
                utils.log_info('Cache MISS')
                data = func(*args, **kwargs)
                if isinstance(data, Generator):
                    data = list(data)
                cache.set(data, check_key)
            return data
        return wrapper
    return decorator
