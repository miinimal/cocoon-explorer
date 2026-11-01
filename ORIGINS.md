# Origins

Independent work on Telegram's Cocoon network by **Aleksandr Shcherbakov** ([@miinimal](https://github.com/miinimal),
Telegram [@miinimal](https://t.me/miinimal)), founder of [MINIMALCULT](https://t.me/minimalcult). Dates are UTC; every
item is backed by a commit in this repository or a transaction on the TON blockchain.

| Date | Milestone |
|---|---|
| 2026-10-31 | Full review of the Cocoon code base, contracts and all public third-party clients; published findings. |
| 2026-10-31 | **Cocoon Explorer** — first public map of the network read directly from the root contract: proxies, allowlisted image/model hashes, pricing, escrow, monthly deposits and payouts, admin timeline. Rebuilt hourly. |
| 2026-11-01 | **First independent RA-TLS attestation check of a Cocoon proxy**: Intel TDX quote v4 parsed, report data bound to the TLS key (SHA-512), image hash `2bdd8214…` confirmed on the root allowlist; expired proxy TLS certificate (since 2026-10-02) reported. Public clients skip this check. |
| 2026-11-01 | Live proxy probe (TCP → proof-of-work → TLS 1.3 → `client.connectToProxy`) without payment or registration. |
| 2026-11-01 | Root cause and fix for funded Cocoon wallets stuck `uninit` with gocoon v0.3.0: emulated-first deploy tool (`tools/deploy_wallet.py`); lite-server list replaced with the official TON config. |
| 2026-11-01 | MINIMALCULT client channel registered on mainnet (15 TON stake); finding: **0 live workers** advertised by the proxy (`no ready model workers advertised by proxy`). |
| 2026-11-01 | `cocoon-up` — one-command Cocoon client installer with the known traps fixed; connection guide in English and Russian ([CONNECT.md](CONNECT.md)). |
| 2026-11-01 | Signed AI verdicts for TON smart contracts (oracle prototype) and a resolver contract verified in the TON sandbox (MINIMALAI, private). |
