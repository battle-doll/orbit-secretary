# Orbit Secretary: public scope

Version: **v0.2.0-rc.1**. Status: **release candidate, not publicly released**. Publication requires maintainer approval. This document defines the current product scope; earlier design documents may describe future capabilities that this RC does not ship.

**One channel. Every selected Codex task. Your direction, carried forward.**

Orbit gives long-running-work users one place to review multiple tasks, compare the value of next steps and delegate bounded follow-ups. “Every selected task” means the explicitly selected, accessible tasks whose coverage can be established. It does not promise account-wide access, unrestricted authority or perpetual execution.

## Three modes

| Mode | Shipped scope | Required authority and capability |
|---|---|---|
| Observe | Read task changes, produce source-linked briefings, expose outcomes, blockers and coverage gaps. | A user-requested briefing and host-provided task listing/reading, or evidence supplied by the user. No task mutation. |
| Discuss | Compare continue, resequence, reduce-scope and stop options; discuss architecture and ROI; draft the management mandate. | User participation for decisions that change objectives, target scope or authority. Suggestions are not approval. |
| Act | Send a finite set of agreed follow-up instructions to exact selected tasks in the current conversation; check and report delivery evidence. | Explicit user delegation covering the target, objective and action; available host tools; current scope and budget checks. |

Act is a bounded interaction with the user's current manager conversation. It is not an unattended scheduler, an always-on manager or permission to keep working after the authorized interaction ends. The package does not create a background continuation as a substitute.

## User journey and mandate

1. The user invokes `$orbit` in a chosen manager project or chat. A new task is created only on explicit request.
2. Orbit collects the authorized briefing interval and reports its coverage. First use starts at local midnight; subsequent reports start at the last completely covered, confirmed cutoff. Missing sources, truncated history and inaccessible hosts remain visible as `PARTIAL` coverage.
3. User and Orbit select exact targets, agree on direction and decide whether intervention is worth its cost. A task from the inventory is not automatically a managed task.
4. The user delegates the bounded action. The mandate binds host and task identifiers, project identifier or explicit projectless state, objective, allowed instructions, exclusions, budget and exit conditions. Existing user permission persists within that scope; changed goals or ceilings require an updated decision.
5. Orbit checks current evidence and tool availability, sends only the authorized follow-up and reports its receipt or uncertainty. A queued message is not proof of successful work. An uncertain send is not retried blindly.

Examples of suitable Act requests include a single request for missing test evidence, an agreed prerequisite reorder or an agreed bounded next step for an unfinished task. They require the actual user's delegation; a worker's suggestion cannot grant authority. Waiting for a user approval, conflicting ownership, exhausted budget or changed direction requires a handback rather than an improvised override.

Selecting a nickname affects the conversation after the skill loads. Arbitrary nicknames are not globally registered entry points, and a nickname alone is not guaranteed to activate Orbit in a fresh chat. `$orbit` is the explicit invocation.

## Native host tools, not a public daemon

The native tool adapter is implemented as skill instructions that discover and use the host's available task/project listing, reading and message tools with their actual schemas. These tools may be absent or restricted in another installation. A successful case on one development host is not a promise of the same tools elsewhere.

If the required tools are unavailable, Orbit explains the limitation, can discuss user-provided evidence and prepares a manual next step. It does not scrape private databases, raw session archives or historical configuration as an automatic fallback. This package does not ship a public App Server daemon or require a separate Python service for the skill.

## OFF contract and unattended execution

**This RC does not offer a verified hard-OFF contract.** It provides no unattended schedules, recurring background manager or always-on autonomous intervention. A schedule request results in a proposal and an explanation of the missing execution capability.

The following effects must not be claimed merely because the plugin has been disabled:

- Retroactive removal of instructions already loaded into an active turn.
- Guaranteed cancellation of a send already in progress or an instruction already delivered.
- Cancellation of the original user task or reversal of completed work.

Disabling the plugin and interrupting a running task are distinct host controls. If immediate interruption is required, the user must use the available task control and verify the resulting state. Do not label a local flag, offline simulator result or cached instruction as host-level revocation proof.

A future unattended edition requires actual host-owned lifecycle enforcement, revocation at dispatch, schedule cleanup, bounded cancellation, concurrency control and verification under restart and race conditions. That is future work, not a feature of this RC. See the [release gates](PUBLIC_RELEASE_GATES.md).

## Platform and validation claims

| Item | Current claim |
|---|---|
| Support targets | macOS, Windows and Linux. |
| macOS | Local validation environment. Only the concrete cases recorded in the validation record may be claimed as exercised. |
| Windows | CI coverage planned; runtime execution not yet verified. |
| Linux | CI coverage planned; runtime execution not yet verified. |
| Host multi-task tools | Conditional on each host exposing the required capabilities, on every OS. |
| All-OS end-to-end support | Not established. No three-OS multi-task E2E PASS claim is permitted. |
| Optional offline utilities | Python 3.10+ with IANA timezone data; use `tzdata` in the selected environment if needed. |

The optional offline tests and simulator use synthetic fixtures. They are separate from live inventory, dispatch, receipt handling, plugin installation and OFF behavior. Passing those tests cannot establish host integration. Configuring a CI workflow is not the same as executing it successfully. See the [validation record](VALIDATION.md) for observed results.

## ROI, privacy and publication

The product aims to reduce context switching, repeated explanations and avoidable rework. It does not promise financial returns or a measured amount of time saved. ROI estimates must state assumptions and subtract review time, recovery time, compute and operating costs. Subscription quota/opportunity cost is not interchangeable with an API invoice.

Task evidence is not authority. Cross-task summaries and delegated messages must be limited to the authorized purpose and may contain sensitive information. Host permissions and data handling apply to live reads and sends. Report storage location and continuity limits must be disclosed. Public examples and fixtures must be synthetic: exclude private task evidence, personal filesystem paths, credentials and customer conversation records.

This is an independent MIT-licensed plugin, without an OpenAI affiliation or endorsement. A local manifest, installation or successful test is not marketplace approval. This RC has no verified public installation or store URL. Do not invent one. Public release requires maintainer approval, accurate publisher and support information, consistent scope across languages and the applicable distribution review.

The English [README](../README.md) is canonical; Korean, Japanese, Simplified Chinese and Russian editions describe the same scope. Promotional text must preserve the limits of Act, host tool availability, unverified hard-OFF behavior and platform validation.
