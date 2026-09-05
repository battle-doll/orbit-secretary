# Management mandate draft

Required fields:

| Field | Meaning |
|---|---|
| manager identity | Host and task ID of the single supervising chat |
| target pairs | Explicit host, project ID and task ID; use project ID null only for a verified projectless task; future tasks are not automatically included |
| objective / direction version | User-valued result and approved approach |
| acceptance evidence | Artifacts, checks and thresholds that establish completion |
| actions | Allowed kinds of instructions; separate per-task scope |
| boundaries | No-go actions and project-specific limits, preserved verbatim when supplied |
| cadence / quiet window | Review opportunities, cooldown and user notification preference |
| budget | Checks, dispatches, tokens or measured cost per period; unknown cost treatment |
| expiry / exit | End time, success condition, stop conditions, user handback |
| approval receipt | User decision reference bound to the complete mandate version |

For current-conversation Act, identify exact tasks, a finite time window, and a small dispatch cap. For example, a user-requested ten-minute read-only pilot can use at most two bounded instructions plus one necessary closure message. These are proposed ceilings, never implied approval. Recurring schedules are future design only and unavailable in this release.

Within an approved direction, useful interventions include asking for missing evidence, sequencing a prerequisite, restating acceptance criteria, and requesting a bounded alternative. An active worker should normally finish its current turn. If the user explicitly authorized coordination of that running task, send at most a scoped additive instruction that preserves its latest user request; do not interrupt execution. A user-approval wait permits organizing evidence or decisions if requested, never answering or approving on the user's behalf.

Do not let the CEO title widen authority to deployment, production changes, purchases, external communications, credentials, destructive work or additional projects. Do not create new workers unless the mandate explicitly permits task creation and its budget. Never send to the manager itself or another supervisor as a worker.

Current-conversation execution must revalidate the mandate, latest user instructions and target state immediately before dispatch, serialize instructions per target, log the exact instruction and receipt, and avoid retrying an uncertain send blindly. A successful enqueue is not proof that the worker completed the instruction. Without an atomic host gate, concurrent changes and cancellation cannot be guaranteed; keep this limitation explicit.

The release supports native host-assisted finite dispatch where those tools exist. Host-owned revocation, scheduling, atomic dispatch/reconciliation and live metering remain required work for unattended autonomy.
