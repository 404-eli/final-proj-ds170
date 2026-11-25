"""keyword baseline: a deliberately simple parser to compare the real one against.

how it differs from parser.py
-----------------------------
this one has no grammar and no error handling. it chops the sentence into
clauses and then hunts for keywords and patterns with regular expressions:

    "i have ... on <day> at <time>"  -> a fixed event
    "no" / "nothing" / "free" / "not" -> a block
    "preferably"                      -> a preference
    anything else                     -> a task

it never raises an error. a sentence the real parser rejects ("gym 3",
"nothing after") still produces some answer, or silently produces nothing.
that contrast is what the evaluation measures.

the output format is the same as parser.parse(): a list of Task, Block,
Preference and FixedEvent rules. it reuses only the word tables and the
clock-time helper from the lexer, not any of the lexing or parsing logic.
"""

import re

from model import (DEFAULT_PENALTY, END_HOUR, FIRST_HOUR, NUM_DAYS, Block,
                   FixedEvent, Preference, Task, hour_range, to_slot)
from parser.lexer import DAY_WORDS, NUMBER_WORDS, PART_WORDS, TIME_RE, clock_hour

# a count or number: digits ("3") or a number word ("three").
NUMBER = r"\d+|" + "|".join(NUMBER_WORDS)

# "i have <name> on <day> at <time> [for <n> hour(s)]".
FIXED_RE = re.compile(
    r"\bi have\s+(?P<name>.+?)\s+on\s+(?P<day>[a-z]+)\s+at\s+"
    r"(?P<time>\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon)"
    rf"(?:\s+for\s+(?P<dur>{NUMBER})\s+hours?)?")

# "<n> times" gives a task's count; "for <n> hour(s)" gives its duration.
COUNT_RE = re.compile(rf"\b({NUMBER})\s+times?\b")
DURATION_RE = re.compile(rf"\bfor\s+({NUMBER})\s+hours?\b")

# "before 9am" / "after 9pm".
BOUND_RE = re.compile(r"\b(before|after)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon)")

# words that mean "block this time".
BLOCK_RE = re.compile(r"\b(no|nothing|free|not)\b")


# a number written as digits or as a word, as an int (None if it is neither).
def number_value(word):
    if word.isdigit():
        return int(word)
    return NUMBER_WORDS.get(word)


# a clock time written like "9pm", "9:30 pm" or "noon", as a 24-hour hour.
def time_value(text):
    if text == "noon":
        return 12
    match = TIME_RE.fullmatch(text)
    return clock_hour(int(match.group(1)), int(match.group(2) or 0), match.group(3)) if match else None


# lowercase the sentence and cut it into clauses at every comma and every
# "and". empty pieces are dropped. sentence punctuation (. ! ? ;) is removed.
def split_clauses(text):
    text = re.sub(r"[.!?;]", " ", text.lower())
    pieces = re.split(r",|\band\b", text)
    return [" ".join(p.split()) for p in pieces if p.strip()]


# find the slots a clause talks about, by looking for day words, part-of-day
# words and "before/after <time>" anywhere in it.
#   days    = every day word found, or all 7 days if there are none
#   hours   = the before/after range if present, else the part-of-day words
#             found, else the whole day
# returns None when the clause names no day, no part and no bound, because
# there is then nothing to block or prefer.
def find_slots(clause):
    words = re.findall(r"[a-z]+", clause)
    days = sorted({d for w in words if w in DAY_WORDS for d in DAY_WORDS[w]})
    parts = [PART_WORDS[w] for w in words if w in PART_WORDS]
    bound = BOUND_RE.search(clause)
    if not (days or parts or bound):
        return None

    if bound:
        hour = time_value(bound.group(2))
        ranges = [(FIRST_HOUR, hour) if bound.group(1) == "before" else (hour, END_HOUR)]
    elif parts:
        ranges = parts
    else:
        ranges = [(FIRST_HOUR, END_HOUR)]

    slots = set()
    for day in days or range(NUM_DAYS):
        for start, end in ranges:
            slots |= hour_range(day, start, end)
    return frozenset(slots)


# "i have ..." -> FixedEvent, or None if the pattern does not match, the day
# is unknown, or the event would not fit on the grid.
def read_fixed(clause):
    match = FIXED_RE.search(clause)
    if not match or match.group("day") not in DAY_WORDS:
        return None
    start = time_value(match.group("time"))
    duration = number_value(match.group("dur") or "1")
    try:
        slots = [to_slot(day, hour)
                 for day in DAY_WORDS[match.group("day")]
                 for hour in range(start, start + duration)]
    except (ValueError, TypeError):
        return None
    return FixedEvent(match.group("name"), slots)


# a clause with "preferably": the words before it are the task name, and the
# words after it say when. returns None if either part is missing.
def read_preference(clause):
    name, _, rest = clause.partition("preferably")
    name, slots = name.strip(), find_slots(rest)
    if not name or slots is None:
        return None
    return Preference(name, slots, DEFAULT_PENALTY)


# any other clause is a task. pull out the count and duration phrases with
# regexes; whatever words are left are the task name. defaults are count 1 and
# duration 1. returns None if no words are left.
def read_task(clause):
    count = duration = 1
    match = DURATION_RE.search(clause)
    if match:
        duration = number_value(match.group(1))
        clause = clause.replace(match.group(0), " ")
    match = COUNT_RE.search(clause)
    if match:
        count = number_value(match.group(1))
        clause = clause.replace(match.group(0), " ")
    name = " ".join(clause.split())
    return Task(name, duration, count) if name else None


# turn one clause into a rule, or None if nothing could be read from it.
# the checks run in a fixed order and the first that applies wins:
#   "i have"     -> fixed event
#   block word   -> block (or None if no time was named)
#   "preferably" -> preference
#   otherwise    -> task
def read_clause(clause):
    if clause.startswith("i have"):
        return read_fixed(clause)
    if BLOCK_RE.search(clause):
        slots = find_slots(clause)
        return Block(slots) if slots is not None else None
    if "preferably" in clause:
        return read_preference(clause)
    return read_task(clause)


# parse a whole sentence into a list of rules, skipping clauses it cannot read.
def parse_baseline(text):
    rules = (read_clause(c) for c in split_clauses(text))
    return [r for r in rules if r is not None]
