"""Tests for model.py (run from project root: python -m unittest tests.test_model)."""

import unittest

from model import (Block, Copy, FixedEvent, Preference, Task, day_of,
                    day_slots, expand_tasks, fits_in_day, from_slot,
                    hour_range, mask_of, task_bits, to_slot, NUM_SLOTS)


class TestSlots(unittest.TestCase):
    def test_corners(self):
        self.assertEqual(to_slot(0, 7), 0)
        self.assertEqual(to_slot(0, 21), 14)
        self.assertEqual(to_slot(1, 7), 15)
        self.assertEqual(to_slot(6, 21), NUM_SLOTS - 1)

    def test_roundtrip(self):
        for s in range(NUM_SLOTS):
            self.assertEqual(to_slot(*from_slot(s)), s)

    def test_out_of_range(self):
        for args in [(0, 6), (0, 22), (7, 9), (-1, 9)]:
            with self.assertRaises(ValueError):
                to_slot(*args)
        with self.assertRaises(ValueError):
            from_slot(NUM_SLOTS)

    def test_day_of(self):
        self.assertEqual(day_of(14), 0)
        self.assertEqual(day_of(15), 1)
        self.assertEqual(day_of(104), 6)

    def test_ranges(self):
        self.assertEqual(len(day_slots(3)), 15)
        self.assertEqual(hour_range(0, 7, 12), frozenset(range(0, 5)))
        self.assertEqual(hour_range(0, 21, 30), frozenset({14}))  # clipped
        self.assertEqual(hour_range(0, 3, 7), frozenset())        # empty

    def test_fits_in_day(self):
        self.assertTrue(fits_in_day(to_slot(0, 20), 2))    # 8-10 PM ok
        self.assertFalse(fits_in_day(to_slot(0, 21), 2))   # would pass 10 PM
        self.assertTrue(fits_in_day(to_slot(0, 7), 15))
        self.assertFalse(fits_in_day(to_slot(0, 7), 16))
        self.assertFalse(fits_in_day(NUM_SLOTS, 1))


class TestMasks(unittest.TestCase):
    def test_mask_of(self):
        self.assertEqual(mask_of([0, 2]), 0b101)
        self.assertEqual(mask_of([]), 0)

    def test_task_bits_and_overlap(self):
        self.assertEqual(task_bits(3, 2), 0b11000)
        occupied = mask_of([4])
        self.assertNotEqual(occupied & task_bits(3, 2), 0)   # overlaps
        self.assertEqual(occupied & task_bits(5, 2), 0)      # free


class TestRules(unittest.TestCase):
    def test_hashable(self):
        rules = [FixedEvent("Class", [0, 1]), Block([2, 3]),
                 Task("Gym", 1, 3), Preference("Gym", [0], 2), Copy("Gym", 1, 1)]
        self.assertEqual(len({*rules}), len(rules))

    def test_slots_normalised_to_frozenset(self):
        self.assertIsInstance(Block([1, 2]).slots, frozenset)
        self.assertEqual(Block([1, 2]), Block((2, 1)))

    def test_defaults(self):
        t = Task("Study")
        self.assertEqual((t.duration, t.count), (1, 1))
        self.assertEqual(Preference("Gym", []).penalty, 2)


class TestExpand(unittest.TestCase):
    def test_order_and_numbers(self):
        copies = expand_tasks([Task("Study", 2, 1), Task("Gym", 1, 3)])
        self.assertEqual([c.label for c in copies],
                         ["Gym#1", "Gym#2", "Gym#3", "Study#1"])
        self.assertEqual(copies[-1].duration, 2)

    def test_empty(self):
        self.assertEqual(expand_tasks([]), [])


if __name__ == "__main__":
    unittest.main()
