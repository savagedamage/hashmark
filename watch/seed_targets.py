#!/usr/bin/env python3
"""Seed the watch target registry from the verified corpus (data/tools.json).

Seeding baseline state matters: without it the first run treats all seven tools as "new releases" and
downloads ~500 MB to re-learn what today's build already verified.
"""
import json, os, sqlite3, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "watch", "watch.db")
PICKS = {
    "WithSecureLabs/chainsaw": "x86_64-unknown-linux-gnu",
    "Yamato-Security/hayabusa": "lin-x64-musl",
    "VirusTotal/yara-x": "x86_64-unknown-linux-gnu",
    "aquasecurity/trivy": "Linux-64bit",
    "anchore/grype": "linux_amd64",
    "Velocidex/velociraptor": "linux-amd64",
    "anchore/syft": "linux_amd64",
}
now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
con = sqlite3.connect(DB)
con.executescript(open(os.path.join(ROOT, "watch", "service.py")).read().split('SCHEMA = """')[1].split('"""')[0])
manifest = json.load(open(os.path.join(ROOT, "data", "tools.json")))
n = 0
for rec in manifest.get("tools", []):
    if rec.get("status") != "ok":
        continue
    repo = rec["repo"]
    con.execute("""INSERT INTO targets(repo,pick,title,last_tag,last_digest,last_integrity,last_check,last_reverify)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(repo) DO UPDATE SET last_tag=excluded.last_tag, last_digest=excluded.last_digest,
                     last_integrity=excluded.last_integrity, last_reverify=excluded.last_reverify""",
                (repo, PICKS.get(repo, rec.get("pick", "linux")), rec["name"], rec["tag"],
                 rec["computed_sha256"], rec["integrity_check"], now, now))
    n += 1
con.commit()
print(f"seeded {n} targets with baseline state from {manifest['generated']}")
print("integrity tiers:", {t: sum(1 for r in manifest["tools"] if r.get("integrity_check") == t) for t in
                           {r.get("integrity_check") for r in manifest["tools"]}})
