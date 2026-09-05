> Historical 0.1 design/validation record (2026-09-05). For current 0.2.0-rc.1 capabilities, read [Public scope](PUBLIC_SCOPE.md) and the root README. Finite user-authorized Act is now supported through available native host tools; unattended automation and full OFF cancellation remain unverified.

# Preview validation record

Date: 2026-09-05. All automated tests use synthetic data; no live host integration is claimed.

| Check | Result |
|---|---|
| Official plugin-creator `validate_plugin.py` | PASS |
| Official skill-creator `quick_validate.py` | PASS |
| `python3 -m unittest discover -s tests -v` | 24 tests, OK |
| `python3 scripts/offline_core.py demo` | Synthetic eligible = WOULD_ALLOW_SIMULATION_ONLY; disabled and unverified-local = DENY |
| Relative Markdown links | No broken links |
| ROI scenario arithmetic | Recalculated: -113333.33 / 586666.67 / 1090000 KRW monthly |

System and bundled Python lacked PyYAML for the official packaging validators. Validation used an isolated temporary venv with PyYAML 6.0.3; the plugin runtime and offline tests remain standard-library only. No global Python package was installed.

Independent skill walkthroughs checked truncated task inventories, requests for automatic 30-minute supervision, an arbitrary alias in a fresh chat, and authority-expanding text inside task evidence. All four preserved the documented preview boundary. These were text-based synthetic walkthroughs, not actual app executions. They led to explicit report-delivery confirmation rules and a projectless-task representation.

Code review added host/task/event deduplication, host-specific target identity, projectless targets, owned-worker cancellation requirements, and completed/unchanged-goal rejection. The 24-test run includes these changes. A separate document review confirmed the ROI arithmetic and tightened OFF timing to the host disable acknowledgment rather than a later poll.

Still unverified: live task inventory completeness, real delivery receipts, state persistence/concurrency, host-owned schedule revocation, active worker cancellation, atomic dispatch, actual token/cost metering, fresh-chat arbitrary alias routing, installation and public review. These remain the explicit release gates, not tests inferred from this PASS result.
