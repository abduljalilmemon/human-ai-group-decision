"""Scripted fallback agent: short casual lines picked to fit the last message, and a simple vote."""
import random
import re

from .base import Agent, AgentView, mentions

OPENERS = [
    "hey all",
    "hi! so who wants to be decision maker?",
    "ok so how do we pick",
    "hello. i don't mind doing it but open to anyone",
    "hi, anyone keen on leading?",
    "so... who's good at making calls?",
    "hey, maybe whoever has a clear plan should do it",
    "hi everyone, what should the decision maker actually be good at?",
]
ROUND_TWO = [
    "ok round 2, anyone change their mind?",
    "so that was close, let's settle it",
    "alright second round. {p} still makes sense to me",
    "hmm interesting votes. what do we think now",
    "ok last round, let's agree on someone",
]
NAMED_ME = [
    "oh thanks, i'd be happy to do it",
    "haha ok i can do it if nobody else wants",
    "sure, i'd try to keep it fair for everyone",
    "me? fine by me, i'm pretty calm about decisions",
    "i could, but {p} would be good too",
]
QUESTION = [
    "good question, i'd say whoever is most decisive",
    "hmm not sure tbh",
    "i think someone who listens first and then decides",
    "maybe? depends what the others think",
    "honestly i'd be ok at it, but i'm not fussed",
    "i'd want someone who explains why they decide something",
]
GENERIC = [
    "yeah fair",
    "hmm good point",
    "i could go either way tbh",
    "makes sense to me",
    "ok but what would you actually decide?",
    "true",
    "i'm fine with that",
    "agreed, mostly",
    "not sure i agree but ok",
    "that's reasonable",
]
SUPPORT = [
    "{p} sounds like they know what they're doing",
    "i'd go with {p} tbh",
    "{p} made a good point earlier",
    "i'm leaning {p}",
    "honestly {p} seems pretty level headed",
]


class ScriptedAgent(Agent):
    def __init__(self, rng: random.Random | None = None, used: set[str] | None = None):
        self._rng = rng or random.Random()
        # Shared by all AI seats of a session, so two of them never send the same line.
        self._used = set() if used is None else used

    async def reply(self, view: AgentView) -> str | None:
        last = next(
            (m for m in reversed(view.transcript) if m.round == view.round and m.label != view.me), None
        )
        if last is None:
            pool = OPENERS if view.round == 1 else ROUND_TWO
        elif mentions(last.text, view.me):
            pool = NAMED_ME
        elif "?" in last.text:
            pool = QUESTION
        else:
            pool = self._rng.choice([GENERIC, SUPPORT])
        line = self._pick(pool).format(p=self._name(favourite(view, self._rng)))
        return self._vary(line)

    async def vote(self, view: AgentView) -> str:
        return favourite(view, self._rng)

    def _pick(self, pool: list[str]) -> str:
        fresh = [line for line in pool if line not in self._used] or pool
        line = self._rng.choice(fresh)
        self._used.add(line)
        return line

    def _name(self, label: str) -> str:
        """Refer to a player the way people type it: 'Player B', 'player b' or just 'B'."""
        letter = label.split()[-1]
        return self._rng.choice([label, label.lower(), letter])

    def _vary(self, line: str) -> str:
        """Small style changes so repeated sessions do not look identical."""
        r = self._rng.random()
        if r < 0.2:
            line = line[0].upper() + line[1:]
        elif r < 0.35:
            line = re.sub(r"[.!?]$", "", line)
        return line


def favourite(view: AgentView, rng: random.Random) -> str:
    """The other player who argued most: their own lines plus mentions by others. Ties are random."""
    scores = {p: 0 for p in view.others}
    for m in view.transcript:
        if m.label in scores:
            scores[m.label] += 1
        for p in scores:
            if p != m.label and mentions(m.text, p):
                scores[p] += 1
    best = max(scores.values())
    return rng.choice(sorted(p for p, s in scores.items() if s == best))
