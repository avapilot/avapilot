"""READ mode tools — safe queries, no wallet needed."""

from web3 import Web3
from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import pchain, glacier, wallet
from avapilot.avalanche._helpers import (
    get_w3, resolve_token, token_decimals, to_token_units, from_token_units,
    get_swap_path,
    ERC20_ABI, TRADER_JOE_ROUTER_ABI,
)
from avapilot.runtime.config import (
    get_chain_config, CHAINS, AVALANCHE_TOKENS, AVALANCHE_DAPPS,
)
from avapilot.runtime.evm import fetch_abi


def register(mcp: FastMCP) -> None:
    """Register all read-only tools on the given MCP server."""

    # ── Network Info ─────────────────────────────────────────────────────

    @mcp.tool()
    def avalanche_network_info() -> dict:
        """Get Avalanche network overview: P-Chain height, current supply, and chain count."""
        try:
            height = pchain.get_height()
        except Exception:
            height = None
        try:
            supply_navax = pchain.get_current_supply()
            supply_avax = int(supply_navax) / 1e9
        except Exception:
            supply_avax = None
        try:
            blockchains = pchain.get_blockchains()
            chain_count = len(blockchains)
        except Exception:
            chain_count = None
        return {
            "network": "Avalanche Mainnet",
            "p_chain_height": height,
            "current_supply_avax": supply_avax,
            "blockchain_count": chain_count,
        }

    @mcp.tool()
    def avalanche_list_l1s() -> list[dict]:
        """List all Avalanche L1 chains tracked by Glacier."""
        try:
            chains = glacier.list_chains()
            return [
                {
                    "chain_id": c.get("chainId"),
                    "chain_name": c.get("chainName"),
                    "network_token": c.get("networkToken", {}).get("symbol"),
                    "rpc_url": c.get("rpcUrl"),
                }
                for c in chains
            ]
        except Exception as e:
            return [{"error": str(e)}]

    @mcp.tool()
    def avalanche_get_l1_info(chain_id_or_name: str) -> dict:
        """Get details about a specific Avalanche L1 chain by chain ID or name."""
        try:
            return glacier.get_chain_info(chain_id_or_name)
        except Exception:
            pass
        try:
            chains = glacier.list_chains()
            name_lower = chain_id_or_name.lower()
            for c in chains:
                if name_lower in c.get("chainName", "").lower():
                    return c
            return {"error": f"No chain found matching '{chain_id_or_name}'"}
        except Exception as e:
            return {"error": str(e)}

    # ── Validators & Staking ─────────────────────────────────────────────

    @mcp.tool()
    def avalanche_list_validators(subnet_id: str | None = None, limit: int = 20) -> list[dict]:
        """List current Avalanche validators. Optionally filter by subnet ID."""
        try:
            validators = pchain.get_current_validators(subnet_id=subnet_id, limit=limit)
            return [
                {
                    "node_id": v.get("nodeID"),
                    "start_time": v.get("startTime"),
                    "end_time": v.get("endTime"),
                    "stake_amount": v.get("stakeAmount"),
                    "uptime": v.get("uptime"),
                    "connected": v.get("connected"),
                }
                for v in validators[:limit]
            ]
        except Exception as e:
            return [{"error": str(e)}]

    @mcp.tool()
    def avalanche_validator_info(node_id: str) -> dict:
        """Get details about a specific validator by node ID."""
        try:
            validators = pchain.get_current_validators()
            for v in validators:
                if v.get("nodeID") == node_id:
                    return {
                        "node_id": v.get("nodeID"),
                        "start_time": v.get("startTime"),
                        "end_time": v.get("endTime"),
                        "stake_amount": v.get("stakeAmount"),
                        "uptime": v.get("uptime"),
                        "connected": v.get("connected"),
                        "delegation_fee": v.get("delegationFee"),
                        "delegator_count": len(v.get("delegators", []) or []),
                    }
            return {"error": f"Validator {node_id} not found"}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def avalanche_staking_info() -> dict:
        """Get staking overview: min stake amounts, total staked, staking asset."""
        result = {}
        try:
            min_stake = pchain.get_min_stake()
            result["min_validator_stake_avax"] = int(min_stake["minValidatorStake"]) / 1e9
            result["min_delegator_stake_avax"] = int(min_stake["minDelegatorStake"]) / 1e9
        except Exception:
            pass
        try:
            total = pchain.get_total_stake()
            result["total_staked_avax"] = int(total) / 1e9
        except Exception:
            pass
        try:
            result["staking_asset_id"] = pchain.get_staking_asset_id()
        except Exception:
            pass
        return result

    @mcp.tool()
    def estimate_staking_rewards(amount_avax: float, duration_days: int) -> dict:
        """Estimate AVAX staking rewards for a given amount and duration.

        Uses approximate mainnet reward rate (~8-10% APY).
        Actual rewards depend on uptime and network conditions.
        """
        if amount_avax <= 0:
            return {"error": "amount_avax must be positive"}
        if duration_days < 14:
            return {"error": "Minimum staking duration is 14 days"}
        if duration_days > 365:
            return {"error": "Maximum staking duration is 365 days"}
        annual_rate = 0.09
        daily_rate = annual_rate / 365
        estimated_reward = amount_avax * daily_rate * duration_days
        return {
            "staked_avax": amount_avax,
            "duration_days": duration_days,
            "estimated_reward_avax": round(estimated_reward, 6),
            "estimated_apy_percent": round(annual_rate * 100, 2),
            "note": "Estimate only. Actual rewards depend on uptime, delegation fee, and network conditions.",
        }

    # ── Token & Balance Queries ──────────────────────────────────────────

    @mcp.tool()
    def avalanche_get_balance(address: str, chain_id: str = "43114") -> dict:
        """Get native + ERC-20 token balances for an address on an Avalanche chain."""
        result = {}
        try:
            native = glacier.get_native_balance(chain_id, address)
            result["native"] = native
        except Exception as e:
            result["native_error"] = str(e)
        try:
            erc20 = glacier.get_erc20_balances(chain_id, address)
            result["erc20"] = erc20
        except Exception as e:
            result["erc20_error"] = str(e)
        return result

    @mcp.tool()
    def avalanche_get_nfts(address: str, chain_id: str = "43114") -> dict:
        """Get NFT holdings for an address on an Avalanche chain."""
        try:
            return glacier.list_nfts(chain_id, address)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def avalanche_token_transfers(address: str, chain_id: str = "43114") -> dict:
        """Get recent token transfers for an address on an Avalanche chain."""
        result = {}
        try:
            result["native_transfers"] = glacier.list_transactions(chain_id, address)
        except Exception as e:
            result["native_error"] = str(e)
        try:
            result["erc20_transfers"] = glacier.list_erc20_transfers(chain_id, address)
        except Exception as e:
            result["erc20_error"] = str(e)
        return result

    # ── Cross-Chain ──────────────────────────────────────────────────────

    @mcp.tool()
    def avalanche_list_blockchains() -> list[dict]:
        """List all blockchains registered on the Avalanche network."""
        try:
            blockchains = pchain.get_blockchains()
            return [
                {
                    "id": bc.get("id"),
                    "name": bc.get("name"),
                    "subnet_id": bc.get("subnetID"),
                    "vm_id": bc.get("vmID"),
                }
                for bc in blockchains
            ]
        except Exception as e:
            return [{"error": str(e)}]

    @mcp.tool()
    def avalanche_get_blockchain_status(blockchain_id: str) -> dict:
        """Check the status of a specific blockchain (Validating, Created, etc.)."""
        try:
            status = pchain.get_blockchain_status(blockchain_id)
            return {"blockchain_id": blockchain_id, "status": status}
        except Exception as e:
            return {"error": str(e)}

    # ── Token Info ───────────────────────────────────────────────────────

    @mcp.tool()
    def token_info(token_symbol_or_address: str) -> dict:
        """Get token info: name, symbol, decimals, total supply."""
        token_addr = resolve_token(token_symbol_or_address)
        w3 = get_w3()
        contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
        try:
            name = contract.functions.name().call()
        except Exception:
            name = "Unknown"
        try:
            symbol = contract.functions.symbol().call()
        except Exception:
            symbol = "Unknown"
        try:
            decimals = contract.functions.decimals().call()
        except Exception:
            decimals = 18
        try:
            total_supply_raw = contract.functions.totalSupply().call()
            total_supply = from_token_units(total_supply_raw, decimals)
        except Exception:
            total_supply = None
        return {
            "address": token_addr,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply": total_supply,
        }

    @mcp.tool()
    def token_allowance(token_address: str, owner: str, spender: str) -> dict:
        """Check how many tokens an owner has approved a spender to use."""
        token_addr = resolve_token(token_address)
        owner_addr = Web3.to_checksum_address(owner)
        spender_addr = Web3.to_checksum_address(spender)
        w3 = get_w3()
        contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
        decimals = contract.functions.decimals().call()
        symbol = contract.functions.symbol().call()
        raw_allowance = contract.functions.allowance(owner_addr, spender_addr).call()
        return {
            "token": symbol,
            "token_address": token_addr,
            "owner": owner_addr,
            "spender": spender_addr,
            "allowance": from_token_units(raw_allowance, decimals),
            "allowance_raw": str(raw_allowance),
        }

    # ── DEX Quotes ───────────────────────────────────────────────────────

    @mcp.tool()
    def get_swap_quote(amount_in: float, token_in: str, token_out: str) -> dict:
        """Get expected output amount for a swap on Trader Joe. Amount in human-readable units."""
        router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])
        path = get_swap_path(token_in, token_out)
        w3 = get_w3()
        wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
        in_decimals = token_decimals(path[0], w3) if path[0] != wavax else 18
        out_decimals = token_decimals(path[-1], w3) if path[-1] != wavax else 18
        if token_in.upper() == "AVAX":
            in_decimals = 18
            path[0] = wavax
        raw_in = to_token_units(amount_in, in_decimals)
        router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
        amounts = router.functions.getAmountsOut(raw_in, path).call()
        raw_out = amounts[-1]
        return {
            "amount_in": amount_in,
            "token_in": token_in,
            "amount_out": from_token_units(raw_out, out_decimals),
            "token_out": token_out,
            "path": path,
            "router": router_addr,
        }

    @mcp.tool()
    def get_token_price(token_symbol_or_address: str) -> dict:
        """Get token price in AVAX and USD (estimated) via Trader Joe router."""
        token_addr = resolve_token(token_symbol_or_address)
        wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
        usdc = Web3.to_checksum_address(AVALANCHE_TOKENS["USDC"])
        router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])
        w3 = get_w3()
        router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
        decimals = token_decimals(token_addr, w3) if token_addr != wavax else 18
        one_token = to_token_units(1, decimals)
        result = {"token": token_symbol_or_address, "address": token_addr}
        if token_addr == wavax:
            result["price_avax"] = 1.0
            try:
                amounts = router.functions.getAmountsOut(one_token, [wavax, usdc]).call()
                usdc_decimals = token_decimals(usdc, w3)
                result["price_usd"] = from_token_units(amounts[-1], usdc_decimals)
            except Exception:
                result["price_usd"] = None
        else:
            try:
                amounts = router.functions.getAmountsOut(one_token, [token_addr, wavax]).call()
                result["price_avax"] = from_token_units(amounts[-1], 18)
            except Exception:
                result["price_avax"] = None
            try:
                if token_addr == usdc:
                    result["price_usd"] = 1.0
                else:
                    path = [token_addr, wavax, usdc] if token_addr != wavax else [wavax, usdc]
                    amounts = router.functions.getAmountsOut(one_token, path).call()
                    usdc_decimals = token_decimals(usdc, w3)
                    result["price_usd"] = from_token_units(amounts[-1], usdc_decimals)
            except Exception:
                result["price_usd"] = None
        return result

    # ── Contract Tools (read-only) ───────────────────────────────────────

    @mcp.tool()
    def read_contract(
        contract_address: str,
        function_name: str,
        args: list | None = None,
        chain: str = "avalanche",
    ) -> dict:
        """Call any view/pure function on a contract. Fetches ABI automatically from Snowtrace."""
        config = get_chain_config(chain)
        addr = Web3.to_checksum_address(contract_address)
        args = args or []
        try:
            abi = fetch_abi(addr, config["explorer_api"])
        except Exception as e:
            return {"error": f"Failed to fetch ABI: {e}. Contract may not be verified."}
        from avapilot.runtime.evm import read_contract as evm_read
        try:
            result = evm_read(config["rpc_url"], addr, abi, function_name, args)
            return {"result": result if not isinstance(result, bytes) else result.hex()}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def get_contract_abi(contract_address: str, chain: str = "avalanche") -> dict:
        """Fetch the ABI for a verified contract from Snowtrace."""
        config = get_chain_config(chain)
        addr = Web3.to_checksum_address(contract_address)
        try:
            abi = fetch_abi(addr, config["explorer_api"])
            functions = [
                item["name"]
                for item in abi
                if item.get("type") == "function"
            ]
            return {
                "contract": addr,
                "abi_item_count": len(abi),
                "functions": functions,
                "abi": abi,
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Gas Tools ────────────────────────────────────────────────────────

    @mcp.tool()
    def estimate_gas(
        to: str,
        data: str = "0x",
        value_avax: float = 0,
    ) -> dict:
        """Estimate gas for a transaction on Avalanche C-Chain."""
        w3 = get_w3()
        to_addr = Web3.to_checksum_address(to)
        value_wei = to_token_units(value_avax, 18) if value_avax else 0
        tx = {"to": to_addr, "value": value_wei, "data": data}
        if wallet.is_wallet_configured():
            tx["from"] = wallet.get_address()
        try:
            gas = w3.eth.estimate_gas(tx)
            gas_price_val = w3.eth.gas_price
            cost_wei = gas * gas_price_val
            return {
                "gas_units": gas,
                "gas_price_gwei": from_token_units(gas_price_val, 9),
                "estimated_cost_avax": from_token_units(cost_wei, 18),
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def gas_price() -> dict:
        """Get current gas price on Avalanche C-Chain in gwei and nAVAX."""
        w3 = get_w3()
        price_wei = w3.eth.gas_price
        return {
            "gas_price_wei": price_wei,
            "gas_price_gwei": from_token_units(price_wei, 9),
            "gas_price_navax": price_wei,
        }

    # ── L1 / Subnet Tools ───────────────────────────────────────────────

    @mcp.tool()
    def get_l1_rpc(chain_id_or_name: str) -> dict:
        """Get the RPC URL for any Avalanche L1 chain."""
        for key, cfg in CHAINS.items():
            if str(cfg["chain_id"]) == str(chain_id_or_name) or key == chain_id_or_name.lower():
                return {"chain": cfg["name"], "rpc_url": cfg["rpc_url"], "chain_id": cfg["chain_id"]}
        try:
            info = glacier.get_chain_info(chain_id_or_name)
            rpc = info.get("rpcUrl")
            if rpc:
                return {
                    "chain": info.get("chainName", chain_id_or_name),
                    "rpc_url": rpc,
                    "chain_id": info.get("chainId"),
                }
        except Exception:
            pass
        try:
            chains = glacier.list_chains()
            name_lower = chain_id_or_name.lower()
            for c in chains:
                if name_lower in c.get("chainName", "").lower():
                    return {
                        "chain": c.get("chainName"),
                        "rpc_url": c.get("rpcUrl"),
                        "chain_id": c.get("chainId"),
                    }
        except Exception:
            pass
        return {"error": f"No RPC found for '{chain_id_or_name}'"}

    @mcp.tool()
    def call_l1_contract(
        chain_id: str,
        contract_address: str,
        function_name: str,
        args: list | None = None,
    ) -> dict:
        """Read from any contract on any Avalanche L1 chain. Fetches ABI from the chain's explorer."""
        args = args or []
        rpc_info = get_l1_rpc(chain_id)
        if "error" in rpc_info:
            return rpc_info
        rpc_url = rpc_info["rpc_url"]
        addr = Web3.to_checksum_address(contract_address)
        for key, cfg in CHAINS.items():
            if str(cfg["chain_id"]) == str(chain_id):
                try:
                    abi = fetch_abi(addr, cfg["explorer_api"])
                    from avapilot.runtime.evm import read_contract as evm_read
                    result = evm_read(rpc_url, addr, abi, function_name, args)
                    return {"result": result if not isinstance(result, bytes) else result.hex()}
                except Exception as e:
                    return {"error": str(e)}
        return {"error": f"No block explorer found for chain {chain_id}. Cannot auto-fetch ABI."}

    # ── Utility Tools ────────────────────────────────────────────────────

    @mcp.tool()
    def resolve_address(name_or_symbol: str) -> dict:
        """Resolve a token symbol or dApp name to its contract address."""
        upper = name_or_symbol.upper()
        for key, addr in AVALANCHE_TOKENS.items():
            if key.upper() == upper:
                return {"type": "token", "name": key, "address": addr}
        lower = name_or_symbol.lower().replace(" ", "_").replace("-", "_")
        for key, addr in AVALANCHE_DAPPS.items():
            if key == lower or lower in key:
                return {"type": "dapp", "name": key, "address": addr}
        if name_or_symbol.startswith("0x") and len(name_or_symbol) == 42:
            return {"type": "address", "address": Web3.to_checksum_address(name_or_symbol)}
        return {
            "error": f"Cannot resolve '{name_or_symbol}'",
            "known_tokens": list(AVALANCHE_TOKENS.keys()),
            "known_dapps": list(AVALANCHE_DAPPS.keys()),
        }

    @mcp.tool()
    def tx_status(tx_hash: str, chain: str = "avalanche") -> dict:
        """Check the status and receipt of a transaction."""
        w3 = get_w3(chain)
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            return {
                "tx_hash": tx_hash,
                "status": "success" if receipt.get("status") == 1 else "failed",
                "block_number": receipt.get("blockNumber"),
                "gas_used": receipt.get("gasUsed"),
                "contract_address": receipt.get("contractAddress"),
                "from": receipt.get("from"),
                "to": receipt.get("to"),
            }
        except Exception:
            pass
        try:
            tx = w3.eth.get_transaction(tx_hash)
            return {
                "tx_hash": tx_hash,
                "status": "pending",
                "from": tx.get("from"),
                "to": tx.get("to"),
                "value_avax": from_token_units(tx.get("value", 0), 18),
            }
        except Exception as e:
            return {"error": f"Transaction not found: {e}"}

    @mcp.tool()
    def encode_function_call(
        contract_address: str,
        function_name: str,
        args: list | None = None,
        chain: str = "avalanche",
    ) -> dict:
        """Encode a function call as calldata without sending it. Useful for multisig or batching."""
        config = get_chain_config(chain)
        addr = Web3.to_checksum_address(contract_address)
        args = args or []
        try:
            abi = fetch_abi(addr, config["explorer_api"])
        except Exception as e:
            return {"error": f"Failed to fetch ABI: {e}"}
        w3 = Web3()
        contract = w3.eth.contract(address=addr, abi=abi)
        func_abi = next(
            (item for item in abi if item.get("name") == function_name and item.get("type") == "function"),
            None,
        )
        if not func_abi:
            return {"error": f"Function '{function_name}' not found in ABI"}
        from avapilot.runtime.evm import _convert_args
        converted = _convert_args(args, func_abi.get("inputs", []))
        calldata = contract.functions[function_name](*converted)._encode_transaction_data()
        return {
            "contract": addr,
            "function": function_name,
            "calldata": calldata,
        }

    # ── Contract Developer Tools ─────────────────────────────────────────

    @mcp.tool()
    def get_contract_events(
        contract_address: str,
        event_name: str | None = None,
        from_block: int | None = None,
        to_block: str = "latest",
        chain: str = "avalanche",
    ) -> dict:
        """Get recent event logs from a contract. Optionally filter by event name. Returns last 1000 blocks by default."""
        w3 = get_w3(chain)
        addr = Web3.to_checksum_address(contract_address)
        config = get_chain_config(chain)

        if from_block is None:
            current = w3.eth.block_number
            from_block = max(0, current - 1000)

        try:
            if event_name:
                # Fetch ABI and filter by event
                abi = fetch_abi(addr, config["explorer_api"])
                contract = w3.eth.contract(address=addr, abi=abi)
                event = getattr(contract.events, event_name, None)
                if not event:
                    return {"error": f"Event '{event_name}' not found. Available: {[e.get('name') for e in abi if e.get('type') == 'event']}"}
                logs = event().get_logs(fromBlock=from_block, toBlock=to_block)
            else:
                logs = w3.eth.get_logs({
                    "address": addr,
                    "fromBlock": from_block,
                    "toBlock": to_block,
                })

            return {
                "contract": addr,
                "event_filter": event_name or "all",
                "block_range": f"{from_block} → {to_block}",
                "count": len(logs),
                "logs": [
                    {
                        "blockNumber": log.get("blockNumber"),
                        "transactionHash": log.get("transactionHash", b"").hex() if isinstance(log.get("transactionHash"), bytes) else str(log.get("transactionHash", "")),
                        "args": dict(log.get("args", {})) if hasattr(log, "get") and log.get("args") else None,
                    }
                    for log in logs[:50]  # cap at 50
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def get_contract_source(contract_address: str, chain: str = "avalanche") -> dict:
        """Check if a contract is verified on Snowtrace and return its source info."""
        import requests
        config = get_chain_config(chain)
        addr = Web3.to_checksum_address(contract_address)
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": addr,
            "apikey": "YourApiKeyToken",
        }
        try:
            resp = requests.get(config["explorer_api"], params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1" or not data.get("result"):
                return {"verified": False, "address": addr}
            info = data["result"][0]
            return {
                "verified": bool(info.get("SourceCode")),
                "address": addr,
                "contract_name": info.get("ContractName", ""),
                "compiler": info.get("CompilerVersion", ""),
                "optimization": info.get("OptimizationUsed", ""),
                "license": info.get("LicenseType", ""),
                "proxy": bool(info.get("Implementation")),
                "implementation": info.get("Implementation", "") or None,
                "abi_available": bool(info.get("ABI") and info["ABI"] != "Contract source code not verified"),
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def is_contract(address: str, chain: str = "avalanche") -> dict:
        """Check if an address is a contract or an EOA (externally owned account)."""
        w3 = get_w3(chain)
        addr = Web3.to_checksum_address(address)
        code = w3.eth.get_code(addr)
        is_contract = len(code) > 0
        balance = w3.eth.get_balance(addr)
        return {
            "address": addr,
            "is_contract": is_contract,
            "code_size_bytes": len(code) if is_contract else 0,
            "avax_balance": from_token_units(balance, 18),
        }

    @mcp.tool()
    def get_block_info(block_number: str = "latest", chain: str = "avalanche") -> dict:
        """Get block details — timestamp, gas used, transaction count."""
        w3 = get_w3(chain)
        block_id = block_number if block_number == "latest" else int(block_number)
        try:
            block = w3.eth.get_block(block_id)
            return {
                "number": block["number"],
                "timestamp": block["timestamp"],
                "gas_used": block["gasUsed"],
                "gas_limit": block["gasLimit"],
                "transaction_count": len(block["transactions"]),
                "base_fee_gwei": block.get("baseFeePerGas", 0) / 1e9,
                "hash": block["hash"].hex(),
                "parent_hash": block["parentHash"].hex(),
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def decode_tx(tx_hash: str, chain: str = "avalanche") -> dict:
        """Decode a transaction — shows from, to, value, method called, gas used, status."""
        w3 = get_w3(chain)
        config = get_chain_config(chain)
        try:
            tx = w3.eth.get_transaction(tx_hash)
            receipt = w3.eth.get_transaction_receipt(tx_hash)

            result = {
                "hash": tx_hash,
                "from": tx["from"],
                "to": tx.get("to"),
                "value_avax": from_token_units(tx["value"], 18),
                "gas_used": receipt["gasUsed"],
                "gas_price_gwei": tx.get("gasPrice", 0) / 1e9,
                "cost_avax": from_token_units(receipt["gasUsed"] * tx.get("gasPrice", 0), 18),
                "status": "success" if receipt["status"] == 1 else "reverted",
                "block": receipt["blockNumber"],
                "input_data_size": len(tx.get("input", b"")),
            }

            # Try to decode function selector
            input_data = tx.get("input", b"")
            if len(input_data) >= 4:
                selector = input_data[:4].hex()
                result["method_selector"] = f"0x{selector}"

                # Try fetching ABI to decode
                if tx.get("to"):
                    try:
                        abi = fetch_abi(Web3.to_checksum_address(tx["to"]), config["explorer_api"])
                        contract = w3.eth.contract(address=Web3.to_checksum_address(tx["to"]), abi=abi)
                        func, args = contract.decode_function_input(input_data)
                        result["method_name"] = func.fn_name
                        result["method_args"] = {k: str(v) for k, v in args.items()}
                    except:
                        pass

            # Log count
            result["log_count"] = len(receipt.get("logs", []))

            return result
        except Exception as e:
            return {"error": str(e)}
