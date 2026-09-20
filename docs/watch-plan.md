# HASHMARK WATCH — the recurring product ($100 target)

**Date:** 2026-09-19 · **State:** service built and proven end-to-end; delivery verified by readback; two
credential gates remain (below), neither of which blocks the build.

## 1. Where the existing business was lacking

HASHMARK Drops is a **one-off**: a $19 corpus, no recurring rail, no push delivery, no per-customer data, no
retention loop, and therefore no asset value — an unmonetised audience is worth less than one with cash flow,
and a one-off sale carries no MRR multiple at resale. The free archive was doing the marketing but nothing was
compounding. WATCH is that compounding half: the same verification engine, turned into a subscription with a
push hook and per-customer configuration.

## 2. What the market actually pays (researched, with sources)

| Fact | Number | Source |
|---|---|---|
| Stars payout per Star (desktop/web) | ~$0.013 (~$13 / 1,000) | ExitBid bot-monetization 2026 |
| Stars payout inside iOS/Android | ~$0.009 (app stores take 30%) | ExitBid |
| Effective commission | 3–4% desktop, ~32% mobile + ~2–3% Fragment spread | ExitBid |
| Stars withdrawal floor / hold | 1,000 Stars minimum, **21-day hold**, cash-out via Fragment | GramBase, Tribute |
| Typical paid-channel price | 200–1,500 Stars/mo; entertainment caps ~150, trading ~1,200, high-utility 2,000+ | TeleSuite pricing guide 2026 |
| Subscription-bot potential | $500–$10,000/mo; real example 180 subs × $25 = $4,500 MRR | AziqDev bot monetization |
| Conversion from a warmed free list | 15–30% after 2–4 weeks of free value | AziqDev |
| SaaS-bot ceiling | $29–$199/user/mo, stickiest model | AziqDev, ExitBid |
| Resale value | recurring bots are valued on an MRR multiple; popular-but-unmonetised bots are not | ExitBid |

**Our price sits deliberately low** ($8/mo ≈ 500 Stars ≈ $6.50 net) because the niche is utility, not trading
signals — but it clears the 1,000-Star withdrawal floor with two subscribers.

## 3. The wedge nobody else occupies

Everyone alerts on *new releases*. Nobody alerts on **the bytes changing under an unchanged tag** — and we
observed that happening three times in one afternoon (trivy `v0.74.0`, grype `v0.119.0`, syft `v1.52.0`), each
verified by independent re-fetch. Dependabot and Renovate track *your* dependency manifests; cosign/Sigstore
verify signatures at *your* build time; GitHub's immutable-releases work reduces part of the problem for
releases that opt in. The gap that remains: the asset you already fetched is not necessarily the asset you will
fetch tomorrow, and nothing in a normal toolchain notices. That is the product.

**Risk, stated plainly:** if release immutability becomes universal, one alert class shrinks. Mitigation is
built in — a private watchlist covers things GitHub never sees (internal mirrors, vendor portals, your own
container images and SBOMs), which is also the higher-margin tier.

## 4. The offer

| Tier | Price | What they get |
|---|---|---|
| Free | 0 | public feed (`feeds/alerts.json`, `feeds/alerts.xml`) — real alerts, delayed |
| **WATCH** | **$8/mo or 500 Stars** | push alerts for the tracked tool set: new release + digest drift + verification failure, with the hash and the verification tier |
| **TEAM** | **$49/mo** | private watchlist (your images, SBOMs, internal tools), webhook into CI, verification record for audit |

**$100 path:** 13 × $8 = $104/mo, or 2 × $49 + 1 × $8 = $106/mo. The team tier reaches it with three customers
instead of thirteen — that is the planned primary sale, with the individual tier as the volume channel.

**Honest cash timing:** Stars earnings are held 21 days and need 1,000 Stars before withdrawal, so even a
same-week sale cashes out weeks later. First money is realistically 4–7 weeks from the rail going live.

## 5. What is built (and proven)

- `watch/service.py` — SQLite store (subscribers/targets/subscriptions/alerts/deliveries/payments), verification
  by vendor signature → vendor checksum → honest hash record, alert renderer, delivery adapters
  (Telegram push, webhook), payment record-keeping, and the public feed generator.
- `watch/seed_targets.py` — seeds baseline state from the verified corpus so the first run doesn't re-download
  500 MB to relearn today's facts.
- `watch/config.json` — rails as adapters: empty TRC-20 address or `telegram.enabled=false` disables that rail
  without breaking verification, feeding or logging.
- **End-to-end test passed:** synthetic digest tamper on chainsaw → `[drift]` detected → alert delivered to a
  live webhook sink → verified by reading the sink back. Test alert reclassified to `audience='test'` so it can
  never reach the public feed; tampered state restored.
- **Public feed live with three real observations** (the trivy/grype/syft drift), published as JSON + RSS.

## 6. Distribution — the actual constraint

A subscription converts at 15–30% of a *warmed* list, and we start at zero list. So the order is: publish the
drift finding as a public writeup (the wedge explains itself), point it at the free feed, let the drops repo
and directory footprint carry it, then convert readers to WATCH with a two-week free trial on their own
watchlist. No pods, no purchased members, no reposted outrage.

## 7. Gates (unchanged, and only one is genuinely blocking)

1. **Payment rail — blocking.** A TRC-20 address, or approval to sell Stars on a named bot (payout settles to
   the bot owner via Fragment). Nothing can be collected without one of these; both are your action.
2. **Delivery bot — soft.** The Telegram adapter reads `TELEGRAM_BOT_TOKEN` and is `enabled:false` until you
   say which bot may carry this product. Webhook delivery works today and is the CI/team channel anyway.
