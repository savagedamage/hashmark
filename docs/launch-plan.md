# HASHMARK — 30-day launch plan and kill criteria

Owner: agent (autonomous). Human inputs required: two, both credential-gated (`docs/blockers.md`).
Kill criteria are pre-committed so the test cannot be rationalised after the fact.

## The offer

Free tier: weekly verified drop (one FOSS security/DFIR tool, vendor bytes, published SHA-256, upstream link).
Paid tier: **the verified corpus — $19 one-off** — machine-readable JSON + JSON-Schema + markdown drops,
with provenance and integrity verdicts, rebuilt on every pipeline run.

Why anyone pays for a JSON file of public information: the value is not the data, it is the *verification
work and the audit trail*. A team that has to prove "the tool we shipped in the IR kit is the vendor's
bytes, here is the digest and here is the check we ran" is buying an hour of somebody's diligence and a
schema they can validate in CI.

## Distribution, in the order it gets attempted

1. **Public repo + Pages site** (done in this build) — the archive is the marketing; every drop is indexable.
2. **Directory footprint** — list the channel/repo on the Telegram directory sites the incumbent network
   already appears on (nicegram, tlg.pm) and the DFIR tool aggregators that index GitHub topics.
3. **Cross-promo, not pods** — offer the free drop as content to adjacent DFIR/blue-team channels and
   subreddits; every ask is "publish this verified drop with a link back", which costs them nothing.
4. **Targeted outreach** — DFIR practitioners who post tool comparisons; the pitch is the verification claim,
   not a discount.
5. **Telegram channel** — the standing surface once B1 is cleared; every drop posted, corpus pinned.

## Cadence (automated)

| When | What | Mechanism |
|---|---|---|
| Weekly | Re-run pipeline → new drops + corpus rebuild | cron job `hashmark-weekly-drop` |
| Daily | Check tracked tools for new upstream releases; alert on any that shipped | cron job `hashmark-release-watch` |
| Daily | Re-verify one random tracked artefact end-to-end (digest drift check) | part of the watch job |
| Per event | Log request/verification/drop events into `tracker/tracker.json` | pipeline + manual |

## Kill criteria (evaluate day 30)

- **< 3 inbound corpus requests** after 4 drops published and 20 targeted outreach touches → the audience does
  not want the artefact. Stop; publish the negative result as a case study.
- **0 payments and 0 requests that survive one reply** → the offer reads as public data with no felt cost.
  Reprice or repackage once (e.g. per-team licence with CI validation step), then stop.
- **Any drop whose vendor checksum mismatches** → the product's core claim is broken; halt publishing, keep
  the record, and publish the mismatch as a finding. A published mismatch is worth more than a silent fix.
- **Any takedown, platform warning or legal contact** → stop immediately and hand to the human with the record.

## Success is not revenue on day 30

The honest bar for day 30 is: a working pipeline, an archive with real verified drops, at least one qualified
conversation, and a recorded conversion number. Revenue per 1,000 subscribers in this asset class is ~$1.90
(measured from the incumbent network), so the plan bets on a small, self-selected, high-intent list rather
than on reach — and the first dollar is the signal worth reporting, not the vanity subscriber count.
