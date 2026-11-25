"""Core data model for AteSked: slot helpers, rule dataclasses, task copies.

The week is Monday-Sunday, 7 AM to 10 PM, in one-hour slots numbered 0-104:
    slot = day * 15 + (hour - 7)      (day 0 = Monday)
Occupied hours are stored as an int bitmask (bit i = slot i).
"""

from dataclasses import dataclass

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
NUM_DAYS = 7
FIRST_HOUR = 7                                # first usable hour (7 AM)
END_HOUR = 22                                 # day ends at 10 PM (exclusive)
HOURS_PER_DAY = END_HOUR - FIRST_HOUR         # 15
NUM_SLOTS = NUM_DAYS * HOURS_PER_DAY          # 105
MOVE_PENALTY = 3                              # cost of moving a copy when re-planning
DEFAULT_PENALTY = 2                           # default soft-preference penalty


# ---------------------------------------------------------------- slot helpers

def to_slot(day, hour):
    """Slot number for (day, hour). Raises ValueError if outside the grid."""
    if not (0 <= day < NUM_DAYS and FIRST_HOUR <= hour < END_HOUR):
        raise ValueError(f"no slot for day={day}, hour={hour}")
    return day * HOURS_PER_DAY + (hour - FIRST_HOUR)


def from_slot(slot):
    """Inverse of to_slot: returns (day, hour)."""
    if not 0 <= slot < NUM_SLOTS:
        raise ValueError(f"slot {slot} out of range")
    day, offset = divmod(slot, HOURS_PER_DAY)
    return day, offset + FIRST_HOUR


def day_of(slot):
    """Day number (0 = Monday) of a slot."""
    return slot // HOURS_PER_DAY


def hour_range(day, start_hour, end_hour):
    """Slots on `day` for hours start_hour .. end_hour-1, clipped to 7-22."""
    lo, hi = max(start_hour, FIRST_HOUR), min(end_hour, END_HOUR)
    return frozenset(to_slot(day, h) for h in range(lo, hi))


def day_slots(day):
    """All slots of one day."""
    return hour_range(day, FIRST_HOUR, END_HOUR)


def all_slots():
    """Every slot in the week."""
    return frozenset(range(NUM_SLOTS))


def fits_in_day(start, duration):
    """True if a task starting at `start` ends by 10 PM on the same day."""
    return 0 <= start < NUM_SLOTS and (start % HOURS_PER_DAY) + duration <= HOURS_PER_DAY


def mask_of(slots):
    """Bitmask with a bit set for each slot."""
    mask = 0
    for s in slots:
        mask |= 1 << s
    return mask


def task_bits(start, duration):
    """Bitmask of slots start .. start+duration-1."""
    return ((1 << duration) - 1) << start


# ------------------------------------------------------------------ rule types

@dataclass(frozen=True)
class FixedEvent:
    """An event that never moves (e.g. a class)."""
    name: str
    slots: frozenset

    def __post_init__(self):
        object.__setattr__(self, "slots", frozenset(self.slots))


@dataclass(frozen=True)
class Block:
    """Hard rule: nothing may use these slots."""
    slots: frozenset

    def __post_init__(self):
        object.__setattr__(self, "slots", frozenset(self.slots))


@dataclass(frozen=True)
class Task:
    """Flexible task, placed `count` times, each `duration` hours long."""
    name: str
    duration: int = 1
    count: int = 1


@dataclass(frozen=True)
class Preference:
    """Soft rule: placing `task_name` outside `good_slots` costs `penalty`."""
    task_name: str
    good_slots: frozenset
    penalty: int = DEFAULT_PENALTY

    def __post_init__(self):
        object.__setattr__(self, "good_slots", frozenset(self.good_slots))


@dataclass(frozen=True)
class Copy:
    """One placement unit of a Task, e.g. Gym#2."""
    task_name: str
    number: int          # 1-based copy number
    duration: int

    @property
    def label(self):
        return f"{self.task_name}#{self.number}"


def expand_tasks(tasks):
    """Expand Tasks into Copies, sorted by task name then copy number.

    This is the fixed placement order used by search. Copies of the same task
    must be placed at increasing start slots (symmetry breaking, done in search).
    """
    copies = []
    for t in sorted(tasks, key=lambda t: t.name):
        for n in range(1, t.count + 1):
            copies.append(Copy(t.name, n, t.duration))
    return copies
