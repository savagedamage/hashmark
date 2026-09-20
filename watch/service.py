#!/usr/bin/env python3
"""
HASHMARK WATCH — the recurring product.

A subscriber declares the security tools / images they depend on. The service watches upstream, verifies
what actually shipped (vendor GPG signature > vendor checksum > honest hash record), and pushes three kinds
of alert nobody else sends: a new release, a digest change under an unchanged tag, and a verification
failure. Delivery is push (Telegram bot or webhook into CI); the free tier is the public feed.

Rails are adapters so the missing credential never blocks the build:
  * stars  — Telegram Stars invoice (recurring, native; payout needs the bot owner's Fragment setup)
  * trc20  — TRC-20 invoice to an address from config (never hard-coded, never invented)

CLI:
  service.py init
  service.py add-subscriber --channel telegram|webhook --address <chat_id|url> --tier free|watch|team [--days 30]
  service.py add-target --repo owner/name --pick linux-amd64 [--kind release]
  service.py run [--reverify] [--dry-run]
  service.py list
  service.py feed            # write public JSON + RSS
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, datetime, urllib.request, urllib.error, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
DB = os.path.join(ROOT, "watch", "watch.db")
FEEDS = os.path.join(ROOT, "feeds")
CONFIG = os.path.join(ROOT, "watch", "config.json")
UA = {"User-Agent": "hashmark-watch/1.0"}
TIERS = {"free": 0, "watch": 1, "team": 2}

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY, channel TEXT NOT NULL, address TEXT NOT NULL, tier TEXT NOT NULL DEFAULT 'free',
  status TEXT NOT NULL DEFAULT 'active', created TEXT, expires TEXT, note TEXT, UNIQUE(channel, address));
CREATE TABLE IF NOT EXISTS targets (
  id INTEGER PRIMARY KEY, repo TEXT UNIQUE NOT NULL, pick TEXT NOT NULL, kind TEXT DEFAULT 'release',
  last_tag TEXT, last_digest TEXT, last_check TEXT, last_reverify TEXT, last_integrity TEXT, title TEXT);
CREATE TABLE IF NOT EXISTS subscriptions (
  subscriber_id INTEGER NOT NULL, target_id INTEGER NOT NULL, PRIMARY KEY (subscriber_id, target_id));
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY, target_id INTEGER, created TEXT, kind TEXT NOT NULL, subject TEXT, body TEXT,
  audience TEXT DEFAULT 'watch');
CREATE TABLE IF NOT EXISTS deliveries (
  id INTEGER PRIMARY KEY, alert_id INTEGER, subscriber_id INTEGER, sent TEXT, ok INTEGER, error TEXT);
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY, subscriber_id INTEGER, ts TEXT, rail TEXT, amount REAL, currency TEXT,
  reference TEXT, status TEXT);
"""


def cfg():
    if os.path.exists(CONFIG):
        with open(CONFIG) as fh:
            return json.load(fh)
    return {"rails": {"trc20": {"address": "", "price_usd": 8, "price_days": 30},
                      "stars": {"price_stars": 500, "price_days": 30}},
            "telegram": {"bot_token_env": "TELEGRAM_BOT_TOKEN", "enabled": False},
            "webhook": {"enabled": True}}


def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    return con


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def http_json(url, data=None, headers=None, timeout=60):
    body = json.dumps(data).encode() if data is not None else None
    h = dict(UA)
    if body:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        return json.loads(raw or b"{}")
    except Exception:
        return {"raw": raw[:500].decode("utf-8", "replace")}


# ---------------------------------------------------------------- verification
def inspect(repo: str, pick: str, download: bool):
    """Resolve the latest release; optionally download and verify it. Returns a dict."""
    from build_drop import stream_to_file, verify_signature, vendor_sums, fetch, SIGNERS  # noqa
    import tempfile
    rel = http_json(f"https://api.github.com/repos/{repo}/releases/latest")
    out = {"repo": repo, "tag": rel.get("tag_name"), "published": rel.get("published_at"),
           "title": rel.get("name") or rel.get("tag_name"), "digest": None, "integrity": None,
           "notes": (rel.get("body") or "")[:1200]}
    if not download:
        return out
    assets = rel.get("assets") or []
    skip = (".sig", ".asc", ".msi", ".deb", ".rpm", ".exe", ".json")
    cands = [a for a in assets if pick.lower() in a["name"].lower() and not a["name"].lower().endswith(skip)]
    if not cands:
        out["integrity"] = "no-matching-asset"
        return out
    target = min(cands, key=lambda a: len(a["name"]))
    sig = next((a for a in assets if a["name"].lower() == (target["name"] + ".sig").lower()), None)
    sums = next((a for a in assets if a["name"].lower().endswith((".sha256", ".sha256sum", "checksums.txt"))), None)
    out["asset"] = target["name"]
    out["asset_url"] = target["browser_download_url"]
    out["asset_bytes"] = target["size"]
    tmp = tempfile.NamedTemporaryFile(prefix="hmwatch-", delete=False)
    tmp.close()
    try:
        digest, size = stream_to_file(target["browser_download_url"], tmp.name)
        out["digest"], out["downloaded_bytes"] = digest, size
        out["integrity"] = "recorded"
        if sig is not None and repo in SIGNERS:
            out["integrity"] = verify_signature(tmp.name, sig["browser_download_url"], SIGNERS[repo])
        if sums is not None and not str(out["integrity"]).startswith("verified-against-vendor-signature"):
            try:
                want = vendor_sums(fetch(sums["browser_download_url"], limit=4 << 20).decode("utf-8", "replace"))
                w = want.get(target["name"]) or want.get(os.path.basename(target["name"]))
                if w:
                    out["integrity"] = "verified-against-vendor" if w == digest else "MISMATCH"
            except Exception:
                pass
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- alert rendering
def render(kind, info, target):
    name = target["title"] or info.get("title") or info["repo"]
    if kind == "release":
        body = (f"<b>{html.escape(name)} {html.escape(info['tag'])}</b>\n"
                f"Verified: {html.escape(str(info.get('integrity')))}"
                f"{' · ' + str(info.get('asset_bytes')) + ' bytes' if info.get('asset_bytes') else ''}\n"
                f"SHA-256: <code>{(info.get('digest') or 'not downloaded')[:32]}</code>\n"
                f"{html.escape(info.get('repo',''))} · released {str(info.get('published'))[:10]}")
        return body
    if kind == "drift":
        body = (f"<b>⚠ DIGEST CHANGED — {html.escape(name)} {html.escape(info['tag'])}</b>\n"
                f"Same tag, different bytes. This is the failure mode a tag or RSS feed cannot see.\n"
                f"was: <code>{html.escape(str(info.get('was'))[:32])}</code>\n"
                f"now: <code>{html.escape(str(info.get('digest'))[:32])}</code>\n"
                f"{html.escape(info.get('repo',''))} · scope: bytes changed, intent not assessed")
        return body
    body = (f"<b>⚠ VERIFICATION FAILED — {html.escape(name)} {html.escape(str(info.get('tag')))}</b>\n"
            f"integrity: {html.escape(str(info.get('integrity')))}\n"
            f"Treat this release as unverified until it clears. {html.escape(info.get('repo',''))}")
    return body


# ---------------------------------------------------------------- delivery
def deliver(con, alert_id, kind, subject, body, repo):
    rows = con.execute("""
        SELECT s.id, s.channel, s.address, s.tier FROM subscribers s
        WHERE s.status='active' AND s.tier IN ('watch','team')
          AND (s.channel='webhook' OR s.tier IN ('watch','team'))
        ORDER BY s.id""").fetchall()
    cfgd = cfg()
    sent = 0
    for sid, channel, address, tier in rows:
        try:
            if channel == "telegram":
                if not cfgd["telegram"].get("enabled"):
                    raise RuntimeError("telegram rail disabled in config")
                token = os.environ.get(cfgd["telegram"]["bot_token_env"], "")
                if not token:
                    raise RuntimeError("bot token env not set")
                http_json(f"https://api.telegram.org/bot{token}/sendMessage",
                          {"chat_id": address, "text": body, "parse_mode": "HTML",
                           "disable_web_page_preview": True})
            elif channel == "webhook":
                http_json(address, {"kind": kind, "subject": subject, "repo": repo, "text": body.strip()})
            else:
                raise RuntimeError(f"unknown channel {channel}")
            con.execute("INSERT INTO deliveries(alert_id,subscriber_id,sent,ok,error) VALUES(?,?,?,?,?)",
                        (alert_id, sid, now(), 1, None))
            sent += 1
        except Exception as e:
            con.execute("INSERT INTO deliveries(alert_id,subscriber_id,sent,ok,error) VALUES(?,?,?,?,?)",
                        (alert_id, sid, now(), 0, f"{type(e).__name__}: {e}"))
    con.commit()
    return sent


# ---------------------------------------------------------------- core run
def run(reverify=False, dry=False):
    con = db()
    targets = con.execute("SELECT id,repo,pick,kind,last_tag,last_digest,last_reverify,title FROM targets").fetchall()
    alerts = 0
    for tid, repo, pick, kind, last_tag, last_digest, last_reverify, title in targets:
        tgt = {"id": tid, "repo": repo, "title": title}
        try:
            info = inspect(repo, pick, download=False)
        except Exception as e:
            print(f"[!] {repo}: {type(e).__name__}: {e}")
            continue
        moved = info["tag"] and info["tag"] != last_tag
        stale = (last_reverify is None or
                 (datetime.datetime.fromisoformat(now()) - datetime.datetime.fromisoformat(last_reverify)).days >= 7)
        if not moved and not (reverify and stale):
            con.execute("UPDATE targets SET last_check=? WHERE id=?", (now(), tid))
            print(f"[same]  {repo} {info['tag']}")
            continue
        info = inspect(repo, pick, download=True)
        detail = "release" if moved else "drift"
        integrity = str(info.get("integrity"))
        if integrity in ("MISMATCH", "SIGNATURE-INVALID"):
            detail = "integrity-failure"
        elif not moved and last_digest and info.get("digest") and info["digest"] != last_digest:
            detail = "drift"
            info["was"] = last_digest
        elif not moved:
            print(f"[pin]   {repo} {info['tag']} unchanged bytes — re-verified")
            con.execute("UPDATE targets SET last_reverify=?, last_check=? WHERE id=?", (now(), now(), tid))
            con.commit()
            continue
        subject = f"{detail}: {repo} {info.get('tag')}"
        body = render({"release": "release", "drift": "drift", "integrity-failure": "fail"}[detail], info, tgt)
        cur = con.execute("INSERT INTO alerts(target_id,created,kind,subject,body,audience) VALUES(?,?,?,?,?,?)",
                          (tid, now(), detail, subject, body, "watch"))
        con.execute("UPDATE targets SET last_tag=?, last_digest=?, last_integrity=?, last_check=?, last_reverify=? WHERE id=?",
                    (info.get("tag"), info.get("digest"), integrity, now(), now(), tid))
        con.commit()
        alerts += 1
        print(f"[{detail}] {repo} {info.get('tag')} integrity={integrity}")
        if not dry:
            n = deliver(con, cur.lastrowid, detail, subject, body, repo)
            print(f"         delivered to {n} subscriber(s)")
    if not dry:
        feed(con)
    con.close()
    return alerts


# ---------------------------------------------------------------- public feed (free tier + marketing)
def feed(con=None):
    own = con is None
    con = con or db()
    os.makedirs(FEEDS, exist_ok=True)
    items = con.execute("""
        SELECT a.created, a.kind, a.subject, a.body, t.repo, t.title FROM alerts a
        JOIN targets t ON t.id=a.target_id WHERE a.audience='watch'
        ORDER BY a.id DESC LIMIT 100""").fetchall()
    out = [{"ts": c, "kind": k, "subject": s, "repo": r, "title": t} for c, k, s, b, r, t in items]
    with open(os.path.join(FEEDS, "alerts.json"), "w") as fh:
        json.dump({"generated": now(), "count": len(out), "alerts": out}, fh, indent=1)
    esc = html.escape
    rss = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           '<title>HASHMARK WATCH — verification alerts</title>',
           '<link>https://savagedamage.github.io/hashmark/</link>',
           '<description>Verified release, digest-drift and verification-failure alerts for tracked security tooling.</description>']
    for c, k, s, b, r, t in items[:50]:
        rss.append(f"<item><title>{esc(s)}</title><pubDate>{esc(c)}</pubDate>"
                   f"<guid isPermaLink=\"false\">{esc(s)}-{esc(c)}</guid>"
                   f"<description>{esc(' '.join((b or '').split()))[:500]}</description></item>")
    rss.append("</channel></rss>")
    with open(os.path.join(FEEDS, "alerts.xml"), "w") as fh:
        fh.write("\n".join(rss))
    if own:
        con.close()
    print(f"feed: {len(out)} alerts -> feeds/alerts.json + feeds/alerts.xml")
    return out


def cli():
    ap = argparse.ArgumentParser(prog="hashmark-watch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    a = sub.add_parser("add-subscriber"); a.add_argument("--channel", required=True)
    a.add_argument("--address", required=True); a.add_argument("--tier", default="free")
    a.add_argument("--days", type=int, default=30); a.add_argument("--note", default=None)
    b = sub.add_parser("add-target"); b.add_argument("--repo", required=True)
    b.add_argument("--pick", required=True); b.add_argument("--title", default=None)
    c = sub.add_parser("run"); c.add_argument("--reverify", action="store_true"); c.add_argument("--dry-run", action="store_true")
    sub.add_parser("feed"); sub.add_parser("list")
    d = sub.add_parser("payment"); d.add_argument("--subscriber", type=int, required=True)
    d.add_argument("--rail", required=True); d.add_argument("--amount", type=float, required=True)
    d.add_argument("--currency", default="USDT"); d.add_argument("--reference", default="")
    args = ap.parse_args()
    con = db()

    if args.cmd == "init":
        con.commit(); print(f"db ready: {DB}")
    elif args.cmd == "add-subscriber":
        exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=args.days)).isoformat(timespec="seconds")
        con.execute("""INSERT INTO subscribers(channel,address,tier,status,created,expires,note)
                       VALUES(?,?,?,'active',?,?,?)
                       ON CONFLICT(channel,address) DO UPDATE SET tier=excluded.tier, expires=excluded.expires""",
                    (args.channel, args.address, args.tier, now(), exp, args.note))
        con.commit(); print(f"subscriber {args.channel}:{args.address} tier={args.tier} until {exp[:10]}")
    elif args.cmd == "add-target":
        con.execute("""INSERT INTO targets(repo,pick,title,last_check) VALUES(?,?,?,?)
                       ON CONFLICT(repo) DO UPDATE SET pick=excluded.pick, title=excluded.title""",
                    (args.repo, args.pick, args.title or args.repo.split("/")[-1], now()))
        con.commit(); print(f"target {args.repo} ({args.pick})")
    elif args.cmd == "run":
        n = run(reverify=args.reverify, dry=args.dry_run); print(f"{n} alert(s)")
    elif args.cmd == "feed":
        feed(con)
    elif args.cmd == "payment":
        con.execute("INSERT INTO payments(subscriber_id,ts,rail,amount,currency,reference,status) VALUES(?,?,?,?,?,?,'observed')",
                    (args.subscriber, now(), args.rail, args.amount, args.currency, args.reference))
        con.execute("UPDATE subscribers SET tier='watch', expires=? WHERE id=?",
                    ((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat(timespec="seconds"), args.subscriber))
        con.commit(); print(f"payment recorded for subscriber {args.subscriber}")
    elif args.cmd == "list":
        print("subscribers:")
        for r in con.execute("SELECT id,channel,address,tier,status,expires FROM subscribers"):
            print("  ", r)
        print("targets:")
        for r in con.execute("SELECT id,repo,pick,last_tag,last_integrity FROM targets"):
            print("  ", r)
        n = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        d = con.execute("SELECT COUNT(*), SUM(ok) FROM deliveries").fetchone()
        print(f"alerts: {n} · deliveries: {d[0]} (ok={d[1] or 0})")
    con.close()


if __name__ == "__main__":
    cli()
