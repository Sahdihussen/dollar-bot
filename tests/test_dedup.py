import unittest

from extraction.dedup import make_dedup_key, deduplicate


def make_obs(**overrides):
    obs = {
        "source": "pashagoldd",
        "raw_post_id": 42,
        "city": "baghdad",
        "market_layer": "local_market",
        "rate": 152850,
        "quote_label_normalized": "عرض",
        "dollar_category_normalized": "STANDARD_MIX",
    }
    obs.update(overrides)
    return obs


class TestMakeDedupKey(unittest.TestCase):
    def test_identical_observations_same_key(self):
        a = make_obs()
        b = make_obs()
        self.assertEqual(make_dedup_key(a), make_dedup_key(b))

    def test_key_changes_with_rate(self):
        self.assertNotEqual(
            make_dedup_key(make_obs(rate=152850)),
            make_dedup_key(make_obs(rate=152900)),
        )

    def test_key_changes_with_city(self):
        self.assertNotEqual(
            make_dedup_key(make_obs(city="baghdad")),
            make_dedup_key(make_obs(city="erbil")),
        )

    def test_key_changes_with_category(self):
        self.assertNotEqual(
            make_dedup_key(make_obs(dollar_category_normalized="STANDARD_MIX")),
            make_dedup_key(make_obs(dollar_category_normalized="5000_IQD_CATEGORY")),
        )

    def test_key_changes_with_post(self):
        self.assertNotEqual(
            make_dedup_key(make_obs(raw_post_id=1)),
            make_dedup_key(make_obs(raw_post_id=2)),
        )

    def test_key_changes_with_product(self):
        self.assertNotEqual(
            make_dedup_key(make_obs(rate=2186, product="silver_kg")),
            make_dedup_key(make_obs(rate=2186, product="usd_iqd")),
        )

    def test_key_is_hex(self):
        key = make_dedup_key(make_obs())
        self.assertEqual(len(key), 32)
        int(key, 16)  # raises if not hex


class TestDeduplicate(unittest.TestCase):
    def test_removes_exact_duplicates(self):
        result = deduplicate([make_obs(), make_obs()])
        self.assertEqual(len(result), 1)

    def test_keeps_distinct_observations(self):
        result = deduplicate([
            make_obs(rate=152850),
            make_obs(rate=152900),
            make_obs(rate=152850, city="erbil"),
        ])
        self.assertEqual(len(result), 3)

    def test_empty_list(self):
        self.assertEqual(deduplicate([]), [])


if __name__ == "__main__":
    unittest.main()
