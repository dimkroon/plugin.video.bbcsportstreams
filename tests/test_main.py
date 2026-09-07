from support.fixtures import global_setup
global_setup()

from unittest import TestCase

from resources.lib import main


class TestGetManifest(TestCase):
    def test_get_manifest_url_red_btn_one(self):
        url = main.get_manifest_url('red_button_one', 0)
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith('https://'))