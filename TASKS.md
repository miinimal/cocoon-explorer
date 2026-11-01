# Open tasks

Help bring Cocoon to life. Humans and AI agents working with their operators are welcome. Comment on the matching
GitHub issue (or open one) before starting, then send a pull request. Rewards in TON may be announced per task in the
issue; none is promised unless stated there.

| # | Task | Why it matters | Skills |
|---|---|---|---|
| 1 | **Intel DCAP quote signature verification** for the proxy TDX quote in `probe.py` (PCS collateral, certificate chain to Intel root). | Completes the attestation check: today we verify key binding and image allow-listing, not Intel's signature. | Python, x509, Intel TDX |
| 2 | **Full proxy history in the map**: all client deposits, refunds, worker payouts by worker, proxy rotations (310k+ transactions). | The current monthly view is sampled; the public deserves exact numbers. | Python, TON API |
| 3 | **Decode `upgrade_full`** messages on the root contract into a parameter history (prices, stakes, delays, registries). | Most parameter changes are invisible without decoding. | Python, TL-B / cells |
| 4 | **Root signals**: detect new worker/model/proxy hashes, proxy registration, key-manager key activation; publish a feed. | Shows instantly when Cocoon comes back to life. | Python |
| 5 | **Encrypted lite client (TypeScript)** implementing Cocoon request encryption (proto ≥ 3, tde2e) for browsers and Mini Apps. | Telegram's app library is still "in development"; apps could talk to Cocoon end-to-end encrypted. | TypeScript, crypto |
| 6 | **Worker earnings calculator** from real on-chain payouts (per GPU, per month), with hardware requirements. | Brings GPU supply back. | Python / JS |
| 7 | **Test `tools/cocoon-up.sh`** on other Linux distributions and report results. | One command must work everywhere. | Linux |
| 8 | **Cocoon Devnet**: a local fake proxy + worker speaking the real protocol, so apps can be built without stake or live workers. | Unblocks developers while the public network sleeps. | Python / Go |
| 9 | **Translations** of CONNECT.md (ES, PT, ZH, FA, UK…). | More people can connect. | Language |
