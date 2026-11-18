"""Ballot rules, tallies and the Decision Maker tie-break. Pure functions: no I/O, no global state."""
import random
from typing import Any, Iterable, Literal, Protocol, Sequence

TieBreak = Literal["none", "round1", "random"]


class Chooser(Protocol):
    def choice(self, seq: Sequence[str]) -> str: ...


def check_vote(phase: str, target: Any, labels: Iterable[str], already_voted: bool) -> str | None:
    """Returns an error reason, or None if the ballot is accepted. Self-votes are allowed."""
    if phase != "VOTING":
        return "voting_closed"
    if already_voted:
        return "already_voted"
    if not isinstance(target, str) or target not in labels:
        return "invalid_target"
    return None


def tally(ballots: Iterable[str | None], labels: Iterable[str]) -> dict[str, int]:
    """Votes per label. Every label appears (0 if nobody chose it); None ballots are abstentions."""
    counts = {label: 0 for label in labels}
    for target in ballots:
        if target is not None:
            counts[target] += 1
    return counts


def _leaders(counts: dict[str, int], among: Iterable[str]) -> list[str]:
    among = list(among)
    top = max(counts[label] for label in among)
    return sorted(label for label in among if counts[label] == top)


def decide_winner(
    final: dict[str, int], earlier: dict[str, int], rng: Chooser | None = None
) -> tuple[str, TieBreak]:
    """Final-round plurality; ties go to more earlier-round votes, then to a random draw."""
    tied = _leaders(final, final)
    if len(tied) == 1:
        return tied[0], "none"
    tied = _leaders(earlier, tied)
    if len(tied) == 1:
        return tied[0], "round1"
    # Sorted input, so a seeded source always draws the same winner.
    return (rng or random).choice(tied), "random"
