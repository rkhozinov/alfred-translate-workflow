import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402


@unittest.skipUnless(os.environ.get("LIVE_TESTS") == "1", "set LIVE_TESTS=1 to run")
class TestLive(unittest.TestCase):
    def test_ru_to_en(self):
        r = main.Translate("en").get_translation("Привет мир")
        self.assertEqual(r["src"], "ru")
        self.assertIn("ello", r["text"].lower())

    def test_en_to_ru(self):
        r = main.Translate("ru").get_translation("hello world")
        self.assertEqual(r["src"], "en")
        self.assertTrue(main.CYRILLIC_RE.search(r["text"]))

    def test_main_entry_latin(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        result = main.main_entry("hello world")
        self.assertIn("Привет", result)

    def test_main_entry_cyrillic(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        result = main.main_entry("Привет мир")
        self.assertIn("ello", result.lower())

    def test_single_word_returns_alternatives(self):
        r = main.Translate("ru").get_translation("hello")
        self.assertTrue(r["alternatives"] or r["dict"],
                        "single common word should return alternatives or dict entries")


if __name__ == "__main__":
    unittest.main()
