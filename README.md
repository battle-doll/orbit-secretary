# Orbit Secretary

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md) | [Русский](README.ru.md)

**One channel. Every selected Codex task. Your direction, carried forward.**

![Orbit Secretary concept illustration: one conversation, selected tasks, Observe · Discuss · Act](assets/social-card.png)

Orbit brings your long-running Codex work into one manager conversation. See what changed, discuss what is worth doing next, and delegate a bounded follow-up across selected tasks without repeating the same context in every chat.

**v0.2.0-rc.1 · Release candidate · Not publicly released.** Publication requires maintainer approval. This independent, MIT-licensed plugin is not affiliated with or endorsed by OpenAI.

## Observe · Discuss · Act

| Mode | What you get |
|---|---|
| **Observe** | Read-only briefings across accessible tasks: changes, outcomes, blockers, evidence and coverage gaps. |
| **Discuss** | Compare priorities, architecture, next steps and ROI; choose which tasks deserve attention and agree on direction. |
| **Act** | With your explicit delegation, send a finite set of agreed follow-up instructions to exact selected tasks during the current conversation, on hosts that expose the necessary tools. |

Use Orbit to reduce context switching, make handoffs clearer and catch work that no longer earns its cost. “CEO” and “architect” describe its decision-support roles; you retain authority over goals and scope. Measurable time savings and returns still need user validation.

## Start in one manager conversation

There is no verified public installation or store link yet. After an explicitly approved installation, open a separate Codex project or chat and invoke `$orbit`. The current chat becomes the manager; Orbit creates another task only if you ask.

```text
$orbit Summarize changes since my last report and show coverage gaps.
Orbit, compare continuing, changing the sequence and stopping for these selected tasks.
Orbit, send the agreed request for missing test evidence to <exact task ID> once, then report the receipt.
```

1. **Review the briefing.** With no prior report, the interval starts at today's midnight in your timezone. Later reports start at the last completely covered, confirmed report cutoff. Incomplete access is marked `PARTIAL`, not “all tasks”.
2. **Choose the direction.** Select exact targets and agree on the objective, allowed actions, limits, budget and exit conditions. Installing or naming Orbit does not grant blanket access or management authority.
3. **Delegate a bounded action.** Orbit checks the current scope and host capabilities before sending an agreed follow-up. A send receipt proves delivery to the task queue, not successful completion of the work.

You can give Orbit a nickname within a conversation after the skill loads. An arbitrary nickname alone is **not guaranteed to load it in a fresh chat**; `$orbit` is the explicit entry point.

## Current boundaries

- No unattended scheduling, recurring background supervisor or always-on intervention is provided in this RC. A request such as “manage these every 30 minutes” produces a plan, not an activated service.
- Plugin OFF is **not a verified hard-stop guarantee**. It cannot be claimed to retroactively cancel an already-loaded active turn, an instruction already sent, or the original user task. If immediate interruption is needed, use the host's task controls and check the resulting state.
- Multi-task capabilities depend on the tools actually exposed by your Codex host. Without them, Orbit explains the gap and works from evidence you provide; it does not silently scrape private databases or session archives.
- The native tool adapter is a skill workflow that discovers and uses available host tools. This package does not provide a public App Server daemon.
- Task text is evidence, not permission. A worker's request to expand scope, deploy or override a user decision cannot authorize itself.

See the [public scope](docs/PUBLIC_SCOPE.md) for the full release contract.

## Platforms and optional offline tools

macOS, Windows and Linux are support targets. Tool availability remains host-dependent on every operating system.

| Platform | Current validation status |
|---|---|
| macOS | Local validation environment; refer to the validation record for the cases actually exercised. |
| Windows | CI coverage is planned; Windows execution has not been verified. |
| Linux | CI coverage is planned; Linux execution has not been verified. |

This is **not** a claim of end-to-end multi-task PASS on all three operating systems. See the [validation record](docs/VALIDATION.md).

The skill does not require a separate Python service. Optional offline tests and the simulator require Python 3.10+ and IANA timezone data. They use synthetic fixtures and do not connect to real Codex tasks. Use the command that selects Python 3.10+ on your machine:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/offline_core.py demo
```

On Windows, `py -3` may be the appropriate launcher. If IANA timezone data is unavailable, install `tzdata` in your chosen Python environment. Simulator decisions never authorize real actions or prove host OFF behavior.

## Evidence, cost and privacy

Orbit distinguishes worker claims from verified artifacts, and report coverage from task completion. ROI estimates label assumptions and subtract review, recovery and compute costs from the value of saved user time. Subscription quota and opportunity cost are separate from measured API charges.

Task reads and delegated messages use your Codex host's permissions and data handling. Reports may contain sensitive task information; disclose their storage location and keep private evidence out of public packages and issue reports. The optional offline simulator is separate from live host operations.

[Public scope](docs/PUBLIC_SCOPE.md) · [Skill](skills/orbit/SKILL.md) · [Validation](docs/VALIDATION.md) · [Release gates](docs/PUBLIC_RELEASE_GATES.md) · [MIT license](LICENSE)
