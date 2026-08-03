#!/usr/bin/env python3
"""Calibrate a Datadog threshold monitor against its own baseline.

Reads a timeseries JSON (as returned by get_datadog_metric with raw_data: true)
and reports per group: point/null counts, min/median/max, breach fraction at
bucket resolution, breach fraction over reconstructed rolling windows, and the
longest consecutive breach run.

Do the arithmetic here rather than by hand. Miscounting a 288-element series is
easy and a whole verdict can rest on it.

Input JSON, either shape:
  {"series": [{"group": "<name>", "pointlist": [[ts_ms, value|null], ...]}, ...]}
  [[ts_ms, value|null], ...]

Group name is read from "group", "scope", "tag_set", or "expression".

Examples:
  calibrate.py series.json --threshold 10 --window-seconds 3600
  calibrate.py series.json --threshold 25 --direction below --rolling-agg sum --json
  cat series.json | calibrate.py --threshold 100
"""

import argparse
import json
import statistics
import sys


def load(path):
    raw = json.load(open(path)) if path else json.load(sys.stdin)

    if isinstance(raw, list):
        return [("(single series)", raw)]

    series = raw.get("series")
    if series is None:
        for key in ("data", "results"):
            if isinstance(raw.get(key), list):
                series = raw[key]
                break
    if series is None:
        sys.exit("no 'series' key and input is not a bare pointlist")

    out = []
    for i, s in enumerate(series):
        if isinstance(s, list):
            out.append((f"series[{i}]", s))
            continue
        name = None
        for key in ("group", "scope", "tag_set", "expression", "name"):
            v = s.get(key)
            if v:
                name = ",".join(v) if isinstance(v, list) else str(v)
                break
        points = s.get("pointlist") or s.get("points") or []
        out.append((name or f"series[{i}]", points))
    return out


def split(points):
    """Return (timestamps, values-with-None-preserved)."""
    ts, vals = [], []
    for p in points:
        if isinstance(p, dict):
            t, v = p.get("timestamp"), p.get("value")
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            t, v = p[0], p[1]
        else:
            continue
        ts.append(t)
        vals.append(None if v is None else float(v))
    return ts, vals


def infer_bucket(ts):
    if len(ts) < 2:
        return None
    deltas = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    if not deltas:
        return None
    return int(round(statistics.median(deltas) / 1000.0))


def breaches(v, threshold, direction):
    return v < threshold if direction == "below" else v > threshold


def rolling(vals, k, agg):
    """Windows of k consecutive buckets. Nulls already resolved to numbers."""
    if k <= 1:
        return list(vals)
    fns = {"sum": sum, "avg": lambda w: sum(w) / len(w), "max": max, "min": min}
    fn = fns[agg]
    return [fn(vals[i:i + k]) for i in range(len(vals) - k + 1)]


def longest_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def analyse(name, points, args):
    ts, vals = split(points)
    nulls = sum(1 for v in vals if v is None)
    present = [v for v in vals if v is not None]

    bucket = args.bucket_seconds or infer_bucket(ts)
    row = {
        "group": name,
        "buckets": len(vals),
        "nulls": nulls,
        "bucket_seconds": bucket,
        "null_policy": args.nulls,
    }

    if not present:
        row["note"] = "no non-null points — nothing to calibrate"
        return row

    row.update(
        min=min(present),
        median=statistics.median(present),
        max=max(present),
    )

    resolved = [(0.0 if args.nulls == "zero" else None) for _ in vals]
    resolved = [v if v is not None else resolved[i] for i, v in enumerate(vals)]
    resolved = [v for v in resolved if v is not None]

    flags = [breaches(v, args.threshold, args.direction) for v in resolved]
    row.update(
        breach_buckets=sum(flags),
        breach_total=len(flags),
        breach_fraction=round(sum(flags) / len(flags), 4) if flags else None,
        longest_breach_run=longest_run(flags),
    )

    if args.window_seconds and bucket:
        k = max(1, int(round(args.window_seconds / bucket)))
        win = rolling(resolved, k, args.rolling_agg)
        wflags = [breaches(v, args.threshold, args.direction) for v in win]
        row.update(
            rolling_k=k,
            rolling_agg=args.rolling_agg,
            rolling_windows=len(wflags),
            rolling_breaches=sum(wflags),
            rolling_breach_fraction=round(sum(wflags) / len(wflags), 4) if wflags else None,
            rolling_longest_run=longest_run(wflags),
        )
        if k == 1:
            row["rolling_note"] = "window equals bucket size — rolling is identical to buckets"

    margin = row["min"] / args.threshold if args.threshold else None
    if margin is not None:
        row["min_over_threshold"] = round(margin, 3)
        row["floor_viable"] = bool(
            row["min"] > args.threshold if args.direction == "below" else row["max"] < args.threshold
        )
    return row


def report(rows, args):
    print(f"threshold {args.direction} {args.threshold}"
          f"{f', rolling window {args.window_seconds}s ({args.rolling_agg})' if args.window_seconds else ''}"
          f", nulls treated as {args.nulls}\n")

    for r in rows:
        bucket = f"  bucket={r['bucket_seconds']}s" if r.get("bucket_seconds") else ""
        print(f"── {r['group']}")
        print(f"   buckets {r['buckets']} ({r['nulls']} null){bucket}")
        if "note" in r:
            print(f"   {r['note']}\n")
            continue
        print(f"   min {r['min']:g}   median {r['median']:g}   max {r['max']:g}")
        print(f"   breaching buckets {r['breach_buckets']}/{r['breach_total']}"
              f" ({r['breach_fraction']:.1%})   longest run {r['longest_breach_run']}")
        if "rolling_breach_fraction" in r:
            print(f"   breaching rolling windows {r['rolling_breaches']}/{r['rolling_windows']}"
                  f" ({r['rolling_breach_fraction']:.1%})   longest run {r['rolling_longest_run']}"
                  f"   k={r['rolling_k']}")
        if r.get("rolling_note"):
            print(f"   note: {r['rolling_note']}")
        print(f"   min/threshold {r['min_over_threshold']}x"
              f"   floor viable: {'yes' if r['floor_viable'] else 'NO'}")
        print()

    viable = [r for r in rows if r.get("floor_viable")]
    if len(rows) > 1:
        print(f"{len(viable)}/{len(rows)} groups can carry this threshold without false positives.")
        if viable and len(viable) < len(rows):
            print("Groups differ — a single threshold cannot serve them all. Tier them.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", help="JSON file; omit to read stdin")
    p.add_argument("--threshold", type=float, required=True)
    p.add_argument("--direction", choices=["below", "above"], default="below",
                   help="direction that constitutes a breach (default: below)")
    p.add_argument("--window-seconds", type=int,
                   help="monitor eval window; reconstructs rolling windows from buckets")
    p.add_argument("--bucket-seconds", type=int,
                   help="input resolution; inferred from timestamps if omitted")
    p.add_argument("--rolling-agg", choices=["sum", "avg", "max", "min"], default="sum",
                   help="how the monitor aggregates over its window (default: sum)")
    p.add_argument("--nulls", choices=["zero", "skip"], default="zero",
                   help="treat null buckets as 0 or exclude them (default: zero)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args()

    rows = [analyse(name, pts, args) for name, pts in load(args.input)]
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        print()
    else:
        report(rows, args)


if __name__ == "__main__":
    main()
