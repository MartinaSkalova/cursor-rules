# Remedy patterns for a defective monitor

Load when the verdict is MONITOR DEFECT and you are proposing a fix.

## Detection design

**Floors and no-data monitors are complements, not alternatives.**

- A rolling-window floor stops evaluating once its window empties, so it is unreliable for a total stop.
- A no-data monitor never fires while data trickles, so it misses a partial collapse. A stream running 80 minutes at 5% of normal, then bursting to catch up, is invisible to no-data and caught only by a floor.

Expect to need both on the same stream, covering different failure modes.

**Sizing a no-data window.** For sparse or scheduled streams, derive the expected maximum gap from the producer's schedule — cron expression, batch window, `flexible_time_window` setting — not from observed history. The schedule is a deterministic bound; history is a sample that may not contain the worst case. Then add margin.

**Sizing a floor.** 30 days minimum of per-group history, 90 days if any group is sparse. Report per-group minimum, not just breach fraction; the minimum is what determines false positives. Use `scripts/calibrate.py` rather than doing the arithmetic by hand.

**Tier membership is per-environment.** The same rule can trough at 309/hr in prd and 4/hr in stg, so it carries a floor in one and cannot in the other. Leave a comment in the code saying so, or a later change will "harmonize" the two and reintroduce the noise.

## Tiering pattern

When one flat threshold covers groups spanning orders of magnitude in volume, split detection three ways per environment:

| Monitor | Scope | Fires on |
|---|---|---|
| Floor (modified in place) | groups whose volume is steady enough | `sum(last_60m) < N` |
| No Matched Events — active | every group that normally reports hourly | 2h of no data |
| No Matched Events — sparse | sparse groups, plus anything not yet tiered | 14h of no data |

New groups land in the sparse tier via a `NOT (...)` exclusion rather than going unmonitored.

## Constraints to check before writing Terraform

- **Preserve monitor IDs.** Edit in place. Converting to `for_each`/`count` recreates the monitor: new ID, lost history and mute state, dead links in past Slack alerts.
- **Compare filters against sibling monitors in the same file.** A missing scoping tag (`aws_account`) is common and makes the monitor evaluate the wrong data.
- **`count`-guarded resources** (`count = var.enable_monitors ? 1 : 0`) have state addresses like `...name[0]`.
- **Env-parameterized single directories** mean one file serves both stg and prd; an edit reaches prd even when only stg is provisioned. Sibling `stg/` and `prd/` directories may also have inconsistent filenames (`datadog-locals.tf` vs `datadog_locals.tf`) — don't assume symmetry.
- **Interpolated queries** built with `join()` over lists are only visible fully rendered in the `terraform plan` output. Read the plan.
- Applying in a shared root module can carry **pre-existing state drift** unrelated to your change. Flag it for a conscious look rather than letting it ride silently.

## What to state in the proposal

- Sizing evidence per group: 30d min/median, and margin to the proposed threshold.
- Time-to-detect for a genuine total stop, under both the current and proposed config. A quiet monitor that catches nothing is not an improvement.
- What the proposal will **not** catch.
- Whether `renotify_interval` should change, and why. It is the amplifier, not the cause — once a monitor is calibrated it is no longer permanently alerting, so renotify becomes harmless. Recommend removing it only if the monitor will still fire legitimately and often.
- Corrected alert/runbook text if the existing text asserts a cause. A runbook that pre-blames the wrong layer actively misdirects the next triage.
