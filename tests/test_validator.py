import unittest

import config
from extraction.validator import validate_observation, validate_all


def make_obs(**overrides):
    obs = {
        "rate": 152850,
        "city": "baghdad",
        "rate_role": "MARKET",
        "time_context": "CURRENT",
        "dollar_category_normalized": "STANDARD_MIX",
        "denomination": 100,
        "confidence": 0.8,
    }
    obs.update(overrides)
    return obs


class TestValidateObservation(unittest.TestCase):
    def test_valid_observation_passes(self):
        ok, reason = validate_observation(make_obs())
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_missing_rate_rejected(self):
        ok, reason = validate_observation(make_obs(rate=None))
        self.assertFalse(ok)
        self.assertIn("missing_or_invalid_rate", reason)

    def test_string_rate_rejected(self):
        ok, _ = validate_observation(make_obs(rate="152850"))
        self.assertFalse(ok)

    def test_out_of_range_rejected(self):
        ok, reason = validate_observation(make_obs(rate=config.SANITY_MIN_RATE - 1))
        self.assertFalse(ok)
        self.assertIn("rate_out_of_range", reason)
        ok, reason = validate_observation(make_obs(rate=config.SANITY_MAX_RATE + 1))
        self.assertFalse(ok)
        self.assertIn("rate_out_of_range", reason)

    def test_unknown_city_rejected(self):
        ok, reason = validate_observation(make_obs(city="atlantis"))
        self.assertFalse(ok)
        self.assertIn("unknown_city", reason)

    def test_invalid_role_coerced(self):
        obs = make_obs(rate_role="GARBAGE")
        ok, _ = validate_observation(obs)
        self.assertTrue(ok)
        self.assertEqual(obs["rate_role"], "UNKNOWN")

    def test_invalid_time_context_coerced(self):
        obs = make_obs(time_context="GARBAGE")
        ok, _ = validate_observation(obs)
        self.assertTrue(ok)
        self.assertEqual(obs["time_context"], "UNKNOWN")

    def test_invalid_category_coerced(self):
        obs = make_obs(dollar_category_normalized="GARBAGE")
        ok, _ = validate_observation(obs)
        self.assertTrue(ok)
        self.assertEqual(obs["dollar_category_normalized"], "UNKNOWN")

    def test_invalid_confidence_coerced(self):
        obs = make_obs(confidence=5)
        ok, _ = validate_observation(obs)
        self.assertTrue(ok)
        self.assertEqual(obs["confidence"], 0.5)

    def test_silver_kg_usd_rate_accepted(self):
        ok, reason = validate_observation(make_obs(rate=2186, product="silver_kg"))
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_dubai_lira_usd_rate_accepted(self):
        ok, _ = validate_observation(make_obs(rate=958, product="dubai_lira"))
        self.assertTrue(ok)

    def test_usd_iqd_low_rate_rejected(self):
        ok, reason = validate_observation(make_obs(rate=5465, product="usd_iqd"))
        self.assertFalse(ok)
        self.assertIn("rate_out_of_range", reason)

    def test_metal_rate_out_of_usd_band_rejected(self):
        # 0 is falsy and is rejected as a missing/invalid rate before the range check
        ok, reason = validate_observation(make_obs(rate=0, product="silver_kg"))
        self.assertFalse(ok)
        self.assertIn("missing_or_invalid_rate", reason)
        # Above the USD band for metals -> out of range
        ok, reason = validate_observation(make_obs(rate=100001, product="silver_kg"))
        self.assertFalse(ok)
        self.assertIn("rate_out_of_range", reason)

    def test_invalid_product_coerced_to_usd_iqd(self):
        # Unknown product coerced to usd_iqd, so a USD metal price then fails the IQD band
        obs = make_obs(rate=2186, product="GARBAGE")
        ok, reason = validate_observation(obs)
        self.assertFalse(ok)
        self.assertIn("rate_out_of_range", reason)
        self.assertEqual(obs["product"], "usd_iqd")


class TestValidateAll(unittest.TestCase):
    def test_splits_valid_and_rejected(self):
        observations = [
            make_obs(rate=152850),
            make_obs(rate=100),  # out of range
            make_obs(rate=152900, city="erbil"),
        ]
        valid, rejected = validate_all(observations)
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(rejected), 1)
        self.assertIn("_rejection_reason", rejected[0])

    def test_empty_list(self):
        valid, rejected = validate_all([])
        self.assertEqual(valid, [])
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
