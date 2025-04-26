#  Copyright (c) 2022-2023 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams
import sys
import inspect
import xbmc
import xbmcgui
from urllib.parse import parse_qsl, urlencode

import xbmcplugin
from resources.lib import utils


USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0'


kodi_version = int(xbmc.getInfoLabel('System.BuildVersionShort').split('.')[0])
utils.log_debug('Kodi version major = {}', kodi_version)
plugin_handle = int(sys.argv[1])
# utils.log_warning("sys args = {}".format(sys.argv))

def root():
    if kodi_version > 20:
        url_fmt = ('https://ve-cmaf-push-uk.live.fastly.md.bbci.co.uk/x=4/i=urn:bbc:pips:service:'
                   'uk_bbc_stream_{:03d}/pc_hd_abr_v2.mpd')
        handler = play_dash_live
    else:
        url_fmt = ('https://ve-hls-push-uk.live.cf.md.bbci.co.uk/x=4/i=urn:bbc:pips:service:'
                   'uk_bbc_stream_{:03d}/pc_hd_abr_v2.m3u8')
        handler = play_hls_live

    nums = ('one', 'two')
    for i in nums:
        stream_name = 'Red button {}'.format(nums.index(i) + 1)
        yield {
            'callback': play_dash_live,
            'channel': stream_name,
            'params': {
                'channel': stream_name,
                'url': ''.join(('https://vs-cmaf-pushb-uk.live.cf.md.bbci.co.uk/x=4/i=urn:bbc:pips:service:red_button_',
                                i, '/pc_hd_abr_v2.mpd'))
                }
        }

    for i in range(1, 101):
        stream_name = 'Sport stream {}'.format(i)
        yield {
            'callback': handler,
            'channel': stream_name,
            'params': {'channel': stream_name,
                       'url': url_fmt.format(i)}
        }


def build_url(callb, params):
    params['callb'] = callb.__name__
    qs = urlencode(params)
    return 'plugin://{}?{}'.format(utils.addon_info['id'], qs)


def main_menu():
    xbmcplugin.setContent(plugin_handle, 'tvshows')
    for item in root():
        li = xbmcgui.ListItem(item['channel'])
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(
            plugin_handle,
            build_url(item['callback'], item['params']),
            li,
            isFolder=False,
        )


def create_stream_item(name, manifest_url, protocol='hls', resume_time=None):
    # noinspection PyImport,PyUnresolvedReferences

    import inputstreamhelper
    utils.log_debug('dash manifest url: {}', manifest_url)

    is_helper = inputstreamhelper.Helper(protocol)
    if not is_helper.check_inputstream():
        utils.log_warning('No inputstream handler available for stream type {}', protocol)
        return

    play_item = xbmcgui.ListItem(name, path=manifest_url)
    play_item.setContentLookup(False)
    if protocol == 'hls':
        play_item.setMimeType('application/vnd.apple.mpegurl')
    else:
        play_item.setMimeType('application/dash+xml')

    headers = ''.join((
        'User-Agent=', USER_AGENT,
        '&Referer=https://emp.bbc.co.uk/&'
        'Origin=https://emp.bbc.co.uk&'
        'Sec-Fetch-Dest=empty&'
        'Sec-Fetch-Mode=cors&'
        'Sec-Fetch-Site=same-site&'))

    play_item.setProperties({
        'inputstream': is_helper.inputstream_addon,
        'inputstream.adaptive.manifest_type': protocol,
        'inputstream.adaptive.stream_headers': headers,
        'inputstream.adaptive.manifest_headers': headers})

    xbmcplugin.setResolvedUrl(plugin_handle, True, play_item)


def play_hls_live(channel, url):
    utils.log_info('play live stream - channel={}, url={}', channel, url)
    create_stream_item(channel, url, resume_time='43200')


def play_dash_live(channel, url):
    utils.log_info('play live dash stream - channel={}, url={}', channel, url)
    create_stream_item(channel, url, protocol='mpd', resume_time='43200')


def run():
    try:
        qs = sys.argv[2][1:]
        params = dict(parse_qsl(qs))
        func_name = params.pop('callb', None)
        funcs = {name: member for name, member in inspect.getmembers(sys.modules[__name__])
                 if (inspect.isfunction(member))}
        callb = funcs.get(func_name)
        if callb:
            callb(**params)
        else:
            main_menu()
        xbmcplugin.endOfDirectory(plugin_handle)
    except:
        import traceback
        utils.log_error("Unhandled exception:\n{}", traceback.format_exc())
        xbmcplugin.endOfDirectory(plugin_handle, False)
