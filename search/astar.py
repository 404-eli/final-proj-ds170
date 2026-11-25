"""a* search (and uniform-cost search) for atesked, written with heapq."""

import heapq
import time

from search.problem import (NODE_LIMIT, initial_state, is_goal, make_result,
                            successors)


# a* search: find the schedule with the lowest total cost.
# the heuristic is passed in, so one function covers both algorithms:
#   astar(problem, make_heuristic(problem))   a*
#   astar(problem, zero_heuristic)            uniform-cost search (h = 0)
#
# process:
#   1. if some copy has an empty domain, return "impossible" right away.
#   2. keep a priority queue of entries (f, counter, g, state) where g is the
#      cost so far and f = g + h(state). the counter only breaks ties between
#      equal f values (earlier-generated first) so heapq never compares states.
#   3. best_g remembers the cheapest g found for each state. when a state is
#      popped with a g worse than best_g, it is a stale entry and is skipped.
#   4. pop the lowest-f entry. if it is a goal, it is optimal (h is
#      consistent), so return it. otherwise expand it: for each successor
#      compute its new g, and push it only if that beats the best g seen so far.
#   5. if node_limit states have been expanded without finishing, stop with
#      status "limit". if the queue empties, no schedule exists: "impossible".
# nodes_expanded counts states whose successors were generated; nodes_generated
# counts successor states pushed onto the queue.
def astar(problem, heuristic, node_limit=NODE_LIMIT):
    start_time = time.perf_counter()
    if problem.impossible:
        return make_result("impossible", problem, None, None, 0, 0, start_time)

    start = initial_state()
    best_g = {start: 0}
    counter = 0
    frontier = [(heuristic(start), counter, 0, start)]
    expanded = generated = 0

    while frontier:
        _, _, g, state = heapq.heappop(frontier)
        if g > best_g[state]:
            continue
        if is_goal(problem, state):
            return make_result("ok", problem, state, g, expanded, generated, start_time)
        if expanded >= node_limit:
            return make_result("limit", problem, None, None, expanded, generated, start_time)
        expanded += 1
        for nxt, step in successors(problem, state):
            new_g = g + step
            if new_g < best_g.get(nxt, float("inf")):
                best_g[nxt] = new_g
                counter += 1
                generated += 1
                heapq.heappush(frontier, (new_g + heuristic(nxt), counter, new_g, nxt))

    return make_result("impossible", problem, None, None, expanded, generated, start_time)
