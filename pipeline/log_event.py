#!/usr/bin/env python3
"""Record funnel events (requests, drops published, payments) into tracker/tracker.json."""
from __future__ import annotations
import json, os, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKER = os.path.join(ROOT, "tracker", "tracker.json")


def main(argv):
    if len(argv) < 2:
        print("usage: log_event.py <kind> <detail> [amount]")
        return 2
    kind, detail = argv[0], argv[1]
    amount = float(argv[2]) if len(argv) > 2 else None
    try:
        with open(TRACKER) as fh:
            t = json.load(fh)
    except Exception:
        t = {"events": [], "state": {}, "stats": {}}
    os.makedirs(os.path.dirname(TRACKER), exist_ok=True)
    t.setdefault("events", []).append({
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "kind": kind, "detail": detail, "amount": amount,
    })
    s = t.setdefault("stats", {})
    if kind == "corpus-request":
        s["corpus_requests"] = s.get("corpus_requests", 0) + 1
    if kind == "payment":
        s["payments"] = s.get("payments", 0) + 1
        s["revenue"] = round(s.get("revenue", 0) + (amount or 0), 2)
    if kind == "drop-published":
        s["drops_published"] = s.get("drops_published", 0) + 1
    if kind == "digest-drift":
        s["drift_events"] = s.get("drift_events", 0) + 1
    # counters must always be derivable from the event log, so recompute rather than trust the counter
    derived = {}
    for e in t.get("events", []):
        k = {"drop-published": "drops_published", "corpus-request": "corpus_requests",
             "digest-drift": "drift_events", "payment": "payments"}.get(e.get("kind"))
        if k:
            derived[k] = derived.get(k, 0) + 1
    for k, v in derived.items():
        s[k] = v
    with open(TRACKER, "w") as fh:
        json.dump(t, fh, indent=1)
    print(f"logged {kind}: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
