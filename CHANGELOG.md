# Changelog

## 0.2.0

- Briefings lead with progress, meaningful blockers and decisions. Details are available on request; important failures and uncertainty remain visible.
- Manager conversations prefer delegating benchmarks and work estimated at one minute or more. Work estimated at ten minutes or more is handed off within the available authorized routes.
- After dispatch, Orbit gives a short update on the known state and returns without waiting for completion. Missing acknowledgment holds further sends.
- An explicit request to perform a particular job directly takes precedence within the authorized scope. New user-owned tasks still require an explicit request.
- Added a source-only delegation reference evaluator and boundary tests, including safe handling of oversized estimates. These do not install a native enforcement gate, scheduler or cancellation mechanism.
- Updated the English, Korean, Japanese, Simplified Chinese and Russian introductions and usage guidance.
