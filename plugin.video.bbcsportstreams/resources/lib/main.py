#  Copyright (c) 2022-2023 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams

import logging
import os
import json

import xbmc

from codequick import Route, Resolver, Listitem, Script, run
from codequick.support import logger_id, addon_data

from resources.lib.errors import *


logger = logging.getLogger(logger_id + '.main')
logger.critical('-------------------------------------')


USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0'

vers_info = xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Application.GetProperties", '
                                 '"params": {"properties": ["version"]}, "id": 1 }')
vers_info = json.loads(vers_info)
KODI_VERSION = vers_info['result']['version']['major']
xbmc.log(f'[SPORT_STREAMS] Kodi version = {KODI_VERSION}.', xbmc.LOGERROR)


@Route.register
def root(_):
    if KODI_VERSION > 20:
        url_fmt = 'https://ve-cmaf-push-uk-live.cf.md.bbci.co.uk/x=4/i=urn:bbc:pips:service:uk_sport_stream_{:02d}/pc_hd_abr_v2.mpd'
        handler = play_dash_live
    else:
        url_fmt = 'https://ve-hls-push-uk-live.cf.md.bbci.co.uk/x=4/i=urn:bbc:pips:service:uk_sport_stream_{:02d}/pc_hd_abr_v2.m3u8'
        handler = play_hls_live

    for i in range(1, 15):
        stream_name = 'Sport stream {}'.format(i)
        yield Listitem.from_dict(
            handler,
            stream_name,
            params={'channel': stream_name,
                    'url': url_fmt.format(i)})

    nums = ('one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine ', 'ten', 'eleven', 'twelve')
    for i in nums:
        stream_name = 'Red button {}'.format(nums.index(i) + 1)
        yield Listitem.from_dict(
            play_dash_live,
            stream_name,
            params={'channel': stream_name,
                    'url': ''.join(('https://vs-cmaf-pushb-uk.live.cf.md.bbci.co.uk/x=4/i=urn:bbc:pips:service:red_button_',
                                   i, '/pc_hd_abr_v2.mpd'))
                    })

def create_stream_item(name, manifest_url, protocol='hls', resume_time=None):
    # noinspection PyImport,PyUnresolvedReferences
    import inputstreamhelper
    logger.debug('dash manifest url: %s', manifest_url)


    is_helper = inputstreamhelper.Helper(protocol)
    if not is_helper.check_inputstream():
        logger.warning('No inputstream handler available for stream type %s', protocol)
        return

    play_item = Listitem()
    play_item.label = name
    play_item.set_path(manifest_url, is_playable=True)

    play_item.listitem.setContentLookup(True)
    # play_item.listitem.setMimeType('application/dash+xml')

    play_item.property['inputstream'] = is_helper.inputstream_addon
    play_item.property['inputstream.adaptive.manifest_type'] = protocol
    # play_item.property['inputstream.adaptive.play_timeshift_buffer'] = 'true'
    # play_item.property['inputstream.adaptive.manifest_update_parameter'] = 'full'
    play_item.property['inputstream.adaptive.stream_headers'] = ''.join((
            'User-Agent=',
            USER_AGENT,
            '&Referer=https://emp.bbc.co.uk/&'
            'Origin=https://emp.bbc.co.uk&'
            'Sec-Fetch-Dest=empty&'
            'Sec-Fetch-Mode=cors&'
            'Sec-Fetch-Site=same-site&'))
    return play_item


@Resolver.register
def play_hls_live(_, channel, url):
    logger.info('play live stream - channel=%s, url=%s', channel, url)
    list_item = create_stream_item(channel, url, resume_time='43200')
    # if list_item:
    #     list_item.property['inputstream.adaptive.manifest_update_parameter'] = 'full'
    return list_item


@Resolver.register
def play_dash_live(_, channel, url):
    logger.info('play live dash stream - channel=%s, url=%s', channel, url)
    list_item = create_stream_item(channel, url, protocol='mpd', resume_time='43200')
    # if list_item:
    #     list_item.property['inputstream.adaptive.manifest_update_parameter'] = 'full'
    return list_item

