# Orbit Secretary (궤도 조정자)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md) | [Русский](README.ru.md)

**Your Codex tasks. One conversation. Your direction.**

> When countless tasks follow their own orbits, Orbit watches, weighs the choices and adjusts their courses to help them avoid collisions.

![Orbit Secretary: one conversation for observing, discussing and coordinating selected tasks](assets/social-card.png)

Orbit is a secretary for people who run several long Codex tasks. Get a briefing in one conversation, decide what deserves attention, and ask Orbit to carry your direction to the tasks you select.

## What Orbit helps you do

- **Catch up in one place.** See what changed, what finished and what is waiting for a decision without opening every conversation.
- **Choose where to spend your time.** Compare priorities, dependencies and expected benefit against the effort still needed.
- **Carry decisions into the work.** Set limits on time and follow-ups, then delegate agreed instructions to selected tasks.

## Observe · Discuss · Act

| Mode | What you can ask for |
|---|---|
| **Observe — get a briefing** | Summarize progress, results, blockers and anything Orbit could not check. Reading and reporting alone do not send instructions to your tasks. |
| **Discuss — choose a direction** | Compare next steps, architecture choices and whether more effort is worthwhile. You choose which tasks to coordinate and how. |
| **Act — coordinate selected tasks** | Send the follow-up instructions you delegate, then report what was received and what the task actually confirmed. |

## Get started

After installing Orbit, open a Codex conversation or project where you want to receive your briefings. Call `$orbit` there:

```text
$orbit Give me a briefing on today's work and the decisions that need my attention.
```

Then continue naturally:

```text
Orbit, which of these tasks should I look at first, and why?
Orbit, compare continuing this task with reducing its scope.
Orbit, ask the task we just selected to organize its pending decisions. Send that instruction once.
```

1. **Read the briefing.** The first report starts at midnight in your timezone. Later reports use the last confirmed report as their starting point. Orbit tells you which information it could not collect.
2. **Select the work to coordinate.** Choose a task from the briefing or name the task you mean. Orbit identifies the target before sending anything.
3. **Set the boundaries.** Agree on the objective, allowed instructions, time limit and number of follow-ups. Orbit carries out that delegation in the current conversation and reports the outcome.

You can also use Orbit only for briefings and discussion. Delegating follow-ups is optional.

## Use a name that suits you

After calling `$orbit`, you can give Orbit a nickname in that conversation. Start a new conversation with `$orbit` again before using the nickname.

## What to expect

- **You choose the scope.** Orbit coordinates the tasks you select. It does not make decisions or grant approvals reserved for you.
- **Coordination runs in the current conversation.** Unattended, recurring background management is not included.
- **Turning the plugin off does not retract work already sent.** Already delivered instructions and running tasks are not automatically cancelled. Use Codex's task controls when you need to stop a running task.
- **Available features depend on your Codex environment.** Reading and coordinating other tasks requires Codex to provide those tools. If a feature is unavailable, Orbit explains the limitation and can help with material you provide.
- **A sent instruction is not a completed task.** Orbit reports delivery, the task's response and confirmed results separately. Missing information stays visible.

See [feature details](docs/PUBLIC_SCOPE.md) for more about reporting and delegation.

## Platforms, cost and privacy

Orbit is designed for Codex environments on **macOS, Windows and Linux**. Use it directly in Codex without setting up a separate service.

Briefings and follow-ups use your Codex usage allowance. ROI discussions make assumptions explicit and account for the time and cost of coordination itself.

Orbit has no separate publisher-operated backend or telemetry service. Task content is processed through Codex and your configured model; reports remain in the conversation or in a workspace you choose.

[Privacy](docs/PRIVACY.md) · [Support](docs/SUPPORT.md) · [Terms](docs/TERMS.md) · [MIT license](LICENSE)

An independent plugin, not an official OpenAI product.
