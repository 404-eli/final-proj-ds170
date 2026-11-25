"""tests for parser/keyword_baseline.py (run: python -m unittest tests.test_baseline).

the baseline is allowed to be wrong, so these tests only pin down what it must
do: handle plain sentences like the real parser, and never raise an error.
"""

import unittest

from model import Block, FixedEvent, Preference, Task, hour_range, to_slot
from parser.keyword_baseline import parse_baseline
from tests.parser_cases import CASES, REJECTED


class TestBaselineBasics(unittest.TestCase):
    def test_task_with_count_and_duration(self):
        self.assertEqual(parse_baseline("study 2 times for 3 hours"), [Task("study", 3, 2)])

    def test_block_and_preference(self):
        got = parse_baseline("nothing after 9pm, gym preferably mornings")
        every = lambda a, b: frozenset().union(*(hour_range(d, a, b) for d in range(7)))
        self.assertEqual(got, [Block(every(21, 22)), Preference("gym", every(7, 12), 2)])

    def test_reject_and_fixed(self):
        self.assertEqual(parse_baseline("not tuesday morning"), [Block(hour_range(1, 7, 12))])
        self.assertEqual(parse_baseline("i have lab on wed at 1pm"),
                         [FixedEvent("lab", [to_slot(2, 13)])])


class TestBaselineNeverRaises(unittest.TestCase):
    def test_every_case_returns_a_list(self):
        for text, _ in CASES:
            with self.subTest(text=text):
                self.assertIsInstance(parse_baseline(text), list)

    def test_rejected_sentences_still_give_an_answer_or_nothing(self):
        # unlike the real parser it never complains. "gym 3" becomes a task
        # literally named "gym 3", and "nothing after" is silently dropped.
        self.assertEqual(parse_baseline("gym 3"), [Task("gym 3", 1, 1)])
        self.assertEqual(parse_baseline("nothing after"), [])
        self.assertEqual(parse_baseline(""), [])
        for text in REJECTED:
            parse_baseline(text)


if __name__ == "__main__":
    unittest.main()
