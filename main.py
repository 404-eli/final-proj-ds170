"""atesked command-line loop: type requests in plain english, get a schedule.

run from the project root:  python main.py

commands:
    <any request sentence>   add rules and re-plan, e.g.
                             gym three times, nothing after 9pm, gym preferably mornings
    show                     print the current schedule again
    reset                    forget every rule and start over
    help                     show this list
    quit                     leave

each request adds to the rules from earlier requests and the week is planned
again with a*. the previous schedule is passed in, so moving something costs
extra and the grid marks what moved ([M]) or is new ([N]).
"""

from dataclasses import dataclass, field

from display import describe_rule, render_grid, render_stats
from model import Block, FixedEvent, Preference, Task
from parser.parser import ParseError, parse
from search.astar import astar
from search.heuristic import make_heuristic
from search.problem import NODE_LIMIT, build_problem

HELP = """type a request, for example:
  gym three times, nothing after 9pm, gym preferably mornings
  not tuesday morning
  i have class on monday at 9am for 2 hours
  study 2 times for 2 hours
commands: show, reset, help, quit"""


# everything the planner remembers between requests.
# tasks is a dict by name, so asking for "gym" again replaces the old gym
# request instead of adding a second one. schedule is the current plan
# ({copy: start_slot}) and previous is the plan before the latest request; the
# grid compares the two to mark moved and new items.
@dataclass
class Session:
    tasks: dict = field(default_factory=dict)
    fixed_events: list = field(default_factory=list)
    blocks: list = field(default_factory=list)
    preferences: list = field(default_factory=list)
    schedule: dict = None
    previous: dict = None
    result: object = None


# return a copy of the session's rules with the new rules added.
# the session itself is not touched, so a request that fails (impossible week,
# search limit) can be thrown away without leaving the rules half-updated.
#   Task        replaces an earlier task with the same name
#   FixedEvent  replaces an earlier event with the same name
#   Block, Preference   added unless an identical one is already there
def with_rules(session, rules):
    tasks = dict(session.tasks)
    fixed = list(session.fixed_events)
    blocks = list(session.blocks)
    prefs = list(session.preferences)
    for rule in rules:
        if isinstance(rule, Task):
            tasks[rule.name] = rule
        elif isinstance(rule, FixedEvent):
            fixed = [e for e in fixed if e.name != rule.name] + [rule]
        elif isinstance(rule, Block):
            if rule not in blocks:
                blocks.append(rule)
        elif isinstance(rule, Preference):
            if rule not in prefs:
                prefs.append(rule)
    return tasks, fixed, blocks, prefs


# the grid and the stats line for a successful plan, as text.
def render_plan(session):
    grid = render_grid(session.fixed_events, session.blocks,
                       session.schedule, session.previous)
    return grid + "\n\n" + render_stats(session.result)


# handle one request sentence and return the text to print.
# steps:
#   1. parse it. a ParseError is shown as a friendly message and nothing changes.
#   2. add the rules to a copy of the current rules.
#   3. build the search problem and run a*, passing the current schedule so the
#      move penalty applies. if some task has no legal slot at all, skip the search.
#   4. "ok": keep the new rules and schedule and show the rules, grid and stats.
#      "impossible" or "limit": explain, and leave everything as it was so the
#      user can try a different request.
def handle_request(session, line, node_limit=NODE_LIMIT):
    try:
        rules = parse(line)
    except ParseError as error:
        return (f"sorry, I could not understand that.\n  {error}\n"
                "type 'help' to see example requests.")

    tasks, fixed, blocks, prefs = with_rules(session, rules)
    problem = build_problem(list(tasks.values()), fixed, blocks, prefs,
                            old_schedule=session.schedule)
    understood = "understood:\n" + "\n".join(f"  {describe_rule(r)}" for r in rules)

    if problem.impossible:
        result = None
    else:
        try:
            result = astar(problem, make_heuristic(problem), node_limit)
        except KeyboardInterrupt:
            return understood + "\n\nsearch cancelled. nothing was changed."

    if result is None or result.status == "impossible":
        return (understood + "\n\nno schedule can satisfy these rules together, so "
                "I did not apply this request. nothing was changed.")
    if result.status == "limit":
        return (understood + "\n\n" + render_stats(result) +
                "\nthis request was not applied. nothing was changed.")

    session.tasks, session.fixed_events = tasks, fixed
    session.blocks, session.preferences = blocks, prefs
    session.previous, session.schedule, session.result = session.schedule, result.schedule, result
    return understood + "\n\n" + render_plan(session)


# handle one line typed by the user and return the text to print.
# "quit" is handled by the loop in main(); everything else is here.
def handle(session, line):
    command = line.strip().lower()
    if not command:
        return ""
    if command == "help":
        return HELP
    if command == "reset":
        session.__init__()
        return "all rules cleared."
    if command == "show":
        if session.result is None:
            return "nothing planned yet. type a request first (or 'help')."
        return render_plan(session)
    return handle_request(session, line)


# read lines until the user types quit (or closes the input).
def main():
    session = Session()
    print("atesked: weekly planner. type 'help' for examples, 'quit' to leave.")
    while True:
        try:
            line = input("\natesked> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() in ("quit", "exit"):
            break
        text = handle(session, line)
        if text:
            print(text)


if __name__ == "__main__":
    main()
