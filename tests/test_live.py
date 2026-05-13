import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402


@unittest.skipUnless(os.environ.get("LIVE_TESTS") == "1", "set LIVE_TESTS=1 to run")
class TestLive(unittest.TestCase):
    def test_ru_to_en(self):
        lang, out = main.Translate("en").get_translation("Привет мир")
        self.assertEqual(lang, "ru")
        self.assertTrue(out and out[0])
        self.assertIn("ello", out[0].lower())

    def test_en_to_ru(self):
        lang, out = main.Translate("ru").get_translation("hello world")
        self.assertEqual(lang, "en")
        self.assertTrue(out and out[0])
        self.assertTrue(main.CYRILLIC_RE.search(out[0]))

    def test_main_entry_latin(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        result = main.main_entry("hello world")
        self.assertIn("Привет", result + "")  # rough check; output is JSON

    def test_main_entry_cyrillic(self):
        os.environ["output_language"] = "ru"
        os.environ["input_language"] = "en"
        result = main.main_entry("Привет мир")
        self.assertIn("ello", result.lower())


if __name__ == "__main__":
    unittest.main()
