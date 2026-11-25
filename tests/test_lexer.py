"""tests for parser/lexer.py (run from project root: python -m unittest tests.test_lexer)."""

import unittest

from parser.lexer import DAY, KEYWORD, NAME, NUMBER, PART, TIME, clock_hour, tokenize


# the (kind, value) pairs of a sentence, which is all most tests care about.
def kv(text):
    return [(t.kind, t.value) for t in tokenize(text)]


class TestDays(unittest.TestCase):
    def test_short_and_full_names(self):
        for word, day in [("mon", 0), ("Tuesday", 1), ("wed", 2), ("THURSDAY", 3),
                          ("fri", 4), ("saturday", 5), ("sun", 6)]:
            self.assertEqual(kv(word), [(DAY, (day,))])

    def test_groups(self):
        self.assertEqual(kv("weekdays"), [(DAY, (0, 1, 2, 3, 4))])
        self.assertEqual(kv("weekend"), [(DAY, (5, 6))])


class TestTimes(unittest.TestCase):
    def test_am_pm_forms(self):
        self.assertEqual(kv("9pm"), [(TIME, 21)])
        self.assertEqual(kv("9 pm"), [(TIME, 21)])
        self.assertEqual(kv("9AM"), [(TIME, 9)])
        self.assertEqual(kv("12pm"), [(TIME, 12)])
        self.assertEqual(kv("12am"), [(TIME, 0)])

    def test_minutes_round_to_the_hour(self):
        self.assertEqual(kv("9:30pm"), [(TIME, 22)])     # 30 rounds up
        self.assertEqual(kv("9:29pm"), [(TIME, 21)])     # below 30 rounds down
        self.assertEqual(kv("9:15 am"), [(TIME, 9)])

    def test_noon(self):
        self.assertEqual(kv("noon"), [(TIME, 12)])

    def test_multi_word_time_is_one_token(self):
        tokens = tokenize("after 9 pm")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[1].text, "9 pm")

    def test_invalid_times_are_not_times(self):
        self.assertIsNone(clock_hour(13, 0, "pm"))
        self.assertIsNone(clock_hour(0, 0, "am"))
        self.assertIsNone(clock_hour(9, 75, "pm"))
        self.assertEqual(kv("13pm"), [(NAME, "13pm")])
        self.assertEqual(kv("9pmx"), [(NAME, "9pmx")])

    def test_number_before_times_is_not_a_time(self):
        self.assertEqual(kv("3 times"), [(NUMBER, 3), (KEYWORD, "times")])


class TestNumbers(unittest.TestCase):
    def test_digits_and_words(self):
        self.assertEqual(kv("1 10"), [(NUMBER, 1), (NUMBER, 10)])
        self.assertEqual(kv("one three ten"), [(NUMBER, 1), (NUMBER, 3), (NUMBER, 10)])

    def test_out_of_range_is_a_name(self):
        self.assertEqual(kv("11"), [(NAME, "11")])
        self.assertEqual(kv("0"), [(NAME, "0")])


class TestPartsAndKeywords(unittest.TestCase):
    def test_parts(self):
        self.assertEqual(kv("morning"), [(PART, (7, 12))])
        self.assertEqual(kv("afternoon"), [(PART, (12, 17))])
        self.assertEqual(kv("evening"), [(PART, (17, 22))])

    def test_plural_parts(self):
        self.assertEqual(kv("mornings"), [(PART, (7, 12))])

    def test_every_keyword(self):
        words = ("no nothing free preferably not before after times hours hour "
                 "for on at i have and").split()
        for word in words:
            self.assertEqual(kv(word), [(KEYWORD, word)])

    def test_comma_is_a_keyword(self):
        self.assertEqual(kv("gym, study"), [(NAME, "gym"), (KEYWORD, ","), (NAME, "study")])
        self.assertEqual(kv("gym,study"), [(NAME, "gym"), (KEYWORD, ","), (NAME, "study")])


class TestNamesAndPunctuation(unittest.TestCase):
    def test_anything_else_is_a_name(self):
        self.assertEqual(kv("gym study group"), [(NAME, "gym"), (NAME, "study"), (NAME, "group")])
        self.assertEqual(kv("don't"), [(NAME, "don't")])

    def test_lowercases_first(self):
        self.assertEqual(kv("GYM Preferably MORNINGS"),
                         [(NAME, "gym"), (KEYWORD, "preferably"), (PART, (7, 12))])

    def test_sentence_punctuation_is_skipped_but_odd_symbols_are_names(self):
        self.assertEqual(kv("gym!"), [(NAME, "gym")])
        self.assertEqual(kv("gym @ 9pm"), [(NAME, "gym"), (NAME, "@"), (TIME, 21)])

    def test_empty_and_blank(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize("   "), [])

    def test_positions(self):
        tokens = tokenize("gym  at 9pm")
        self.assertEqual([t.pos for t in tokens], [0, 5, 8])


class TestFullSentences(unittest.TestCase):
    def test_example_request(self):
        got = kv("gym three times, nothing after 9pm, gym preferably mornings")
        self.assertEqual(got, [
            (NAME, "gym"), (NUMBER, 3), (KEYWORD, "times"), (KEYWORD, ","),
            (KEYWORD, "nothing"), (KEYWORD, "after"), (TIME, 21), (KEYWORD, ","),
            (NAME, "gym"), (KEYWORD, "preferably"), (PART, (7, 12)),
        ])

    def test_fixed_event_sentence(self):
        got = kv("I have class on Monday at 9am for 2 hours")
        self.assertEqual(got, [
            (KEYWORD, "i"), (KEYWORD, "have"), (NAME, "class"), (KEYWORD, "on"),
            (DAY, (0,)), (KEYWORD, "at"), (TIME, 9), (KEYWORD, "for"),
            (NUMBER, 2), (KEYWORD, "hours"),
        ])

    def test_reject_sentence(self):
        self.assertEqual(kv("not tuesday morning"),
                         [(KEYWORD, "not"), (DAY, (1,)), (PART, (7, 12))])


if __name__ == "__main__":
    unittest.main()
