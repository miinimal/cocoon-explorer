# Cocoon Explorer

Live, open map of Telegram's **Cocoon** confidential AI network on TON — read directly from the blockchain. No keys, no stake, no affiliation with Telegram or Cocoon.

Shows: registered proxies, allowed image/model hashes, on-chain pricing, proxy escrow balance, monthly client deposits and worker payouts, root-contract admin timeline.

Built by **Aleksandr Shcherbakov** ([@miinimal](https://github.com/miinimal), founder of [MINIMALCULT](https://t.me/minimalcult)). Part of the MINIMALAI project. See [ORIGINS.md](ORIGINS.md).

## Connect your own server to Cocoon

One command, traps included — see **[CONNECT.md](CONNECT.md)** (EN/RU):

```bash
curl -sL https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/cocoon-up.sh | bash
```

Tools: `tools/cocoon-up.sh` (client installer), `tools/deploy_wallet.py` (deploy a funded `uninit` Cocoon wallet),
`tools/cocoon-watch-install.sh` (hourly Telegram alert when live workers appear or disappear).

## Open letter to the Cocoon team

What we observe on the public network and what we asked the team: [LETTER.md](LETTER.md).

## Help build it

Open tasks for humans and AI agents (working with their operators): **[TASKS.md](TASKS.md)** · agent guide: **[AGENTS.md](AGENTS.md)** · summary for LLMs: **[llms.txt](llms.txt)**.

## Run locally

```bash
pip install pytoniq-core
python3 indexer.py --out data/snapshot.json   # reads tonapi.io
python3 build_page.py data/snapshot.json      # -> dist/index.html (self-contained)
```

The page rebuilds itself hourly via GitHub Actions and is published with GitHub Pages.

## Contracts (mainnet)

- Root: `EQCns7bYSp0igFvS1wpb5wsZjCKCV19MD5AVzI4EyxsnU73k`
- Proxy: `EQDGkQM7RIWp6yGW79i8oV3zJ-vdnpV68pdZ2W8mrpE3cJ2y`
- ABI: ton-blockchain/abis `data/cocoon`

License: MIT.
