# Blockers — what stands between this and the first payment

Recorded 2026-09-19. Everything not listed here is built and runnable on this host.

## B1 — Publish destination (capability: credential/account)

A Telegram channel is the distribution surface. **A bot cannot create a channel** — Telegram's API requires a
user account (phone + OTP) to create one, and the only MTProto CLI installed here (`tg-mtproto-cli`) is
read-only by design with no session configured. The bot tokens present on this host
(`TELEGRAM_BOT_TOKEN`, `CAR_BOT_TOKEN`, `MAID_BOT_TOKEN`) can *post to* a channel where they are admins, and
can serve checkout, but they cannot create or own the channel.

**Unblock (one human action, ~60 seconds):** create a channel, add the bot as an admin with post rights, and
hand back the `@username`. Nothing else is needed — the pipeline, drops, corpus and site are done.

*Fallback that needs nothing:* ship the drops as a public GitHub repo + Pages site only (already done in this
build). Slower distribution, but it converts without Telegram.

## B2 — Payment destination (capability: credential)

No Tron/TRX address, no wallet file, no x402 paywall config, no Stars payout account exists anywhere on this
host (checked: `~/.hermes/.env` keys, skills, project configs). The standing rail is crypto/Tron with no
Stripe, so the receiving address is a hard input.

**Unblock:** a TRC-20 address (USDT/TRX) to receive to, or approval to sell via Telegram Stars on one of the
existing bots (Stars payout requires the bot owner's account, so this is also your action).

## B3 — Not a blocker, but a dependency

Cold-start distribution. The incumbent network grew on cross-promo inside a ~80K-subscriber mesh that already
existed. Standing up from zero has no such mesh, so the launch plan front-loads directory listings, GitHub
discovery and adjacent-channel cross-promo rather than assuming reach.
