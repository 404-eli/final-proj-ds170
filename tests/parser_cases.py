"""test sentences for the parser, each with the rules it should produce.

CASES is a list of (sentence, expected_rules). an expected value of None means
the sentence must be rejected (the parser raises ParseError). the expected rules
are written by hand from the model helpers, not produced by the parser, so
they are an independent check. evaluate.py reuses this list to compare the
parser with the keyword baseline.
"""

from model import Block, FixedEvent, Preference, Task, hour_range, to_slot


# slots for hours [start, end) on each of the listed days (default: all 7).
def slots(start, end, days=range(7)):
    return frozenset().union(*(hour_range(d, start, end) for d in days))


# ----------------------------------------------------------- normal requests
NORMAL = [
    ("gym", [Task("gym", 1, 1)]),
    ("gym three times", [Task("gym", 1, 3)]),
    ("study for 2 hours", [Task("study", 2, 1)]),
    ("study 2 times for 3 hours", [Task("study", 3, 2)]),
    ("gym three times, nothing after 9pm, gym preferably mornings",
     [Task("gym", 1, 3), Block(slots(21, 22)), Preference("gym", slots(7, 12), 2)]),
    ("not tuesday morning", [Block(slots(7, 12, [1]))]),
    ("nothing before 9am", [Block(slots(7, 9))]),
    ("free sunday", [Block(slots(7, 22, [6]))]),
    ("no weekdays evening", [Block(slots(17, 22, range(5)))]),
    ("gym preferably mornings and study preferably afternoons",
     [Preference("gym", slots(7, 12), 2), Preference("study", slots(12, 17), 2)]),
    ("i have class on monday at 9am for 2 hours",
     [FixedEvent("class", [to_slot(0, 9), to_slot(0, 10)])]),
    ("i have lab on wednesday at 1pm", [FixedEvent("lab", [to_slot(2, 13)])]),
]

# ------------------------------------------------------- unusual phrasing
UNUSUAL = [
    ("  GYM   Three Times ,  NOTHING after 9 PM!  ",
     [Task("gym", 1, 3), Block(slots(21, 22))]),
    ("nothing after 8:30pm", [Block(slots(21, 22))]),                # rounds up to 9pm
    ("no mon morning, no fri evening",
     [Block(slots(7, 12, [0])), Block(slots(17, 22, [4]))]),
    ("do not schedule anything after 9pm", [Block(slots(21, 22))]),
    ("reading 2 times and gym preferably tue morning",
     [Task("reading", 1, 2), Preference("gym", slots(7, 12, [1]), 2)]),
    ("no weekend", [Block(slots(7, 22, [5, 6]))]),
    ("gym preferably before 9am", [Preference("gym", slots(7, 9), 2)]),
    ("study group 2 times", [Task("study group", 1, 2)]),
    ("do laundry", [Task("do laundry", 1, 1)]),
    ("i have standup on weekdays at 9am",
     [FixedEvent("standup", [to_slot(d, 9) for d in range(5)])]),
]

# ---------------------------- valid sentences built to trip up keyword matching
# the names contain a grammar word joined to other letters by hyphens
# ("no-bake", "free-weights", "not-for-profit"). the real lexer reads each as
# one ordinary word; a regex that looks for the word "no", "free" or "not"
# sees it inside the name and misreads the whole clause as a block.
TRICKY = [
    ("no-bake dessert preferably evenings",
     [Preference("no-bake dessert", slots(17, 22), 2)]),
    ("free-weights 2 times", [Task("free-weights", 1, 2)]),
    ("not-for-profit meeting for 2 hours", [Task("not-for-profit meeting", 2, 1)]),
]

# ------------------------------------------------ sentences that must be rejected
REJECTED = [
    "gym 3",                              # a number needs "times" after it
    "nothing after",                      # missing time
    "i have class monday at 9am",         # missing "on"
    "gym, , study",                       # separator with no clause
    "9pm",                                # cannot start a clause
    "i have class on monday at 6am",      # starts before the grid (7 am)
    "nothing monday tuesday",             # two days need a separator
    "",                                   # empty request
]

CASES = NORMAL + UNUSUAL + TRICKY + [(text, None) for text in REJECTED]
