"""Pure reference decisions for routing work and returning after a handoff.

No host access, I/O, clock, dispatch, persistence, or authority verification exists
here. Callers must supply a whole-undertaking estimate and current authorization
evidence, then reevaluate if the work grows. These results do not execute policy
or grant permission to execute it on a real Codex host.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class WorkKind(str, Enum):
    INSTANT_ANSWER = "INSTANT_ANSWER"
    SHORT_STATUS = "SHORT_STATUS"
    SCOPE_OR_PRIORITY = "SCOPE_OR_PRIORITY"
    DISPATCH_OR_RECEIPT = "DISPATCH_OR_RECEIPT"
    UNAVOIDABLE_SHORT_HANDLING = "UNAVOIDABLE_SHORT_HANDLING"
    BENCHMARK = "BENCHMARK"
    OTHER = "OTHER"


class PathKind(str, Enum):
    EXISTING_TASK = "EXISTING_TASK"
    INTERNAL_AGENT = "INTERNAL_AGENT"
    NEW_USER_TASK = "NEW_USER_TASK"


@dataclass(frozen=True)
class Work:
    work_id: str
    scope_id: str
    kind: WorkKind
    initial_total_seconds: float | None
    elapsed_seconds: float
    remaining_seconds: float | None
    covers_whole_undertaking: bool
    scope_authorized: bool


@dataclass(frozen=True)
class DelegationPath:
    kind: PathKind
    target_id: str
    authorized_scope_ids: frozenset[str]
    available: bool = True
    appropriate: bool = True
    host_authorized: bool = False
    new_task_requested_for_work_id: str | None = None


@dataclass(frozen=True)
class UnavoidableDirect:
    work_id: str
    scope_id: str
    reason: str
    max_total_seconds: float


@dataclass(frozen=True)
class UserDirectOverride:
    work_id: str
    scope_id: str
    explicitly_requested: bool = False


@dataclass(frozen=True)
class RoutingDecision:
    decision: str
    reasons: tuple[str, ...]
    effective_total_seconds: float | None
    selected_path: DelegationPath | None = None
    direct_reason: str | None = None
    direct_scope_id: str | None = None
    direct_limit_seconds: float | None = None
    enforcement_scope: str = "reference_only"
    execution_authority_granted: bool = False


def _exact_id(value: object) -> bool:
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and not any(char in value for char in "*?[]\x00"))


def _seconds(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except (OverflowError, ValueError):
        return False


def _select_path(work: Work, paths: tuple[DelegationPath, ...]) -> DelegationPath | None:
    # Preserve the caller's preference order within each authorized path kind.
    if not isinstance(paths, tuple):
        return None
    for kind in (PathKind.EXISTING_TASK, PathKind.INTERNAL_AGENT, PathKind.NEW_USER_TASK):
        for path in paths:
            if (not isinstance(path, DelegationPath) or path.kind is not kind
                    or path.available is not True or path.appropriate is not True
                    or not _exact_id(path.target_id)
                    or not isinstance(path.authorized_scope_ids, frozenset)
                    or work.scope_id not in path.authorized_scope_ids):
                continue
            if kind is PathKind.INTERNAL_AGENT and path.host_authorized is not True:
                continue
            if (kind is PathKind.NEW_USER_TASK
                    and path.new_task_requested_for_work_id != work.work_id):
                continue
            return path
    return None


def route_work(
    work: Work, paths: tuple[DelegationPath, ...] = (), *,
    unavoidable: UnavoidableDirect | None = None,
    user_override: UserDirectOverride | None = None,
) -> RoutingDecision:
    """Evaluate total work, never a convenient slice of an undertaking.

    The effective estimate is max(initial total, elapsed + remaining). Unknown,
    invalid, or partial estimates cannot justify direct work. An exact explicit
    direct override with an unknown estimate holds for a short scoping step;
    it does not silently delegate contrary to that choice. Missing delegation
    paths never create an exception.
    All approval/path fields are supplied reference inputs, not authenticated
    execution authority.
    """
    if (not isinstance(work, Work) or not _exact_id(work.work_id)
            or not _exact_id(work.scope_id) or work.scope_authorized is not True):
        return RoutingDecision("HOLD_SCOPE_DENIED", ("SCOPE_NOT_AUTHORIZED_OR_INVALID",), None)

    selected = _select_path(work, paths)
    reasons = []
    exact_override = (isinstance(user_override, UserDirectOverride)
                      and user_override.explicitly_requested is True
                      and user_override.work_id == work.work_id
                      and user_override.scope_id == work.scope_id)
    estimate_known = (work.covers_whole_undertaking is True
                      and all(_seconds(value) for value in
                              (work.initial_total_seconds, work.elapsed_seconds, work.remaining_seconds)))
    total = None
    if estimate_known:
        total = max(work.initial_total_seconds, work.elapsed_seconds + work.remaining_seconds)
        if not _seconds(total):
            total = None
            estimate_known = False
    if not estimate_known:
        reasons.append("WHOLE_UNDERTAKING_ESTIMATE_UNKNOWN_OR_INVALID")
        if exact_override:
            return RoutingDecision("HOLD_ESTIMATE_REQUIRED",
                                   tuple(reasons + ["RESOLVE_ESTIMATE_WITHOUT_OVERRIDING_USER_DIRECT_CHOICE"]),
                                   None)
    else:
        if exact_override:
            return RoutingDecision("DIRECT", ("EXACT_USER_DIRECT_OVERRIDE",), total,
                                   direct_reason="Explicit user override for this exact work and scope.",
                                   direct_scope_id=work.scope_id, direct_limit_seconds=total)
        if user_override is not None:
            reasons.append("USER_OVERRIDE_NOT_EXACT_OR_NOT_EXPLICIT")

        if total >= 600:
            reasons.append("TEN_MINUTES_OR_MORE_REQUIRES_DELEGATION")
        else:
            exception_valid = (
                isinstance(unavoidable, UnavoidableDirect)
                and unavoidable.work_id == work.work_id and unavoidable.scope_id == work.scope_id
                and isinstance(unavoidable.reason, str) and 1 <= len(unavoidable.reason.strip()) <= 240
                and _seconds(unavoidable.max_total_seconds)
                and 0 < unavoidable.max_total_seconds < 600
                and total <= unavoidable.max_total_seconds
            )
            if exception_valid:
                return RoutingDecision("DIRECT", ("BOUNDED_UNAVOIDABLE_DIRECT_EXCEPTION",), total,
                                       direct_reason=unavoidable.reason.strip(), direct_scope_id=work.scope_id,
                                       direct_limit_seconds=unavoidable.max_total_seconds)
            if unavoidable is not None:
                reasons.append("UNAVOIDABLE_EXCEPTION_MISSING_REASON_SCOPE_OR_BOUND")
            short_direct_kinds = (
                WorkKind.INSTANT_ANSWER, WorkKind.SHORT_STATUS,
                WorkKind.SCOPE_OR_PRIORITY, WorkKind.DISPATCH_OR_RECEIPT,
            )
            if total < 60 and any(work.kind is kind for kind in short_direct_kinds):
                return RoutingDecision("DIRECT", tuple(reasons + ["SHORT_PERMITTED_DIRECT_WORK"]), total,
                                       direct_scope_id=work.scope_id, direct_limit_seconds=total)
            if work.kind is WorkKind.BENCHMARK:
                reasons.append("BENCHMARK_PREFERS_DELEGATION")
            elif total >= 60:
                reasons.append("ONE_TO_TEN_MINUTES_PREFERS_DELEGATION")
            else:
                reasons.append("WORK_OUTSIDE_DEFAULT_DIRECT_CATEGORIES")

    if selected is None:
        return RoutingDecision("HANDOFF_DRAFT_PATH_BLOCKED",
                               tuple(reasons + ["NO_AUTHORIZED_DELEGATION_PATH"]), total)
    return RoutingDecision("DELEGATE", tuple(reasons), total, selected_path=selected)


class SendState(str, Enum):
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"
    NOT_SENT = "NOT_SENT"


class WorkerState(str, Enum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class WorkerResponse:
    decision_id: str | None
    state: WorkerState
    completion_evidence_verified: bool = False


@dataclass(frozen=True)
class HandoffDecision:
    send_state: str
    worker_state: str
    next_action: str
    reasons: tuple[str, ...]
    additional_snapshots: int
    snapshots_after_decision: int
    requested_snapshot_wait_seconds: int = 0
    wait_loop_allowed: bool = False
    parallel_implementation_allowed: bool = False
    further_dispatch_authorized: bool = False
    enforcement_scope: str = "reference_only"
    execution_authority_granted: bool = False


def after_send(
    decision_id: str, send_state: SendState, *, response: WorkerResponse | None = None,
    snapshots_taken: int = 0, request_snapshot: bool = False,
) -> HandoffDecision:
    """Plan at most one nonblocking snapshot, then return to the user.

    SENT is a send receipt, not worker acceptance. A response must match the
    decision ID. Claimed completion without verified acceptance evidence remains
    COMPLETION_UNVERIFIED. The caller must carry snapshots_after_decision forward;
    this pure function has no persistent counter or real-time enforcement.
    """
    reasons = []
    known_send = send_state if isinstance(send_state, SendState) else SendState.UNKNOWN
    worker = "ACK_UNKNOWN"
    if not _exact_id(decision_id):
        reasons.append("INVALID_DECISION_ID")
    elif (isinstance(response, WorkerResponse) and response.decision_id == decision_id
          and known_send is not SendState.NOT_SENT):
        if response.state is WorkerState.COMPLETED:
            if response.completion_evidence_verified is True:
                worker = "COMPLETED"
            else:
                worker = "COMPLETION_UNVERIFIED"
                reasons.append("WORKER_CLAIM_IS_NOT_VERIFIED_COMPLETION")
        elif response.state is WorkerState.RUNNING:
            worker = "RUNNING"
        elif response.state is WorkerState.ACCEPTED:
            worker = "ACCEPTED"
        else:
            reasons.append("WORKER_STATE_UNKNOWN")
    else:
        reasons.append("ACK_MISSING_UNCORRELATED_OR_SEND_NOT_CONFIRMED")

    counter_valid = (not isinstance(snapshots_taken, bool)
                     and isinstance(snapshots_taken, int) and snapshots_taken >= 0)
    if not counter_valid:
        reasons.append("SNAPSHOT_COUNT_UNKNOWN_OR_INVALID")
    used = snapshots_taken if counter_valid else 1
    can_snapshot = (request_snapshot is True and counter_valid and used == 0
                    and _exact_id(decision_id) and known_send is not SendState.NOT_SENT
                    and worker != "COMPLETED")
    extra = 1 if can_snapshot else 0
    return HandoffDecision(
        send_state=known_send.value, worker_state=worker,
        next_action="ONE_NONBLOCKING_SNAPSHOT_THEN_RETURN" if extra else "RETURN_TO_USER",
        reasons=tuple(reasons), additional_snapshots=extra, snapshots_after_decision=used + extra,
    )
