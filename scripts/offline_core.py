#!/usr/bin/env python3
"""Pure, offline policy prototype. No Codex access, scheduler, or dispatcher.

All host attestations accepted by the simulator are explicitly synthetic. This
module cannot verify a real host's plugin state or lifecycle guarantees and
cannot authorize production actions. A local enabled flag is never evidence.
Event summaries are untrusted data; this module does not interpret instructions.
Python 3.10+; standard library only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
import hashlib
import json
from typing import Iterable
from zoneinfo import ZoneInfo


UTC = timezone.utc
REQUIRED_HARD_OFF_CAPABILITIES = frozenset({
    "cancel_future_runs", "cancel_in_flight_controller", "deny_dispatch_when_disabled",
    "cancel_owned_workers",
})
SUPPORTED_ACTIONS = frozenset({
    "REQUEST_STATUS", "SUGGEST_NEXT_STEP", "REPLAN_WITHIN_APPROVED_DIRECTION",
    "DEFER_LOW_ROI_WORK",
})


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "*?[]"):
        raise ValueError(f"{label} must be a nonempty exact identifier; wildcards are forbidden")


def _nonnegative_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")


@dataclass(frozen=True)
class TaskEvent:
    event_id: str
    project_id: str | None
    thread_id: str
    occurred_at: datetime
    summary: str
    host_id: str = "synthetic-host"

    def __post_init__(self) -> None:
        for label in ("event_id", "thread_id", "host_id"):
            _identifier(getattr(self, label), label)
        if self.project_id is not None:
            _identifier(self.project_id, "project_id")
        _aware(self.occurred_at, "occurred_at")
        if not isinstance(self.summary, str):
            raise ValueError("summary must be text")


@dataclass(frozen=True)
class Coverage:
    """Declared coverage of the requested source inventory, not proof of all Codex tasks.

    The future collector must supply an exhaustive, current inventory. A matching
    subset is not evidence that inaccessible hosts or historical tasks were read.
    """

    complete: bool
    requested_sources: frozenset[str]
    read_sources: frozenset[str]
    truncated: bool = False
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.requested_sources, frozenset) or not isinstance(self.read_sources, frozenset):
            raise ValueError("coverage source sets must be immutable frozensets")
        if not isinstance(self.errors, tuple):
            raise ValueError("coverage errors must be an immutable tuple")
        for source in self.requested_sources | self.read_sources:
            _identifier(source, "source")

    @property
    def is_complete(self) -> bool:
        return (
            self.complete is True and self.truncated is False and not self.errors
            and bool(self.requested_sources)
            and self.read_sources == self.requested_sources
        )


@dataclass(frozen=True)
class ReportBatch:
    report_id: str
    start_inclusive: datetime
    captured_until: datetime
    previous_watermark: datetime | None
    timezone_name: str
    events: tuple[TaskEvent, ...]
    coverage: Coverage


def prepare_report(
    events: Iterable[TaskEvent], *, captured_until: datetime, now: datetime,
    timezone_name: str, last_delivered_cutoff: datetime | None, coverage: Coverage,
) -> ReportBatch:
    """Select unique changes in [local day start or last delivery cutoff, cutoff).

    Selection uses the event timestamp, never the task's creation date. The
    capture instant is frozen before collection, avoiding a moving end boundary.
    No storage, delivery, or watermark mutation occurs here.
    """
    cutoff = _aware(captured_until, "captured_until")
    checked_now = _aware(now, "now")
    if cutoff > checked_now:
        raise ValueError("captured_until cannot be in the future")
    tz = ZoneInfo(timezone_name)
    previous = None if last_delivered_cutoff is None else _aware(last_delivered_cutoff, "last_delivered_cutoff")
    if previous is not None:
        if previous > cutoff:
            raise ValueError("last_delivered_cutoff cannot exceed captured_until")
        start = previous
    else:
        start = datetime.combine(cutoff.astimezone(tz).date(), time.min, tzinfo=tz).astimezone(UTC)
    unique: dict[tuple[str, str, str], TaskEvent] = {}
    for event in events:
        if not isinstance(event, TaskEvent):
            raise ValueError("events must contain TaskEvent values")
        event_key = (event.host_id, event.thread_id, event.event_id)
        old = unique.get(event_key)
        if old is not None and old != event:
            raise ValueError(f"conflicting duplicate host/task/event identity: {event_key}")
        unique[event_key] = event
    selected = tuple(sorted(
        (event for event in unique.values() if start <= _aware(event.occurred_at, "occurred_at") < cutoff),
        key=lambda event: (_aware(event.occurred_at, "occurred_at"), event.host_id, event.thread_id, event.event_id),
    ))
    digest_input = {
        "start": start.isoformat(), "cutoff": cutoff.isoformat(), "timezone": timezone_name,
        "previous": previous.isoformat() if previous is not None else None,
        "events": [{"id": e.event_id, "host": e.host_id, "project": e.project_id, "thread": e.thread_id,
                    "at": _aware(e.occurred_at, "occurred_at").isoformat(), "summary": e.summary}
                   for e in selected],
        "coverage": {"complete": coverage.complete, "requested": sorted(coverage.requested_sources),
                     "read": sorted(coverage.read_sources), "truncated": coverage.truncated,
                     "errors": coverage.errors},
    }
    report_id = hashlib.sha256(json.dumps(digest_input, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return ReportBatch(report_id, start, cutoff, previous, timezone_name, selected, coverage)


class DeliveryStatus(str, Enum):
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class DeliveryReceipt:
    report_id: str
    status: DeliveryStatus
    delivered_at: datetime | None = None


@dataclass(frozen=True)
class WatermarkResult:
    watermark: datetime | None
    advanced: bool
    reasons: tuple[str, ...]


def commit_report_delivery(
    report: ReportBatch, *, current_watermark: datetime | None,
    receipt: DeliveryReceipt | None, now: datetime,
) -> WatermarkResult:
    """Return the proposed new watermark; no persistence is performed.

    Real delivery receipts and atomic compare-and-swap persistence are future
    integration requirements. A receipt supplied here is only offline input.
    """
    checked_now = _aware(now, "now")
    current = None if current_watermark is None else _aware(current_watermark, "current_watermark")
    reasons = []
    if report.captured_until > checked_now:
        reasons.append("FUTURE_CUTOFF")
    if current != report.previous_watermark:
        reasons.append("STALE_REPORT_WATERMARK")
    if not report.coverage.is_complete:
        reasons.append("COVERAGE_INCOMPLETE")
    if receipt is None or receipt.status is not DeliveryStatus.DELIVERED:
        reasons.append("DELIVERY_NOT_CONFIRMED")
    elif receipt.report_id != report.report_id:
        reasons.append("DELIVERY_REPORT_MISMATCH")
    elif receipt.delivered_at is None:
        reasons.append("DELIVERY_TIME_MISSING")
    else:
        delivered = _aware(receipt.delivered_at, "delivered_at")
        if delivered < report.captured_until or delivered > checked_now:
            reasons.append("INVALID_DELIVERY_TIME")
    if reasons:
        return WatermarkResult(current, False, tuple(reasons))
    if current == report.captured_until:
        return WatermarkResult(current, False, ("ALREADY_AT_CUTOFF",))
    return WatermarkResult(report.captured_until, True, ("COMPLETE_REPORT_DELIVERED",))


@dataclass(frozen=True)
class Target:
    project_id: str | None
    thread_id: str
    host_id: str = "synthetic-host"

    def __post_init__(self) -> None:
        if self.project_id is not None:
            _identifier(self.project_id, "project_id")
        _identifier(self.thread_id, "thread_id")
        _identifier(self.host_id, "host_id")


@dataclass(frozen=True)
class Mandate:
    """Immutable, simulated user-approved scope and limits.

    This object does not authenticate user consent. Production requires a host
    integration that verifies the approval and binds it to this exact revision.
    Cost units are abstract integer budget units, not observed API billing.
    """

    mandate_id: str
    revision: int
    plugin_id: str
    controller_id: str
    manager_thread_id: str
    allowed_targets: frozenset[Target]
    allowed_action_kinds: frozenset[str]
    approved_direction_version: str
    user_approved: bool
    approved_at: datetime
    expires_at: datetime
    timezone_name: str
    max_interventions_per_day: int
    max_cost_units_per_day: int
    max_single_action_cost_units: int
    cooldown_seconds: int
    max_evidence_age_seconds: int = 60

    def __post_init__(self) -> None:
        for label in ("mandate_id", "plugin_id", "controller_id", "manager_thread_id", "approved_direction_version"):
            _identifier(getattr(self, label), label)
        if not isinstance(self.allowed_targets, frozenset) or not self.allowed_targets:
            raise ValueError("allowed_targets must be a nonempty immutable frozenset")
        if not all(isinstance(target, Target) for target in self.allowed_targets):
            raise ValueError("allowed_targets must contain exact Target pairs")
        if not isinstance(self.allowed_action_kinds, frozenset) or not self.allowed_action_kinds:
            raise ValueError("allowed_action_kinds must be a nonempty immutable frozenset")
        if not self.allowed_action_kinds <= SUPPORTED_ACTIONS:
            raise ValueError("unsupported action kind in mandate")
        for label in ("revision", "max_interventions_per_day", "max_cost_units_per_day",
                      "max_single_action_cost_units", "cooldown_seconds", "max_evidence_age_seconds"):
            _nonnegative_int(getattr(self, label), label)
        if self.revision < 1 or not 1 <= self.max_evidence_age_seconds <= 300:
            raise ValueError("revision must be positive; evidence freshness must be 1..300 seconds")
        if _aware(self.expires_at, "expires_at") <= _aware(self.approved_at, "approved_at"):
            raise ValueError("expires_at must follow approved_at")
        ZoneInfo(self.timezone_name)


class EvidenceOrigin(str, Enum):
    UNVERIFIED_LOCAL = "UNVERIFIED_LOCAL"
    SYNTHETIC_HOST_ATTESTATION = "SYNTHETIC_HOST_ATTESTATION"


class WorkerState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAITING_HUMAN = "WAITING_HUMAN"
    UNKNOWN = "UNKNOWN"


class GoalState(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    COMPLETE = "COMPLETE"
    UNKNOWN = "UNKNOWN"


class IdempotencyState(str, Enum):
    UNUSED = "UNUSED"
    SENT = "SENT"
    IN_FLIGHT = "IN_FLIGHT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HostEvidence:
    """Synthetic observation contract, never a real attestation verifier.

    Every fact must be observed at captured_at by a future trusted host adapter.
    This prototype accepts only explicitly synthetic evidence for a simulated
    success. Marking a local flag enabled does not make its origin trusted.
    """

    origin: EvidenceOrigin
    captured_at: datetime
    plugin_id: str
    plugin_enabled: bool
    hard_off_capabilities: frozenset[str]
    mandate_id: str
    mandate_revision: int
    mandate_is_active: bool
    direction_version: str
    target: Target
    exclusive_controller_id: str | None
    worker_state: WorkerState
    goal_state: GoalState
    new_material_evidence: bool
    budget_day: date
    interventions_today: int
    cost_units_today: int
    cooldown_history_complete: bool
    last_intervention_at: datetime | None
    idempotency_key: str
    idempotency_state: IdempotencyState


@dataclass(frozen=True)
class ProposedAction:
    target: Target
    kind: str
    direction_version: str
    estimated_cost_units: int
    idempotency_key: str


@dataclass(frozen=True)
class EligibilityDecision:
    decision: str
    reasons: tuple[str, ...]
    simulation_only: bool = True
    production_authorized: bool = False


def evaluate(mandate: Mandate, evidence: HostEvidence, action: ProposedAction, *, now: datetime) -> EligibilityDecision:
    """Fail-closed eligibility simulation. This function never dispatches anything.

    Even the all-green result is WOULD_ALLOW_SIMULATION_ONLY. Production
    authorization cannot be obtained from this module or its input flags.
    """
    reasons: list[str] = []
    try:
        if not (isinstance(mandate, Mandate) and isinstance(evidence, HostEvidence)
                and isinstance(action, ProposedAction)):
            raise ValueError("typed mandate, evidence, and action values are required")
        if not isinstance(action.target, Target) or not isinstance(evidence.target, Target):
            raise ValueError("targets must be exact Target pairs")
        if not isinstance(action.kind, str):
            raise ValueError("action kind must be text")
        checked_now = _aware(now, "now")
        captured = _aware(evidence.captured_at, "captured_at")
        approved = _aware(mandate.approved_at, "approved_at")
        expires = _aware(mandate.expires_at, "expires_at")
        for label, value in (("interventions_today", evidence.interventions_today),
                             ("cost_units_today", evidence.cost_units_today),
                             ("mandate_revision", evidence.mandate_revision),
                             ("estimated_cost_units", action.estimated_cost_units)):
            _nonnegative_int(value, label)
        _identifier(action.idempotency_key, "idempotency_key")
    except (ValueError, TypeError, AttributeError):
        return EligibilityDecision("DENY", ("INVALID_INPUT",))
    if evidence.origin is not EvidenceOrigin.SYNTHETIC_HOST_ATTESTATION:
        reasons.append("HOST_EVIDENCE_UNVERIFIED")
    if evidence.plugin_id != mandate.plugin_id or evidence.plugin_enabled is not True:
        reasons.append("PLUGIN_NOT_PROVEN_ENABLED")
    if (not isinstance(evidence.hard_off_capabilities, frozenset)
            or not REQUIRED_HARD_OFF_CAPABILITIES <= evidence.hard_off_capabilities):
        reasons.append("HOST_HARD_OFF_UNPROVEN")
    if mandate.user_approved is not True or evidence.mandate_is_active is not True:
        reasons.append("MANDATE_NOT_APPROVED_OR_ACTIVE")
    if approved > checked_now or expires <= checked_now:
        reasons.append("MANDATE_NOT_CURRENT")
    if evidence.mandate_id != mandate.mandate_id or evidence.mandate_revision != mandate.revision:
        reasons.append("MANDATE_REVISION_MISMATCH")
    if (action.direction_version != mandate.approved_direction_version
            or evidence.direction_version != mandate.approved_direction_version):
        reasons.append("DIRECTION_CHANGED_REQUIRES_USER_APPROVAL")
    if action.target not in mandate.allowed_targets:
        reasons.append("TARGET_NOT_ALLOWLISTED")
    if evidence.target != action.target:
        reasons.append("EVIDENCE_TARGET_MISMATCH")
    if action.kind not in mandate.allowed_action_kinds:
        reasons.append("ACTION_NOT_APPROVED")
    if action.target.thread_id == mandate.manager_thread_id:
        reasons.append("MANAGER_WORKER_CONFLICT")
    if evidence.exclusive_controller_id != mandate.controller_id:
        reasons.append("EXCLUSIVE_CONTROL_UNPROVEN")
    age_seconds = (checked_now - captured).total_seconds()
    if not 0 <= age_seconds <= mandate.max_evidence_age_seconds:
        reasons.append("EVIDENCE_NOT_FRESH")
    if evidence.worker_state is WorkerState.RUNNING:
        reasons.append("WORKER_ACTIVE_SKIP")
    elif evidence.worker_state is WorkerState.WAITING_HUMAN:
        reasons.append("HUMAN_WAITING_SKIP")
    elif evidence.worker_state is not WorkerState.IDLE:
        reasons.append("WORKER_STATE_UNKNOWN")
    if evidence.goal_state is GoalState.COMPLETE:
        reasons.append("GOAL_COMPLETE_SKIP")
    elif evidence.goal_state is not GoalState.INCOMPLETE:
        reasons.append("GOAL_STATE_UNKNOWN")
    if evidence.new_material_evidence is not True:
        reasons.append("NO_NEW_MATERIAL_EVIDENCE_SKIP")
    if evidence.budget_day != checked_now.astimezone(ZoneInfo(mandate.timezone_name)).date():
        reasons.append("BUDGET_PERIOD_UNVERIFIED")
    if evidence.interventions_today >= mandate.max_interventions_per_day:
        reasons.append("INTERVENTION_BUDGET_EXHAUSTED")
    if (action.estimated_cost_units > mandate.max_single_action_cost_units
            or evidence.cost_units_today + action.estimated_cost_units > mandate.max_cost_units_per_day):
        reasons.append("COST_BUDGET_EXCEEDED")
    if evidence.cooldown_history_complete is not True:
        reasons.append("COOLDOWN_HISTORY_UNKNOWN")
    elif evidence.last_intervention_at is None:
        if evidence.interventions_today > 0:
            reasons.append("COOLDOWN_HISTORY_UNKNOWN")
    else:
        try:
            elapsed = (checked_now - _aware(evidence.last_intervention_at, "last_intervention_at")).total_seconds()
            if elapsed < 0 or elapsed < mandate.cooldown_seconds:
                reasons.append("COOLDOWN_ACTIVE_OR_FUTURE")
        except (ValueError, TypeError):
            reasons.append("COOLDOWN_HISTORY_UNKNOWN")
    if evidence.idempotency_key != action.idempotency_key:
        reasons.append("IDEMPOTENCY_KEY_MISMATCH")
    if evidence.idempotency_state is not IdempotencyState.UNUSED:
        reasons.append("IDEMPOTENCY_ALREADY_USED_OR_UNKNOWN")
    if reasons:
        return EligibilityDecision("DENY", tuple(reasons))
    return EligibilityDecision("WOULD_ALLOW_SIMULATION_ONLY", ("ALL_SYNTHETIC_CHECKS_PASSED",))


def synthetic_fixture() -> tuple[datetime, Mandate, HostEvidence, ProposedAction]:
    """Invented identifiers and host guarantees for tests/demo, never live facts."""
    now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    target = Target("synthetic-project", "synthetic-worker")
    mandate = Mandate(
        mandate_id="synthetic-mandate", revision=1, plugin_id="orbit-secretary",
        controller_id="synthetic-controller", manager_thread_id="synthetic-manager",
        allowed_targets=frozenset({target}), allowed_action_kinds=frozenset({"SUGGEST_NEXT_STEP"}),
        approved_direction_version="synthetic-direction-v1", user_approved=True,
        approved_at=now - timedelta(hours=1), expires_at=now + timedelta(days=1),
        timezone_name="Asia/Seoul", max_interventions_per_day=6,
        max_cost_units_per_day=1000, max_single_action_cost_units=200,
        cooldown_seconds=900,
    )
    action = ProposedAction(target, "SUGGEST_NEXT_STEP", mandate.approved_direction_version, 100, "synthetic-decision-1")
    evidence = HostEvidence(
        origin=EvidenceOrigin.SYNTHETIC_HOST_ATTESTATION, captured_at=now,
        plugin_id=mandate.plugin_id, plugin_enabled=True,
        hard_off_capabilities=REQUIRED_HARD_OFF_CAPABILITIES,
        mandate_id=mandate.mandate_id, mandate_revision=mandate.revision, mandate_is_active=True,
        direction_version=mandate.approved_direction_version, target=target,
        exclusive_controller_id=mandate.controller_id, worker_state=WorkerState.IDLE,
        goal_state=GoalState.INCOMPLETE, new_material_evidence=True,
        budget_day=now.astimezone(ZoneInfo(mandate.timezone_name)).date(),
        interventions_today=0, cost_units_today=0, cooldown_history_complete=True, last_intervention_at=None,
        idempotency_key=action.idempotency_key, idempotency_state=IdempotencyState.UNUSED,
    )
    return now, mandate, evidence, action


def demo() -> dict:
    """Return deterministic synthetic output without files, network, or user state."""
    from dataclasses import replace

    now, mandate, evidence, action = synthetic_fixture()
    example_event = TaskEvent("synthetic-change-1", action.target.project_id, action.target.thread_id,
                              now - timedelta(minutes=5), "Synthetic old task received a new progress event.")
    report = prepare_report(
        [example_event, example_event], captured_until=now, now=now, timezone_name="Asia/Seoul",
        last_delivered_cutoff=None,
        coverage=Coverage(True, frozenset({"synthetic-source"}), frozenset({"synthetic-source"})),
    )
    result = evaluate(mandate, evidence, action, now=now)
    disabled = evaluate(mandate, replace(evidence, plugin_enabled=False), action, now=now)
    local_flag = evaluate(mandate, replace(evidence, origin=EvidenceOrigin.UNVERIFIED_LOCAL), action, now=now)
    withheld = commit_report_delivery(report, current_watermark=None, receipt=None, now=now)
    return {
        "warning": "SYNTHETIC OFFLINE SIMULATION. Host lifecycle=true is invented fixture input, not verified Codex support.",
        "real_codex_tasks_read": False, "external_dispatch_implemented": False,
        "production_authorized": False, "local_flags_are_trusted_evidence": False,
        "report": {"start_inclusive": report.start_inclusive.isoformat(),
                   "captured_until_exclusive": report.captured_until.isoformat(),
                   "unique_event_count": len(report.events), "coverage": "synthetic-source only",
                   "undelivered_watermark_advanced": withheld.advanced},
        "synthetic_eligible": {"decision": result.decision, "reasons": result.reasons},
        "synthetic_disabled": {"decision": disabled.decision, "reasons": disabled.reasons},
        "local_flag_only": {"decision": local_flag.decision, "reasons": local_flag.reasons},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo"], help="print an invented offline fixture; never reads Codex state")
    parser.parse_args()
    print(json.dumps(demo(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
