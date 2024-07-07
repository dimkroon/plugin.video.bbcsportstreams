#!/usr/bin/python

import xbmc
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
        "profile": translatePath(addon.getAddonInfo('profile'))
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
