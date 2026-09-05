"""Meaningful boundaries of the offline policy model; all data is invented."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "offline_core.py"
SPEC = importlib.util.spec_from_file_location("offline_core", MODULE_PATH)
core = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = core
SPEC.loader.exec_module(core)
UTC = timezone.utc


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
        self.full = core.Coverage(True, frozenset({"host-a", "host-b"}), frozenset({"host-a", "host-b"}))

    def event(self, event_id, at, thread="old-task"):
        return core.TaskEvent(event_id, "project-a", thread, at, "Untrusted plain event text")

    def report(self, events=(), **kwargs):
        args = dict(captured_until=self.now, now=self.now, timezone_name="Asia/Seoul",
                    last_delivered_cutoff=None, coverage=self.full)
        args.update(kwargs)
        return core.prepare_report(events, **args)

    def deliver(self, report, **kwargs):
        args = dict(current_watermark=report.previous_watermark,
                    receipt=core.DeliveryReceipt(report.report_id, core.DeliveryStatus.DELIVERED, self.now),
                    now=self.now)
        args.update(kwargs)
        return core.commit_report_delivery(report, **args)

    def test_first_report_uses_local_day_and_half_open_boundaries(self):
        start = datetime(2026, 9, 4, 15, 0, tzinfo=UTC)  # Seoul Sep 5 midnight.
        events = [self.event("before", start - timedelta(microseconds=1)),
                  self.event("start", start), self.event("inside", self.now - timedelta(microseconds=1)),
                  self.event("cutoff", self.now), self.event("future", self.now + timedelta(seconds=1))]
        report = self.report(events)
        self.assertEqual(report.start_inclusive, start)
        self.assertEqual([e.event_id for e in report.events], ["start", "inside"])

    def test_incremental_report_includes_old_task_changes_and_deduplicates(self):
        cutoff = self.now - timedelta(hours=2)
        event = self.event("new-change-old-task", cutoff)
        report = self.report([event, event, self.event("too-old", cutoff - timedelta(seconds=1))],
                             last_delivered_cutoff=cutoff)
        self.assertEqual(report.events, (event,))
        self.assertEqual(report.start_inclusive, cutoff)

    def test_conflicting_duplicate_event_ids_cannot_silently_drop_data(self):
        event = self.event("same-id", self.now - timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            self.report([event, replace(event, summary="different payload")])

    def test_dedup_namespace_preserves_equal_event_ids_from_other_hosts_and_tasks(self):
        event = self.event("shared-local-id", self.now - timedelta(seconds=1))
        other_host = replace(event, host_id="other-host")
        other_task = replace(event, thread_id="other-task")
        report = self.report([event, event, other_host, other_task])
        self.assertEqual(len(report.events), 3)
        self.assertEqual(set(report.events), {event, other_host, other_task})

    def test_projectless_changes_are_explicit_and_reportable(self):
        event = core.TaskEvent("projectless-change", None, "projectless-thread",
                               self.now - timedelta(seconds=1), "Projectless task changed", "host-a")
        report = self.report([event])
        self.assertEqual(report.events, (event,))
        self.assertIsNone(report.events[0].project_id)

    def test_aware_datetimes_and_nonfuture_cutoffs_are_required(self):
        naive = datetime(2026, 9, 5, 12)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.event("bad", naive)
        for kwargs in ({"captured_until": naive}, {"now": naive},
                       {"last_delivered_cutoff": naive},
                       {"captured_until": self.now + timedelta(seconds=1)},
                       {"last_delivered_cutoff": self.now + timedelta(seconds=1)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.report(**kwargs)

    def test_dst_transition_uses_local_midnight_not_fixed_24_hours(self):
        cutoff = datetime(2026, 3, 8, 12, 0, tzinfo=UTC)
        report = self.report(captured_until=cutoff, now=cutoff, timezone_name="America/New_York")
        self.assertEqual(report.start_inclusive, datetime(2026, 3, 8, 5, 0, tzinfo=UTC))
        self.assertEqual(report.captured_until - report.start_inclusive, timedelta(hours=7))

    def test_successful_complete_delivery_advances_even_empty_report(self):
        report = self.report()
        result = self.deliver(report)
        self.assertTrue(result.advanced)
        self.assertEqual(result.watermark, self.now)

    def test_incomplete_coverage_never_advances_watermark(self):
        previous = self.now - timedelta(hours=1)
        bad_coverages = [replace(self.full, complete=False), replace(self.full, read_sources=frozenset({"host-a"})),
                         replace(self.full, truncated=True), replace(self.full, errors=("permission denied",)),
                         core.Coverage(True, frozenset(), frozenset()),
                         replace(self.full, read_sources=frozenset({"host-a", "host-b", "unrequested"}))]
        for coverage in bad_coverages:
            with self.subTest(coverage=coverage):
                report = self.report(last_delivered_cutoff=previous, coverage=coverage)
                result = self.deliver(report)
                self.assertFalse(result.advanced)
                self.assertEqual(result.watermark, previous)
                self.assertIn("COVERAGE_INCOMPLETE", result.reasons)

    def test_missing_failed_partial_or_mismatched_delivery_cannot_advance(self):
        report = self.report()
        receipts = [None, core.DeliveryReceipt(report.report_id, core.DeliveryStatus.FAILED),
                    core.DeliveryReceipt(report.report_id, core.DeliveryStatus.UNKNOWN),
                    core.DeliveryReceipt(report.report_id, core.DeliveryStatus.PARTIAL),
                    core.DeliveryReceipt("another-report", core.DeliveryStatus.DELIVERED, self.now),
                    core.DeliveryReceipt(report.report_id, core.DeliveryStatus.DELIVERED),
                    core.DeliveryReceipt(report.report_id, core.DeliveryStatus.DELIVERED, self.now + timedelta(seconds=1)),
                    core.DeliveryReceipt(report.report_id, core.DeliveryStatus.DELIVERED, self.now - timedelta(seconds=1))]
        for receipt in receipts:
            with self.subTest(receipt=receipt):
                result = self.deliver(report, receipt=receipt)
                self.assertFalse(result.advanced)
                self.assertIsNone(result.watermark)

    def test_stale_receipt_cannot_overwrite_a_newer_watermark(self):
        report = self.report()
        current = self.now - timedelta(minutes=1)
        result = self.deliver(report, current_watermark=current)
        self.assertFalse(result.advanced)
        self.assertEqual(result.watermark, current)
        self.assertIn("STALE_REPORT_WATERMARK", result.reasons)
        result = self.deliver(report, now=self.now - timedelta(seconds=1))
        self.assertFalse(result.advanced)
        self.assertIn("FUTURE_CUTOFF", result.reasons)


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.now, self.mandate, self.evidence, self.action = core.synthetic_fixture()

    def evaluate(self, mandate=None, evidence=None, action=None, now=None):
        return core.evaluate(mandate or self.mandate, evidence or self.evidence,
                             action or self.action, now=now or self.now)

    def deny(self, reason, **kwargs):
        result = self.evaluate(**kwargs)
        self.assertEqual(result.decision, "DENY")
        self.assertIn(reason, result.reasons)
        self.assertFalse(result.production_authorized)
        return result

    def test_green_fixture_is_only_simulation_and_local_flags_are_untrusted(self):
        result = self.evaluate()
        self.assertEqual(result.decision, "WOULD_ALLOW_SIMULATION_ONLY")
        self.assertTrue(result.simulation_only)
        self.assertFalse(result.production_authorized)
        self.deny("HOST_EVIDENCE_UNVERIFIED", evidence=replace(self.evidence, origin=core.EvidenceOrigin.UNVERIFIED_LOCAL))
        self.deny("HOST_EVIDENCE_UNVERIFIED", evidence=replace(self.evidence, origin="SYNTHETIC_HOST_ATTESTATION"))

    def test_disabled_plugin_missing_hard_off_or_foreign_plugin_is_denied(self):
        self.deny("PLUGIN_NOT_PROVEN_ENABLED", evidence=replace(self.evidence, plugin_enabled=False))
        self.deny("PLUGIN_NOT_PROVEN_ENABLED", evidence=replace(self.evidence, plugin_enabled="true"))
        self.deny("PLUGIN_NOT_PROVEN_ENABLED", evidence=replace(self.evidence, plugin_id="foreign-plugin"))
        for missing in core.REQUIRED_HARD_OFF_CAPABILITIES:
            with self.subTest(missing=missing):
                self.deny("HOST_HARD_OFF_UNPROVEN", evidence=replace(
                    self.evidence, hard_off_capabilities=core.REQUIRED_HARD_OFF_CAPABILITIES - {missing}))

    def test_expired_unapproved_revoked_and_revised_mandates_are_denied(self):
        self.deny("MANDATE_NOT_CURRENT", mandate=replace(self.mandate, expires_at=self.now))
        self.deny("MANDATE_NOT_CURRENT", mandate=replace(self.mandate, approved_at=self.now + timedelta(seconds=1)))
        self.deny("MANDATE_NOT_APPROVED_OR_ACTIVE", mandate=replace(self.mandate, user_approved=False))
        self.deny("MANDATE_NOT_APPROVED_OR_ACTIVE", evidence=replace(self.evidence, mandate_is_active=False))
        self.deny("MANDATE_REVISION_MISMATCH", evidence=replace(self.evidence, mandate_revision=2))
        self.deny("MANDATE_REVISION_MISMATCH", evidence=replace(self.evidence, mandate_id="different-mandate"))

    def test_direction_changes_cannot_be_self_approved(self):
        self.deny("DIRECTION_CHANGED_REQUIRES_USER_APPROVAL", action=replace(self.action, direction_version="v2"))
        self.deny("DIRECTION_CHANGED_REQUIRES_USER_APPROVAL", evidence=replace(self.evidence, direction_version="v2"))
        self.deny("DIRECTION_CHANGED_REQUIRES_USER_APPROVAL", action=replace(self.action, direction_version="v2"),
                  evidence=replace(self.evidence, direction_version="v2"))

    def test_scope_is_immutable_exact_pair_and_actions_are_bounded(self):
        with self.assertRaises(FrozenInstanceError):
            self.mandate.allowed_targets = frozenset()
        with self.assertRaises(ValueError):
            replace(self.mandate, allowed_targets={self.action.target})
        for target in (core.Target("foreign-project", self.action.target.thread_id),
                       core.Target(self.action.target.project_id, "foreign-thread"),
                       replace(self.action.target, host_id="foreign-host")):
            with self.subTest(target=target):
                self.deny("TARGET_NOT_ALLOWLISTED", action=replace(self.action, target=target))
        with self.assertRaises(ValueError):
            core.Target("*", "any-thread")
        self.deny("ACTION_NOT_APPROVED", action=replace(self.action, kind="PUBLISH_OR_DEPLOY"))
        self.deny("INVALID_INPUT", action=replace(self.action, kind=["SUGGEST_NEXT_STEP"]))
        self.deny("INVALID_INPUT", action=replace(self.action, target={"project_id": "malformed"}))

    def test_projectless_scope_requires_its_own_explicit_allowlist_entry(self):
        projectless = core.Target(None, "explicit-projectless-thread", "host-a")
        action = replace(self.action, target=projectless)
        evidence = replace(self.evidence, target=projectless)
        self.deny("TARGET_NOT_ALLOWLISTED", evidence=evidence, action=action)
        result = self.evaluate(mandate=replace(self.mandate, allowed_targets=frozenset({projectless})),
                               evidence=evidence, action=action)
        self.assertEqual(result.decision, "WOULD_ALLOW_SIMULATION_ONLY")

    def test_manager_conflicts_and_mismatched_observations_are_denied(self):
        self.deny("MANAGER_WORKER_CONFLICT", mandate=replace(self.mandate, manager_thread_id=self.action.target.thread_id))
        for controller in (None, "competing-controller"):
            with self.subTest(controller=controller):
                self.deny("EXCLUSIVE_CONTROL_UNPROVEN", evidence=replace(self.evidence, exclusive_controller_id=controller))
        self.deny("EVIDENCE_TARGET_MISMATCH", evidence=replace(self.evidence, target=core.Target("wrong-project", "wrong-thread")))

    def test_evidence_must_be_fresh_nonfuture_and_timezone_aware(self):
        age = self.mandate.max_evidence_age_seconds
        for captured in (self.now - timedelta(seconds=age + 1), self.now + timedelta(microseconds=1)):
            with self.subTest(captured=captured):
                self.deny("EVIDENCE_NOT_FRESH", evidence=replace(self.evidence, captured_at=captured))
        self.deny("INVALID_INPUT", evidence=replace(self.evidence, captured_at=self.now.replace(tzinfo=None)))
        boundary = self.evaluate(evidence=replace(self.evidence, captured_at=self.now - timedelta(seconds=age)))
        self.assertEqual(boundary.decision, "WOULD_ALLOW_SIMULATION_ONLY")

    def test_active_human_waiting_and_unknown_workers_are_skipped(self):
        for state, reason in ((core.WorkerState.RUNNING, "WORKER_ACTIVE_SKIP"),
                              (core.WorkerState.WAITING_HUMAN, "HUMAN_WAITING_SKIP"),
                              (core.WorkerState.UNKNOWN, "WORKER_STATE_UNKNOWN")):
            with self.subTest(state=state):
                self.deny(reason, evidence=replace(self.evidence, worker_state=state))

    def test_idle_completed_unknown_or_unchanged_goals_are_not_restarted(self):
        self.deny("GOAL_COMPLETE_SKIP", evidence=replace(self.evidence, goal_state=core.GoalState.COMPLETE))
        self.deny("GOAL_STATE_UNKNOWN", evidence=replace(self.evidence, goal_state=core.GoalState.UNKNOWN))
        self.deny("NO_NEW_MATERIAL_EVIDENCE_SKIP", evidence=replace(self.evidence, new_material_evidence=False))
        self.deny("NO_NEW_MATERIAL_EVIDENCE_SKIP", evidence=replace(self.evidence, new_material_evidence="true"))

    def test_budget_limits_day_rollover_and_unknown_costs_fail_closed(self):
        self.deny("INTERVENTION_BUDGET_EXHAUSTED", evidence=replace(
            self.evidence, interventions_today=self.mandate.max_interventions_per_day))
        self.deny("COST_BUDGET_EXCEEDED", evidence=replace(self.evidence, cost_units_today=901))
        self.deny("COST_BUDGET_EXCEEDED", action=replace(self.action, estimated_cost_units=201))
        self.deny("BUDGET_PERIOD_UNVERIFIED", evidence=replace(self.evidence, budget_day=self.evidence.budget_day - timedelta(days=1)))
        for invalid in (None, -1, True, float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                self.deny("INVALID_INPUT", action=replace(self.action, estimated_cost_units=invalid))
        self.assertEqual(self.evaluate(evidence=replace(self.evidence, cost_units_today=900)).decision,
                         "WOULD_ALLOW_SIMULATION_ONLY")

    def test_cooldown_including_midnight_and_missing_history_is_enforced(self):
        self.deny("COOLDOWN_HISTORY_UNKNOWN", evidence=replace(self.evidence, cooldown_history_complete=False))
        self.deny("COOLDOWN_HISTORY_UNKNOWN", evidence=replace(self.evidence, interventions_today=1))
        for last in (self.now - timedelta(seconds=self.mandate.cooldown_seconds - 1), self.now + timedelta(seconds=1)):
            with self.subTest(last=last):
                self.deny("COOLDOWN_ACTIVE_OR_FUTURE", evidence=replace(self.evidence, last_intervention_at=last))
        boundary = self.now - timedelta(seconds=self.mandate.cooldown_seconds)
        self.assertEqual(self.evaluate(evidence=replace(self.evidence, last_intervention_at=boundary)).decision,
                         "WOULD_ALLOW_SIMULATION_ONLY")
        midnight = datetime(2026, 9, 5, 15, 1, tzinfo=UTC)  # Seoul next day 00:01.
        self.deny("COOLDOWN_ACTIVE_OR_FUTURE", now=midnight, evidence=replace(
            self.evidence, captured_at=midnight, budget_day=self.evidence.budget_day + timedelta(days=1),
            interventions_today=0, last_intervention_at=midnight - timedelta(minutes=2)))

    def test_sent_inflight_unknown_or_mismatched_idempotency_never_allows_retry(self):
        for state in (core.IdempotencyState.SENT, core.IdempotencyState.IN_FLIGHT, core.IdempotencyState.UNKNOWN):
            with self.subTest(state=state):
                self.deny("IDEMPOTENCY_ALREADY_USED_OR_UNKNOWN", evidence=replace(self.evidence, idempotency_state=state))
        self.deny("IDEMPOTENCY_KEY_MISMATCH", evidence=replace(self.evidence, idempotency_key="different-key"))
        self.deny("INVALID_INPUT", action=replace(self.action, idempotency_key=""))


if __name__ == "__main__":
    unittest.main()
