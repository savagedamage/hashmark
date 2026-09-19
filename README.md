# HASHMARK — verified tool drops

**What it is:** a distribution + monetisation asset built from the one mechanic that actually worked in the
network we dissected — *file/utility posts travel*. Every drop is a vendor-release FOSS security/DFIR tool,
downloaded, SHA-256 hashed, and checked against the vendor's own published checksum before it is published.

**What it is deliberately not:** no cracked software, no patched clients, no pirate media, no bought
subscribers, no engagement pods, no harvested handles. The differentiating claim is verifiable:
*every byte we ship matches the vendor's published hash.*

## Why this shape

Measured from the incumbent network (2026-09-18): news posts on a 29,600-subscriber channel reached 426 views
(1.4%), while file/utility posts on a **657-subscriber** channel reached 2,290 — the mechanic that carries
reach is the utility post, not the reposted outrage. Monetisation on top of commodity Telegram reach is worth
~$1.90 per 1,000 subscribers per month; selling an actual artefact to a self-selected audience is worth more,
from a far smaller list.

## Live

| Surface | URL |
|---|---|
| Funnel site | https://savagedamage.github.io/hashmark/ |
| Repo (public, archive of every drop) | https://github.com/savagedamage/hashmark |
| Live corpus JSON | https://savagedamage.github.io/hashmark/data/tools.json |
| Corpus requests (the conversion event) | repo → Issues → "corpus-request" |

## Verification tiers published per tool

| Tier | Meaning | Current count |
|---|---|---|
| `verified-against-vendor-signature` | vendor's detached GPG signature checked against their published key | 1 (Velociraptor) |
| `verified-against-vendor` | digest matched the vendor's published checksum file | 3 (Trivy, Grype, Syft) |
| `recorded` | vendor publishes neither checksum nor signature — the hash of the bytes we fetched, stated plainly | 3 (Chainsaw, Hayabusa, YARA-X) |

## Finding worth keeping (from two consecutive runs)

**Digests changed at an unchanged release tag.** Trivy `v0.74.0`, Grype `v0.119.0` and Syft `v1.52.0`
produced different SHA-256 digests on two runs minutes apart while the tag stayed the same — upstream
re-uploads assets under a live tag. Re-checked independently afterwards: the current bytes match the current
record and are *not* the earlier byte stream, so this is a real change in the published artefact and not a
transient read error. Scope of the claim is exactly **"the bytes changed under an unchanged tag"** — it says
nothing about intent or malice, and a rebuilt binary is a boring explanation. Recorded in
`tracker/tracker.json` and `data/digest-history.jsonl` rather than silently overwritten. This is the whole
argument for the product in one observation: **a digest without a date and a re-check is not provenance.**

## Layout

| Path | Purpose |
|---|---|
| `pipeline/build_drop.py` | Resolve latest release → download asset → SHA-256 → verify vs vendor checksum → render drop + corpus |
| `drops/` | Publishable drop posts (free tier) |
| `bundle/hashmark-corpus.json` | The paid artefact: machine-readable verified-tool corpus |
| `bundle/schema.json` | Schema for the corpus, so consumers can validate it |
| `site/` | Public funnel (self-contained HTML, no dependencies) |
| `tracker/tracker.json` | Drop cadence, verification stats, funnel events |
| `docs/` | Launch plan, blockers, 30-day kill criteria |

## Cadence

Weekly drop (free tier) → corpus updated → corpus is the paid artefact. The pipeline is deterministic and
re-runnable: `python3 pipeline/build_drop.py`.

## Status / blockers

Two inputs are required before the first payment can be taken, and both are credential-gated (recorded in
`docs/blockers.md`): a Telegram channel to publish to (a bot cannot create one), and a payment destination
(Tron address or Telegram Stars bot) — no address exists on this host.
