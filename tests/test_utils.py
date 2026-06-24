
from unittest import TestCase

from resources.lib import utils


class ISODuration(TestCase):
    def test_seconds_to_ISO(self):
        self.assertEqual('PT1H2M3S', utils.seconds_2_iso_duration(3723))
        self.assertEqual('PT1H2M3.05S', utils.seconds_2_iso_duration(3723.05))
        self.assertEqual('PT1H2M3.056S', utils.seconds_2_iso_duration(3723.05555))
        self.assertEqual('PT1H2M3.055S', utils.seconds_2_iso_duration(3723.05544))
        self.assertEqual('PT0H3M0S', utils.seconds_2_iso_duration(180))
        self.assertEqual('PT0H0M2S', utils.seconds_2_iso_duration(2))
