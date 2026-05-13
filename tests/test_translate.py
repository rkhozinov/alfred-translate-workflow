import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402


class TestCyrillicDetect(unittest.TestCase):
    def test_pure_cyrillic(self):
        self.assertTrue(main.CYRILLIC_RE.search("Привет"))

    def test_pure_latin(self):
        self.assertFalse(main.CYRILLIC_RE.search("hello"))

    def test_mixed(self):
        self.assertTrue(main.CYRILLIC_RE.search("hello Привет"))

    def test_single_cyrillic_char(self):
        self.assertTrue(main.CYRILLIC_RE.search("a б c"))

    def test_punctuation_only(self):
        self.assertFalse(main.CYRILLIC_RE.search("!?.,"))

    def test_empty(self):
        self.assertFalse(main.CYRILLIC_RE.search(""))

    def test_ukrainian_yi(self):
        self.assertTrue(main.CYRILLIC_RE.search("Привіт"))

    def test_emoji_only(self):
        self.assertFalse(main.CYRILLIC_RE.search("🚀"))

    def test_french(self):
        self.assertFalse(main.CYRILLIC_RE.search("Bonjour le monde"))


class TestPickTarget(unittest.TestCase):
    def test_cyrillic_picks_secondary(self):
        self.assertEqual(main.pick_target("Привет", out_lang="ru", in_lang="en"), "en")

    def test_latin_picks_primary(self):
        self.assertEqual(main.pick_target("hello", out_lang="ru", in_lang="en"), "ru")

    def test_mixed_picks_secondary(self):
        self.assertEqual(main.pick_target("hi Привет", out_lang="ru", in_lang="en"), "en")


class TestParseResponse(unittest.TestCase):
    def test_single_segment(self):
        t = main.Translate("en")
        data = [[["Hello", "Привет", None, None, 1]], None, "ru"]
        lang, out = t._parse_response(data)
        self.assertEqual(lang, "ru")
        self.assertEqual(out, ["Hello"])

    def test_multi_segment_joined(self):
        t = main.Translate("en")
        data = [
            [
                ["Hello ", "Привет ", None, None, 1],
                ["world", "мир", None, None, 1],
            ],
            None,
            "ru",
        ]
        _, out = t._parse_response(data)
        self.assertEqual(out, ["Hello world"])

    def test_empty_segments_skipped(self):
        t = main.Translate("en")
        data = [
            [
                ["Hello", None, None, None, 1],
                [None, None, None, None, 1],
            ],
            None,
            "ru",
        ]
        _, out = t._parse_response(data)
        self.assertEqual(out, ["Hello"])


class TestLanguageValidation(unittest.TestCase):
    def test_supported(self):
        main.Translate("en")
        main.Translate("ru")

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            main.Translate("xx")


class TestWorkflowOutput(unittest.TestCase):
    def test_json_shape(self):
        out = json.loads(main.generate_worflow_output(["Hello"]))
        self.assertEqual(out["items"][0]["title"], "Hello")
        self.assertEqual(out["items"][0]["arg"], "Hello")

    def test_unicode_preserved(self):
        out = main.generate_worflow_output(["Привет"])
        self.assertIn("Привет", out)


class TestSingleHTTPCall(unittest.TestCase):
    def setUp(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"

    def _mock_response(self, text):
        return [[[text + "_MOCKED", text, None, None, 1]], None, "xx"]

    def test_latin_input_one_call_to_out_lang(self):
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = self._mock_response("hello")
            with patch.object(main.Translate, "__init__", side_effect=main.Translate.__init__, autospec=True) as mock_init:
                main.main_entry("hello world")
                langs = [call.args[1] for call in mock_init.call_args_list]
                self.assertEqual(langs, ["ru"], "Latin input must hit out_lang=ru exactly once")
            self.assertEqual(mock_req.call_count, 1)

    def test_cyrillic_input_one_call_to_in_lang(self):
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = self._mock_response("Привет")
            with patch.object(main.Translate, "__init__", side_effect=main.Translate.__init__, autospec=True) as mock_init:
                main.main_entry("Привет мир")
                langs = [call.args[1] for call in mock_init.call_args_list]
                self.assertEqual(langs, ["en"], "Cyrillic input must hit in_lang=en exactly once")
            self.assertEqual(mock_req.call_count, 1)


if __name__ == "__main__":
    unittest.main()
