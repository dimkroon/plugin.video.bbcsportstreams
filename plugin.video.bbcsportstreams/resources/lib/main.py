#  Copyright (c) 2022-2026 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams
import json
import sys
import inspect
import xbmc
import xbmcgui

from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmcplugin
from resources.lib import utils
from resources.lib.cache import file_cache


USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0'


kodi_version = int(xbmc.getInfoLabel('System.BuildVersionShort').split('.')[0])
utils.log_debug('Kodi version major = {}', kodi_version)
plugin_handle = int(sys.argv[1])
# utils.log_warning("sys args = {}".format(sys.argv))

supports_mpd = True  # kodi_version > 20


@file_cache('channelcache.json', max_age=300, check_key=utils.is_hevc_enabled())
def root():
    service_ids = ['red_button_one']

    # main streams
    for i in range(1, 101):
        service_ids.append(f'uk_bbc_stream_{i:03d}')


    def worker(service_id):
        try:
            return process_service(service_id)
        except:
            return None

    ordered = [None] * len(service_ids)

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {
            executor.submit(worker, service_id): idx
            for idx, service_id in enumerate(service_ids)
        }

        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                ordered[idx] = future.result()
            except:
                ordered[idx] = None

    return [res for res in ordered if res]



def fetch_data(service_id: str):
    base_url = 'https://ess.api.bbci.co.uk/schedules'
    params = urlencode({'serviceId': service_id})
    url = f"{base_url}?{params}"

    try:
        with urlopen(url, timeout=1) as response:
            raw_data = response.read().decode('utf-8')
            return json.loads(raw_data)
    except Exception:
        return None


def url_is_up(url):
    try:
        req = Request(url, method='HEAD')
        with urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_current_item(data):
    if data:
        def parse(ts):
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))

        now = datetime.now(timezone.utc)
        return next(
            (
                item for item in data['items']
                if parse(item['published_time']['start']) <= now < parse(item['published_time']['end'])
            ),
            None
        )
    return None


def build_url(callb, params):
    if isinstance(callb, str):
        params['callb'] = callb
    else:
        params['callb'] = callb.__name__
    qs = urlencode(params)
    return 'plugin://{}?{}'.format(utils.addon_info['id'], qs)


def main_menu():
    xbmcplugin.setContent(plugin_handle, 'tvshows')
    for item in root():
        li = xbmcgui.ListItem(item['channel'])
        li.setProperty('IsPlayable', 'true')
        if kodi_version < 20:
            li.setProperties({'resumetime': '0',
                              'totaltime': 3600})
            li.setInfo('video', {'playcount': '0'})
        else:
            inf_tag = li.getVideoInfoTag()
            inf_tag.setResumePoint(0)
            inf_tag.setPlaycount(0)
        xbmcplugin.addDirectoryItem(
            plugin_handle,
            build_url(item['callback'], item['params']),
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

    headers = ''.join((
        'User-Agent=', USER_AGENT,
        '&Referer=https://emp.bbc.co.uk/&'
        'Origin=https://emp.bbc.co.uk&'
        'Sec-Fetch-Dest=empty&'
        'Sec-Fetch-Mode=cors&'
        'Sec-Fetch-Site=same-site&'))

    play_item.setProperties({
        'inputstream': is_helper.inputstream_addon,
        'inputstream.adaptive.manifest_type': protocol})

    xbmcplugin.setResolvedUrl(plugin_handle, True, play_item)
    if proxy_server:
        # Ensure the proxy stops, no matter what.
        xbmc.Monitor().waitForAbort(10)
        proxy_server.stop_server()


def get_url(pid):
    hevc_enabled = utils.is_hevc_enabled()
    encoding = 'h265' if hevc_enabled else 'h264'
    media_sets = ['iptv-native-hd']

    if supports_mpd and hevc_enabled:
        media_sets.append('iptv-uhd')

    transfer_format = 'dash' if supports_mpd else 'hls'

    base_url = 'https://open.live.bbc.co.uk/mediaselector/6/select/version/3.0/mediaset/{}/cvid/urn:bbc:pips:pid:{}/format/json/cors/1'

    for media_set in media_sets:
        try:
            with urlopen(base_url.format(media_set, pid), timeout=1) as response:
                json_data = json.loads(response.read().decode("utf-8"))
                for media in json_data['media']:
                    if media['encoding'] == encoding:
                        for connection in media['connection']:
                            if connection['protocol'] == 'https':
                                if connection['transferFormat'] == transfer_format:
                                    url = connection['href']
                                    return url
        except Exception:
            pass
    return None


def process_service(service_id):
    data = fetch_data(service_id)
    item = get_current_item(data)
    if not item:
        return None

    is_uk_bbc_stream = 'uk_bbc_stream_' in service_id
    pid = item['version']['id'] if is_uk_bbc_stream else service_id

    name = data['service']['name'] + ' - '
    brand_title = item['brand']['title']
    if brand_title == 'no_brand_title':
        brand_title = ''
    episode_title = item['episode']['title']
    name += ': '.join(filter(None, [brand_title, episode_title]))

    url = get_url(pid)
    if url:
        filename = url.rsplit("/", 1)[-1]
        if filename and "uhd" in filename:
            name += ' (UHD)'
        return {
            'callback': 'play_live',
            'channel': name,
            'params': {
                'channel': name,
                'url': url
            }
        }
    return None


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
    except:
        import traceback
        utils.log_error("Unhandled exception:\n{}", traceback.format_exc())
        xbmcplugin.endOfDirectory(plugin_handle, False)
