"""English-only famous hashtag helpers."""
import unittest

from tools.news_fetcher import is_english_text, phrase_to_hashtag


class EnglishHashtagTests(unittest.TestCase):
    def test_rejects_non_latin_scripts(self):
        self.assertFalse(is_english_text("আগামীকালের আবহাওয়া"))
        self.assertFalse(is_english_text("ज्ञानेश कुमार"))
        self.assertFalse(phrase_to_hashtag("মুশ্তাক খান"))

    def test_builds_tag_from_english_phrase(self):
        self.assertTrue(is_english_text("Big Billion Days"))
        self.assertEqual(phrase_to_hashtag("Big Billion Days"), "#BigBillionDays")
        self.assertEqual(phrase_to_hashtag("#MiviOne5G"), "#MiviOne5G")

    def test_keeps_existing_hashtag_shape(self):
        self.assertEqual(phrase_to_hashtag("Snapdragon"), "#Snapdragon")


if __name__ == "__main__":
    unittest.main()
