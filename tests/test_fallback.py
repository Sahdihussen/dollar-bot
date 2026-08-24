import unittest

from extraction.preprocessor import preprocess, build_fallback_observations
from extraction.validator import validate_all


class TestFallbackObservations(unittest.TestCase):
    def _fallback(self, text, post_id=1, source="nrxidraw852"):
        return build_fallback_observations(preprocess(text), post_id, source)

    def test_baghdad_plain_rate(self):
        obs = self._fallback("بغداد 154000")
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["city"], "baghdad")
        self.assertEqual(obs[0]["rate"], 154000)
        self.assertEqual(obs[0]["rate_role"], "MARKET")
        self.assertEqual(obs[0]["product"], "usd_iqd")
        self.assertEqual(obs[0]["raw_post_id"], 1)
        self.assertEqual(obs[0]["source"], "nrxidraw852")

    def test_erbil_with_label_ع(self):
        obs = self._fallback("هەولێر 152900 ع")
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["city"], "erbil")
        self.assertEqual(obs[0]["rate_role"], "SELL")  # ع -> عرض -> SELL

    def test_sulaymaniyah_with_label_ط(self):
        obs = self._fallback("سلێمانی 152800 ط")
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["city"], "sulaymaniyah")
        self.assertEqual(obs[0]["rate_role"], "BUY")  # ط -> طلب -> BUY

    def test_requires_city(self):
        obs = self._fallback("154000")
        self.assertEqual(obs, [])

    def test_out_of_band_rate_dropped(self):
        obs = self._fallback("بغداد 5465")
        self.assertEqual(obs, [])

    def test_no_candidates_returns_empty(self):
        obs = self._fallback("لا يوجد تحديث اليوم")
        self.assertEqual(obs, [])

    def test_observations_pass_validation(self):
        obs = self._fallback("بغداد 154000 ع\nهەولێر 152900 ط")
        valid, rejected = validate_all(obs)
        self.assertEqual(len(rejected), 0)
        self.assertGreaterEqual(len(valid), 1)

    def test_channel_city_fallback_without_city_in_text(self):
        # Post has an in-band rate but no city name; the channel maps to erbil.
        obs = build_fallback_observations(
            preprocess("154000 ع"), 1, "Borsa_Erbil"
        )
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["city"], "erbil")

    def test_unknown_channel_without_city_returns_empty(self):
        obs = build_fallback_observations(
            preprocess("154000 ع"), 1, "some_random_channel"
        )
        self.assertEqual(obs, [])


if __name__ == "__main__":
    unittest.main()
