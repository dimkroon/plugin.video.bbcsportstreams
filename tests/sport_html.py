import json
import os
import unittest
import re

from support.testutils import open_doc

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
