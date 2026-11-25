"""depth-first search for atesked: returns the first complete schedule it finds."""

import time

from search.problem import NODE_LIMIT, initial_state, is_goal, make_result, successors


# depth-first search with an explicit stack (no recursion).
# it is the simple baseline: it stops at the first complete schedule, which
# respects every hard rule but is usually NOT the cheapest one.
#
# process:
#   1. if some copy has an empty domain, return "impossible" right away.
#   2. keep a stack of (state, cost so far). pop the top entry.
#   3. if it is a goal, return it. otherwise expand it and push its successors
#      in reverse order, so the first (earliest) start slot is popped next.
#   4. if node_limit states have been expanded, stop with status "limit".
#   5. if the stack empties, every branch was tried and failed: "impossible".
# no visited set is needed: every state is reached through exactly one
# sequence of placements, so the same state never appears twice.
def dfs(problem, node_limit=NODE_LIMIT):
    start_time = time.perf_counter()
    if problem.impossible:
        return make_result("impossible", problem, None, None, 0, 0, start_time)

    stack = [(initial_state(), 0)]
    expanded = generated = 0

    while stack:
        state, g = stack.pop()
        if is_goal(problem, state):
            return make_result("ok", problem, state, g, expanded, generated, start_time)
        if expanded >= node_limit:
            return make_result("limit", problem, None, None, expanded, generated, start_time)
        expanded += 1
        children = successors(problem, state)
        generated += len(children)
        for nxt, step in reversed(children):
            stack.append((nxt, g + step))

    return make_result("impossible", problem, None, None, expanded, generated, start_time)
