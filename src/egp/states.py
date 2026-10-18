"""
Explicit step and result states — the vocabulary of fail-closed operation.

Verdictum's requirement: the system must prove what happened, distinguish a
legitimate zero-result from a failure, and never return a shallow-but-complete
-looking answer. That is impossible if "nothing found", "not run", "skipped"
and "crashed" all collapse into an empty list. So we keep them structurally
distinct (the classic "empty array vs null vs error" modelling problem).
"""
from __future__ import annotations

from enum import Enum


class StepState(str, Enum):
    """Lifecycle state of a single planned processing step."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"              # a precondition/gate stopped it (fail-closed)
    SKIPPED = "skipped"             # deliberately not run (must record why)
    NOT_APPLICABLE = "not_applicable"  # does not apply here (must record a validated reason)


class ResultStatus(str, Enum):
    """Why an analysis produced the output it did.

    COMPLETE_ZERO is the crucial one: it means "we ran the full analysis and the
    true answer is zero", which is completely different from UNVERIFIED (we could
    not establish the answer). Only COMPLETE_* may ever be presented as a result.
    """
    COMPLETE_NONZERO = "complete_nonzero"  # ran fully, found something
    COMPLETE_ZERO = "complete_zero"        # ran fully, genuine zero result
    UNVERIFIED = "unverified"              # could not establish (low confidence, missing input)
    FAILED = "failed"                      # the step errored


# States that are safe to treat as a trustworthy, finished result.
TERMINAL_OK = frozenset({StepState.COMPLETED, StepState.NOT_APPLICABLE})

# States that must block a release if they appear on a required step.
BLOCKING = frozenset({StepState.FAILED, StepState.BLOCKED, StepState.STARTED})


def is_presentable(status: ResultStatus) -> bool:
    """A result may be shown to a lawyer only if the analysis actually completed."""
    return status in (ResultStatus.COMPLETE_NONZERO, ResultStatus.COMPLETE_ZERO)
