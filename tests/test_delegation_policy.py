"""Synthetic boundary tests of reference routing and handoff outcomes only."""

from dataclasses import replace
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from delegation_policy import (
    DelegationPath, PathKind, SendState, UnavoidableDirect, UserDirectOverride,
    Work, WorkKind, WorkerResponse, WorkerState, after_send, route_work,
)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.work = Work("synthetic-whole-work", "synthetic-scope", WorkKind.SHORT_STATUS,
                         59, 0, 59, True, True)
        self.existing = DelegationPath(PathKind.EXISTING_TASK, "synthetic-existing",
                                       frozenset({self.work.scope_id}))
        self.internal = DelegationPath(PathKind.INTERNAL_AGENT, "synthetic-internal",
                                       frozenset({self.work.scope_id}), host_authorized=True)
        self.new = DelegationPath(PathKind.NEW_USER_TASK, "synthetic-new",
                                  frozenset({self.work.scope_id}),
                                  new_task_requested_for_work_id=self.work.work_id)

    def duration(self, seconds):
        return replace(self.work, initial_total_seconds=seconds, remaining_seconds=seconds)

    def exception(self, **changes):
        value = UnavoidableDirect(self.work.work_id, self.work.scope_id,
                                  "A necessary brief action is only available to the manager.", 599)
        return replace(value, **changes)

    def test_59_60_599_and_600_second_routing_boundaries(self):
        for seconds, decision in ((59, "DIRECT"), (60, "DELEGATE"), (599, "DELEGATE"), (600, "DELEGATE")):
            with self.subTest(seconds=seconds):
                result = route_work(self.duration(seconds), (self.existing,))
                self.assertEqual(result.decision, decision)
                self.assertEqual(result.effective_total_seconds, seconds)
        self.assertIn("TEN_MINUTES_OR_MORE_REQUIRES_DELEGATION",
                      route_work(self.duration(600), (self.existing,)).reasons)

    def test_benchmarks_and_nontrivial_work_prefer_delegation_even_when_short(self):
        for kind in (WorkKind.BENCHMARK, WorkKind.OTHER, WorkKind.UNAVOIDABLE_SHORT_HANDLING):
            with self.subTest(kind=kind):
                self.assertEqual(route_work(replace(self.work, kind=kind), (self.existing,)).decision, "DELEGATE")

    def test_direct_categories_are_limited_to_short_allowed_handling(self):
        for kind in (WorkKind.INSTANT_ANSWER, WorkKind.SHORT_STATUS,
                     WorkKind.SCOPE_OR_PRIORITY, WorkKind.DISPATCH_OR_RECEIPT):
            with self.subTest(kind=kind):
                self.assertEqual(route_work(replace(self.work, kind=kind)).decision, "DIRECT")
                self.assertEqual(route_work(replace(self.duration(60), kind=kind)).decision, "HANDOFF_DRAFT_PATH_BLOCKED")

    def test_elapsed_plus_remaining_growth_triggers_delegation_without_resetting_estimate(self):
        grown = replace(self.work, elapsed_seconds=40, remaining_seconds=20)
        self.assertEqual(route_work(grown, (self.existing,)).decision, "DELEGATE")
        grown_long = replace(self.work, elapsed_seconds=550, remaining_seconds=50)
        result = route_work(grown_long, (self.existing,), unavoidable=self.exception())
        self.assertEqual(result.effective_total_seconds, 600)
        self.assertEqual(result.decision, "DELEGATE")
        shrunken_remainder = replace(self.duration(600), elapsed_seconds=500, remaining_seconds=1)
        self.assertEqual(route_work(shrunken_remainder, (self.existing,)).effective_total_seconds, 600)

    def test_partial_or_invalid_estimates_cannot_make_work_direct(self):
        invalid = [replace(self.work, covers_whole_undertaking=False)]
        for value in (None, -1, True, float("nan"), float("inf"), 10 ** 1000, "59"):
            invalid.extend(replace(self.work, **{field: value}) for field in
                           ("initial_total_seconds", "elapsed_seconds", "remaining_seconds"))
        for work in invalid:
            with self.subTest(work=work):
                self.assertEqual(route_work(work, (self.existing,)).decision, "DELEGATE")
                self.assertEqual(route_work(work, unavoidable=self.exception()).decision, "HANDOFF_DRAFT_PATH_BLOCKED")

    def test_exact_direct_choice_with_unknown_or_partial_estimate_holds_instead_of_delegating(self):
        exact = UserDirectOverride(self.work.work_id, self.work.scope_id, True)
        unresolved = (replace(self.work, initial_total_seconds=None),
                      replace(self.work, remaining_seconds=float("nan")),
                      replace(self.work, covers_whole_undertaking=False))
        for work in unresolved:
            for paths in ((), (self.existing, self.internal)):
                with self.subTest(work=work, paths=paths):
                    result = route_work(work, paths, user_override=exact)
                    self.assertEqual(result.decision, "HOLD_ESTIMATE_REQUIRED")
                    self.assertIsNone(result.selected_path)
                    self.assertFalse(result.execution_authority_granted)
        resolved = replace(unresolved[0], initial_total_seconds=600, remaining_seconds=600)
        self.assertEqual(route_work(resolved, (self.existing,), user_override=exact).decision, "DIRECT")

    def test_finite_individual_estimates_with_overflowing_total_are_treated_as_unknown(self):
        # Each integer converts to a finite float; their sum does not.
        work = replace(self.work, elapsed_seconds=10 ** 308, remaining_seconds=10 ** 308)
        delegated = route_work(work, (self.existing,))
        self.assertEqual(delegated.decision, "DELEGATE")
        self.assertIsNone(delegated.effective_total_seconds)
        self.assertEqual(route_work(work).decision, "HANDOFF_DRAFT_PATH_BLOCKED")
        override = UserDirectOverride(work.work_id, work.scope_id, True)
        held = route_work(work, (self.existing,), user_override=override)
        self.assertEqual(held.decision, "HOLD_ESTIMATE_REQUIRED")
        self.assertIsNone(held.selected_path)

    def test_no_authorized_path_never_substitutes_long_direct_work(self):
        for seconds in (60, 599, 600, 1200):
            with self.subTest(seconds=seconds):
                result = route_work(self.duration(seconds))
                self.assertEqual(result.decision, "HANDOFF_DRAFT_PATH_BLOCKED")
                self.assertIsNone(result.selected_path)
        self.assertEqual(route_work(replace(self.work, kind=WorkKind.BENCHMARK)).decision, "HANDOFF_DRAFT_PATH_BLOCKED")

    def test_unavoidable_exception_requires_exact_scope_concise_reason_and_bounded_total(self):
        work = self.duration(599)
        allowed = route_work(work, unavoidable=self.exception())
        self.assertEqual(allowed.decision, "DIRECT")
        self.assertEqual(allowed.direct_scope_id, work.scope_id)
        self.assertEqual(allowed.direct_limit_seconds, 599)
        invalid = (self.exception(reason=" "), self.exception(reason="x" * 241),
                   self.exception(scope_id="another-scope"), self.exception(work_id="another-work"),
                   self.exception(max_total_seconds=598), self.exception(max_total_seconds=600),
                   self.exception(max_total_seconds=None))
        for exception in invalid:
            with self.subTest(exception=exception):
                self.assertEqual(route_work(work, (self.existing,), unavoidable=exception).decision, "DELEGATE")
        self.assertEqual(route_work(self.duration(600), (self.existing,), unavoidable=self.exception()).decision, "DELEGATE")

    def test_only_an_exact_explicit_user_override_permits_ten_minute_direct_work(self):
        work = self.duration(600)
        exact = UserDirectOverride(work.work_id, work.scope_id, True)
        self.assertEqual(route_work(work, user_override=exact).decision, "DIRECT")
        for override in (replace(exact, explicitly_requested=False), replace(exact, work_id="different-work"),
                         replace(exact, scope_id="different-scope")):
            with self.subTest(override=override):
                self.assertEqual(route_work(work, (self.existing,), user_override=override).decision, "DELEGATE")

    def test_scope_denial_overrides_paths_exceptions_and_user_override(self):
        work = replace(self.duration(600), scope_authorized=False)
        result = route_work(work, (self.existing,), unavoidable=self.exception(),
                            user_override=UserDirectOverride(work.work_id, work.scope_id, True))
        self.assertEqual(result.decision, "HOLD_SCOPE_DENIED")
        self.assertIsNone(result.selected_path)
        unknown = replace(work, initial_total_seconds=None)
        self.assertEqual(route_work(unknown, (self.existing,), user_override=UserDirectOverride(
            work.work_id, work.scope_id, True)).decision, "HOLD_SCOPE_DENIED")

    def test_existing_then_host_authorized_internal_then_explicit_new_task_precedence(self):
        work = self.duration(60)
        self.assertEqual(route_work(work, (self.new, self.internal, self.existing)).selected_path, self.existing)
        self.assertEqual(route_work(work, (self.new, self.internal, replace(self.existing, appropriate=False))).selected_path,
                         self.internal)
        self.assertEqual(route_work(work, (replace(self.internal, host_authorized=False), self.new)).selected_path, self.new)
        for path in (replace(self.existing, available=False),
                     replace(self.existing, authorized_scope_ids=frozenset({"different-scope"})),
                     replace(self.internal, host_authorized=False),
                     replace(self.new, new_task_requested_for_work_id=None),
                     replace(self.new, new_task_requested_for_work_id="different-work")):
            with self.subTest(path=path):
                self.assertEqual(route_work(work, (path,)).decision, "HANDOFF_DRAFT_PATH_BLOCKED")

    def test_all_routing_results_are_reference_only_without_execution_authority(self):
        outcomes = (route_work(self.work), route_work(self.duration(60), (self.existing,)),
                    route_work(self.duration(600)), route_work(replace(self.work, scope_authorized=False)))
        for result in outcomes:
            self.assertEqual(result.enforcement_scope, "reference_only")
            self.assertFalse(result.execution_authority_granted)


class HandoffTests(unittest.TestCase):
    def test_send_receipt_is_distinct_from_acceptance_running_and_completion(self):
        sent = after_send("synthetic-decision", SendState.SENT)
        self.assertEqual((sent.send_state, sent.worker_state), ("SENT", "ACK_UNKNOWN"))
        for state in (WorkerState.ACCEPTED, WorkerState.RUNNING, WorkerState.COMPLETED):
            with self.subTest(state=state):
                result = after_send("synthetic-decision", SendState.SENT,
                                    response=WorkerResponse("synthetic-decision", state, True))
                self.assertEqual(result.send_state, "SENT")
                self.assertEqual(result.worker_state, state.value)

    def test_uncorrelated_completion_never_becomes_confirmed_progress(self):
        result = after_send("synthetic-decision", SendState.SENT,
                            response=WorkerResponse("other-decision", WorkerState.COMPLETED, True))
        self.assertEqual(result.worker_state, "ACK_UNKNOWN")
        self.assertFalse(result.further_dispatch_authorized)
        claimed = after_send("synthetic-decision", SendState.SENT,
                             response=WorkerResponse("synthetic-decision", WorkerState.COMPLETED))
        self.assertEqual(claimed.worker_state, "COMPLETION_UNVERIFIED")

    def test_one_nonblocking_snapshot_then_return_without_wait_loop_or_parallel_work(self):
        first = after_send("synthetic-decision", SendState.SENT, request_snapshot=True)
        self.assertEqual(first.additional_snapshots, 1)
        self.assertEqual(first.requested_snapshot_wait_seconds, 0)
        self.assertEqual(first.next_action, "ONE_NONBLOCKING_SNAPSHOT_THEN_RETURN")
        second = after_send("synthetic-decision", SendState.SENT, request_snapshot=True,
                            snapshots_taken=first.snapshots_after_decision)
        self.assertEqual(second.additional_snapshots, 0)
        self.assertEqual(second.next_action, "RETURN_TO_USER")
        for result in (first, second):
            self.assertFalse(result.wait_loop_allowed)
            self.assertFalse(result.parallel_implementation_allowed)
            self.assertFalse(result.execution_authority_granted)
            self.assertEqual(result.enforcement_scope, "reference_only")

    def test_default_and_completed_handoffs_return_immediately(self):
        self.assertEqual(after_send("synthetic-decision", SendState.SENT).next_action, "RETURN_TO_USER")
        completed = after_send("synthetic-decision", SendState.SENT, request_snapshot=True,
                               response=WorkerResponse("synthetic-decision", WorkerState.COMPLETED, True))
        self.assertEqual(completed.next_action, "RETURN_TO_USER")
        self.assertEqual(completed.additional_snapshots, 0)

    def test_unknown_send_and_invalid_snapshot_counter_do_not_enable_retry_or_waiting(self):
        for count in (-1, None, True, 1, 5):
            with self.subTest(count=count):
                result = after_send("synthetic-decision", SendState.UNKNOWN, request_snapshot=True, snapshots_taken=count)
                self.assertEqual(result.send_state, "UNKNOWN")
                self.assertEqual(result.worker_state, "ACK_UNKNOWN")
                self.assertEqual(result.next_action, "RETURN_TO_USER")
                self.assertFalse(result.further_dispatch_authorized)
        not_sent = after_send("synthetic-decision", SendState.NOT_SENT, request_snapshot=True,
                              response=WorkerResponse("synthetic-decision", WorkerState.COMPLETED, True))
        self.assertEqual(not_sent.worker_state, "ACK_UNKNOWN")
        self.assertEqual(not_sent.additional_snapshots, 0)


if __name__ == "__main__":
    unittest.main()
