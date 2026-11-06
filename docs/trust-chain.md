# How a Cocoon request is protected: the trust chain, checked in the code

An independent reading of [TelegramMessenger/cocoon](https://github.com/TelegramMessenger/cocoon) at branch `dev`
(commit `541432c`, 2026-05-21). Each step names the code that enforces it, so anyone can check it.
This map watches the same chain from outside, every hour, on the live network.

## 1. The machine is a real TEE, signed by Intel

When a node connects, the router reads the TDX quote from the peer's RA-TLS certificate and verifies it with
Intel's quote verification library: `tee_verify_quote` in `tee/cocoon/tdx/tdx.cpp` (`validate_quote`).
The result must be exactly `SGX_QL_QV_RESULT_OK`, and expired collateral is rejected, so out-of-date TCB levels
do not pass. The Intel root key ID of the chain can additionally be pinned (`allowed_collateral_root_hashes`,
`tee/cocoon/RATLS.cpp`).

This map runs the same check independently with [dcap-qvl](https://github.com/Phala-Network/dcap-qvl) and
publishes the raw quote of each live proxy, so the result can be re-verified without trusting either side.

## 2. The TLS key belongs to that machine

The quote's report data must equal the hash of the certificate's public key (`RATLS.cpp`,
`DefaultPolicy::validate`: "Report data mismatch"). A certificate cannot borrow another machine's attestation.

## 3. The software inside is an approved image

The image hash is computed from the TDX measurements (MRTD, RTMR0–3, `image_hash` in `tee/cocoon/tdx/tdx.cpp`)
and compared with the lists in the root contract:

| Connection | Check | Code |
|---|---|---|
| client to proxy | proxy image allowed by root | `runners/client/ClientProxyConnection.cpp` (`has_proxy_hash`) |
| worker to proxy | proxy image allowed by root | `runners/worker/WorkerProxyConnection.cpp` (`has_proxy_hash`) |
| proxy accepts worker | worker image and model allowed by root | `runners/proxy/ProxyInboundWorkerConnection.cpp` (`has_worker_hash`, model) |
| root config changes | workers whose image was removed are dropped | `runners/proxy/ProxyRunner.cpp` (`has_worker_hash` on update) |
| key manager | proxy and worker images allowed by root | `runners/key-manager/KeyManagerRunner.cpp` |

These checks are on whenever a runner is not in test mode (`check_*_hashes || !is_test`).

## 4. Who decides which images are allowed

Only the root contract owner can add or remove image hashes. The current lists, with the date each hash was
added, are on this map (section "Image allow-list"), and
[`scripts/image-hash-check`](https://github.com/miinimal/cocoon/blob/image-hash-check/scripts/image-hash-check)
answers for any hash.

## What this does not cover

- The router's own default policy accepts any genuine TEE (`tee` with empty lists); image pinning happens one
  level up, in the runners, as listed above. A setup that runs a runner in test mode, or a custom router policy
  for a different application, does not get those checks.
- Money is a separate layer: payments and refunds run through TON contracts and the proxy runner. See the
  "Client stakes" section of this map and [cocoon-contracts#9](https://github.com/TelegramMessenger/cocoon-contracts/pull/9).

Reviewed 2026-11-06. Corrections are welcome as issues in this repository.
