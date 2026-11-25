"""tests for parser/parser.py (run from project root: python -m unittest tests.test_parser)."""

import unittest

from model import (Block, FixedEvent, Preference, Task, hour_range, to_slot)
from parser.parser import ParseError, parse

DAYS = range(7)


# slots for hours [start, end) on every day of the week.
def every_day(start, end):
    return frozenset().union(*(hour_range(d, start, end) for d in DAYS))


class TestTasks(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(parse("gym"), [Task("gym", 1, 1)])

    def test_count(self):
        self.assertEqual(parse("gym three times"), [Task("gym", 1, 3)])
        self.assertEqual(parse("gym 3 times"), [Task("gym", 1, 3)])

    def test_duration(self):
        self.assertEqual(parse("study for 2 hours"), [Task("study", 2, 1)])
        self.assertEqual(parse("study for 1 hour"), [Task("study", 1, 1)])

    def test_count_and_duration(self):
        self.assertEqual(parse("study two times for three hours"), [Task("study", 3, 2)])

    def test_multi_word_name(self):
        self.assertEqual(parse("study group 2 times"), [Task("study group", 1, 2)])

    def test_name_may_start_with_do(self):
        self.assertEqual(parse("do laundry"), [Task("do laundry", 1, 1)])


class TestBlocksAndRejects(unittest.TestCase):
    def test_nothing_after(self):
        self.assertEqual(parse("nothing after 9pm"), [Block(every_day(21, 22))])

    def test_no_before(self):
        self.assertEqual(parse("no before 9am"), [Block(every_day(7, 9))])

    def test_whole_day_and_part(self):
        self.assertEqual(parse("free sunday"), [Block(hour_range(6, 7, 22))])
        self.assertEqual(parse("no friday evening"), [Block(hour_range(4, 17, 22))])

    def test_day_with_bound(self):
        self.assertEqual(parse("nothing tuesday after 6pm"), [Block(hour_range(1, 18, 22))])

    def test_part_alone_is_every_day(self):
        self.assertEqual(parse("no mornings"), [Block(every_day(7, 12))])

    def test_group_days(self):
        weekend = hour_range(5, 7, 22) | hour_range(6, 7, 22)
        self.assertEqual(parse("nothing weekend"), [Block(weekend)])
        weekday_mornings = frozenset().union(*(hour_range(d, 7, 12) for d in range(5)))
        self.assertEqual(parse("no weekdays morning"), [Block(weekday_mornings)])

    def test_do_not_schedule_anything(self):
        self.assertEqual(parse("do not schedule anything after 9pm"),
                         [Block(every_day(21, 22))])

    def test_reject(self):
        self.assertEqual(parse("not tuesday morning"), [Block(hour_range(1, 7, 12))])

    def test_rounded_time(self):
        self.assertEqual(parse("nothing after 8:30pm"), [Block(every_day(21, 22))])


class TestPreferencesAndFixed(unittest.TestCase):
    def test_preference(self):
        self.assertEqual(parse("gym preferably mornings"),
                         [Preference("gym", every_day(7, 12), 2)])

    def test_preference_with_day(self):
        self.assertEqual(parse("study preferably monday afternoon"),
                         [Preference("study", hour_range(0, 12, 17), 2)])

    def test_fixed_event(self):
        got = parse("i have class on monday at 9am for 2 hours")
        self.assertEqual(got, [FixedEvent("class", [to_slot(0, 9), to_slot(0, 10)])])

    def test_fixed_default_duration(self):
        self.assertEqual(parse("I have lab on Wed at 1pm"),
                         [FixedEvent("lab", [to_slot(2, 13)])])

    def test_fixed_on_several_days(self):
        got = parse("i have standup on weekdays at 9am")
        self.assertEqual(got, [FixedEvent("standup", [to_slot(d, 9) for d in range(5)])])


class TestRequests(unittest.TestCase):
    def test_example_request(self):
        got = parse("gym three times, nothing after 9pm, gym preferably mornings")
        self.assertEqual(got, [Task("gym", 1, 3), Block(every_day(21, 22)),
                               Preference("gym", every_day(7, 12), 2)])

    def test_and_separator(self):
        self.assertEqual(parse("gym and study"), [Task("gym"), Task("study")])

    def test_mixed_case_and_punctuation(self):
        self.assertEqual(parse("Gym 2 Times, Not Tuesday Morning!"),
                         [Task("gym", 1, 2), Block(hour_range(1, 7, 12))])


class TestErrors(unittest.TestCase):
    # parse the text, expect a ParseError, and return it for inspection.
    def fail(self, text):
        with self.assertRaises(ParseError) as caught:
            parse(text)
        return caught.exception

    def test_error_names_the_token(self):
        err = self.fail("gym 3 hours")
        self.assertEqual(err.token.text, "hours")
        self.assertIn("'hours'", str(err))
        self.assertIn("position 6", str(err))

    def test_end_of_input_errors(self):
        for text in ["", "gym,", "gym and", "nothing", "gym preferably",
                     "gym three", "gym for", "not", "i have class on monday at"]:
            with self.subTest(text=text):
                self.assertIsNone(self.fail(text).token)

    def test_cannot_start_a_clause(self):
        for text in ["9pm", "monday", "after 9pm", "morning", "before"]:
            with self.subTest(text=text):
                self.assertEqual(self.fail(text).token.text, text)

    def test_bad_time_expressions(self):
        self.assertEqual(self.fail("nothing gym").token.text, "gym")
        self.assertEqual(self.fail("nothing after gym").token.text, "gym")
        self.assertEqual(self.fail("nothing after 9").token.text, "9")

    def test_leftover_tokens(self):
        self.assertEqual(self.fail("nothing after 9pm gym").token.text, "gym")
        self.assertEqual(self.fail("gym 3 times 4").token.text, "4")

    def test_fixed_event_must_follow_the_grammar(self):
        self.assertEqual(self.fail("i have class monday at 9am").token.text, "monday")
        self.assertEqual(self.fail("i class on monday at 9am").token.text, "class")
        self.assertEqual(self.fail("i have class on monday at 9").token.text, "9")

    def test_fixed_event_must_fit_the_grid(self):
        self.assertEqual(self.fail("i have class on monday at 6am").token.text, "6am")
        self.assertEqual(self.fail("i have class on monday at 9pm for 2 hours").token.text, "2")
        self.assertEqual(self.fail("i have class on monday at 10pm").token.text, "10pm")

    def test_separator_without_clause(self):
        self.assertEqual(self.fail("gym, , study").token.text, ",")

    def test_two_days_need_a_separator(self):
        self.assertEqual(self.fail("nothing monday tuesday").token.text, "tuesday")

    def test_do_not_schedule_must_be_complete(self):
        self.assertEqual(self.fail("do not schedule after 9pm").token.text, "not")


if __name__ == "__main__":
    unittest.main()
