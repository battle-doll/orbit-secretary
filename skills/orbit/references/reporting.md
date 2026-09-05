# Briefing collection contract

1. Establish an aware `captured_until` timestamp at collection start and the user's IANA timezone. First report starts at local midnight on that date. Later reports start at the last successfully delivered cutoff, even across dates. Use `[start, captured_until)`; an event exactly at the cutoff belongs to the next report.
2. Inventory accessible Codex tasks, including pinned and unpinned tasks, and archived tasks when they may contain changes in the interval. Filter Codex work separately from ChatGPT conversations. A task created earlier belongs in the report if it changed in the interval. Include old running tasks only as clearly labeled carryover context, not new activity.
3. Respect each tool's pagination and limits. Never infer completeness from a default ten-item listing or a fixed recent-task cap. Expand listings and turn history until the interval is covered when the tool permits. Record exclusions, unavailable hosts, truncated pages and time gaps. Without exhaustive coverage proof, say `PARTIAL`, not “all tasks”.
4. Read compact summaries first, expanding only relevant changes and the evidence for proposed decisions. Recover all turns in the interval for included tasks when claiming complete interval coverage. Do not ingest every transcript into the CEO context.
5. Deduplicate by host + task + event/turn identifier. Observe task changes at event time, not folder modification time. Treat missing or conflicting timestamps as a coverage gap. If a source can deliver late events, use a bounded lookback plus persisted IDs; retain source cursors and disclose any unbounded lateness. The preview's offline timestamp filter alone does not solve late arrival.
6. Keep a report ID, interval, per-source cursors, task IDs, coverage, evidence links and delivery status. Store only in the user's manager workspace or a host-provided plugin data directory whose availability is verified. Never write into managed repositories just to keep secretary state. If no safe state store is available, use the current conversation and disclose that cross-chat continuity is unavailable.
7. Save a report before handing it off. Advance the global delivered watermark only after complete coverage and confirmed delivery. Confirmation is a host delivery receipt tied to report ID, or a subsequent user message explicitly acknowledging that report. An enqueue receipt alone is not delivery. If neither is available, mark delivery unconfirmed, preserve the old watermark and deduplicate at retry; do not demand acknowledgment on every report just to improve bookkeeping. A saved draft alone does not prove delivery. Partial reports can be useful but cannot silently skip missing work on the next run.

Suggested output:

- Period: local start → cutoff; coverage: COMPLETE/PARTIAL, inspected N tasks, specific gaps.
- Material outcomes: task title + evidence + implication.
- Decisions: continue / change sequence / reduce scope / stop proposal, expected value and uncertainty.
- Management candidates: exact task IDs, rationale, suggested boundaries.

No report history means local today, not the last 24 hours. An existing report does not permit reading excluded or unrelated historical persona/configuration material.
