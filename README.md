# agent-toolkit

Portable instructions and skills for AI coding agents.

## Layout

- `rules/` — coding standards and workflow conventions, written to be dropped into an agent's instruction file (`CLAUDE.md`, `.cursorrules`, or equivalent).
- `skills/` — self-contained skills. Each directory holds a `SKILL.md` plus whatever references and scripts it needs.

## Using a skill with Claude Code

Copy or symlink the directory into `~/.claude/skills/`:

```bash
ln -s "$PWD/skills/monitor-review" ~/.claude/skills/monitor-review
```

Invoke it as `/monitor-review <input>`, or let the agent select it when the task matches its description.

## skills/monitor-review

Triages a single Datadog monitor and returns one of four verdicts: ACTION REQUIRED, MONITOR DEFECT, NOISE, or INVESTIGATE FURTHER. Requires a pasted Slack alert message or a Datadog monitor URL. Needs a Datadog MCP server.

It is built around the mistakes that are easy to make when triaging an alert:

- **Branches by monitor class.** An absence-of-signal alert has no error spans and no trace to follow; triaging it as though it did leads to inventing a failure. Error, latency, saturation, and absence-of-signal monitors get different health checks.
- **Checks the threshold against the metric's own baseline** over 30 days before believing the alert. A threshold sitting below normal traffic is the root cause, not whatever happened in the alert window.
- **Refuses to treat silence as evidence.** "Observed zero", "metric doesn't exist", "not instrumented", and "not checked" all render as no data and mean completely different things. An unobservable hop is a blind spot, not a clean check — unless counts on both sides of it reconcile, which neutralizes it.
- **Separates a broken service from a broken monitor.** MONITOR DEFECT exists because NOISE implies close-and-move-on and ACTION REQUIRED implies the service needs attention; neither fits a healthy service behind a miscalibrated monitor.
- **Does the arithmetic in code.** `scripts/calibrate.py` computes per-group min/median, breach fraction at bucket and rolling-window resolution, and longest breach run — with an explicit null policy, since whether you count nulls as zero changes the answer.
