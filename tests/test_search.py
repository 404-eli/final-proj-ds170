"""tests for the search code (run from project root: python -m unittest tests.test_search).

each hand-made week is a dict of keyword arguments for build_problem(). the
weeks are kept small by blocking most of the grid, so a brute-force check that
tries every possible placement can confirm the optimal cost independently.
"""

import itertools
import unittest

from model import (Block, FixedEvent, Preference, Task, all_slots, day_of,
                   day_slots, from_slot, hour_range, task_bits, to_slot)
from search.astar import astar
from search.dfs import dfs
from search.heuristic import make_heuristic, zero_heuristic
from search.problem import (build_problem, initial_state, schedule_of,
                            successors)


# ---------------------------------------------------------------- week builders

# a Block covering every slot of the week except the listed (day, hour) pairs.
def only_open(pairs):
    return Block(all_slots() - frozenset(to_slot(d, h) for d, h in pairs))


# the 3-day reference example from PLAN.md on the 7-day grid.
# each of mon/tue/wed keeps three open hours: 9 (morning), 14 (afternoon) and
# 19 (evening). every other hour, and thu-sun, is blocked.
def tiny_week(extra_blocks=()):
    open_pairs = [(d, h) for d in range(3) for h in (9, 14, 19)]
    morning = {to_slot(d, 9) for d in range(3)}
    afternoon = {to_slot(d, 14) for d in range(3)}
    return dict(
        tasks=[Task("Gym", 1, 2), Task("Study", 1, 1)],
        fixed_events=[FixedEvent("Class", [to_slot(0, 9)])],
        blocks=[only_open(open_pairs), Block([to_slot(2, 19)]), *extra_blocks],
        preferences=[Preference("Gym", morning, 2), Preference("Study", afternoon, 1)],
    )


# gym x2 both want the one open morning slot, so one of them pays a penalty.
def clash_week():
    open_pairs = [(1, 9), (2, 14), (3, 14), (4, 19)]
    return dict(
        tasks=[Task("Gym", 1, 2), Task("Read", 1, 1)],
        blocks=[only_open(open_pairs)],
        preferences=[Preference("Gym", {to_slot(1, 9)}, 2),
                     Preference("Read", {to_slot(3, 14)}, 1)],
    )


# two-hour tasks next to the 10 pm edge, plus a fixed event.
def long_tasks_week():
    open_pairs = [(0, 8), (0, 9), (0, 10), (0, 11), (1, 20), (1, 21), (2, 9),
                  (2, 10), (2, 11), (2, 12)]
    return dict(
        tasks=[Task("Study", 2, 2), Task("Read", 1, 1)],
        fixed_events=[FixedEvent("Lab", [to_slot(0, 9)])],
        blocks=[only_open(open_pairs)],
        preferences=[Preference("Read", {to_slot(1, 20)}, 2),
                     Preference("Study", {to_slot(2, 9), to_slot(2, 10)}, 3)],
    )


# six copies and exactly six open hours, so every hour gets used.
def packed_week():
    open_pairs = [(0, 9), (0, 10), (0, 11), (1, 9), (1, 10), (1, 11)]
    morning = {to_slot(0, 9), to_slot(0, 10), to_slot(0, 11)}
    return dict(
        tasks=[Task("Gym", 1, 2), Task("Study", 1, 2), Task("Read", 1, 2)],
        blocks=[only_open(open_pairs)],
        preferences=[Preference("Gym", morning, 2), Preference("Study", morning, 1)],
    )


# a wide-open week with a nightly 9 pm cutoff: a "light" load.
def light_week():
    cutoff = Block(frozenset().union(*(hour_range(d, 21, 22) for d in range(7))))
    mornings = frozenset().union(*(hour_range(d, 7, 12) for d in range(7)))
    afternoons = frozenset().union(*(hour_range(d, 12, 17) for d in range(7)))
    return dict(
        tasks=[Task("Gym", 1, 2), Task("Study", 1, 1)],
        blocks=[cutoff],
        preferences=[Preference("Gym", mornings, 2), Preference("Study", afternoons, 1)],
    )


# a week where the rules cannot all be met although every domain is non-empty:
# two tasks, one open hour.
def crowded_week():
    return dict(
        tasks=[Task("Gym", 1, 1), Task("Study", 1, 1)],
        blocks=[only_open([(0, 9)])],
    )


# a week where one copy has no legal start slot at all (every hour blocked).
def empty_domain_week():
    return dict(tasks=[Task("Gym", 1, 1)], blocks=[Block(all_slots())])


SOLVABLE_WEEKS = {
    "tiny": tiny_week,
    "tiny_after_reject": lambda: tiny_week([Block(hour_range(1, 7, 12))]),
    "clash": clash_week,
    "long_tasks": long_tasks_week,
    "packed": packed_week,
    "light": light_week,
}


# ------------------------------------------------------------ independent oracle

# cost of a full assignment, computed straight from the rules (not from the
# problem's step_costs table), to cross-check the code under test.
def rule_cost(problem, placements, week, old_schedule=None, move_penalty=3):
    total = 0
    for copy, start in zip(problem.copies, placements):
        for pref in week.get("preferences", ()):
            if pref.task_name == copy.task_name and start not in pref.good_slots:
                total += pref.penalty
        if old_schedule and copy in old_schedule and old_schedule[copy] != start:
            total += move_penalty
    return total


# try every combination of start slots and return the lowest valid cost.
def brute_force_cost(problem, week, old_schedule=None):
    best = None
    for combo in itertools.product(*problem.domains):
        mask, ok = 0, True
        for k, (copy, start) in enumerate(zip(problem.copies, combo)):
            bits = task_bits(start, copy.duration)
            same_task_before = k > 0 and problem.copies[k - 1].task_name == copy.task_name
            if mask & bits or (same_task_before and combo[k - 1] >= start):
                ok = False
                break
            mask |= bits
        if ok:
            cost = rule_cost(problem, combo, week, old_schedule)
            best = cost if best is None else min(best, cost)
    return best


def solve_all(week, old_schedule=None):
    problem = build_problem(**week, old_schedule=old_schedule)
    h = make_heuristic(problem)
    return problem, astar(problem, h), astar(problem, zero_heuristic), dfs(problem)


# ------------------------------------------------------------------------ tests

class TestReferenceExample(unittest.TestCase):
    def test_best_schedule_costs_zero(self):
        problem, result, _, _ = solve_all(tiny_week())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.cost, 0)
        got = {(c.task_name, c.number): from_slot(s) for c, s in result.schedule.items()}
        self.assertEqual(got, {("Gym", 1): (1, 9),      # gym tue am
                               ("Gym", 2): (2, 9),      # gym wed am
                               ("Study", 1): (0, 14)})  # study mon pm

    def test_not_tuesday_morning_costs_two(self):
        week = tiny_week([Block(hour_range(1, 7, 12))])
        _, result, ucs_result, _ = solve_all(week)
        self.assertEqual(result.cost, 2)
        self.assertEqual(ucs_result.cost, 2)


class TestOptimality(unittest.TestCase):
    def test_astar_matches_ucs_and_brute_force(self):
        for name, make_week in SOLVABLE_WEEKS.items():
            with self.subTest(week=name):
                week = make_week()
                problem, a, u, _ = solve_all(week)
                self.assertEqual(a.status, "ok")
                self.assertEqual(a.cost, u.cost)
                if name != "light":     # light week is too big to brute-force
                    self.assertEqual(a.cost, brute_force_cost(problem, week))

    def test_astar_expands_no_more_than_ucs(self):
        for name, make_week in SOLVABLE_WEEKS.items():
            with self.subTest(week=name):
                _, a, u, _ = solve_all(make_week())
                self.assertLessEqual(a.nodes_expanded, u.nodes_expanded)

    def test_start_heuristic_is_admissible(self):
        for name, make_week in SOLVABLE_WEEKS.items():
            with self.subTest(week=name):
                problem, a, _, _ = solve_all(make_week())
                self.assertLessEqual(make_heuristic(problem)(initial_state()), a.cost)

    def test_heuristic_is_consistent_everywhere(self):
        # walk every state of two small weeks and check h(s) <= step + h(s').
        for make_week in (tiny_week, packed_week, long_tasks_week):
            problem = build_problem(**make_week())
            h = make_heuristic(problem)
            stack = [initial_state()]
            while stack:
                state = stack.pop()
                if state[0] == len(problem.copies):
                    continue
                for nxt, step in successors(problem, state):
                    self.assertLessEqual(h(state), step + h(nxt))
                    stack.append(nxt)

    def test_dfs_finds_a_valid_but_possibly_costlier_schedule(self):
        for name, make_week in SOLVABLE_WEEKS.items():
            with self.subTest(week=name):
                _, a, _, d = solve_all(make_week())
                self.assertEqual(d.status, "ok")
                self.assertGreaterEqual(d.cost, a.cost)


class TestReplanning(unittest.TestCase):
    def test_move_penalty_is_charged_and_cost_matches_oracle(self):
        _, first, _, _ = solve_all(tiny_week())
        old = first.schedule
        week = tiny_week([Block(hour_range(1, 7, 12))])      # "not tuesday morning"
        problem, a, u, _ = solve_all(week, old_schedule=old)
        self.assertEqual(a.cost, u.cost)
        self.assertEqual(a.cost, brute_force_cost(problem, week, old))
        moved = [c for c, s in a.schedule.items() if old[c] != s]
        self.assertTrue(moved)                       # gym#1 had to leave tuesday
        self.assertGreater(a.cost, 2)                # moving costs extra

    def test_unchanged_week_costs_nothing_extra(self):
        _, first, _, _ = solve_all(tiny_week())
        _, again, _, _ = solve_all(tiny_week(), old_schedule=first.schedule)
        self.assertEqual(again.cost, first.cost)
        self.assertEqual(again.schedule, first.schedule)


class TestFailureModes(unittest.TestCase):
    def test_crowded_week_is_impossible(self):
        _, a, u, d = solve_all(crowded_week())
        self.assertEqual((a.status, u.status, d.status), ("impossible",) * 3)
        self.assertIsNone(a.schedule)

    def test_empty_domain_is_impossible_without_searching(self):
        problem, a, u, d = solve_all(empty_domain_week())
        self.assertTrue(problem.impossible)
        for result in (a, u, d):
            self.assertEqual(result.status, "impossible")
            self.assertEqual(result.nodes_expanded, 0)

    def test_node_limit_returns_limit_status(self):
        problem = build_problem(**light_week())
        for result in (astar(problem, zero_heuristic, node_limit=3),
                       dfs(problem, node_limit=1)):
            self.assertEqual(result.status, "limit")
            self.assertIsNone(result.schedule)


class TestScheduleValidity(unittest.TestCase):
    def test_no_task_crosses_a_day_or_10pm_and_nothing_overlaps(self):
        for name, make_week in SOLVABLE_WEEKS.items():
            week = make_week()
            problem, a, u, d = solve_all(week)
            forbidden = set()
            for block in week.get("blocks", ()):
                forbidden |= block.slots
            for event in week.get("fixed_events", ()):
                forbidden |= event.slots
            for result in (a, u, d):
                with self.subTest(week=name):
                    used = set()
                    for copy, start in result.schedule.items():
                        last = start + copy.duration - 1
                        self.assertEqual(day_of(start), day_of(last))
                        self.assertLessEqual(from_slot(last)[1] + 1, 22)
                        slots = set(range(start, last + 1))
                        self.assertFalse(slots & used)          # no overlap
                        self.assertFalse(slots & forbidden)     # respects rules
                        used |= slots


if __name__ == "__main__":
    unittest.main()
