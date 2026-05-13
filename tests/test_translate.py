import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402
import pathlib  # noqa: E402

# Isolate test cache writes
_TMP_CACHE = tempfile.mkdtemp(prefix="gtranslate-test-")
main.CACHE_DIR = pathlib.Path(_TMP_CACHE)


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
    # Config A: out=ru, in=en (upstream default)
    def test_cyrillic_out_ru(self):
        self.assertEqual(main.pick_target("Привет", out_lang="ru", in_lang="en"), "en")

    def test_latin_out_ru(self):
        self.assertEqual(main.pick_target("hello", out_lang="ru", in_lang="en"), "ru")

    def test_mixed_out_ru(self):
        self.assertEqual(main.pick_target("hi Привет", out_lang="ru", in_lang="en"), "en")

    # Config B: out=en, in=ru (user's chosen config)
    def test_cyrillic_in_ru(self):
        self.assertEqual(main.pick_target("Привет", out_lang="en", in_lang="ru"), "en")

    def test_latin_in_ru(self):
        self.assertEqual(main.pick_target("hello", out_lang="en", in_lang="ru"), "ru")

    def test_mixed_in_ru(self):
        self.assertEqual(main.pick_target("hi Привет", out_lang="en", in_lang="ru"), "en")

    # Config C: neither side is ru — fall back to slot-position routing
    def test_cyrillic_neither_ru(self):
        self.assertEqual(main.pick_target("Привет", out_lang="fr", in_lang="de"), "de")

    def test_latin_neither_ru(self):
        self.assertEqual(main.pick_target("hello", out_lang="fr", in_lang="de"), "fr")


class TestParseResponse(unittest.TestCase):
    def test_clients5_array_shape(self):
        t = main.Translate("en")
        data = [["Hello", "ru"]]
        lang, out = t._parse_response(data)
        self.assertEqual(lang, "ru")
        self.assertEqual(out, ["Hello"])

    def test_clients5_dict_shape(self):
        t = main.Translate("en")
        data = {"sentences": [{"trans": "Hello ", "orig": "Привет "},
                              {"trans": "world", "orig": "мир"}],
                "src": "ru"}
        lang, out = t._parse_response(data)
        self.assertEqual(lang, "ru")
        self.assertEqual(out, ["Hello world"])

    def test_unknown_shape(self):
        t = main.Translate("en")
        lang, out = t._parse_response("garbage")
        self.assertEqual(lang, "unknown")


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
        # fresh cache per test
        for f in main.CACHE_DIR.glob("*.json"):
            f.unlink()

    def _mock_response(self, text):
        return [[text + "_MOCKED", "xx"]]

    def test_latin_input_one_call_to_out_lang(self):
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = self._mock_response("hello")
            with patch.object(main.Translate, "__init__", side_effect=main.Translate.__init__, autospec=True) as mock_init:
                main.main_entry("hello world unique-A")
                langs = [call.args[1] for call in mock_init.call_args_list]
                self.assertEqual(langs, ["ru"])
            self.assertEqual(mock_req.call_count, 1)

    def test_cyrillic_input_one_call_to_in_lang(self):
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = self._mock_response("Привет")
            with patch.object(main.Translate, "__init__", side_effect=main.Translate.__init__, autospec=True) as mock_init:
                main.main_entry("Привет мир unique-B")
                langs = [call.args[1] for call in mock_init.call_args_list]
                self.assertEqual(langs, ["en"])
            self.assertEqual(mock_req.call_count, 1)


class TestCache(unittest.TestCase):
    def setUp(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        for f in main.CACHE_DIR.glob("*.json"):
            f.unlink()

    def test_second_call_uses_cache(self):
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = [["Привет, мир", "en"]]
            main.main_entry("hello world cache-test")
            main.main_entry("hello world cache-test")
            self.assertEqual(mock_req.call_count, 1, "second call must hit cache")

    def test_different_text_misses(self):
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = [["X", "en"]]
            main.main_entry("alpha cache-test")
            main.main_entry("beta cache-test")
            self.assertEqual(mock_req.call_count, 2)

    def test_different_target_misses(self):
        # Cache key includes target lang — swap out/in entirely (no ru),
        # otherwise pick_target routes both configs to the same lang.
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = [["X", "en"]]
            os.environ["output_language"] = "fr"
            os.environ["input_language"] = "de"
            main.main_entry("hello target-A")  # target=fr (Latin, no ru side)
            os.environ["output_language"] = "de"
            os.environ["input_language"] = "fr"
            main.main_entry("hello target-A")  # target=de
            self.assertEqual(mock_req.call_count, 2)

    def test_ttl_expired(self):
        import time as _t
        with patch.object(main.Translate, "_get_request") as mock_req:
            mock_req.return_value = [["X", "en"]]
            main.main_entry("ttl text")
            # backdate cache file
            for f in main.CACHE_DIR.glob("*.json"):
                old = _t.time() - (main.CACHE_TTL_SEC + 10)
                os.utime(f, (old, old))
            main.main_entry("ttl text")
            self.assertEqual(mock_req.call_count, 2)


if __name__ == "__main__":
    unittest.main()
