# AGENTS.md

Guidance for AI coding agents (and the humans who run them) working on this repository.

## What this project is
Open infrastructure for Telegram's **Cocoon** network (confidential AI inference on TON): a public network map read
from the blockchain, an independent TEE attestation checker for Cocoon proxies, a one-command client installer, and
tools that fix known client problems. Started by Aleksandr Shcherbakov (@miinimal), founder of MINIMALCULT.
Goal: make Cocoon usable, verifiable and alive for everyone — developers, GPU operators, users.

## How you can help
Pick a task from [TASKS.md](TASKS.md), discuss it with the person you work for, then open a pull request.
Every contribution is reviewed by a human maintainer before it is merged.

## Ground rules
- Work with your operator's knowledge and approval. Do not act on behalf of anyone who has not asked you to.
- Never commit secrets: wallet files, mnemonics, API keys, `.env` contents.
- Facts must be verifiable: cite the on-chain transaction, contract method, or source file you relied on.
- Do not send transactions or spend funds as part of a contribution. Tests run offline or read-only.
- Keep changes small and focused; one task per pull request.

## Repository map
- `indexer.py` — reads the Cocoon root and proxy contracts via tonapi.io and writes `data/snapshot.json`.
- `probe.py` — live proxy handshake (TCP → proof-of-work → TLS 1.3 → `client.connectToProxy`) without payment;
  parses the proxy's Intel TDX quote and checks key binding and image allow-listing.
- `build_page.py` + `template.html` — builds the self-contained map page (`dist/index.html`).
- `tools/cocoon-up.sh` — client installer; `tools/deploy_wallet.py` — deploys a funded `uninit` Cocoon wallet;
  `tools/cocoon-watch*.sh` — worker watcher with Telegram alerts.
- `CONNECT.md` — connection guide (EN/RU); `ORIGINS.md` — dated history of this work.

## Build and test
```bash
pip install pytoniq-core cryptography
python3 indexer.py --out data/snapshot.json --months 8   # network calls to tonapi.io, read-only
python3 build_page.py data/snapshot.json                  # -> dist/index.html
bash -n tools/*.sh
```
The page must render without horizontal overflow at 390 px width in light and dark themes.

## Contact
Telegram channel: https://t.me/minimalcult · GitHub: https://github.com/miinimal
