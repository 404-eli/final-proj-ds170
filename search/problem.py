"""search problem for atesked: domains, states, successors and costs.

how the problem is set up
-------------------------
the flexible tasks are expanded into copies (gym#1, gym#2, ...) in a fixed
order, and search places them one at a time in that order. everything the
search needs to know about the rules is worked out once, up front, in
build_problem():

    domains[k]      the start slots copy k is allowed to use (it fits on one
                    day and does not touch a block or fixed event)
    step_costs[k]   {start slot: cost of placing copy k there}, which is the
                    preference penalty plus the move penalty when re-planning

a search state is the tuple (k, placements, mask):

    k           index of the next copy to place (k == len(copies) means done)
    placements  start slot of each copy placed so far
    mask        bitmask of the slots those copies occupy

states are plain tuples of ints, so they are hashable and can be dictionary keys.
"""

import time
from dataclasses import dataclass

from model import (MOVE_PENALTY, NUM_SLOTS, expand_tasks, fits_in_day,
                   mask_of, task_bits)

NODE_LIMIT = 200_000      # default cap on expanded nodes before search gives up


# what every search function returns.
# status is "ok" (schedule and cost are filled in), "impossible" (no schedule
# can satisfy the hard rules) or "limit" (the node limit was hit first).
# schedule is a dict {copy: start_slot}, or None when status is not "ok".
@dataclass
class SearchResult:
    status: str
    schedule: dict = None
    cost: int = None
    nodes_expanded: int = 0
    nodes_generated: int = 0
    runtime_seconds: float = 0.0


# everything the search needs, computed once from the user's rules.
@dataclass
class Problem:
    copies: list          # task copies in placement order
    domains: list         # domains[k] = tuple of allowed start slots for copy k
    step_costs: list      # step_costs[k] = {start slot: cost}

    # true when some copy has no legal start slot at all. no search can fix
    # that, so callers report "impossible" without searching.
    @property
    def impossible(self):
        return any(not d for d in self.domains)


# turn the rules into a Problem.
# steps:
#   1. expand the tasks into copies, sorted by name then copy number.
#   2. forbidden = every slot used by a block or a fixed event, as a bitmask.
#   3. for each copy, keep the start slots where it fits on one day and its
#      bits do not overlap forbidden. these are its domain.
#   4. for each (copy, start) work out the step cost: the penalty of every
#      preference for that task whose good_slots do not include the start slot,
#      plus move_penalty if an old schedule exists, this copy was in it, and it
#      sat at a different slot.
# old_schedule is the previous {copy: start_slot} dict when re-planning, else None.
def build_problem(tasks, fixed_events=(), blocks=(), preferences=(),
                  old_schedule=None, move_penalty=MOVE_PENALTY):
    copies = expand_tasks(tasks)
    forbidden = 0
    for event in fixed_events:
        forbidden |= mask_of(event.slots)
    for block in blocks:
        forbidden |= mask_of(block.slots)

    domains, step_costs = [], []
    for copy in copies:
        prefs = [p for p in preferences if p.task_name == copy.task_name]
        domain, costs = [], {}
        for start in range(NUM_SLOTS):
            if not fits_in_day(start, copy.duration):
                continue
            if task_bits(start, copy.duration) & forbidden:
                continue
            cost = sum(p.penalty for p in prefs if start not in p.good_slots)
            if old_schedule is not None and copy in old_schedule \
                    and old_schedule[copy] != start:
                cost += move_penalty
            domain.append(start)
            costs[start] = cost
        domains.append(tuple(domain))
        step_costs.append(costs)
    return Problem(copies, domains, step_costs)


# the state before anything is placed: copy 0 is next, nothing placed, no slots taken.
def initial_state():
    return (0, (), 0)


# a state is a goal once every copy has been placed.
def is_goal(problem, state):
    return state[0] == len(problem.copies)


# list the states reachable by placing the next copy, with the cost of each move.
# for every start slot in the next copy's domain:
#   - skip it if its bits overlap a slot already taken (mask & bits != 0)
#   - skip it if the previous copy of the same task starts at or after it.
#     copies of one task are interchangeable, so this forces them into
#     increasing start order and avoids searching the same schedule twice.
# the new state is (k + 1, placements + (start,), mask | bits).
def successors(problem, state):
    k, placements, mask = state
    copy = problem.copies[k]
    prev_start = -1
    if k > 0 and problem.copies[k - 1].task_name == copy.task_name:
        prev_start = placements[k - 1]
    result = []
    for start in problem.domains[k]:
        if start <= prev_start:
            continue
        bits = task_bits(start, copy.duration)
        if mask & bits:
            continue
        result.append(((k + 1, placements + (start,), mask | bits),
                       problem.step_costs[k][start]))
    return result


# convert a goal state's placements into the {copy: start_slot} dict that the
# display code and later re-planning use.
def schedule_of(problem, state):
    return dict(zip(problem.copies, state[1]))


# build a SearchResult, filling in the schedule and cost only when status is "ok".
def make_result(status, problem, state, cost, expanded, generated, start_time):
    return SearchResult(
        status=status,
        schedule=schedule_of(problem, state) if status == "ok" else None,
        cost=cost if status == "ok" else None,
        nodes_expanded=expanded,
        nodes_generated=generated,
        runtime_seconds=time.perf_counter() - start_time,
    )
