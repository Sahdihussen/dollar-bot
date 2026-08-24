import unittest

from extraction.preprocessor import (
    normalize_numbers,
    detect_city,
    detect_label,
    detect_category,
    detect_market_layer,
    is_official_rate,
    detect_time_context,
    extract_rates_from_text,
    preprocess,
)


class TestNormalizeNumbers(unittest.TestCase):
    def test_arabic_indic_digits(self):
        self.assertEqual(normalize_numbers("١٥٢٨٥٠"), "152850")

    def test_arabic_thousands_separator(self):
        self.assertEqual(normalize_numbers("١٥٢٬٨٥٠"), "152850")
        self.assertEqual(normalize_numbers("١٥٢،٨٥٠"), "152850")

    def test_latin_separators(self):
        self.assertEqual(normalize_numbers("152,850"), "152850")
        self.assertEqual(normalize_numbers("152.850"), "152850")
        self.assertEqual(normalize_numbers("152 850"), "152850")
        self.assertEqual(normalize_numbers("152,850,500"), "152850500")

    def test_plain_numbers_untouched(self):
        self.assertEqual(normalize_numbers("152850"), "152850")
        self.assertEqual(normalize_numbers("hello 123"), "hello 123")


class TestDetectCity(unittest.TestCase):
    def test_arabic(self):
        self.assertEqual(detect_city("بغداد"), ("baghdad", "بغداد"))
        self.assertEqual(detect_city("اربيل"), ("erbil", "اربيل"))

    def test_kurdish(self):
        self.assertEqual(detect_city("سلێمانی"), ("sulaymaniyah", "سلێمانی"))
        self.assertEqual(detect_city("سلێماني"), ("sulaymaniyah", "سلێماني"))
        self.assertEqual(detect_city("هەولێر"), ("erbil", "هەولێر"))

    def test_english(self):
        self.assertEqual(detect_city("erbil"), ("erbil", "erbil"))
        self.assertEqual(detect_city("baghdad"), ("baghdad", "baghdad"))

    def test_none(self):
        self.assertEqual(detect_city("hello world"), (None, None))


class TestDetectLabel(unittest.TestCase):
    def test_short_labels(self):
        self.assertEqual(detect_label("152,950 ع"), ("عرض", "ع"))
        self.assertEqual(detect_label("153,050 ط"), ("طلب", "ط"))

    def test_full_labels(self):
        self.assertEqual(detect_label("بيع"), ("SELL", "بيع"))
        self.assertEqual(detect_label("شراء"), ("BUY", "شراء"))
        self.assertEqual(detect_label("شرا"), ("BUY", "شرا"))

    def test_none(self):
        self.assertEqual(detect_label("152,950"), (None, None))


class TestDetectCategory(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(detect_category("پێنجی"), ("5000_IQD_CATEGORY", "پێنجی"))
        self.assertEqual(detect_category("سوور"), ("25000_IQD_CATEGORY", "سوور"))
        self.assertEqual(detect_category("ستاندارد"), ("STANDARD_MIX", "ستاندارد"))
        self.assertEqual(detect_category("خبط"), ("MIXED", "خبط"))

    def test_none(self):
        self.assertEqual(detect_category("152,950"), (None, None))


class TestDetectMarketLayer(unittest.TestCase):
    def test_markets(self):
        self.assertEqual(detect_market_layer("الكفاح"), ("AL_KIFAH_BOURSE", "الكفاح"))
        self.assertEqual(detect_market_layer("صيرفات"), ("EXCHANGE_OFFICES", "صيرفات"))

    def test_none(self):
        self.assertEqual(detect_market_layer("152,950"), (None, None))


class TestOfficialAndTime(unittest.TestCase):
    def test_official_markers(self):
        self.assertTrue(is_official_rate("السعر الرسمي 153,000"))
        self.assertTrue(is_official_rate("البنك المركزي العراقي"))
        self.assertFalse(is_official_rate("152,000"))

    def test_time_context(self):
        self.assertEqual(detect_time_context("أمس 152,800"), "HISTORICAL")
        self.assertEqual(detect_time_context("اليوم 152,900"), "CURRENT")
        self.assertEqual(detect_time_context("غداً 153,000"), "FORECAST")
        self.assertEqual(detect_time_context("hello"), "UNKNOWN")


class TestExtractRates(unittest.TestCase):
    def test_rate_with_currency(self):
        rates = extract_rates_from_text("153050 دولار")
        self.assertEqual([r["value"] for r in rates], [153050])

    def test_100_dollar_pattern(self):
        rates = extract_rates_from_text("100$ = 152850")
        self.assertEqual([r["value"] for r in rates], [152850])

    def test_rate_with_label(self):
        rates = extract_rates_from_text("152,950 ع")
        self.assertEqual([r["value"] for r in rates], [152950])

    def test_plain_in_range(self):
        rates = extract_rates_from_text("152800")
        self.assertEqual([r["value"] for r in rates], [152800])

    def test_rate_glued_to_arabic_word(self):
        # \b fails between Arabic letters and digits; the extractor must still find it
        rates = extract_rates_from_text("فرۆشتن154000\nكرين153750")
        self.assertEqual([r["value"] for r in rates], [154000, 153750])

    def test_rate_glued_after_word(self):
        rates = extract_rates_from_text("بۆڕسەی هەولێر 154,125")
        self.assertEqual([r["value"] for r in rates], [154125])

    def test_no_partial_match_of_longer_number(self):
        # 9-digit number must not yield a false 6-digit rate
        self.assertEqual(extract_rates_from_text("152850500"), [])

    def test_plain_out_of_range_excluded(self):
        rates = extract_rates_from_text("120000")
        self.assertEqual(rates, [])

    def test_deduplicates_by_value(self):
        rates = extract_rates_from_text("152850 ع 152850 ط")
        self.assertEqual([r["value"] for r in rates], [152850])

    def test_no_rates(self):
        self.assertEqual(extract_rates_from_text("good morning"), [])


class TestPreprocessIntegration(unittest.TestCase):
    def test_kurdish_post(self):
        result = preprocess("سلێمانی پێنجی 152,950 ع")
        self.assertEqual(result["city"], "sulaymaniyah")
        self.assertEqual(result["category"], "5000_IQD_CATEGORY")
        self.assertEqual(result["label"], "عرض")
        self.assertEqual(result["time_context"], "UNKNOWN")
        self.assertEqual(result["candidate_rates"][0]["value"], 152950)

    def test_official_post(self):
        result = preprocess("السعر الرسمي للدولار 153,000")
        self.assertTrue(result["is_official"])
        self.assertEqual(result["candidate_rates"][0]["value"], 153000)


if __name__ == "__main__":
    unittest.main()
