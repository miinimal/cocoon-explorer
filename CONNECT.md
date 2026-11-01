# Connect to Cocoon (Telegram's confidential AI network) — the working way, November 2026

*Русская версия ниже.*

Cocoon runs AI models inside Intel TDX enclaves and settles payments in TON. There is no hosted API and no Docker
client from the Cocoon team yet; to use the network you run a client that holds a payment channel with a Cocoon
proxy. This guide is what actually worked for us, including the traps.

## One command

```bash
curl -sL https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/cocoon-up.sh | bash
```

1. First run: installs `gocoon` v0.3.0 (checksum verified), creates a Cocoon wallet, prints the address to fund.
2. Send **20 TON** to the printed `UQ…` address (15 TON is a refundable stake, ~1.7 TON gas, the rest is budget).
3. Run the same command again: it deploys the wallet, registers your channel on-chain and starts the client as a
   systemd service with an OpenAI-compatible endpoint at `http://127.0.0.1:10000/v1`.

## What you should know before paying

| Fact (checked 2026-11-01) | Source |
|---|---|
| Root contract `EQCns7bY…U73k`, 1 registered proxy (`91.108.4.11`) | on-chain, see the [map](https://miinimal.github.io/cocoon-explorer/) |
| Minimum client stake 15 TON, refund delay 12 h after closing | root `get_cur_params` |
| Price: 20 nanoTON per token; completion ×8, cached ×0.1 | root parameters |
| Only model: `Qwen/Qwen3-32B` | proxy |
| **Live workers on 2026-11-01: 0** — requests fail with `no ready model workers advertised by proxy` | our client |
| Proxy runs in Intel TDX, image hash on the root allowlist; its TLS certificate expired on 2026-10-02 | our probe |

## Traps we hit and how the script avoids them

- **Funded wallet stays `uninit`.** gocoon sends deploy + register in one external message; on our setup it never
  landed. The script deploys the wallet first with a plain signed message, emulated before broadcast
  (`tools/deploy_wallet.py`).
- **Messages silently dropped.** The bundled lite-server list accepted reads but lost outgoing messages. The script
  switches to `https://ton.org/global.config.json` (backup kept as `ton-config.bak`).
- **Tonkeeper ignores `init=` in `ton://transfer` links** — you cannot deploy the wallet from a wallet app link.
- **Attestation is not checked by any public client** (`InsecureSkipVerify` / `SKIP_PROXY_HASH`). The map verifies
  the proxy's TDX quote independently every hour; Intel DCAP signature verification is the next step.
- **Your keys:** `/root/cocoon/gocoon-data/wallet.json` holds the node key and a 24-word owner mnemonic. The owner
  can always withdraw everything from the Cocoon wallet (op `w` in `cocoon_wallet.fc`), even if the node key path fails.

## Get your TON back

```bash
gocoon channel close            # starts the 12 h refund delay
gocoon wallet withdraw -wallet /root/cocoon/gocoon-data/wallet.json -config /root/cocoon/gocoon-data/client-config.json -to <your TON address>
```

---

# Как подключиться к Cocoon — рабочий способ, ноябрь 2026

Cocoon запускает модели ИИ внутри Intel TDX и рассчитывается в TON. Готового API и Docker-клиента от команды
Cocoon пока нет: чтобы пользоваться сетью, нужен свой клиент с платёжным каналом к прокси Cocoon.

## Одна команда

```bash
curl -sL https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/cocoon-up.sh | bash
```

1. Первый запуск ставит `gocoon` v0.3.0 (с проверкой контрольной суммы), создаёт кошелёк и печатает адрес для пополнения.
2. Отправьте **20 TON** на напечатанный адрес `UQ…`: 15 TON — возвратный стейк, около 1.7 TON — газ, остальное — бюджет на запросы.
3. Запустите команду ещё раз: она развернёт кошелёк, зарегистрирует канал и запустит клиент как службу.
   Адрес в формате OpenAI: `http://127.0.0.1:10000/v1`.

## Что важно знать до оплаты

- На 01.11.2026 у сети **0 живых воркеров**: запросы возвращают `no ready model workers advertised by proxy`.
- Один прокси, одна модель (`Qwen/Qwen3-32B`), стейк 15 TON возвращается через 12 часов после закрытия канала.
- Прокси работает в Intel TDX, его образ одобрен корневым контрактом; TLS-сертификат прокси просрочен с 02.10.2026.

## Ловушки, которые скрипт обходит

- Пополненный кошелёк остаётся `uninit` — скрипт разворачивает его отдельным подписанным сообщением с предварительной эмуляцией.
- Встроенный список серверов TON теряет исходящие сообщения — скрипт переключает на официальный `ton.org/global.config.json`.
- Tonkeeper игнорирует параметр `init=` в ссылках `ton://transfer`.
- Ни один публичный клиент не проверяет аттестацию TEE — карта проверяет её независимо каждый час.

Сделано MINIMALCULT · [t.me/minimalcult](https://t.me/minimalcult) · [карта сети](https://miinimal.github.io/cocoon-explorer/)
