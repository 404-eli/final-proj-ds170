"""lexer for atesked: turns a request sentence into a list of tokens.

what a token is
---------------
every token has a kind, a value the parser can use directly, the text it came
from and its position in the (lowercased) sentence:

    kind     value                                 examples
    DAY      tuple of day numbers (0 = monday)     "tue" -> (1,)   "weekdays" -> (0, 1, 2, 3, 4)
    TIME     clock hour 0-24 (24-hour clock)       "9pm" -> 21     "9:30pm" -> 22   "noon" -> 12
    NUMBER   int 1-10                              "3" -> 3        "three" -> 3
    PART     (start_hour, end_hour)                "morning" -> (7, 12)
    KEYWORD  the word itself                       "nothing", "preferably", "and", ","
    NAME     the word itself                       "gym", "study"

the lexer never guesses. a word it does not recognise becomes a NAME, and
deciding whether that NAME makes sense is the parser's job.
"""

import re
from dataclasses import dataclass

DAY, TIME, NUMBER, PART, KEYWORD, NAME = "DAY", "TIME", "NUMBER", "PART", "KEYWORD", "NAME"


# one piece of the sentence. frozen so tokens can be compared in tests and
# never change after the lexer creates them.
@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    text: str       # the exact characters matched, e.g. "9 pm"
    pos: int        # index of the first character in the lowercased sentence


# day words -> the day numbers they stand for (0 = monday).
# "weekdays" and "weekend" stand for several days at once, so every value is a tuple.
DAY_WORDS = {
    "mon": (0,), "monday": (0,),
    "tue": (1,), "tues": (1,), "tuesday": (1,),
    "wed": (2,), "wednesday": (2,),
    "thu": (3,), "thur": (3,), "thurs": (3,), "thursday": (3,),
    "fri": (4,), "friday": (4,),
    "sat": (5,), "saturday": (5,),
    "sun": (6,), "sunday": (6,),
    "weekdays": (0, 1, 2, 3, 4),
    "weekend": (5, 6),
}

# parts of the day -> (first hour, hour it ends at). plurals are accepted too,
# because people write "gym preferably mornings".
PART_WORDS = {
    "morning": (7, 12), "mornings": (7, 12),
    "afternoon": (12, 17), "afternoons": (12, 17),
    "evening": (17, 22), "evenings": (17, 22),
}

# number words -> value. the digits "1".."10" are handled separately.
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

# words with a fixed meaning in the grammar. "," is added by the lexer itself.
KEYWORDS = {"no", "nothing", "free", "preferably", "not", "before", "after",
            "times", "hours", "hour", "for", "on", "at", "i", "have", "and"}

# a clock time with am/pm: "9pm", "9 pm", "9:30pm". the \b at the end stops
# "9pmx" or "5 amazing" from being read as a time.
TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b")

# any other word: letters and digits, with apostrophes or hyphens inside
# ("don't", "check-in").
WORD_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")

# sentence punctuation that carries no meaning here and is skipped.
IGNORED_CHARS = ".!?;"


# turn a matched clock time into a 24-hour clock hour.
# steps:
#   1. 12 am is hour 0 and 12 pm is hour 12, so take the hour mod 12 and add
#      12 for pm: 9pm -> 21, 12pm -> 12, 12am -> 0.
#   2. the planner works in whole hours, so minutes round to the nearest hour,
#      with 30 or more rounding up: 9:30pm -> 22, 9:29pm -> 21.
# returns None when the digits are not a real clock time (13pm, 0am, 9:75pm),
# so the caller can treat them as an ordinary word instead of guessing.
# the result can fall outside the 7-22 grid (e.g. 24 for 11:45pm); the model's
# hour_range clips to the grid later.
def clock_hour(hour, minute, meridiem):
    if not 1 <= hour <= 12 or minute > 59:
        return None
    result = hour % 12 + (12 if meridiem == "pm" else 0)
    return result + 1 if minute >= 30 else result


# decide what a single word is, by checking the lists in a fixed order:
#   keyword -> day -> part of day -> number (digits 1-10 or one..ten) -> "noon"
# and falling back to NAME. keywords come first so a grammar word is never
# mistaken for anything else.
def classify_word(word, pos):
    if word in KEYWORDS:
        return Token(KEYWORD, word, word, pos)
    if word in DAY_WORDS:
        return Token(DAY, DAY_WORDS[word], word, pos)
    if word in PART_WORDS:
        return Token(PART, PART_WORDS[word], word, pos)
    if word in NUMBER_WORDS:
        return Token(NUMBER, NUMBER_WORDS[word], word, pos)
    if word.isdigit() and 1 <= int(word) <= 10:
        return Token(NUMBER, int(word), word, pos)
    if word == "noon":
        return Token(TIME, 12, word, pos)
    return Token(NAME, word, word, pos)


# split a sentence into tokens.
# steps:
#   1. lowercase the whole sentence so "Gym", "GYM" and "gym" are the same.
#   2. walk left to right. at each position skip spaces, then try in order:
#        a comma            -> KEYWORD ","
#        a clock time       -> TIME (so "9 pm" is one token, not "9" and "pm")
#        a word             -> classify_word()
#        sentence punctuation (. ! ? ;) -> skipped
#        anything else      -> a one-character NAME, so the parser can reject it
#      time is tried before word so "9pm" is not swallowed as the word "9pm".
#   3. every token remembers where it started, so errors can point at it.
def tokenize(text):
    text = text.lower()
    tokens = []
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char.isspace():
            pos += 1
            continue
        if char == ",":
            tokens.append(Token(KEYWORD, ",", ",", pos))
            pos += 1
            continue

        match = TIME_RE.match(text, pos)
        if match:
            hour = clock_hour(int(match.group(1)), int(match.group(2) or 0), match.group(3))
            if hour is not None:
                tokens.append(Token(TIME, hour, match.group(0), pos))
                pos = match.end()
                continue

        match = WORD_RE.match(text, pos)
        if match:
            tokens.append(classify_word(match.group(0), pos))
            pos = match.end()
            continue

        if char not in IGNORED_CHARS:
            tokens.append(Token(NAME, char, char, pos))
        pos += 1
    return tokens
