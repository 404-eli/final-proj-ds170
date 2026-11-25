"""Core data model for AteSked: slot helpers, rule dataclasses, task copies.

How the week is represented
---------------------------
The planner sees the week as a flat line of 105 one-hour slots, numbered 0-104:
Monday 7 AM is slot 0, Monday 9 PM is slot 14, Tuesday 7 AM is slot 15, and so
on up to Sunday 9 PM at slot 104. The formula is
    slot = day * 15 + (hour - 7)        (day 0 = Monday)
Each day has 15 usable hours (7 AM up to, but not including, 10 PM). A slot
named "9 PM" is the hour from 9:00 to 10:00.

Occupied hours are kept as one int bitmask (bit i set = slot i is taken), so
"does this task collide with anything already placed?" is a single AND.
"""

from dataclasses import dataclass

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
NUM_DAYS = 7
FIRST_HOUR = 7                                # first usable hour (7 AM)
END_HOUR = 22                                 # day ends at 10 PM (exclusive)
HOURS_PER_DAY = END_HOUR - FIRST_HOUR         # 15 slots per day
NUM_SLOTS = NUM_DAYS * HOURS_PER_DAY          # 105 slots per week
MOVE_PENALTY = 3                              # extra cost when re-planning moves a copy
DEFAULT_PENALTY = 2                           # cost of breaking a preference if none given


# Task 1: SLOT HELPERS

# convert (day, hour) to a slot number.
# multiply the day by 15 to jump to the start of that day, then add how many
# hours past 7 AM it is. raises ValueError for anything off the grid (6 AM,
# 10 PM, day 7...) so bad input fails loudly instead of landing in the wrong day.
def to_slot(day, hour):
    if not (0 <= day < NUM_DAYS and FIRST_HOUR <= hour < END_HOUR):
        raise ValueError(f"no slot for day={day}, hour={hour}")
    return day * HOURS_PER_DAY + (hour - FIRST_HOUR)


# convert a slot number back to (day, hour); the inverse of to_slot.
# divmod by 15 splits the slot into a day number and an offset within that day;
# adding 7 to the offset turns it back into a clock hour.
def from_slot(slot):
    if not 0 <= slot < NUM_SLOTS:
        raise ValueError(f"slot {slot} out of range")
    day, offset = divmod(slot, HOURS_PER_DAY)
    return day, offset + FIRST_HOUR


# which day (0 = Monday) a slot belongs to: integer-divide by 15.
def day_of(slot):
    return slot // HOURS_PER_DAY


# slots on `day` covering hours start_hour .. end_hour-1.
# the range is clipped to the 7 AM-10 PM grid first, so "before 9 AM" (hours
# 0-9) safely gives hours 7-8, and a range entirely off the grid gives an empty
# set. the parser will use this to turn "tuesday morning" or "after 9pm" into
# sets of slots.
def hour_range(day, start_hour, end_hour):
    lo, hi = max(start_hour, FIRST_HOUR), min(end_hour, END_HOUR)
    return frozenset(to_slot(day, h) for h in range(lo, hi))


# every slot of one day (for rules like "nothing on sunday").
def day_slots(day):
    return hour_range(day, FIRST_HOUR, END_HOUR)


# every slot in the week.
def all_slots():
    return frozenset(range(NUM_SLOTS))


# check that a task starting at `start` stays within one day.
# position within the day is start % 15. adding the duration must not run past
# 15, otherwise the task would spill into the next day or end after 10 PM.
# start slots outside the week are rejected too.
def fits_in_day(start, duration):
    return 0 <= start < NUM_SLOTS and (start % HOURS_PER_DAY) + duration <= HOURS_PER_DAY


# build a bitmask from a collection of slots by OR-ing together 1 << slot.
def mask_of(slots):
    mask = 0
    for s in slots:
        mask |= 1 << s
    return mask


# bitmask for a task occupying slots start .. start+duration-1.
# (1 << duration) - 1 makes `duration` consecutive 1-bits at the bottom;
# shifting left by `start` moves them to the task's position in the week.
# A placement is legal when `occupied_mask & task_bits(start, d) == 0`.
def task_bits(start, duration):
    return ((1 << duration) - 1) << start


# task 2 RULE TYPES

# rules come from the user's requests (or hard-coded test weeks). they are
# frozen dataclasses so they can be hashed and never change once created.
# slot collections are converted to frozensets in __post_init__ so two rules
# with the same slots compare equal however they were built.

# an event already on the calendar (e.g. a class); search never moves it.
# its slots count as occupied, so no flexible task may overlap them.
@dataclass(frozen=True)
class FixedEvent:
    name: str
    slots: frozenset

    def __post_init__(self):
        object.__setattr__(self, "slots", frozenset(self.slots))


# hard rule ("nothing after 9pm", "not tuesday morning"): no task may use
# these slots. Unlike a FixedEvent it has no name; it just forbids the time.
@dataclass(frozen=True)
class Block:
    slots: frozenset

    def __post_init__(self):
        object.__setattr__(self, "slots", frozenset(self.slots))


# A flexible task the planner must place ("gym three times").
# `count` is how many times it must be scheduled in the week; each time lasts
# `duration` consecutive hours.
@dataclass(frozen=True)
class Task:
    name: str
    duration: int = 1
    count: int = 1


# soft rule ("gym preferably mornings"): allowed to break, but at a price.
# each copy of `task_name` whose start slot is outside `good_slots` adds
# `penalty` to the schedule's cost. search minimises total cost, so preferences
# are honoured whenever the hard rules leave room.
@dataclass(frozen=True)
class Preference:
    task_name: str
    good_slots: frozenset
    penalty: int = DEFAULT_PENALTY

    def __post_init__(self):
        object.__setattr__(self, "good_slots", frozenset(self.good_slots))


# one placement unit of a Task, such as the second of three gym sessions.
# search places one Copy at a time, so a Task with count=3 becomes three
# copies numbered 1, 2, 3.
@dataclass(frozen=True)
class Copy:
    task_name: str
    number: int          # 1-based copy number within its task
    duration: int

    # display name such as "Gym#2".
    @property
    def label(self):
        return f"{self.task_name}#{self.number}"


# Expand each Task into `count` Copies, in a fixed, repeatable order.
# Process: sort the tasks by name, then for each task emit copies numbered
# 1..count. The resulting list is the order search places things in, so a
# search state only needs an index k = "next copy to place".
# A fixed order matters because the same input then always gives the same
# search, and because copies of one task are interchangeable (Gym#1 Tue +
# Gym#2 Wed is the same schedule as the reverse). Search removes that
# duplication by requiring copies of the same task to start at increasing slots.
def expand_tasks(tasks):
    copies = []
    for t in sorted(tasks, key=lambda t: t.name):
        for n in range(1, t.count + 1):
            copies.append(Copy(t.name, n, t.duration))
    return copies
