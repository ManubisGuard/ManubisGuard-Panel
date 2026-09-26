# AWG Peer/Client-Key Mismatch Fix — 2026-09-26

## Root cause

The persisted WireGuard/AmneziaWG user `private_key` and `public_key` were allowed to diverge.

The subscription/client configuration uses the user's private key, while the Node peer registration uses the stored public key. A stale public key therefore produced a syntactically valid client configuration whose cryptographic identity did not match the peer registered on `WG_51820`, preventing handshake.

This is separate from the interface PSK and AWG J/S/H parameters.

## Fix

Commit: `0bb0e1c019f4e26e655287a891ca57be4bda2c65`

- Treat the user private key as the source of truth.
- Recompute the user public key whenever a private key exists.
- Perform uniqueness validation after canonicalizing the public key.
- Repair stale public keys during WireGuard allocation/reconciliation.
- Added regression coverage for stale and matching key pairs.

## TEST validation

- Focused WireGuard/AmneziaWG tests: `13 passed, 75 deselected`.
- Ruff: passed.
- Regression test file: `tests/test_wireguard_key_consistency.py`.
- The disposable TEST environment did not have a live Node/AWG listener, so a real TEST handshake was not available.

## Main server CLY327268

- Panel rebuilt from `feature/amnezia-wg` and redeployed.
- Panel health: healthy.
- TimescaleDB health: healthy.
- `WG_51820` initialized and remains listening on UDP 51820.
- Server interface public key and the registered peer were inspected without exposing private keys.
- Node peer for `10.0.0.2/32` matches the Panel DB user public key.
- User 1389 allocation/key reconciliation returned `changed=false`, confirming the existing persisted key pair was already canonical; Node user sync was then executed successfully.
- Generated subscription artifact was inspected for endpoint, address and AWG parameters; endpoint is `all.qoqnusradio.top:51820`, address is `10.0.0.2/32`, and AWG J/S/H parameters match the `WG_51820` interface.

## Handshake status

At the time of this checkpoint, `awg show WG_51820 latest-handshakes` and transfer counters were still zero. No active external client handshake was available from the server side, so this report does **not** mark real client handshake as PASS.

The code/peer identity mismatch is fixed and deployed; final acceptance requires fetching a fresh client configuration and observing a non-zero real handshake/transfer counter on `WG_51820`.