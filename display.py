"""text display for atesked: prints the week as a grid, then the search stats.

what the grid looks like
------------------------
rows are the hours 7 am - 9 pm (the 15 slots of a day) and columns are mon-sun.
every cell is one hour and holds a short mark plus a name:

    [F] class    fixed event, never moves
    [N] gym      task copy that is new (not in the previous schedule)
    [M] gym      task copy that moved compared with the previous schedule
        gym      task copy at the same slot as in the previous schedule
    x            blocked, nothing may be scheduled here
    .            free

a schedule is passed in as a dict {copy: start_slot}. the search keeps its
placements as a tuple lined up with the list of copies, so the caller builds
this with dict(zip(copies, placements)).
"""

from model import (DAY_NAMES, FIRST_HOUR, HOURS_PER_DAY, NUM_DAYS, Block,
                   FixedEvent, Preference, Task, from_slot, to_slot)

CELL_WIDTH = 11       # characters per day column: "[N] " mark, up to 6 name letters, 1 gap
NAME_WIDTH = CELL_WIDTH - 5
LABEL_WIDTH = 5       # characters for the hour label column ("12pm ")


# turn a clock hour (7..21) into a short label such as "7am" or "12pm".
# hours past noon have 12 subtracted, and 12 itself is "12pm" (noon).
def hour_label(hour):
    suffix = "am" if hour < 12 else "pm"
    return f"{hour if hour <= 12 else hour - 12}{suffix}"


# build the text that goes inside one grid cell, padded to CELL_WIDTH.
# the mark (e.g. "[N]") is followed by a space and the name cut down to fit.
# an empty mark gives an unmarked cell, which keeps names lined up in a column.
def make_cell(mark, name):
    return f"{mark:<3} {name[:NAME_WIDTH]}".ljust(CELL_WIDTH)


# work out the mark for one placed copy by comparing it with the old schedule.
#   no old schedule at all  -> everything is being planned for the first time: [N]
#   copy missing from old   -> a task added by the latest request: [N]
#   copy at a different slot -> the re-plan moved it: [M]
#   copy at the same slot   -> unchanged, no mark
def copy_mark(copy, start, old_placements):
    if old_placements is None or copy not in old_placements:
        return "[N]"
    return "[M]" if old_placements[copy] != start else ""


# fill a dict {slot: cell_text} for every occupied or blocked slot.
# the layers are written from lowest to highest priority so a later layer
# overwrites an earlier one on overlap:
#   1. blocked slots ("x")
#   2. placed task copies (a task of duration d fills slots start .. start+d-1)
#   3. fixed events, which win over everything because they cannot move
def build_cells(fixed_events, blocks, placements, old_placements):
    cells = {}
    for block in blocks:
        for slot in block.slots:
            cells[slot] = "x".ljust(CELL_WIDTH)
    for copy, start in placements.items():
        mark = copy_mark(copy, start, old_placements)
        for slot in range(start, start + copy.duration):
            cells[slot] = make_cell(mark, copy.task_name)
    for event in fixed_events:
        for slot in event.slots:
            cells[slot] = make_cell("[F]", event.name)
    return cells


# render the whole week as one multi-line string.
# steps: build the slot -> cell lookup, print a header row of day names, then
# for each hour 7..21 print one row that looks up the cell for each of the
# 7 days (an unoccupied slot shows "."). separators are drawn with "-".
def render_grid(fixed_events, blocks, placements, old_placements=None):
    cells = build_cells(fixed_events, blocks, placements, old_placements)
    blank = ".".ljust(CELL_WIDTH)
    header = " " * LABEL_WIDTH + "".join(f"{d:<{CELL_WIDTH}}" for d in DAY_NAMES)
    lines = [header.rstrip(), "-" * len(header)]
    for hour in range(FIRST_HOUR, FIRST_HOUR + HOURS_PER_DAY):
        row = f"{hour_label(hour):<{LABEL_WIDTH}}"
        for day in range(NUM_DAYS):
            row += cells.get(to_slot(day, hour), blank)
        lines.append(row.rstrip())
    return "\n".join(lines)


# render the stats line(s) for a search result.
# the result object comes from the search code and is expected to have
# status, cost, nodes_expanded and runtime_seconds. only an "ok" result has a
# meaningful cost, so the other two statuses print a short explanation instead.
def render_stats(result):
    if result.status == "impossible":
        return "no schedule exists: the rules leave no room for every task."
    if result.status == "limit":
        return (f"search limit reached after {result.nodes_expanded} nodes "
                "without finishing; try fewer or simpler requests.")
    return (f"cost: {result.cost}   "
            f"nodes expanded: {result.nodes_expanded}   "
            f"runtime: {result.runtime_seconds:.4f}s")


# print the grid (when there is a schedule) followed by the stats.
# an impossible or limit result has no schedule, so only the stats message shows.
def print_schedule(result, fixed_events, blocks, placements=None, old_placements=None):
    if result.status == "ok":
        print(render_grid(fixed_events, blocks, placements, old_placements))
        print()
    print(render_stats(result))


# ------------------------------------------------------- describing the rules
# these turn parsed rules into short sentences, so the command-line loop can
# show the user what it understood.

# join consecutive hours into runs of (start_hour, end_hour_exclusive).
# [9, 10, 11, 14] -> [(9, 12), (14, 15)]
def hour_runs(hours):
    runs = []
    for hour in sorted(hours):
        if runs and runs[-1][1] == hour:
            runs[-1] = (runs[-1][0], hour + 1)
        else:
            runs.append((hour, hour + 1))
    return runs


# a list of day numbers as text. all seven days is "every day"; three or more
# days in a row are shortened to a range ("Mon-Fri"); the rest are listed.
def format_days(days):
    days = sorted(days)
    if len(days) == NUM_DAYS:
        return "every day"
    pieces, i = [], 0
    while i < len(days):
        j = i
        while j + 1 < len(days) and days[j + 1] == days[j] + 1:
            j += 1
        if j - i >= 2:
            pieces.append(f"{DAY_NAMES[days[i]]}-{DAY_NAMES[days[j]]}")
        else:
            pieces.extend(DAY_NAMES[d] for d in days[i:j + 1])
        i = j + 1
    return ", ".join(pieces)


# a set of slots as text, e.g. "Mon-Fri 9pm-10pm" or "Tue 7am-12pm".
# steps: collect the hours used on each day, turn them into runs, then group
# days that have identical runs so "every day 9pm-10pm" is one phrase and not
# seven.
def describe_slots(slots):
    hours_by_day = {}
    for slot in slots:
        day, hour = from_slot(slot)
        hours_by_day.setdefault(day, []).append(hour)
    groups = {}
    for day, hours in hours_by_day.items():
        groups.setdefault(tuple(hour_runs(hours)), []).append(day)
    parts = []
    for runs, days in groups.items():
        if runs == ((FIRST_HOUR, FIRST_HOUR + HOURS_PER_DAY),):
            when = "all day"
        else:
            when = ", ".join(f"{hour_label(a)}-{hour_label(b)}" for a, b in runs)
        parts.append(f"{format_days(days)} {when}")
    return "; ".join(parts) if parts else "no hours at all"


# one rule as a short sentence for the "understood" list.
def describe_rule(rule):
    if isinstance(rule, Task):
        times = "once" if rule.count == 1 else f"{rule.count} times"
        hours = "1 hour" if rule.duration == 1 else f"{rule.duration} hours"
        return f"task: {rule.name}, {times}, {hours} each"
    if isinstance(rule, Block):
        return f"block (nothing scheduled): {describe_slots(rule.slots)}"
    if isinstance(rule, Preference):
        return (f"preference: {rule.task_name} preferably {describe_slots(rule.good_slots)}"
                f" (penalty {rule.penalty} otherwise)")
    if isinstance(rule, FixedEvent):
        return f"fixed event: {rule.name}, {describe_slots(rule.slots)}"
    return str(rule)
