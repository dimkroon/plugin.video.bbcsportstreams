
from resources.lib import proxy
from support.testutils import open_doc, doc_path

from unittest import TestCase
from unittest.mock import patch, MagicMock


class ModifyManifest(TestCase):
    def test_modify_manifest(self):
        manifest = open_doc('manifest.mpd')()
        new_mpd = proxy.modify_manifest(manifest, 'http://my.stream.url/')
        self.assertTrue('presentationTimeOffset' not in new_mpd)

    def test_compare_segment_init(self):
        with open(doc_path('seg_02.init'), 'rb') as f:
            evt_strm_02 = f.read()
        with open(doc_path('seg_03.init'), 'rb') as f:
            evt_strm_03 = f.read()
        self.assertIsInstance(evt_strm_02, bytes)
        self.assertEqual(len(evt_strm_02), len(evt_strm_03))
        self.assertEqual(evt_strm_02, evt_strm_03)