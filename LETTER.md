# Open letter to the Cocoon team

Written on 1 November 2026. Email route: security@telegram.org (new issues in TelegramMessenger/cocoon are currently restricted).
Published here so that anyone can check the facts. All figures are read from the TON chain or from the code.

**Subject: Cocoon public network — independent observations, two fund/security issues, and an offer to help**

Hello Cocoon team,

We are MINIMALCULT, a small team building open tooling around Cocoon. Over the past days we built an independent
explorer of the network (https://miinimal.github.io/cocoon-explorer, rebuilt hourly from the chain, code:
https://github.com/miinimal/cocoon-explorer), a client-side attestation check of the proxy, a one-command client
installer, and an OpenAI-compatible gateway with signed receipts. We registered as a client ourselves (15 TON stake).

What we observe on the public network today:

1. **Client refunds appear to have no working path.** Issue #77 (opened 2 Sep 2026, no reply yet) describes a
   15 TON stake stranded after contract close: the refund request is forwarded with 1 nanoTON and skipped by the proxy
   (`cskip_no_gas`), and the proxy-side `refund_granted` / `refund_force` handlers are empty. If this is right, every
   client who closes a contract may lose their stake. We are keeping ours open for that reason.
2. **The proxy's TLS certificate at 91.108.4.11:8888 expired on 2 October 2026.** The TDX quote, image hash and
   on-chain allow-list still verify, so this is not a confidentiality break, but strict clients will fail the handshake.
3. **The public side is idle.** Proxy heartbeats stopped on 29 September; the last worker payout was 17 August; there
   are zero live workers. Over its life the network served 95 clients, 8,692 TON in, 6,514 TON paid to 7 worker owners.

What we would like to ask:

- Is the public network still supported, and is there a roadmap we can align with?
- Could issue #77 be acknowledged, and could stranded stakes be released with the signed grant?
- Is there an onboarding contact for GPU operators? We are ready to help operators bring workers back online
  (we already maintain a one-command client installer and can do the same for workers).
- Would you be open to linking community tools such as the explorer from cocoon.org/developers?

Everything we build is open and checkable. We want Cocoon to work, and we are ready to carry part of the work on the
public side.

With respect,
MINIMALCULT — github.com/miinimal/cocoon-explorer

---

Sources: root contract EQCns7bYSp0igFvS1wpb5wsZjCKCV19MD5AVzI4EyxsnU73k and proxy EQDGkQM7RIWp6yGW79i8oV3zJ-vdnpV68pdZ2W8mrpE3cJ2y
(tonapi), live handshake to 91.108.4.11:8888 (probe.py), github.com/TelegramMessenger/cocoon/issues/77.
