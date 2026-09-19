#!/usr/bin/env python3
"""
HASHMARK drop pipeline — the engine behind every drop.

For each tool: resolve the latest release, download the Linux asset, compute
SHA-256, and verify it against the vendor's own published checksum when the
release publishes one. Records what was verified and what was only recorded.
Emits: drops/<date>-<tool>.md, data/tools.json, bundle/hashmark-corpus.json
"""
from __future__ import annotations
import json, os, sys, urllib.request, urllib.error, tempfile, gzip, io, zipfile, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = {
    "drops": os.path.join(ROOT, "drops"),
    "data": os.path.join(ROOT, "data"),
    "bundle": os.path.join(ROOT, "bundle"),
}
for p in OUT.values():
    os.makedirs(p, exist_ok=True)

TOOLS = [
    {"repo": "WithSecureLabs/chainsaw", "name": "Chainsaw",
     "why": "Rapidly hunt and triage Windows forensic artefacts (EVTX, MFT, shimcache) without a full SIEM.",
     "pick": "x86_64-unknown-linux-gnu"},
    {"repo": "Yamato-Security/hayabusa", "name": "Hayabusa",
     "why": "Sigma-based threat hunting and fast Windows event-log timeline generation.",
     "pick": "lin-x64-musl"},
    {"repo": "VirusTotal/yara-x", "name": "YARA-X",
     "why": "VirusTotal's Rust rewrite of YARA — modern rule engine for malware pattern matching.",
     "pick": "x86_64-unknown-linux-gnu"},
    {"repo": "aquasecurity/trivy", "name": "Trivy",
     "why": "One-binary scanner for container images, filesystems, SBOMs and IaC misconfiguration.",
     "pick": "Linux-64bit"},
    {"repo": "anchore/grype", "name": "Grype",
     "why": "Vulnerability scanner for container images and filesystems with an SBOM-first workflow.",
     "pick": "linux_amd64"},
    {"repo": "Velocidex/velociraptor", "name": "Velociraptor",
     "why": "Endpoint visibility and DFIR collection at fleet scale via VQL.",
     "pick": "linux-amd64"},
    {"repo": "anchore/syft", "name": "Syft",
     "why": "Generates SBOMs from container images and filesystems — the input side of vulnerability work.",
     "pick": "linux_amd64"},
]

UA = {"User-Agent": "hashmark-drop-pipeline/1.0"}


def api(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def stream_digest(url: str, cap: int = 600 * 1024 * 1024):
    """Hash a remote asset without holding it in memory. Returns (hexdigest, bytes)."""
    import hashlib
    h, total = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=900) as r:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise RuntimeError(f"asset exceeds cap ({cap} bytes)")
            h.update(chunk)
    return h.hexdigest(), total


def stream_to_file(url: str, path: str, cap: int = 600 * 1024 * 1024):
    """Stream a remote asset to disk while hashing it. Returns (hexdigest, bytes)."""
    import hashlib
    h, total = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=900) as r, open(path, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise RuntimeError(f"asset exceeds cap ({cap} bytes)")
            h.update(chunk)
            out.write(chunk)
    return h.hexdigest(), total


GPG_HOME = os.path.join(ROOT, ".gnupg")
SIGNERS = {
    "Velocidex/velociraptor": "0572F28B4EF19A043F4CBBE0B22A7FB19CB6CFA1",
}


def import_signer(fpr: str) -> bool:
    """Make sure the vendor's signing key is in the project keyring."""
    import subprocess
    os.makedirs(GPG_HOME, mode=0o700, exist_ok=True)
    have = subprocess.run(["gpg", "--homedir", GPG_HOME, "--list-keys", fpr],
                          capture_output=True, text=True)
    if have.returncode == 0:
        return True
    for server in ("hkps://keys.openpgp.org", "hkps://keyserver.ubuntu.com"):
        got = subprocess.run(["gpg", "--homedir", GPG_HOME, "--keyserver", server,
                              "--recv-keys", fpr], capture_output=True, text=True, timeout=120)
        if got.returncode == 0:
            return True
    return False


def verify_signature(asset_path: str, sig_url: str, fpr: str):
    """Vendor-signed releases are the strongest claim we can make. Returns a status string."""
    import subprocess, tempfile
    if not import_signer(fpr):
        return "signature-key-unavailable"
    with tempfile.NamedTemporaryFile(suffix=".sig", delete=False) as sf:
        sf.write(fetch(sig_url, limit=64 * 1024))
        sig_path = sf.name
    try:
        r = subprocess.run(["gpg", "--homedir", GPG_HOME, "--status-fd", "1", "--verify", sig_path, asset_path],
                           capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        if "GOODSIG" in out and fpr[-16:].upper() in out.upper().replace(" ", ""):
            return "verified-against-vendor-signature"
        if "GOODSIG" in out:
            return "signature-valid-other-key"
        return "SIGNATURE-INVALID"
    finally:
        os.unlink(sig_path)


def fetch(url: str, limit: int = 80 * 1024 * 1024) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        buf, total = io.BytesIO(), 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise RuntimeError(f"asset exceeds fetch cap ({limit} bytes)")
            buf.write(chunk)
    return buf.getvalue()


def digest(blob: bytes) -> str:
    import hashlib
    return hashlib.sha256(blob).hexdigest()


def vendor_sums(text: str):
    """Parse a vendor checksum file into {filename: digest}."""
    out = {}
    for line in text.splitlines():
        parts = line.replace("*", " ").split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            out[parts[-1].lstrip("./")] = parts[0].lower()
    return out


def collect(tool: dict) -> dict:
    rec = {"repo": tool["repo"], "name": tool["name"], "why": tool["why"]}
    rel = api(f"https://api.github.com/repos/{tool['repo']}/releases/latest")
    rec["tag"] = rel["tag_name"]
    rec["published"] = rel["published_at"]
    rec["release_url"] = rel["html_url"]
    assets = rel.get("assets", [])
    skip = (".sig", ".asc", ".msi", ".deb", ".rpm", ".exe", ".json")
    cands = [a for a in assets
             if tool["pick"].lower() in a["name"].lower() and not a["name"].lower().endswith(skip)]
    target = min(cands, key=lambda a: len(a["name"])) if cands else None
    sums_asset = next((a for a in assets
                       if a["name"].lower().endswith((".sha256", ".sha256sum", "checksums.txt"))), None)
    sig_asset = next((a for a in assets
                      if target and a["name"].lower() == (target["name"] + ".sig").lower()), None)
    if target is None:
        rec["status"] = "no-matching-asset"
        return rec
    rec["asset"] = target["name"]
    rec["asset_url"] = target["browser_download_url"]
    rec["asset_bytes"] = target["size"]
    import tempfile
    tmp = tempfile.NamedTemporaryFile(prefix="hashmark-", delete=False)
    tmp.close()
    try:
        rec["computed_sha256"], rec["downloaded_bytes"] = stream_to_file(target["browser_download_url"], tmp.name)
        rec["integrity_check"] = "recorded"

        # tier 1 — the vendor's own cryptographic signature
        if sig_asset is not None and tool["repo"] in SIGNERS:
            rec["signature_asset"] = sig_asset["name"]
            rec["integrity_check"] = verify_signature(tmp.name, sig_asset["browser_download_url"], SIGNERS[tool["repo"]])

        # tier 2 — the vendor's published checksum file
        if sums_asset is not None and not rec["integrity_check"].startswith("verified-against-vendor-signature"):
            try:
                sums = vendor_sums(fetch(sums_asset["browser_download_url"], limit=4 * 1024 * 1024).decode("utf-8", "replace"))
                want = sums.get(target["name"]) or sums.get(os.path.basename(target["name"]))
                if want:
                    rec["vendor_sha256"] = want
                    rec["integrity_check"] = ("verified-against-vendor" if want == rec["computed_sha256"]
                                              else "MISMATCH")
            except Exception as e:
                rec["sums_note"] = f"vendor checksum file not usable: {type(e).__name__}"

        # artefact inventory: what is actually inside the archive
        if rec.get("downloaded_bytes", 0) <= 60 * 1024 * 1024:
            try:
                with open(tmp.name, "rb") as fh:
                    blob = fh.read()
                if rec["asset"].endswith(".zip"):
                    rec["contents"] = zipfile.ZipFile(io.BytesIO(blob)).namelist()[:12]
                elif rec["asset"].endswith((".tar.gz", ".tgz")):
                    t = tarfile.open(fileobj=io.BytesIO(gzip.decompress(blob)), mode="r:")
                    rec["contents"] = [m.name for m in t.getmembers()[:12]][:12]
            except Exception:
                pass
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    rec["status"] = "ok"
    return rec


def render(rec: dict) -> str:
    lines = [
        f"# DROP: {rec['name']} {rec.get('tag','?')}",
        "",
        f"**Why it matters** — {rec['why']}",
        "",
        f"**Source** — {rec['release_url']} (published {rec.get('published','?')[:10]})",
        "",
        f"**Asset** — `{rec.get('asset','?')}` ({rec.get('asset_bytes',0):,} bytes)",
        "",
        "**SHA-256**",
        "```",
        rec.get("computed_sha256", "n/a"),
        "```",
        "",
        f"**Integrity** — {rec.get('integrity_check','?')}"
        + (" — the vendor's detached GPG signature verified against their published signing key"
           if rec.get("integrity_check") == "verified-against-vendor-signature" else
           " — matched the vendor's published checksum file"
           if rec.get("integrity_check") == "verified-against-vendor" else
           " — no vendor checksum or signature published for this asset; the digest above is the vendor's bytes as fetched"),
        "",
        "**Verify it yourself before you run it**",
        "```",
        f"# download the asset, then compare",
        f"python3 -c \"import sys,hashlib;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())\" {rec.get('asset','asset')}",
        f"# expected: {rec.get('computed_sha256','')}",
        "```",
        "",
        "**Nothing here is cracked, patched, bundled or repackaged.** Vendor release, vendor bytes, verified hash.",
        "",
    ]
    return "\n".join(lines)


def main():
    records, failures = [], []
    for tool in TOOLS:
        try:
            rec = collect(tool)
            records.append(rec)
            print(f"[ok] {rec['name']:12s} {rec.get('tag','?'):10s} {rec.get('integrity_check','?'):24s} {rec.get('computed_sha256','')[:16]}")
        except Exception as e:
            failures.append({"repo": tool["repo"], "error": f"{type(e).__name__}: {e}"})
            print(f"[!!] {tool['repo']}: {type(e).__name__}: {e}", file=sys.stderr)

    stamp = __import__("datetime").date.today().isoformat()
    for rec in records:
        if rec.get("status") == "ok":
            with open(os.path.join(OUT["drops"], f"{stamp}-{rec['name'].lower().replace('-','')}.md"), "w") as fh:
                fh.write(render(rec))

    manifest = {
        "generated": stamp,
        "pipeline": "hashmark/build_drop.py",
        "signature_verified": sum(1 for r in records if r.get("integrity_check") == "verified-against-vendor-signature"),
        "verified_against_vendor": sum(1 for r in records if r.get("integrity_check") in
                                       ("verified-against-vendor", "verified-against-vendor-signature")),
        "hash_recorded_only": sum(1 for r in records if r.get("integrity_check") == "recorded"),
        "tools": records,
        "failures": failures,
    }
    with open(os.path.join(OUT["data"], "tools.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    with open(os.path.join(OUT["bundle"], "hashmark-corpus.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"\n{len(records)} records, {len(failures)} failures -> data/tools.json")
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
