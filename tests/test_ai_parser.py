import unittest

from extraction.ai_parser import _extract_json_array, parse_with_ai


class TestExtractJsonArray(unittest.TestCase):
    def test_plain_array(self):
        self.assertEqual(_extract_json_array('[{"rate": 1}]'), [{"rate": 1}])

    def test_markdown_fenced_array(self):
        self.assertEqual(
            _extract_json_array('```json\n[{"rate": 2}]\n```'),
            [{"rate": 2}],
        )

    def test_envelope_with_observations(self):
        self.assertEqual(
            _extract_json_array('{"observations": [{"rate": 3}]}'),
            [{"rate": 3}],
        )

    def test_prose_with_embedded_array(self):
        self.assertEqual(
            _extract_json_array('Here are the prices:\n[{"rate": 4}, {"rate": 5}]\nregards'),
            [{"rate": 4}, {"rate": 5}],
        )

    def test_empty_on_no_json(self):
        self.assertEqual(_extract_json_array("no json here at all"), [])

    def test_non_dict_items_filtered(self):
        self.assertEqual(
            _extract_json_array('[{"rate": 6}, 7, "x", null]'),
            [{"rate": 6}],
        )

    def test_empty_input(self):
        self.assertEqual(_extract_json_array(""), [])
        self.assertEqual(_extract_json_array(None), [])


class TestProviderOrder(unittest.IsolatedAsyncioTestCase):
    async def test_first_provider_wins(self):
        async def first(text, pre):
            return [{"rate": 1}]

        async def second(text, pre):
            return [{"rate": 2}]

        result, failed = await parse_with_ai("x", {}, providers=[first, second])
        self.assertEqual(result, [{"rate": 1}])
        self.assertFalse(failed)

    async def test_falls_through_when_first_returns_none(self):
        async def first(text, pre):
            return None

        async def second(text, pre):
            return [{"rate": 2}]

        result, failed = await parse_with_ai("x", {}, providers=[first, second])
        self.assertEqual(result, [{"rate": 2}])
        self.assertFalse(failed)

    async def test_empty_list_counts_as_success_not_failure(self):
        # A provider that answers "no rates here" ([]) is SUCCESS: the fallback
        # must NOT run, so all_failed must be False.
        async def first(text, pre):
            return []

        async def second(text, pre):
            return [{"rate": 2}]

        result, failed = await parse_with_ai("x", {}, providers=[first, second])
        self.assertEqual(result, [])
        self.assertFalse(failed)

    async def test_all_fail_flags_failure(self):
        async def first(text, pre):
            return None

        async def second(text, pre):
            return None

        result, failed = await parse_with_ai("x", {}, providers=[first, second])
        self.assertEqual(result, [])
        self.assertTrue(failed)

    async def test_default_order_is_orcarouter_first(self):
        import extraction.ai_parser as parser

        calls = []

        async def fake_orca(text, pre):
            calls.append("orcarouter")
            return [{"rate": 1}]

        async def fake_rest(text, pre):
            calls.append("rest")
            return None

        original_orca = parser.call_orcarouter
        original_m, original_g, original_o = (
            parser.call_mistral,
            parser.call_groq,
            parser.call_openrouter,
        )
        parser.call_orcarouter = fake_orca
        parser.call_mistral = parser.call_groq = parser.call_openrouter = fake_rest
        try:
            result, failed = await parse_with_ai("x", {})
        finally:
            parser.call_orcarouter = original_orca
            parser.call_mistral = original_m
            parser.call_groq = original_g
            parser.call_openrouter = original_o

        self.assertEqual(result, [{"rate": 1}])
        self.assertFalse(failed)
        self.assertEqual(calls, ["orcarouter"])  # OrcaRouter tried first and won

    async def test_default_order_falls_through_orca_mistral_groq_openrouter(self):
        import extraction.ai_parser as parser

        calls = []

        async def fake_orca(text, pre):
            calls.append("orcarouter")
            return None

        async def fake_mistral(text, pre):
            calls.append("mistral")
            return None

        async def fake_groq(text, pre):
            calls.append("groq")
            return None

        async def fake_or(text, pre):
            calls.append("openrouter")
            return [{"rate": 2}]

        original_orca = parser.call_orcarouter
        original_m, original_g, original_o = (
            parser.call_mistral,
            parser.call_groq,
            parser.call_openrouter,
        )
        parser.call_orcarouter = fake_orca
        parser.call_mistral = fake_mistral
        parser.call_groq = fake_groq
        parser.call_openrouter = fake_or
        try:
            result, failed = await parse_with_ai("x", {})
        finally:
            parser.call_orcarouter = original_orca
            parser.call_mistral = original_m
            parser.call_groq = original_g
            parser.call_openrouter = original_o

        self.assertEqual(result, [{"rate": 2}])
        self.assertFalse(failed)
        self.assertEqual(calls, ["orcarouter", "mistral", "groq", "openrouter"])


if __name__ == "__main__":
    unittest.main()
