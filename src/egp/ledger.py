"""
Run-level execution ledger — proof of what happened, not inference from files.

This answers Verdictum's section 7 directly. A run is an append-only record of:
  - a unique run identity,
  - the steps that were PLANNED vs the steps that were ACTIVATED,
  - each step's state, with a validated reason for every NOT_APPLICABLE,
  - input and output identity (content hashes),
  - exit status and schema-validation outcome,
  - retries recorded as additional attempts WITHOUT erasing prior ones,
  - model usage and cost per attempt,
  - any missing required outputs.

The release gate is fail-closed (Saltzer & Schroeder "fail-safe defaults"):
release is permitted only if every required step reached a terminal-OK state
and produced its required output. Anything else blocks and names the broken link.

Design note (a trade-off I made deliberately): attempts are immutable and
append-only. A retry never overwrites the previous attempt's record, so the
history *is* the audit trail (the Temporal event-history property). This costs
storage but makes "why did this run cost what it did / where did it fail" always
answerable.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from .states import StepState, BLOCKING, TERMINAL_OK


@dataclass
class Attempt:
    """One execution attempt of a step. Immutable once appended."""
    attempt_no: int
    state: StepState
    reason: str = ""                 # required for SKIPPED / NOT_APPLICABLE / FAILED / BLOCKED
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    exit_status: Optional[int] = None
    schema_valid: Optional[bool] = None
    model: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


@dataclass
class StepRecord:
    name: str
    required: bool
    produces: Optional[str] = None   # name of the required output artifact, if any
    activated: bool = False
    attempts: list = field(default_factory=list)

    @property
    def current_state(self) -> StepState:
        if not self.attempts:
            return StepState.BLOCKED  # planned-but-never-activated is not "ok"
        return self.attempts[-1].state

    @property
    def produced_output(self) -> bool:
        return any(a.output_hash for a in self.attempts)


class ReleaseBlocked(Exception):
    """Raised when a run is asked to release while a required link is broken."""


@dataclass
class RunLedger:
    run_id: str
    case_id: str
    tenant_id: str
    planned_steps: list = field(default_factory=list)  # list[str]
    steps: dict = field(default_factory=dict)          # name -> StepRecord

    # ---- planning -------------------------------------------------------
    def plan(self, name: str, *, required: bool = True,
             produces: Optional[str] = None) -> None:
        self.planned_steps.append(name)
        self.steps[name] = StepRecord(name=name, required=required, produces=produces)

    # ---- recording attempts --------------------------------------------
    def record(self, name: str, state: StepState, *, reason: str = "",
               input_hash: Optional[str] = None, output_hash: Optional[str] = None,
               exit_status: Optional[int] = None, schema_valid: Optional[bool] = None,
               model: Optional[str] = None, tokens_in: int = 0, tokens_out: int = 0,
               cost_usd: float = 0.0) -> Attempt:
        if name not in self.steps:
            raise ValueError(f"step {name!r} was never planned; refusing to record")
        # A validated reason is mandatory for these states — no silent skips.
        if state in (StepState.SKIPPED, StepState.NOT_APPLICABLE,
                     StepState.FAILED, StepState.BLOCKED) and not reason:
            raise ValueError(f"state {state.value} on {name!r} requires a reason")
        step = self.steps[name]
        step.activated = True
        attempt = Attempt(
            attempt_no=len(step.attempts) + 1, state=state, reason=reason,
            input_hash=input_hash, output_hash=output_hash, exit_status=exit_status,
            schema_valid=schema_valid, model=model, tokens_in=tokens_in,
            tokens_out=tokens_out, cost_usd=cost_usd,
        )
        step.attempts.append(attempt)  # append-only; never overwrite
        return attempt

    # ---- cost -----------------------------------------------------------
    def total_cost_usd(self) -> float:
        return round(sum(a.cost_usd for s in self.steps.values() for a in s.attempts), 6)

    def cost_breakdown(self) -> list:
        """Per step, per attempt — the auditable cost trail."""
        out = []
        for name in self.planned_steps:
            for a in self.steps[name].attempts:
                out.append({"step": name, "attempt": a.attempt_no,
                            "model": a.model, "tokens_in": a.tokens_in,
                            "tokens_out": a.tokens_out, "cost_usd": a.cost_usd})
        return out

    # ---- the fail-closed release gate ----------------------------------
    def broken_links(self) -> list:
        """Every reason this run must NOT be released. Empty list == releasable."""
        problems = []
        for name in self.planned_steps:
            step = self.steps[name]
            if not step.required:
                continue
            if not step.activated:
                problems.append({"step": name, "problem": "planned step never activated"})
                continue
            state = step.current_state
            if state not in TERMINAL_OK:
                problems.append({"step": name, "problem": f"ended in state {state.value}",
                                 "reason": step.attempts[-1].reason})
            last = step.attempts[-1]
            if last.schema_valid is False:
                problems.append({"step": name, "problem": "output failed schema validation"})
            if step.produces and state == StepState.COMPLETED and not step.produced_output:
                problems.append({"step": name,
                                 "problem": f"required output '{step.produces}' missing"})
        return problems

    def is_releasable(self) -> bool:
        return not self.broken_links()

    def assert_releasable(self) -> None:
        problems = self.broken_links()
        if problems:
            raise ReleaseBlocked(problems)

    def summary(self) -> dict:
        return {
            "run_id": self.run_id, "case_id": self.case_id, "tenant_id": self.tenant_id,
            "planned": len(self.planned_steps),
            "activated": sum(1 for s in self.steps.values() if s.activated),
            "states": {n: self.steps[n].current_state.value for n in self.planned_steps},
            "total_cost_usd": self.total_cost_usd(),
            "releasable": self.is_releasable(),
            "broken_links": self.broken_links(),
        }
