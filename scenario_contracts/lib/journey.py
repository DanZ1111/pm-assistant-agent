"""Journey scenario shape.

A journey is a multi-step narrative. Where a contract is
`setup → run → check`, a journey is:

    setup → [step.do, step.check, step.do, step.check, ...]

Each Step pins the predicted system state after its `do` runs. The
runner walks the steps in order; on the first failed check, the journey
fails with `step N (name): <reason>`.

Discipline boundary (User lock 9) still applies:
- step.do may call only actions.* (and fixtures.* when seeding world)
- step.check may call only assertions.*
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Step:
    """One narrative step in a journey.

    Fields:
        name: short human-readable label (shown in reports on failure).
        do: callable invoked as do(world, db, http). Performs the
            action via actions.*. May mutate `world`.
        check: callable invoked as check(db, world). Asserts the
            predicted state via assertions.* — never raw asserts.
    """
    name: str
    do: Callable
    check: Callable
