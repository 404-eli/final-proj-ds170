"""heuristics for a* search.

a heuristic h(state) estimates the cost still to come. for a* to return an
optimal schedule it must never overestimate (be admissible).
"""


# the "no information" heuristic. a* with this is uniform-cost search (ucs).
def zero_heuristic(state):
    return 0


# build the heuristic for one problem.
# idea: every copy that has not been placed yet must still pay at least its
# cheapest possible step cost, so the remaining cost is at least the sum of
# those minimums. the minimum for a copy ignores every other task, which can
# only make it smaller than the real cost. so h never overestimates.
#
# process:
#   1. for each copy k take min(step_costs[k].values()). the step cost already
#      includes the move penalty, so the minimum counts it as 0 whenever the
#      copy's old slot is still in its domain.
#   2. suffix[k] = sum of those minimums for copies k .. end, built from the
#      back so each h(state) call is just one list lookup.
# h(state) = suffix[k], where k is the index of the next copy to place.
#
# this h is also consistent: placing copy k costs at least its minimum, which
# is exactly how much h drops, so h(s) <= cost(s, s') + h(s'). that is why a*
# can safely skip a state it has already reached more cheaply.
def make_heuristic(problem):
    n = len(problem.copies)
    suffix = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        cheapest = min(problem.step_costs[k].values(), default=0)
        suffix[k] = suffix[k + 1] + cheapest

    def h(state):
        return suffix[state[0]]

    return h
