#  Copyright (c) 2023-2026 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams

from __future__ import annotations
import time
import xbmc
from datetime import datetime
from xbmcvfs import translatePath
import xbmcaddon


loglevel = xbmc.LOGDEBUG


def create_addon_info(addon_id=None):
    if addon_id:
        addon = xbmcaddon.Addon(addon_id)
    else:
        addon = xbmcaddon.Addon()
        global loglevel
        loglevel = addon.getSettingInt('log-level')
    return {
        "name": addon.getAddonInfo("name"),
        "id": addon.getAddonInfo("id"),
        "addon": addon,
        "language": addon.getLocalizedString,
        "version": addon.getAddonInfo("version"),
        "path": addon.getAddonInfo("path"),
        "profile": translatePath(addon.getAddonInfo('profile')),
    }


addon_info = create_addon_info()


def log(level, message, *args, **kwargs):
    if level < loglevel:
        return
    xbmc_lvl = xbmc.LOGDEBUG
    xbmc.log('[BBC Sportstreams] ' + message.format(*args, **kwargs), xbmc_lvl)


def log_debug(msg, *args, **kwargs):
    log(xbmc.LOGDEBUG, msg, *args, **kwargs)


def log_info(msg, *args, **kwargs):
    log(xbmc.LOGINFO, msg, *args, **kwargs)


def log_warning(msg, *args, **kwargs):
    log(xbmc.LOGWARNING, msg, *args, **kwargs)


def log_error(msg, *args, **kwargs):
    log(xbmc.LOGERROR, msg, *args, **kwargs)


def is_hevc_enabled():
    has_hevc = getattr(is_hevc_enabled, '_has_hevc', None)
    if has_hevc is None:
        has_hevc = is_hevc_enabled._has_hevc = addon_info['addon'].getSettingBool('hevc_enabled')
    return has_hevc


def iso_duration_2_seconds(iso_str: str) -> int | None:
    """Convert an ISO 8601 duration string into seconds.

    A simple parser to match durations found in films and tv episodes.
    Handles only hours, minutes and seconds.

    """
    if iso_str is None:
        return None
    try:
        if len(iso_str) > 3:
            import re
            match = re.match(r'^PT(?:([\d.]+)H)?(?:([\d.]+)M)?(?:([\d.]+)S)?$', iso_str)
            if match:
                hours, minutes, seconds = match.groups(default=0)
                return int(float(hours) * 3600 + float(minutes) * 60 + float(seconds))
    except (ValueError, AttributeError, TypeError):
        pass

    log_warning("Invalid ISO8601 duration: '{}'", iso_str)
    return None


def seconds_2_iso_duration(secs: int | float):
    hrs, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    iso_duration = f'PT{int(hrs)}H{int(mins)}M{secs:.4g}S'
    return iso_duration


def strptime(dt_str: str, format: str):
    """A bug free alternative to `datetime.datetime.strptime(...)`"""
    return datetime(*(time.strptime(dt_str, format)[0:6]))
