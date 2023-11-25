import json
import os
import unittest
import re
import requests

from support.testutils import open_doc, save_json

class TestPortsPage(unittest.TestCase):
    def test_json_data(self):
        page = open_doc('sport.html')()
        match = re.search('<script nonce=.*?window.__INITIAL_DATA__ = "(.*?)";</script>', page)
        if not match:
            print("no data")
            return
        json_str = re.sub(r'(?<!\\)(\\\")', '"', match[1])
        print(json_str[59806:59886])
        data = json.loads(json_str)
        print(data)


class MediaSelector(unittest.TestCase):
    def test_sport_stream_02(self):
        resp = requests.get('https://open.live.bbc.co.uk/mediaselector/6/select/version/2.0/mediaset/pc/vpid/p0gt1zcf/format/json/jsfunc/JS_callbacks0')
        self.assertEqual(200, resp.status_code)
        body = resp.text
        self.assertTrue(body.startswith('JS_callbacks0 ( '))
        self.assertTrue(body.endswith(');'))
        data = json.loads(body[16:-2])
        # save_json(data, 'stream02_selector.json')