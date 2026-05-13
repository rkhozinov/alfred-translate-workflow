import json
import os
import pathlib
import sys
import tempfile
import time as _t
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402

# Isolate cache writes during tests
_TMP_CACHE = tempfile.mkdtemp(prefix="gtranslate-test-")
main.CACHE_DIR = pathlib.Path(_TMP_CACHE)


def _clear_cache():
    for f in main.CACHE_DIR.glob("*.json"):
        f.unlink()


# ---------- Cyrillic detection ----------

class TestCyrillicDetect(unittest.TestCase):
    def test_pure_cyrillic(self):       self.assertTrue(main.CYRILLIC_RE.search("Привет"))
    def test_pure_latin(self):          self.assertFalse(main.CYRILLIC_RE.search("hello"))
    def test_mixed(self):               self.assertTrue(main.CYRILLIC_RE.search("hello Привет"))
    def test_single_cyrillic_char(self): self.assertTrue(main.CYRILLIC_RE.search("a б c"))
    def test_punctuation_only(self):    self.assertFalse(main.CYRILLIC_RE.search("!?.,"))
    def test_empty(self):               self.assertFalse(main.CYRILLIC_RE.search(""))
    def test_ukrainian_yi(self):        self.assertTrue(main.CYRILLIC_RE.search("Привіт"))
    def test_emoji_only(self):          self.assertFalse(main.CYRILLIC_RE.search("🚀"))
    def test_french(self):              self.assertFalse(main.CYRILLIC_RE.search("Bonjour le monde"))


# ---------- pick_target ----------

class TestPickTarget(unittest.TestCase):
    def test_cyrillic_out_ru(self):
        self.assertEqual(main.pick_target("Привет", "ru", "en"), "en")
    def test_latin_out_ru(self):
        self.assertEqual(main.pick_target("hello", "ru", "en"), "ru")
    def test_cyrillic_in_ru(self):
        self.assertEqual(main.pick_target("Привет", "en", "ru"), "en")
    def test_latin_in_ru(self):
        self.assertEqual(main.pick_target("hello", "en", "ru"), "ru")
    def test_cyrillic_neither_ru(self):
        self.assertEqual(main.pick_target("Привет", "fr", "de"), "de")
    def test_latin_neither_ru(self):
        self.assertEqual(main.pick_target("hello", "fr", "de"), "fr")


class TestReverseTarget(unittest.TestCase):
    def test_swap(self):
        self.assertEqual(main.reverse_target("en", "ru", "en"), "ru")
        self.assertEqual(main.reverse_target("ru", "ru", "en"), "en")
    def test_unknown_target_returns_out(self):
        self.assertEqual(main.reverse_target("xx", "ru", "en"), "ru")


# ---------- gtx parser ----------

class TestParseResponse(unittest.TestCase):
    def setUp(self):
        self.t = main.Translate("en")

    def test_simple(self):
        data = [[["Hello", "Привет", None, None, 10]], None, "ru"]
        r = self.t._parse_response(data)
        self.assertEqual(r["text"], "Hello")
        self.assertEqual(r["src"], "ru")
        self.assertEqual(r["alternatives"], [])
        self.assertEqual(r["dict"], [])

    def test_multi_segment(self):
        data = [[["Hello ", "Привет ", None, None, 10],
                 ["world", "мир", None, None, 10]], None, "ru"]
        r = self.t._parse_response(data)
        self.assertEqual(r["text"], "Hello world")

    def test_alternatives(self):
        # idx 5 = dt=at section
        data = [
            [["привет", "hello", None, None, 10]],
            None,
            "en",
            None, None,
            [["hello", None, [["привет", None, True, False, [10]],
                               ["приветствовать", None, True, False, [10]],
                               ["Здравствуйте", None, True, False, [10]]],
              [[0, 5]], "hello", 0, 0]],
        ]
        r = self.t._parse_response(data)
        self.assertEqual(r["text"], "привет")
        # "привет" is the main → skipped from alts; the rest stay
        self.assertEqual(r["alternatives"], ["приветствовать", "Здравствуйте"])

    def test_dict_entries(self):
        data = [
            [["привет", "hello", None, None, 10]],
            [["verb", ["здороваться", "звать"], None, None, 0],
             ["noun", ["приветствие"], None, None, 0]],
            "en",
        ]
        r = self.t._parse_response(data)
        self.assertEqual(r["dict"], [("verb", ["здороваться", "звать"]),
                                      ("noun", ["приветствие"])])

    def test_garbage_returns_defaults(self):
        r = self.t._parse_response("garbage")
        self.assertEqual(r, {"text": "", "src": "unknown", "alternatives": [], "dict": []})

    def test_empty_list(self):
        r = self.t._parse_response([])
        self.assertEqual(r["text"], "")


# ---------- Language validation ----------

class TestLanguageValidation(unittest.TestCase):
    def test_supported(self):
        main.Translate("en"); main.Translate("ru")
    def test_unsupported(self):
        with self.assertRaises(ValueError):
            main.Translate("xx")


# ---------- main_entry / build_items output ----------

class TestMainEntryOutput(unittest.TestCase):
    def setUp(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        _clear_cache()

    def _mock_get(self, parsed_value):
        # Return raw mock that the parser would produce parsed_value from;
        # simplest: patch _parse_response.
        return patch.object(main.Translate, "_parse_response", return_value=parsed_value)

    def test_basic_row(self):
        parsed = {"text": "Hello", "src": "ru", "alternatives": [], "dict": []}
        with self._mock_get(parsed), patch.object(main.Translate, "_get_request", return_value=[]):
            out = json.loads(main.main_entry("Привет"))
            self.assertEqual(out["items"][0]["title"], "Hello")
            self.assertIn("ru → en", out["items"][0]["subtitle"])
            self.assertTrue(out["items"][0]["valid"])
            self.assertIn("cmd", out["items"][0]["mods"])

    def test_alternatives_appear_as_rows(self):
        parsed_fwd = {"text": "привет", "src": "en", "alternatives": ["приветствовать"], "dict": []}
        parsed_back = {"text": "hello", "src": "ru", "alternatives": [], "dict": []}
        call = {"n": 0}
        def fake_parse(self_, data):
            call["n"] += 1
            return parsed_fwd if call["n"] == 1 else parsed_back
        with patch.object(main.Translate, "_parse_response", autospec=True, side_effect=fake_parse), \
             patch.object(main.Translate, "_get_request", return_value=[]):
            out = json.loads(main.main_entry("hello"))
            titles = [it["title"] for it in out["items"]]
            self.assertIn("привет", titles)
            self.assertIn("приветствовать", titles)

    def test_dict_rows(self):
        parsed = {"text": "привет", "src": "en", "alternatives": [],
                  "dict": [("verb", ["здороваться", "звать"])]}
        with patch.object(main.Translate, "_parse_response", return_value=parsed), \
             patch.object(main.Translate, "_get_request", return_value=[]):
            out = json.loads(main.main_entry("hello"))
            joined_titles = [it["title"] for it in out["items"]]
            self.assertIn("здороваться, звать", joined_titles)

    def test_back_translation_in_cmd(self):
        fwd = {"text": "Hello", "src": "ru", "alternatives": [], "dict": []}
        back = {"text": "Привет (back)", "src": "en", "alternatives": [], "dict": []}
        call = {"n": 0}
        def fake_parse(self_, data):
            call["n"] += 1
            return fwd if call["n"] == 1 else back
        with patch.object(main.Translate, "_parse_response", autospec=True, side_effect=fake_parse), \
             patch.object(main.Translate, "_get_request", return_value=[]):
            out = json.loads(main.main_entry("Привет"))
            cmd = out["items"][0]["mods"]["cmd"]
            self.assertEqual(cmd["arg"], "Привет (back)")
            self.assertIn("Привет (back)", cmd["subtitle"])

    def test_empty_input(self):
        out = json.loads(main.main_entry(""))
        self.assertFalse(out["items"][0]["valid"])
        self.assertIn("Type", out["items"][0]["title"])

    def test_missing_env_returns_error(self):
        del os.environ["output_language"]
        out = json.loads(main.main_entry("hi"))
        self.assertFalse(out["items"][0]["valid"])
        self.assertIn("config", out["items"][0]["title"].lower())
        os.environ["output_language"] = "ru"

    def test_http_error_returns_error_row(self):
        with patch.object(main.Translate, "_get_request", side_effect=RuntimeError("HTTP 429")):
            out = json.loads(main.main_entry("hello unique-err"))
            self.assertFalse(out["items"][0]["valid"])
            self.assertIn("failed", out["items"][0]["title"].lower())
            self.assertIn("HTTP 429", out["items"][0]["subtitle"])

    def test_unsupported_lang_error(self):
        os.environ["output_language"] = "xx"
        out = json.loads(main.main_entry("hello unique-bad-lang"))
        self.assertFalse(out["items"][0]["valid"])
        os.environ["output_language"] = "ru"


# ---------- Cache ----------

class TestCache(unittest.TestCase):
    def setUp(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        _clear_cache()

    def test_hit_avoids_http(self):
        parsed = {"text": "Привет", "src": "en", "alternatives": [], "dict": []}
        with patch.object(main.Translate, "_get_request") as mock_req, \
             patch.object(main.Translate, "_parse_response", return_value=parsed):
            mock_req.return_value = []
            main.main_entry("hello cache-A")
            n_after_first = mock_req.call_count
            main.main_entry("hello cache-A")
            self.assertEqual(mock_req.call_count, n_after_first,
                             "second call must hit cache and not re-request")

    def test_different_text_misses(self):
        parsed = {"text": "x", "src": "en", "alternatives": [], "dict": []}
        with patch.object(main.Translate, "_get_request") as mock_req, \
             patch.object(main.Translate, "_parse_response", return_value=parsed):
            mock_req.return_value = []
            main.main_entry("alpha cache-text")
            n1 = mock_req.call_count
            main.main_entry("beta cache-text")
            self.assertGreater(mock_req.call_count, n1)

    def test_ttl_expired(self):
        parsed = {"text": "x", "src": "en", "alternatives": [], "dict": []}
        with patch.object(main.Translate, "_get_request") as mock_req, \
             patch.object(main.Translate, "_parse_response", return_value=parsed):
            mock_req.return_value = []
            main.main_entry("ttl-text-uniq")
            n1 = mock_req.call_count
            for f in main.CACHE_DIR.glob("*.json"):
                old = _t.time() - (main.CACHE_TTL_SEC + 10)
                os.utime(f, (old, old))
            main.main_entry("ttl-text-uniq")
            self.assertGreater(mock_req.call_count, n1)


if __name__ == "__main__":
    unittest.main()
