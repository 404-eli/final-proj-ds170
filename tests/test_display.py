"""tests for display.py (run from project root: python -m unittest tests.test_display)."""

import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from display import (describe_rule, describe_slots, hour_label, print_schedule,
                     render_grid, render_stats)
from model import Block, Copy, FixedEvent, Preference, Task, hour_range, to_slot


def grid_row(text, label):
    """return the grid line whose hour label is `label` (e.g. "9am")."""
    return next(l for l in text.splitlines() if l.startswith(label))


class TestDisplay(unittest.TestCase):
    def setUp(self):
        self.gym = Copy("Gym", 1, 1)
        self.study = Copy("Study", 1, 2)
        self.fixed = [FixedEvent("Class", [to_slot(0, 9)])]
        self.blocks = [Block(hour_range(2, 19, 22))]

    def test_hour_labels(self):
        self.assertEqual([hour_label(h) for h in (7, 11, 12, 13, 21)],
                         ["7am", "11am", "12pm", "1pm", "9pm"])

    def test_grid_shape(self):
        lines = render_grid([], [], {}).splitlines()
        self.assertEqual(len(lines), 2 + 15)           # header + rule + 15 hours
        for day in ("Mon", "Tue", "Sun"):
            self.assertIn(day, lines[0])

    def test_marks_first_plan(self):
        text = render_grid(self.fixed, self.blocks,
                           {self.gym: to_slot(1, 8)})  # gym tue 8am
        self.assertIn("[F] Class", grid_row(text, "9am"))
        self.assertIn("[N] Gym", grid_row(text, "8am"))
        self.assertIn("x", grid_row(text, "7pm"))      # wed evening blocked

    def test_moved_and_unchanged(self):
        old = {self.gym: to_slot(1, 8), self.study: to_slot(0, 13)}
        new = {self.gym: to_slot(2, 8), self.study: to_slot(0, 13)}
        text = render_grid([], [], new, old)
        self.assertIn("[M] Gym", grid_row(text, "8am"))
        self.assertNotIn("[M] Study", text)            # unchanged: no mark
        self.assertNotIn("[N]", text)
        self.assertEqual(text.count("Study"), 2)       # 2-hour task fills 2 rows

    def test_new_copy_in_replan(self):
        old = {self.gym: to_slot(1, 8)}
        new = {self.gym: to_slot(1, 8), self.study: to_slot(0, 13)}
        text = render_grid([], [], new, old)
        self.assertIn("[N] Study", text)

    def test_fixed_wins_over_block(self):
        slot_day, hour = 0, 9
        text = render_grid([FixedEvent("Class", [to_slot(slot_day, hour)])],
                           [Block([to_slot(slot_day, hour)])], {})
        self.assertIn("[F] Class", grid_row(text, "9am"))

    def test_stats(self):
        ok = SimpleNamespace(status="ok", cost=2, nodes_expanded=17,
                             runtime_seconds=0.0123)
        self.assertEqual(render_stats(ok),
                         "cost: 2   nodes expanded: 17   runtime: 0.0123s")
        self.assertIn("no schedule", render_stats(SimpleNamespace(status="impossible")))
        limit = SimpleNamespace(status="limit", nodes_expanded=200000)
        self.assertIn("limit", render_stats(limit))

    def test_print_schedule_skips_grid_when_impossible(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_schedule(SimpleNamespace(status="impossible"), [], [])
        self.assertNotIn("Mon", buf.getvalue())
        self.assertIn("no schedule", buf.getvalue())


class TestDescribe(unittest.TestCase):
    def test_describe_slots(self):
        every = frozenset().union(*(hour_range(d, 21, 22) for d in range(7)))
        self.assertEqual(describe_slots(every), "every day 9pm-10pm")
        self.assertEqual(describe_slots(hour_range(1, 7, 12)), "Tue 7am-12pm")
        self.assertEqual(describe_slots(hour_range(6, 7, 22)), "Sun all day")
        weekdays = frozenset().union(*(hour_range(d, 17, 22) for d in range(5)))
        self.assertEqual(describe_slots(weekdays), "Mon-Fri 5pm-10pm")
        two_runs = hour_range(0, 8, 10) | hour_range(0, 14, 15)
        self.assertEqual(describe_slots(two_runs), "Mon 8am-10am, 2pm-3pm")
        split = hour_range(0, 9, 10) | hour_range(2, 9, 10)
        self.assertEqual(describe_slots(split), "Mon, Wed 9am-10am")
        self.assertEqual(describe_slots([]), "no hours at all")

    def test_describe_rule(self):
        self.assertEqual(describe_rule(Task("gym", 1, 3)), "task: gym, 3 times, 1 hour each")
        self.assertEqual(describe_rule(Task("study", 2, 1)), "task: study, once, 2 hours each")
        self.assertIn("penalty 2", describe_rule(Preference("gym", hour_range(0, 7, 12), 2)))
        self.assertEqual(describe_rule(FixedEvent("lab", [to_slot(2, 13)])),
                         "fixed event: lab, Wed 1pm-2pm")


if __name__ == "__main__":
    unittest.main()
