"""phase 1 demo: plan a hard-coded week with a*, then re-plan after a new rule.

run from the project root:  python demo.py
there is no parser yet, so the rules are written out by hand below.
"""

from display import print_schedule
from model import Block, FixedEvent, Preference, Task, hour_range, to_slot
from search.astar import astar
from search.heuristic import make_heuristic
from search.problem import build_problem

DAYS = range(7)
MORNING = frozenset().union(*(hour_range(d, 7, 12) for d in DAYS))
AFTERNOON = frozenset().union(*(hour_range(d, 12, 17) for d in DAYS))


# build the problem, run a*, and print the grid and stats.
# old_schedule is the previous result's schedule (or None for a first plan);
# passing it makes moved copies cost extra and shows them as [M] in the grid.
def plan(title, tasks, fixed_events, blocks, preferences, old_schedule=None):
    print(f"=== {title} ===")
    problem = build_problem(tasks, fixed_events, blocks, preferences, old_schedule)
    result = astar(problem, make_heuristic(problem))
    print_schedule(result, fixed_events, blocks, result.schedule, old_schedule)
    print()
    return result


def main():
    tasks = [Task("Gym", 1, 3), Task("Study", 2, 1)]
    fixed = [FixedEvent("Class", [to_slot(0, h) for h in range(7, 12)]),   # mon 7-12
             FixedEvent("Lab", [to_slot(2, 13), to_slot(2, 14)])]    # wed 1-3
    prefs = [Preference("Gym", MORNING, 2), Preference("Study", AFTERNOON, 1)]
    nothing_after_9pm = Block(frozenset().union(*(hour_range(d, 21, 22) for d in DAYS)))

    # "gym three times, study for 2 hours, nothing after 9pm, gym preferably mornings"
    first = plan("first plan", tasks, fixed, [nothing_after_9pm], prefs)

    # then: "not tuesday morning". gym on tuesday morning has to move.
    not_tue_morning = Block(hour_range(1, 7, 12))
    plan("after 'not tuesday morning'", tasks, fixed,
         [nothing_after_9pm, not_tue_morning], prefs, old_schedule=first.schedule)


if __name__ == "__main__":
    main()
