#  Copyright (c) 2022-2026 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams

from __future__ import annotations
import json
import sys
import inspect
import xbmc
import xbmcgui

import requests
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode
from concurrent import futures

import xbmcplugin
from resources.lib import utils
from resources.lib.cache import file_cache


USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0'


kodi_version = int(xbmc.getInfoLabel('System.BuildVersionShort').split('.')[0])
utils.log_debug('Kodi version major = {}', kodi_version)
plugin_handle = int(sys.argv[1])
# utils.log_warning("sys args = {}".format(sys.argv))

supports_mpd = True  # kodi_version > 20


@file_cache('channelcache.json',
            max_age=300,
            check_key=str(utils.is_hevc_enabled()) + utils.addon_info['version'])
def root():
    service_ids = ['red_button_one']
    local_tz = utils.local_tz()

    # main streams
    for i in range(1, 101):
        service_ids.append(f'uk_bbc_stream_{i:03d}')

    with futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_results = [executor.submit(process_service, service_id, local_tz) for service_id in service_ids]
        futures.wait(future_results)

    results = (res.result() for res in future_results)
    return [res for res in results if res]


def fetch_schedule(service_id: str):
    resp = requests.get('https://ess.api.bbci.co.uk/schedules',
                        params={'serviceId': service_id},
                        timeout=1)
    if resp.status_code == 200:
        return json.loads(resp.content)
    else:
        return {}


def url_is_up(url):
    resp = requests.head(url)
    return resp.status_code == 200


def current_programmes(schedule_data):
    if not schedule_data:
        return

    now = datetime.now(timezone.utc)

    for pgm in schedule_data['items']:
        publish_time = pgm['published_time']
        end_t = datetime.fromisoformat(publish_time['end'].replace('Z', '+00:00'))
        if end_t > now:
            start_t = datetime.fromisoformat(publish_time['start'].replace('Z', '+00:00'))
            pgm['published_time'] = {'start': start_t, 'end': end_t}
            if pgm['brand']['title'] == 'no_brand_title':
                pgm['brand']['title'] = ''
            yield pgm


def callback_url(callb, params):
    if isinstance(callb, str):
        params['callb'] = callb
    else:
        params['callb'] = callb.__name__
    qs = urlencode(params)
    return 'plugin://{}?{}'.format(utils.addon_info['id'], qs)


def main_menu():
    xbmcplugin.setContent(plugin_handle, 'episodes')
    xbmcplugin.addSortMethod(plugin_handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(plugin_handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    for item in root():
        li = xbmcgui.ListItem(item['title'])
        li.setProperty('IsPlayable', 'true')
        if kodi_version < 20:
            li.setProperties({'resumetime': '0',
                              'totaltime': '3600'})
            li.setInfo('video', {'playcount': '0',
                                 'plot': item['description']})
        else:
            inf_tag = li.getVideoInfoTag()
            inf_tag.setResumePoint(0)
            inf_tag.setPlaycount(0)
            inf_tag.setPlot(item['description'])
        xbmcplugin.addDirectoryItem(
            plugin_handle,
            callback_url(item['callback'], item['params']),
            li,
            isFolder=False,
        )


def create_stream_item(name, manifest_url, resume_time=None):
    # noinspection PyImport,PyUnresolvedReferences

    import inputstreamhelper
    utils.log_debug('dash manifest url: {}', manifest_url)
    protocol = 'mpd' if 'mpd' in manifest_url else 'hls'
    is_helper = inputstreamhelper.Helper(protocol)
    if not is_helper.check_inputstream():
        utils.log_warning('No inputstream handler available for stream type {}', protocol)
        return

    play_item = xbmcgui.ListItem(name, path=manifest_url)
    play_item.setContentLookup(False)
    proxy_server = None
    if protocol == 'hls':
        play_item.setMimeType('application/vnd.apple.mpegurl')
    else:
        play_item.setMimeType('application/dash+xml')
        if kodi_version < 22:
            from resources.lib.proxy import run_proxy
            proxy_address, proxy_server = run_proxy(manifest_url)
            play_item.setPath(proxy_address)

    play_item.setProperties({
        'inputstream': is_helper.inputstream_addon,
        'inputstream.adaptive.manifest_type': protocol})

    xbmcplugin.setResolvedUrl(plugin_handle, True, play_item)
    if proxy_server:
        # Ensure the proxy stops, no matter what.
        xbmc.Monitor().waitForAbort(10)
        proxy_server.stop_server()


def get_manifest_url(pid, strm_idx):
    hevc_enabled = utils.is_hevc_enabled()
    encoding = 'h265' if hevc_enabled else 'h264'
    media_sets = ['iptv-native-hd']

    if supports_mpd and hevc_enabled:
        # Sometimes the HD and UHD streams have the same pid.
        # If the stream is between 40 and 50 try UHD first.
        if 40 < strm_idx < 50:
            media_sets.insert(0, 'iptv-uhd')
        else:
            media_sets.append('iptv-uhd')

    transfer_format = 'dash' if supports_mpd else 'hls'

    base_url = ('https://open.live.bbc.co.uk/mediaselector/6/select/version/3.0/mediaset/'
                '{}/cvid/urn:bbc:pips:pid:{}/format/json/cors/1')

    for media_set in media_sets:
        resp = requests.get(base_url.format(media_set, pid), timeout=1)
        if resp.status_code == 404:
            continue
        if (resp.status_code == 403
            and json.loads(resp.content).get('result') == 'geolocation'):
                raise GeoBLockError
        resp.raise_for_status()

        try:
            json_data = json.loads(resp.content)
            for media in json_data['media']:
                if media['encoding'] == encoding:
                    for connection in media['connection']:
                        if connection['protocol'] == 'https':
                            if connection['transferFormat'] == transfer_format:
                                url = connection['href']
                                return url
        except (json.JSONDecodeError, KeyError) as err:
            utils.log_error(f"Error parsing media selector for pid '{pid}', "
                            f"strm_idx '{strm_idx}', media_set '{media_set}' : {err}")
    return None


def process_service(service_id, local_timezone):
    schedule_data = fetch_schedule(service_id)
    programme_data = list(current_programmes(schedule_data))
    if not programme_data:
        return None

    cur_pgm = programme_data[0]
    is_uk_bbc_stream = 'uk_bbc_stream_' in service_id
    pid = cur_pgm['version']['id'] if is_uk_bbc_stream else service_id

    chan_name = schedule_data['service']['name']
    brand_title = cur_pgm['brand']['title']
    episode_title = cur_pgm['episode']['title']
    title = ': '.join(filter(None, [brand_title, episode_title]))

    url = get_manifest_url(pid, int(service_id[-3:] if is_uk_bbc_stream else 0))
    if not url:
        return None

    filename = url.rsplit("/", 1)[-1]
    is_uhd = "uhd" in filename

    def pgm_info():
        for pgm in programme_data:
            yield ''. join(('[B][COLOR orange]',
                            pgm['published_time']['start'].astimezone(local_timezone).strftime('%H:%M'),
                            '  ',
                            pgm['brand']['title'],
                            '[/COLOR][/B]'))
            yield pgm['episode']['title']

    description = '\n'.join((chan_name, '[B]UHD[/B]' if is_uhd else '',
                             *(line for line in pgm_info())))

    return {
        'callback': 'play_live',
        'description': description,
        'title': title + ' (UHD)' if is_uhd else title,
        'params': {
            'channel': chan_name,
            'url': url
        }
    }



def play_live(channel, url):
    utils.log_info('play {}', channel)
    create_stream_item(channel, url, resume_time='43200')


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
        xbmcplugin.endOfDirectory(plugin_handle, cacheToDisc=False)
    except Exception as err:
        import traceback
        utils.log_error("Unhandled exception:\n{}", traceback.format_exc())
        xbmcgui.Dialog().notification('BBC Sport Streams', str(err), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(plugin_handle, False)


class GeoBLockError(RuntimeError):
    def __init__(self, message: str | None = None):
        if not message:
            message = "BBC streams are available only in the UK."
        super().__init__(message)