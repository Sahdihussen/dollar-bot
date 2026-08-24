import json
import unittest

from market.calculator import calculate_snapshot


def make_obs(rate, city="baghdad", time_context="CURRENT", rate_role="MARKET",
             category="STANDARD_MIX", source="pashagoldd", **overrides):
    obs = {
        "rate": rate,
        "city": city,
        "time_context": time_context,
        "rate_role": rate_role,
        "dollar_category_normalized": category,
        "source": source,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    obs.update(overrides)
    return obs


class TestCalculateSnapshot(unittest.TestCase):
    def test_uses_median_not_mean(self):
        # Mean would be 152666; median is 153000
        obs = [
            make_obs(152000),
            make_obs(153000),
            make_obs(153000),
        ]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["consensus_rate"], 153000)
        self.assertEqual(snap["median_rate"], 153000)

    def test_high_low_and_spread(self):
        obs = [make_obs(152000), make_obs(152500), make_obs(153000)]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["min_rate"], 152000)
        self.assertEqual(snap["max_rate"], 153000)
        self.assertEqual(snap["spread"], 1000)

    def test_only_current_observations_count(self):
        obs = [
            make_obs(153000),  # CURRENT
            make_obs(120000, time_context="PREVIOUS"),
            make_obs(100000, time_context="HISTORICAL"),
        ]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["consensus_rate"], 153000)
        self.assertEqual(snap["observation_count"], 1)

    def test_no_current_observations_returns_none(self):
        obs = [make_obs(153000, time_context="PREVIOUS")]
        self.assertIsNone(calculate_snapshot("baghdad", obs))

    def test_buy_sell_medians(self):
        obs = [
            make_obs(152800, rate_role="BUY"),
            make_obs(152900, rate_role="BUY"),
            make_obs(153000, rate_role="SELL"),
        ]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["buy_rate"], 152850)
        self.assertEqual(snap["sell_rate"], 153000)

    def test_category_breakdown_median(self):
        obs = [
            make_obs(152800, category="5000_IQD_CATEGORY"),
            make_obs(152950, category="5000_IQD_CATEGORY"),
            make_obs(153050, category="25000_IQD_CATEGORY"),
        ]
        snap = calculate_snapshot("baghdad", obs)
        category_rates = json.loads(snap["category_rates"])
        self.assertEqual(category_rates["5000_IQD_CATEGORY"], 152875)
        self.assertEqual(category_rates["25000_IQD_CATEGORY"], 153050)

    def test_source_count_unique(self):
        obs = [
            make_obs(152800, source="pashagoldd"),
            make_obs(152850, source="pashagoldd"),
            make_obs(152900, source="nrxidolar"),
        ]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["source_count"], 2)

    def test_market_layer_detected(self):
        obs = [make_obs(152800, **{"market_layer": "bourse"})]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["market_layer"], "bourse")

    def test_metal_observations_excluded_from_usd_consensus(self):
        obs = [
            make_obs(154000),
            make_obs(2186, product="silver_kg"),
            make_obs(958, product="dubai_lira"),
        ]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["consensus_rate"], 154000)
        self.assertEqual(snap["observation_count"], 1)

    def test_only_metal_observations_returns_none(self):
        obs = [make_obs(2186, product="silver_kg")]
        self.assertIsNone(calculate_snapshot("baghdad", obs))

    def test_null_product_treated_as_usd(self):
        # Legacy rows may have product=None; they must still count toward USD consensus
        obs = [make_obs(154100, **{"product": None})]
        snap = calculate_snapshot("baghdad", obs)
        self.assertEqual(snap["consensus_rate"], 154100)


if __name__ == "__main__":
    unittest.main()
