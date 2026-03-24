"""
Secure wallet management for AvaPilot MCP Gateway.

Loads private keys from environment variables only — never hardcoded.
Supports: AVAPILOT_PRIVATE_KEY or AVAPILOT_KEYSTORE_PATH + AVAPILOT_KEYSTORE_PASSWORD
"""

import os
from pathlib import Path

# Auto-load .env file from project root
def _load_dotenv():
    for p in [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break

_load_dotenv()
import json

from web3 import Web3
from eth_account import Account

from avapilot.runtime.config import get_chain_config


def is_wallet_configured() -> bool:
    """Check if a wallet is configured via environment variables."""
    if os.environ.get("AVAPILOT_PRIVATE_KEY"):
        return True
    if os.environ.get("AVAPILOT_KEYSTORE_PATH") and os.environ.get("AVAPILOT_KEYSTORE_PASSWORD"):
        return True
    return False


def get_account() -> Account:
    """Get a web3 Account object from environment variables.

    Supports:
        AVAPILOT_PRIVATE_KEY — hex-encoded private key (with or without 0x prefix)
        AVAPILOT_KEYSTORE_PATH + AVAPILOT_KEYSTORE_PASSWORD — encrypted keystore file
    """
    pk = os.environ.get("AVAPILOT_PRIVATE_KEY")
    if pk:
        if not pk.startswith("0x"):
            pk = "0x" + pk
        return Account.from_key(pk)

    keystore_path = os.environ.get("AVAPILOT_KEYSTORE_PATH")
    keystore_password = os.environ.get("AVAPILOT_KEYSTORE_PASSWORD")
    if keystore_path and keystore_password:
        with open(keystore_path) as f:
            keystore = json.load(f)
        pk = Account.decrypt(keystore, keystore_password)
        return Account.from_key(pk)

    raise RuntimeError(
        "No wallet configured. Set AVAPILOT_PRIVATE_KEY environment variable, "
        "or set AVAPILOT_KEYSTORE_PATH + AVAPILOT_KEYSTORE_PASSWORD."
    )


def get_address() -> str:
    """Return the checksummed address of the configured wallet."""
    return get_account().address


def _get_web3(chain: str = "avalanche") -> Web3:
    """Get a connected Web3 instance for a chain."""
    config = get_chain_config(chain)
    w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {config['rpc_url']}")
    return w3


def sign_and_send(tx_dict: dict, chain: str = "avalanche") -> str:
    """Sign a transaction and send it. Returns the transaction hash as hex string.

    tx_dict should contain: to, value, data (optional), gas (optional).
    Nonce, chainId, and gas price are filled automatically if missing.
    """
    account = get_account()
    w3 = _get_web3(chain)
    config = get_chain_config(chain)

    # Fill in transaction fields
    if "nonce" not in tx_dict:
        tx_dict["nonce"] = w3.eth.get_transaction_count(account.address)
    if "chainId" not in tx_dict:
        tx_dict["chainId"] = config["chain_id"]
    if "gasPrice" not in tx_dict and "maxFeePerGas" not in tx_dict:
        tx_dict["gasPrice"] = w3.eth.gas_price
    if "gas" not in tx_dict:
        try:
            tx_dict["gas"] = w3.eth.estimate_gas({
                "from": account.address,
                "to": tx_dict.get("to"),
                "value": tx_dict.get("value", 0),
                "data": tx_dict.get("data", b""),
            })
        except Exception:
            tx_dict["gas"] = 300_000  # fallback

    signed = account.sign_transaction(tx_dict)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def wait_for_receipt(tx_hash: str, chain: str = "avalanche", timeout: int = 120) -> dict:
    """Wait for a transaction to be confirmed and return the receipt."""
    w3 = _get_web3(chain)
    if isinstance(tx_hash, str):
        tx_hash = bytes.fromhex(tx_hash.replace("0x", ""))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
    return dict(receipt)
