#  Copyright (c) 2026 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.bbcsportstreams

import requests
import threading
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

from resources.lib import utils


def modify_manifest(mpd: bytes, base_url: str) -> bytes:
    """Modify DASH manifest `mpd` in such a way that it's payable by ISA < 22."""
    root = ET.fromstring(mpd)
    # Register the default namespace to prevent ET from adding prefixes when writing.
    fq_tag_name = root.tag
    def_namespace = fq_tag_name[1:fq_tag_name.index('}')]
    ET.register_namespace('', def_namespace)
    # Define the base url, to avoid media requests being made to the proxy.
    url_elem = ET.Element('BaseURL')
    url_elem.text = base_url
    root.insert(0, url_elem)

    # Adjust timeshift buffer to prevent it having a starting point earlier than the stream's start time.
    # Note: The time format can vary slightly and can cause errors when parsed with fromisoformat()
    start_t = utils.strptime(root.attrib['availabilityStartTime'][:19], '%Y-%m-%dT%H:%M:%S')
    start_t = start_t.replace(tzinfo=timezone.utc)
    max_timeshift = (datetime.now(timezone.utc) - start_t).total_seconds()
    max_timeshift = max_timeshift // 60 * 60
    timeshift_buf = utils.iso_duration_2_seconds(root.attrib['timeShiftBufferDepth'])
    if timeshift_buf:
        new_ts_buf = min(max_timeshift, timeshift_buf)
    else:
        new_ts_buf = max_timeshift
    root.attrib['timeShiftBufferDepth'] = utils.seconds_2_iso_duration(new_ts_buf)

    new_mpd = ET.tostring(root, encoding='utf-8', xml_declaration=False)
    return new_mpd


class ProxyServer(HTTPServer):
    def __init__(self,
                 server_address,
                 request_handler_class,
                 mpd_url,
                 bind_and_activate=True):
        super().__init__(server_address, request_handler_class, bind_and_activate)
        self.mpd_url = mpd_url
        self._serv_thread = None

    def start_server(self):
        self._serv_thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._serv_thread.start()
        utils.log_info('[proxy] Proxy server started.')

    def stop_server(self, timeout=None):
        utils.log_info('[proxy] Stopping proxy server.')
        self.shutdown()
        if self._serv_thread:
            if self._serv_thread.is_alive():
                utils.log_debug('[proxy] Waiting for server thread to end.')
                self._serv_thread.join(timeout)
                utils.log_debug('[proxy] Proxy server has stopped.')
            else:
                utils.log_debug('[proxy] Server has already stopped.')
        else:
            utils.log_info('[proxy] Proxy server has not started yet.')

    def manifest_handled(self):
        """Called by a request handler when a manifest has been handled.

        Since only one manifest is requested at the start of the stream,
        the server can now shut down after the request is handled.

        """
        # noinspection PyAttributeOutsideInit
        self._BaseServer__shutdown_request = True


class ProxyRequestHandler(BaseHTTPRequestHandler):
    def __init__(self,
                 request,
                 client_address,
                 server: ProxyServer):
        super().__init__(request, client_address, server)
        self.protocol_version = 'HTTP/1.1'

    def do_GET(self):
        # path, qs = self.path.rsplit('?', 1)  # Path with parameters received from request e.g. "/manifest?id=234324"
        utils.log_debug('[proxy] HTTP GET Request received to {}.', self.path)
        # noinspection PyBroadException
        try:
            if self.path == '/bbcsportstream/manifest.mpd':
                self._send_manifest()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception:
            import traceback
            utils.log_error('[proxy] Error handling request "{}":\n{}', self.path, traceback.format_exc())
            self.send_response(500)
            self.end_headers()

    def _send_manifest(self):
        # noinspection PyUnresolvedReferences
        url = self.server.mpd_url
        utils.log_debug('[proxy] Upstream manifest url = "{}".', url)
        resp = requests.get(url)
        status_code = resp.status_code
        self.send_response(status_code)
        if status_code != 200:
            self.end_headers()
            return None
        utils.log_info('[proxy] Received manifest from upstream server.')
        base_url = url.rsplit('/', 1)[0]
        utils.log_debug("[proxy] Setting base url to '{}'.", base_url)
        new_manifest = modify_manifest(resp.content, base_url)
        self.send_header('content-type', 'application/dash+xml')
        self.send_header('content_length', str(len(new_manifest)))
        self.send_header('connection', 'close')
        self.end_headers()
        self.wfile.write(new_manifest)
        self.server.manifest_handled()
        utils.log_info('[proxy] Finished proxying manifest.')
        return True


def run_proxy(mpd_url):
    proxy = ProxyServer(('127.0.0.1', 0), ProxyRequestHandler, mpd_url)
    proxy_address = ''.join(('http://127.0.0.1:', str(proxy.server_port), '/bbcsportstream/manifest.mpd'))
    proxy.start_server()
    return proxy_address, proxy
