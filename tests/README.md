# AvaPilot Tests

## Setup

1. Get test AVAX from the faucet: https://faucet.avax.network/
2. Set your Fuji testnet private key:

```bash
export AVAPILOT_PRIVATE_KEY=0xYourFujiTestnetPrivateKeyHere
```

⚠️  NEVER put your private key in a file that gets committed to git.

## Run tests

```bash
cd avapilot
python tests/test_fuji.py
```
