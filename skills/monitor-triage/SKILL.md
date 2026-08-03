---
name: monitor-triage
description: Triage one specific Datadog monitor and decide whether it needs action, is noise, or is a miscalibrated monitor. Requires either a pasted Slack alert message or a Datadog monitor URL — do not invoke without one. Not for general observability, dashboard, or metric-exploration questions.
argument-hint: "<slack-alert-message | datadog-monitor-url>"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/calibrate.py *)
---

Triage a Datadog monitor alert and determine whether it requires action.

Bundled resources — read when the step says to, not up front:

- `${CLAUDE_SKILL_DIR}/references/tool-notes.md` — Datadog MCP traps. Read before running queries.
- `${CLAUDE_SKILL_DIR}/references/remedy-patterns.md` — detection design and Terraform constraints. Read when the verdict is MONITOR DEFECT.
- `${CLAUDE_SKILL_DIR}/scripts/calibrate.py` — baseline arithmetic. Use in Step 2 instead of computing by hand.

## Input

**Required — one of these two.** If neither is supplied, stop and ask for one. Do not guess a monitor or go hunting for a recent alert.

- **A Slack alert message.** Parse the monitor name, metric or query fragment, threshold, group key, env, and trigger time. The heading in the message body is authored in the monitor's own template and is frequently not the monitor's Datadog name — get the real name from the definition in Step 0.
- **A Datadog monitor URL.** Take `monitors/<id>`, `group=<key>:<value>`, and `link_event_ts`; everything else comes from Step 0. A bare monitor ID works the same way, since the ID is all that's load-bearing.

Two traps in URL input:

- `from_ts`/`to_ts` is a graph display window, not the eval window. On a sparse metric it holds zero points and reads as "no data." Derive the eval window from the monitor's `last_Xm` and the alert timestamp.
- A `group=` value is not a service. `rulename:foo` is an event-bus rule name; the alerting service may be the bus itself, with `foo` merely its target. Confirm against the monitor definition and `search_datadog_services`.

All timestamps in UTC.

## Step 0 — Monitor definition and class

`search_datadog_monitors` with `query: "id:<monitor_id>"`. Record verbatim: exact query (`last_Xm`, rollup, `by {...}`), threshold and direction, type, `env`/`service`/`team` tags, notification targets.

Classify — this selects the Step 4 branch:

| Class | Looks like |
|---|---|
| Error/failure | error counts or rates, failed/DLQ counters, status checks |
| Latency | p95/p99 duration, timeouts |
| Absence-of-signal | low count, traffic drop, no-data, `< N` thresholds |
| Saturation/infra | CPU, memory, replicas, pod lifecycle |

## Step 1 — Signal state

Firing, recovered, or re-notifying — a re-notification is not a new incident. Note the first trigger, re-notifications, and any earlier recovery today. Record the current value over the real eval window using the monitor's own query, and whether the threshold is still breached.

## Step 2 — Threshold vs. baseline

Pull the alerting metric at the monitor's eval resolution, then run it through `calibrate.py` rather than counting by hand:

```
python3 ${CLAUDE_SKILL_DIR}/scripts/calibrate.py series.json \
  --threshold <N> --direction below --window-seconds <eval window> --rolling-agg sum
```

It reports per group: null counts, min/median/max, breach fraction at bucket resolution and over reconstructed rolling windows, longest breach run, and whether a floor is viable. Save the raw timeseries to a file first; `--json` gives machine-readable output.

If most normal windows breach, the miscalibrated threshold is the root cause — not whatever happened in the alert window.

- 24h and 7d explains a single firing. **30d minimum if the output will drive a threshold change**, 90d for gap analysis on sparse streams — a 7d trough is not a 30d trough.
- Report per-group minimum and median, not just breach fraction. The minimum determines false positives.
- Never assume tier symmetry across envs. The same rule can trough at 309/hr in prd and 4/hr in stg.
- `sum(last_Xm)` is rolling; `.rollup(sum, X)` buckets only approximate it. Pass `--window-seconds` so the script reconstructs the rolling view.
- State the null policy — `--nulls zero` or `skip` changes the answer.
- Check baseline shape, diurnal and weekday. Compare a sibling stream on separate infrastructure.
- If the query isn't filtered to the alerting group, check the volume range across every group it covers.

## Step 3 — Alert history

`aggregate_events` on the monitor's title string, grouped by group key, over 14d. Note total firings, flapping (recovery faster than the eval window), multi-group fan-out, and whether anyone still reads the channel.

Sample the firings before judging the monitor by its rate. A chronically noisy monitor can still be the only thing catching a real failure mode.

## Step 4 — Health

Run only the branch matching the class. Say which.

### 4a — Error, latency, saturation

Last 2 hours, not 30 minutes — pre-existing degradation won't show:

- Error rate: `aggregate_spans` COUNT by `service` and `status`
- Throughput: span count trend
- P95: `aggregate_spans` P95 on `@duration`, rather than hunting a `trace.*` namespace that often doesn't exist

If error spans exist, pull a representative trace with `get_datadog_trace` and map the call chain — a 504 at the alerting service is often a 507 one hop deeper. Treat each error type at meaningful volume as its own failure mode. Reconcile span errors against the monitor's own metric; if they disagree, find out why before concluding.

### 4b — Absence-of-signal

No error to find; the question is where the signal stopped and whether anything was lost.

1. Map the producer path from Terraform, repo code, and telemetry — not from service names.
2. Label every hop observed-zero, observed-nonzero, or unobservable.
3. Reconcile counts end to end: ingress → invocations → published → matched → received → processed. 1:1 means nothing was lost and the absence is genuine at the origin; divergence locates the loss.

Also: 4xx/5xx at each ingress hop (producers retry on non-2xx, so sustained errors mean loss, not absence); queue depth, oldest-message age, every DLQ; onset shape — taper means human activity ending, cliff means breakage — and whether it self-recovered.

## Step 5 — Change context

`get_change_stories` ±2h plus `search_datadog_events` for deploys, Karpenter, scaling, and pod lifecycle. Note tight timeline overlap. Check the deployed version — if it predates the alert by weeks, code isn't the explanation. If nothing is found, say change stories miss some deploy paths and recommend CI/CD and git log — unless the root cause is already established, in which case say the empty result isn't load-bearing.

## Step 6 — Provenance (before calling a monitor defective)

- Find the Terraform source via Glean. `renotify_interval`, `notify_no_data`, and priority live there, not in the API. Check whether sibling env copies share the defect.
- Check sibling monitors in the same file — a `failed_invocations > 0` next door may make a volume monitor redundant. Also compare filters against them: a missing scoping tag (`aws_account`) is common and makes the monitor fire on the wrong data.
- Prefer in-place edits. Converting to `for_each`/`count` recreates the monitor — new ID, lost history and mute state, dead links in past alerts.
- Search for in-flight work: merged PRs, open PRs, tickets, monitors already migrated. Cite the precedent.
- Note if the monitor was auto-generated by platform onboarding. Unowned monitors are a distinct root cause and change who fixes it.
- Source: for a clone under `~/repos/`, `git fetch origin` and read from `origin/main` via `git show`/`git grep` rather than checking out, so the working tree is left alone. Report the branch it was on. With no clone, read GitHub `main` via Glean and say so — that is not a pinned checkout.

## Step 7 — Verdict

First match wins. Apply per failure mode when several exist.

| # | Condition | Verdict |
|---|---|---|
| 1 | Real user/service impact or data loss, any cause | **ACTION REQUIRED** |
| 2 | A hop is unobservable and the signal is unexplained | **INVESTIGATE FURTHER** — name the hop |
| 3 | Threshold miscalibrated, or fires on conditions expected in normal operation, and no subset of its firings tracked real anomalies | **MONITOR DEFECT** |
| 4 | A change explains it, no impact | **NOISE** — expected from change |
| 5 | Transient, self-resolved, path verified clean end to end | **NOISE** |
| 6 | Signal active, no impact, path clean, threshold sane, nothing explains it | **INVESTIGATE FURTHER** |

MONITOR DEFECT = service healthy, signal explained, fix belongs in monitor config. If some firings did track real anomalies, the fix must preserve that coverage — say which failure mode would otherwise go uncovered.

## Step 8 — Remedy design (MONITOR DEFECT only)

Read `${CLAUDE_SKILL_DIR}/references/remedy-patterns.md` and follow it. In brief: floors and no-data monitors are complements; size no-data windows from the producer's schedule rather than observed history; state time-to-detect and what the fix won't catch; don't strip `renotify_interval` reflexively.

## Output Format

```
## Alert: [monitor name] (monitor [id], group [key:value])
**Query:** [exact query and threshold]  **Class:** [class]
**Status:** [Triggered / Re-notified / Recovered] at [time UTC], plus earlier transitions today
**Current value:** [value over the real eval window, or "no data"] — [breached / within]

## Threshold Calibration
[Per-group min/median and breach fraction from calibrate.py, over the window used. Baseline
shape. Volume range across all groups covered, if unfiltered. State the null policy.]

## Alert History
[14d firings for this group and total. Flapping, fan-out, channel signal-to-noise. Whether any
firings tracked real anomalies.]

## Health
[Only the axes relevant to the class. For absence-of-signal: the hop-by-hop path with each
hop labeled, and the end-to-end count reconciliation.]

## Blind Spots
[Unobservable hops or signals, each marked load-bearing or neutralized-and-how. Omit if none.]

## Change Context
[What changed, when, whether it overlaps — and whether that matters to the conclusion.]

## Root Cause
[1–2 sentences. The actual cause, not the surface symptom. If the cause is the threshold, say so.]

## Verdict
**[ACTION REQUIRED / MONITOR DEFECT / NOISE / INVESTIGATE FURTHER]**
[One sentence justification.]

## Next Steps
- [Concrete and owned — file and resource for a config fix, or "no action required"]

## Recovery Check
[Re-check immediately before reporting. State whether it resolved and whether it can be
expected to self-resolve, on what timescale.]

## Monitor Quality Note
[Whenever Step 2 or 3 found a problem. Cite Terraform file and resource, existing tickets or
merged PRs, and whether a fix is in flight.]
```

## Rules

- Label every claim verified or inferred, and show the tool call and numbers behind quantitative ones.
- "No data" is not a value. Distinguish observed zero, metric doesn't exist, not instrumented, not checked, and tooling artifact.
- Negative evidence is only as good as your proof that the channel carrying it is alive. Before treating silence as a finding, show the channel reports — the same metric firing in another window/env/group, or the same log index carrying other lines from that service in that window. Prefer gauges (queue depth, message age) over `> 0` counters for negative claims: counters don't publish zeros, so their silence is the healthy steady state *and* the misconfigured state. An unobservable hop bracketed by two hops whose counts reconcile 1:1 is neutralized — say so. One sitting on the causal question is the verdict.
- Never use an aggregate as proof about one of its components. A service spanning several streams can look clean while the alerting stream sits at zero — check that stream's own counter and its siblings.
- Span error counts are not application failures — cross-check the metric the monitor fires on.
- Never declare NOISE without a confirmed change overlap or a path verified clean end to end.
- Skip tracing when there are no error spans. Don't invent an error to trace.
- Report what a source actually says. An inconclusive thread is not a decision.
- If the monitor's runbook asserts a cause, check it — a wrong runbook misdirects triage and is itself a finding.
- On INVESTIGATE FURTHER, name the specific next thing to look at.
- Surface incidental findings separately from the verdict rather than dropping them.
