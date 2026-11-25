"""tests for main.py's command handling (run: python -m unittest tests.test_main).

these drive handle() directly with lines of text, the same way the loop does.
"""

import unittest

from main import Session, handle, handle_request
from model import Task

FIRST = "gym three times, nothing after 9pm, gym preferably mornings"


class TestCommands(unittest.TestCase):
    def test_blank_help_and_show_before_any_plan(self):
        session = Session()
        self.assertEqual(handle(session, "   "), "")
        self.assertIn("commands:", handle(session, "help"))
        self.assertIn("nothing planned yet", handle(session, "show"))

    def test_reset_clears_everything(self):
        session = Session()
        handle(session, FIRST)
        self.assertEqual(handle(session, "reset"), "all rules cleared.")
        self.assertEqual((session.tasks, session.blocks, session.schedule), ({}, [], None))
        self.assertIn("nothing planned yet", handle(session, "show"))


class TestPlanning(unittest.TestCase):
    def test_first_request_shows_rules_grid_and_stats(self):
        session = Session()
        out = handle(session, FIRST)
        self.assertIn("task: gym, 3 times", out)
        self.assertIn("block (nothing scheduled): every day 9pm-10pm", out)
        self.assertIn("preference: gym preferably every day 7am-12pm", out)
        self.assertIn("[N] gym", out)
        self.assertIn("cost: 0", out)
        self.assertEqual(len(session.schedule), 3)
        self.assertIsNone(session.previous)

    def test_second_request_marks_moved_items(self):
        session = Session()
        handle(session, FIRST)
        first_schedule = dict(session.schedule)
        out = handle(session, "not monday morning")     # gym starts on monday morning
        self.assertIn("[M] gym", out)
        self.assertNotIn("[N]", out)
        self.assertEqual(session.previous, first_schedule)
        self.assertNotEqual(session.schedule, first_schedule)
        self.assertIn("cost: 9", out)                   # three moves at 3 each

    def test_a_rule_that_changes_nothing_moves_nothing(self):
        session = Session()
        handle(session, FIRST)
        out = handle(session, "not tuesday morning")    # gym is not on tuesday
        self.assertNotIn("[M]", out)
        self.assertIn("cost: 0", out)

    def test_show_repeats_the_latest_plan(self):
        session = Session()
        handle(session, FIRST)
        out = handle(session, "not monday morning")
        self.assertEqual(handle(session, "show"), out.split("\n\n", 1)[1])

    def test_new_task_is_marked_new_and_old_ones_are_not(self):
        session = Session()
        handle(session, "gym")
        out = handle(session, "study for 2 hours")
        self.assertIn("[N] study", out)
        self.assertNotIn("[N] gym", out)

    def test_same_task_name_replaces_the_old_request(self):
        session = Session()
        handle(session, "gym three times")
        handle(session, "gym 2 times")
        self.assertEqual(session.tasks, {"gym": Task("gym", 1, 2)})
        self.assertEqual(len(session.schedule), 2)

    def test_repeating_a_rule_does_not_duplicate_it(self):
        session = Session()
        handle(session, FIRST)
        handle(session, "nothing after 9pm")
        handle(session, "gym preferably mornings")
        self.assertEqual(len(session.blocks), 1)
        self.assertEqual(len(session.preferences), 1)

    def test_fixed_event_appears_on_the_grid(self):
        session = Session()
        out = handle(session, "i have class on monday at 9am for 2 hours")
        self.assertIn("fixed event: class, Mon 9am-11am", out)
        self.assertIn("[F] class", out)


class TestFriendlyFailures(unittest.TestCase):
    def test_parse_error_changes_nothing(self):
        session = Session()
        handle(session, FIRST)
        before = (dict(session.tasks), list(session.blocks), dict(session.schedule))
        out = handle(session, "gym 3")
        self.assertIn("could not understand", out)
        self.assertIn("expected 'times'", out)
        self.assertEqual((session.tasks, session.blocks, session.schedule), before)

    def test_impossible_request_is_not_applied(self):
        session = Session()
        handle(session, "gym")
        handle(session, "nothing weekdays")
        schedule = dict(session.schedule)
        out = handle(session, "nothing weekend")        # now gym has nowhere to go
        self.assertIn("no schedule can satisfy", out)
        self.assertIn("nothing was changed", out)
        self.assertEqual(len(session.blocks), 1)
        self.assertEqual(session.schedule, schedule)

    def test_impossible_by_crowding_is_not_applied(self):
        session = Session()
        handle(session, "nothing weekdays, nothing weekend morning, nothing weekend afternoon")
        out = handle(session, "gym 3 times for 5 hours")  # 15 hours, only 5 free evening hours
        self.assertIn("no schedule can satisfy", out)
        self.assertEqual(session.tasks, {})

    def test_search_limit_is_reported_and_not_applied(self):
        session = Session()
        out = handle_request(session, "gym three times, study 2 times", node_limit=1)
        self.assertIn("search limit reached", out)
        self.assertIn("not applied", out)
        self.assertEqual(session.tasks, {})
        self.assertIsNone(session.schedule)


if __name__ == "__main__":
    unittest.main()
