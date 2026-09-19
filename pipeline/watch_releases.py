#!/usr/bin/env python3
"""
HASHMARK release watcher.

Cheap mode (default): query each tracked repo's latest release tag and diff it against the state recorded in
tracker/tracker.json. Alerts on anything that moved and logs the event.

Deep mode (--reverify N): re-download and re-hash N previously verified artefacts to catch digest drift —
a changed digest for an unchanged tag is the single most important signal this project can produce.
"""
from __future__ import annotations
import json, os, sys, random, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_JSON = os.path.join(ROOT, "data", "tools.json")
TRACKER = os.path.join(ROOT, "tracker", "tracker.json")
UA = {"User-Agent": "hashmark-release-watch/1.0"}
sys.path.insert(0, os.path.join(ROOT, "pipeline"))


def load(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1)


def latest_tag(repo: str):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest", headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.load(r)
    return d["tag_name"], d["published_at"]


def main(argv):
    deep = 0
    if "--reverify" in argv:
        deep = int(argv[argv.index("--reverify") + 1])
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    manifest = load(TOOLS_JSON, {"tools": []})
    tracker = load(TRACKER, {"events": [], "state": {}, "stats": {}})
    state, events = tracker.get("state", {}), tracker.get("events", [])

    moved = []
    for rec in manifest.get("tools", []):
        if rec.get("status") != "ok":
            continue
        repo = rec["repo"]
        try:
            tag, published = latest_tag(repo)
        except Exception as e:
            events.append({"ts": now, "kind": "watch-error", "repo": repo, "detail": f"{type(e).__name__}: {e}"})
            print(f"[!] {repo}: {type(e).__name__}")
            continue
        prev = state.get(repo, {}).get("tag")
        state[repo] = {"tag": tag, "published": published, "name": rec["name"],
                       "last_checked": now, "last_digest": rec.get("computed_sha256")}
        if prev and prev != tag:
            moved.append({"repo": repo, "name": rec["name"], "from": prev, "to": tag})
            events.append({"ts": now, "kind": "release-moved", "repo": repo, "from": prev, "to": tag})
            print(f"[moved] {rec['name']}: {prev} -> {tag}")
        elif prev is None:
            print(f"[seed]  {rec['name']}: {tag}")
        else:
            print(f"[same]  {rec['name']}: {tag}")

    drift = []
    if deep:
        from build_drop import stream_digest
        pool = [r for r in manifest.get("tools", []) if r.get("downloaded_bytes", 0) < 60 * 1024 * 1024]
        random.shuffle(pool)
        for rec in pool[:deep]:
            try:
                got, size = stream_digest(rec["asset_url"])
                ok = got == rec.get("computed_sha256")
                index = {"ts": now, "kind": "reverify", "repo": rec["repo"], "tag": rec["tag"],
                         "expected": rec.get("computed_sha256"), "got": got, "match": ok}
                events.append(index)
                if not ok:
                    drift.append(index)
                    print(f"[DRIFT] {rec['name']} {rec['tag']}: {got[:16]} != {rec.get('computed_sha256','')[:16]}")
                else:
                    print(f"[pin]   {rec['name']} {rec['tag']} re-verified")
            except Exception as e:
                events.append({"ts": now, "kind": "reverify-error", "repo": rec["repo"], "detail": f"{type(e).__name__}: {e}"})
                print(f"[!] reverify {rec['repo']}: {type(e).__name__}")

    tracker["state"] = state
    tracker["events"] = events[-500:]
    stats = tracker.setdefault("stats", {})
    stats["tracked"] = len([r for r in manifest.get("tools", []) if r.get("status") == "ok"])
    stats["checks"] = stats.get("checks", 0) + 1
    stats["drift_events"] = stats.get("drift_events", 0) + len(drift)
    stats["last_run"] = now
    save(TRACKER, tracker)
    print(f"\nwatched {stats['tracked']} tools · {len(moved)} moved · {len(drift)} digest drift · tracker updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
