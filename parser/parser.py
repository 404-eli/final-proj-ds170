"""recursive-descent parser for atesked: turns tokens into rules.

the grammar (one function below per line)
-----------------------------------------
    request    := clause (("," | "and") clause)*
    clause     := task | block | preference | fixed | reject
    task       := NAME [NUMBER "times"] ["for" NUMBER ("hour"|"hours")]
    block      := ("no" | "nothing" | "free") time_expr
                  (also "do not schedule anything" time_expr)
    preference := NAME "preferably" time_expr
    fixed      := "i have" NAME "on" DAY "at" TIME ["for" NUMBER ("hour"|"hours")]
    reject     := "not" time_expr
    time_expr  := DAY [PART] | PART | ("before" | "after") TIME
                  | DAY ("before" | "after") TIME

what comes out
--------------
parse(text) returns a list of rules from model.py:
    task        -> Task(name, duration, count)
    block       -> Block(slots)
    reject      -> Block(slots)      (a "not ..." sentence is just a hard rule)
    preference  -> Preference(task_name, good_slots, penalty=2)
    fixed       -> FixedEvent(name, slots)

the parser never guesses: if the tokens do not fit the grammar it raises
ParseError naming the token where it got stuck.
"""

from dataclasses import dataclass

from model import (DEFAULT_PENALTY, END_HOUR, FIRST_HOUR, NUM_DAYS, Block,
                   FixedEvent, Preference, Task, hour_range, to_slot)
from parser.lexer import DAY, KEYWORD, NAME, NUMBER, PART, TIME, tokenize


# raised when the sentence does not fit the grammar.
# token is the token where parsing stopped (None means the sentence ended too
# early). the message names that token and says what was expected instead.
class ParseError(Exception):
    def __init__(self, token, expected):
        self.token = token
        self.expected = expected
        if token is None:
            where = "the end of the request"
        else:
            where = f"'{token.text}' (position {token.pos})"
        super().__init__(f"could not parse at {where}: expected {expected}")


# the parser's position in the token list, plus small helpers every grammar
# function uses. keeping the position in one object means the grammar
# functions can be plain functions that just pass it along.
@dataclass
class Stream:
    tokens: list
    i: int = 0

    # look at a token without consuming it (None past the end).
    def peek(self, offset=0):
        j = self.i + offset
        return self.tokens[j] if j < len(self.tokens) else None

    # consume and return the current token.
    def advance(self):
        token = self.tokens[self.i]
        self.i += 1
        return token

    # true if the next token is the given keyword (or one of several).
    def at_keyword(self, *words):
        token = self.peek()
        return token is not None and token.kind == KEYWORD and token.value in words

    # consume the next token if it is one of the keywords; says whether it did.
    def accept_keyword(self, *words):
        if self.at_keyword(*words):
            self.advance()
            return True
        return False

    # consume a required keyword or fail at the current token.
    def expect_keyword(self, *words):
        if not self.at_keyword(*words):
            raise ParseError(self.peek(), " or ".join(f"'{w}'" for w in words))
        return self.advance()

    # consume a required token of one kind or fail at the current token.
    def expect_kind(self, kind, description):
        token = self.peek()
        if token is None or token.kind != kind:
            raise ParseError(token, description)
        return self.advance()


# ----------------------------------------------------------------- entry point

# parse a whole sentence into a list of rules.
# steps: tokenize, parse one request, then check nothing is left over.
def parse(text):
    stream = Stream(tokenize(text))
    return parse_request(stream)


# request := clause (("," | "and") clause)*
# parse one clause, then keep going for as long as a "," or "and" follows.
# a separator must be followed by another clause, so "gym," is an error.
# when the loop stops, any token still left over is an error: the request
# should have ended there.
def parse_request(s):
    rules = [parse_clause(s)]
    while s.accept_keyword(",", "and"):
        rules.append(parse_clause(s))
    if s.peek() is not None:
        raise ParseError(s.peek(), "',' or 'and' or the end of the request")
    return rules


# clause := task | block | preference | fixed | reject
# the first token(s) decide which kind of clause it is, so the parser never
# has to back up:
#   "no" / "nothing" / "free"        -> block
#   "do not schedule anything"       -> block
#   "not"                            -> reject
#   "i"                              -> fixed (must continue "have ...")
#   a name                           -> preference if "preferably" follows the
#                                       name, otherwise task
# anything else cannot start a clause.
def parse_clause(s):
    token = s.peek()
    if s.at_keyword("no", "nothing", "free"):
        s.advance()
        return parse_block_rest(s)
    if starts_do_not_schedule_anything(s):
        for _ in range(4):
            s.advance()
        return parse_block_rest(s)
    if s.at_keyword("not"):
        s.advance()
        return parse_reject_rest(s)
    if s.at_keyword("i"):
        s.advance()
        s.expect_keyword("have")
        return parse_fixed_rest(s)
    if token is not None and token.kind == NAME:
        name = parse_name(s)
        if s.accept_keyword("preferably"):
            return parse_preference_rest(s, name)
        return parse_task_rest(s, name)
    raise ParseError(token, "a task name, 'no ...', 'not ...' or 'i have ...'")


# the four-word phrase "do not schedule anything". "do", "schedule" and
# "anything" are ordinary NAME tokens (so a task like "do laundry" still
# works); only this exact run of four tokens counts as a block.
def starts_do_not_schedule_anything(s):
    wanted = [(NAME, "do"), (KEYWORD, "not"), (NAME, "schedule"), (NAME, "anything")]
    for offset, (kind, value) in enumerate(wanted):
        token = s.peek(offset)
        if token is None or token.kind != kind or token.value != value:
            return False
    return True


# a task or event name: one or more NAME tokens joined by spaces, so
# "study group" is a single name. it stops at the first non-NAME token.
def parse_name(s):
    words = [s.expect_kind(NAME, "a task name").value]
    while s.peek() is not None and s.peek().kind == NAME:
        words.append(s.advance().value)
    return " ".join(words)


# ------------------------------------------------------------- clause bodies
# each function below runs after the clause's first word(s) are consumed.

# task := NAME [NUMBER "times"] ["for" NUMBER ("hour"|"hours")]
# the name is already parsed. an optional "<n> times" sets the count, and an
# optional "for <n> hours" sets the duration. defaults are count 1, duration 1.
# a number must be followed by "times", so "gym 3" is an error, not a guess.
def parse_task_rest(s, name):
    count = 1
    token = s.peek()
    if token is not None and token.kind == NUMBER:
        count = s.advance().value
        s.expect_keyword("times")
    duration, _ = parse_duration(s)
    return Task(name, duration, count)


# block := ("no" | "nothing" | "free") time_expr
# the keyword is already consumed; the time expression gives the blocked slots.
def parse_block_rest(s):
    return Block(parse_time_expr(s))


# reject := "not" time_expr
# the same hard rule as a block; the command-line loop treats "not ..."
# sentences as a request to rule that time out.
def parse_reject_rest(s):
    return Block(parse_time_expr(s))


# preference := NAME "preferably" time_expr
# the name and "preferably" are already consumed. placing the task outside the
# time expression's slots will cost DEFAULT_PENALTY.
def parse_preference_rest(s, name):
    return Preference(name, parse_time_expr(s), DEFAULT_PENALTY)


# fixed := "i have" NAME "on" DAY "at" TIME ["for" NUMBER ("hour"|"hours")]
# "i have" is already consumed. the event occupies `duration` hours starting at
# the given hour on each day named. an event that would start before 7 am or end
# after 10 pm cannot be shown on the grid, so it is an error at the token that
# causes it (the duration number if given, otherwise the time).
def parse_fixed_rest(s):
    name = parse_name(s)
    s.expect_keyword("on")
    days = s.expect_kind(DAY, "a day such as 'monday'").value
    s.expect_keyword("at")
    time_token = s.expect_kind(TIME, "a time such as '9am'")
    duration, duration_token = parse_duration(s)
    start = time_token.value
    if start < FIRST_HOUR:
        raise ParseError(time_token, "a start time of 7am or later")
    if start + duration > END_HOUR:
        raise ParseError(duration_token or time_token, "an event that ends by 10pm")
    slots = [to_slot(day, hour) for day in days for hour in range(start, start + duration)]
    return FixedEvent(name, slots)


# optional "for <n> hour(s)". returns (hours, the number token or None).
# with no "for", the duration defaults to 1 hour.
def parse_duration(s):
    if not s.accept_keyword("for"):
        return 1, None
    number = s.expect_kind(NUMBER, "a number of hours")
    s.expect_keyword("hour", "hours")
    return number.value, number


# --------------------------------------------------------------- time_expr

# time_expr := DAY [PART] | PART | ("before"|"after") TIME | DAY ("before"|"after") TIME
# returns the frozenset of slots the expression names. look at the first token:
#   DAY alone                 -> every hour of those days
#   DAY PART                  -> that part of the day on those days
#   DAY before/after TIME     -> the hours before/after that time on those days
#   PART                      -> that part of the day on every day
#   before/after TIME         -> the hours before/after that time on every day
# "weekdays" and "weekend" are DAY tokens covering several days at once.
def parse_time_expr(s):
    token = s.peek()
    if token is not None and token.kind == DAY:
        days = s.advance().value
        following = s.peek()
        if following is not None and following.kind == PART:
            return slots_for(days, s.advance().value)
        if s.at_keyword("before", "after"):
            return slots_for(days, parse_time_bound(s))
        return slots_for(days, (FIRST_HOUR, END_HOUR))
    if token is not None and token.kind == PART:
        return slots_for(range(NUM_DAYS), s.advance().value)
    if s.at_keyword("before", "after"):
        return slots_for(range(NUM_DAYS), parse_time_bound(s))
    raise ParseError(token, "a day, a part of the day, or 'before'/'after' a time")


# "before 9am" or "after 9pm" as an (start_hour, end_hour) pair.
# "before T" covers the hours from 7 am up to T, and "after T" covers T up to
# 10 pm. a slot named "9pm" is the hour 9-10 pm, so "after 9pm" includes it.
def parse_time_bound(s):
    word = s.expect_keyword("before", "after").value
    hour = s.expect_kind(TIME, "a time such as '9pm'").value
    return (FIRST_HOUR, hour) if word == "before" else (hour, END_HOUR)


# all slots in hours [start_hour, end_hour) on each of the given days.
# hour_range clips to the 7 am - 10 pm grid, so bounds outside it are safe.
def slots_for(days, hours):
    slots = set()
    for day in days:
        slots |= hour_range(day, hours[0], hours[1])
    return frozenset(slots)
