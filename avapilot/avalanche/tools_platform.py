"""Platform CLI wrapper — L1 creation, staking, cross-chain transfers via platform-cli."""

import json
import os
import subprocess
import shutil
import sys
from mcp.server.fastmcp import FastMCP

PLATFORM_CLI = shutil.which("platform-cli") or os.path.expanduser("~/go/bin/platform-cli")


def _run_platform(args: list[str], chain: str = "fuji") -> dict:
    """Run a platform-cli command and return parsed output."""
    cmd = [PLATFORM_CLI, "--network", chain] + args
    
    env = os.environ.copy()
    # Use the same private key as AvaPilot wallet
    pk = os.environ.get("AVAPILOT_PRIVATE_KEY", "")
    if pk:
        env["AVALANCHE_PRIVATE_KEY"] = pk.replace("0x", "")
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=env,
        )
        output = result.stdout.strip()
        stderr = result.stderr.strip()
        
        if result.returncode != 0:
            return {"success": False, "error": stderr or output or f"Exit code {result.returncode}"}
        
        return {"success": True, "output": output, "stderr": stderr}
    except FileNotFoundError:
        return {"success": False, "error": "platform-cli not installed. Run: go install github.com/ava-labs/platform-cli@latest"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Operation timed out (120s)"}


def register(mcp: FastMCP, chain: str = "avalanche") -> None:
    """Register platform (P-Chain) tools — L1, staking, cross-chain."""
    default_chain = chain

    # ── Info Tools ────────────────────────────────────────────────────

    @mcp.tool(
        name="platform_wallet_balance",
        description="Check P-Chain wallet balance (AVAX). This is separate from C-Chain balance.",
    )
    def platform_wallet_balance() -> str:
        """Get the P-Chain AVAX balance for the configured wallet."""
        result = _run_platform(["wallet", "balance"], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="platform_wallet_address",
        description="Get the P-Chain wallet address (P-avax1... format).",
    )
    def platform_wallet_address() -> str:
        """Get the P-Chain address for the configured wallet."""
        result = _run_platform(["wallet", "address"], default_chain)
        return json.dumps(result)

    # ── Transfer Tools ────────────────────────────────────────────────

    @mcp.tool(
        name="transfer_c_to_p",
        description="Transfer AVAX from C-Chain to P-Chain. Required before staking or creating subnets.",
    )
    def transfer_c_to_p(amount: float) -> str:
        """Move AVAX from C-Chain to P-Chain.
        
        Args:
            amount: Amount in AVAX to transfer
        """
        result = _run_platform(["transfer", "c-to-p", "--amount", str(amount)], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="transfer_p_to_c",
        description="Transfer AVAX from P-Chain back to C-Chain.",
    )
    def transfer_p_to_c(amount: float) -> str:
        """Move AVAX from P-Chain to C-Chain.
        
        Args:
            amount: Amount in AVAX to transfer
        """
        result = _run_platform(["transfer", "p-to-c", "--amount", str(amount)], default_chain)
        return json.dumps(result)

    # ── Subnet / L1 Tools ─────────────────────────────────────────────

    @mcp.tool(
        name="create_subnet",
        description="Create a new subnet on Avalanche. This is step 1 of creating an L1. Returns a subnet ID.",
    )
    def create_subnet() -> str:
        """Create a new subnet. The wallet address becomes the subnet owner.
        Costs a small amount of AVAX. Returns the subnet ID needed for subsequent operations.
        """
        result = _run_platform(["subnet", "create"], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="convert_subnet_to_l1",
        description="Convert a subnet to an L1 blockchain. Step 2 after create_subnet. Requires a subnet ID and chain config.",
    )
    def convert_subnet_to_l1(
        subnet_id: str,
        chain_name: str,
        vm_id: str = "srEXiWaHuhNyGwPUi444Tu47ZEDwxTWrbQiuD7FmgSAQ6X7Dy",
        genesis_path: str = "",
    ) -> str:
        """Convert a subnet to a sovereign L1.
        
        Args:
            subnet_id: Subnet ID from create_subnet
            chain_name: Name for the new chain
            vm_id: Virtual machine ID (default: SubnetEVM)
            genesis_path: Path to genesis.json (optional)
        """
        args = ["subnet", "convert-l1", "--subnet-id", subnet_id, "--chain-name", chain_name, "--vm-id", vm_id]
        if genesis_path:
            args.extend(["--genesis", genesis_path])
        result = _run_platform(args, default_chain)
        return json.dumps(result)

    # ── Validator / Staking Tools ─────────────────────────────────────

    @mcp.tool(
        name="delegate_stake",
        description="Delegate AVAX to a Primary Network validator to earn staking rewards.",
    )
    def delegate_stake(
        node_id: str,
        amount: float,
        duration_days: int = 14,
    ) -> str:
        """Delegate AVAX to a validator on the Primary Network.
        
        Args:
            node_id: Validator's NodeID (e.g., NodeID-...)
            amount: Amount of AVAX to delegate (minimum 25 AVAX on mainnet)
            duration_days: Delegation period in days (min 14, max 365)
        """
        duration = f"{duration_days * 24}h"
        result = _run_platform([
            "validator", "delegate",
            "--node-id", node_id,
            "--amount", str(amount),
            "--duration", duration,
        ], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="add_validator",
        description="Add a new validator to the Primary Network. Requires running an Avalanche node.",
    )
    def add_validator(
        node_id: str,
        stake_amount: float,
        duration_days: int = 14,
        delegation_fee: int = 2,
    ) -> str:
        """Register a node as a Primary Network validator.
        
        Args:
            node_id: Your node's NodeID
            stake_amount: AVAX to stake (minimum 2000 on mainnet, 1 on fuji)
            duration_days: Validation period in days
            delegation_fee: Fee charged to delegators (percentage, min 2)
        """
        duration = f"{duration_days * 24}h"
        result = _run_platform([
            "validator", "add",
            "--node-id", node_id,
            "--amount", str(stake_amount),
            "--duration", duration,
            "--delegation-fee", str(delegation_fee),
        ], default_chain)
        return json.dumps(result)

    # ── L1 Validator Tools ────────────────────────────────────────────

    @mcp.tool(
        name="register_l1_validator",
        description="Register a validator for an L1 chain (after subnet is converted to L1).",
    )
    def register_l1_validator(
        subnet_id: str,
        node_id: str,
        weight: int = 100,
        balance: float = 1.0,
    ) -> str:
        """Register a validator for a specific L1.
        
        Args:
            subnet_id: The L1's subnet ID
            node_id: Validator's NodeID
            weight: Validator weight (voting power)
            balance: Initial balance in AVAX for the validator
        """
        result = _run_platform([
            "l1", "register-validator",
            "--subnet-id", subnet_id,
            "--node-id", node_id,
            "--weight", str(weight),
            "--balance", str(balance),
        ], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="set_l1_validator_weight",
        description="Change the weight (voting power) of an L1 validator.",
    )
    def set_l1_validator_weight(subnet_id: str, node_id: str, weight: int) -> str:
        """Update an L1 validator's weight.
        
        Args:
            subnet_id: The L1's subnet ID
            node_id: Validator's NodeID
            weight: New weight value
        """
        result = _run_platform([
            "l1", "set-weight",
            "--subnet-id", subnet_id,
            "--node-id", node_id,
            "--weight", str(weight),
        ], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="add_l1_validator_balance",
        description="Add AVAX balance to an L1 validator to keep it running.",
    )
    def add_l1_validator_balance(subnet_id: str, node_id: str, amount: float) -> str:
        """Top up an L1 validator's balance.
        
        Args:
            subnet_id: The L1's subnet ID
            node_id: Validator's NodeID  
            amount: AVAX to add
        """
        result = _run_platform([
            "l1", "add-balance",
            "--subnet-id", subnet_id,
            "--node-id", node_id,
            "--amount", str(amount),
        ], default_chain)
        return json.dumps(result)

    @mcp.tool(
        name="disable_l1_validator",
        description="Disable a validator on an L1 chain.",
    )
    def disable_l1_validator(subnet_id: str, node_id: str) -> str:
        """Disable an L1 validator.
        
        Args:
            subnet_id: The L1's subnet ID
            node_id: Validator's NodeID to disable
        """
        result = _run_platform([
            "l1", "disable-validator",
            "--subnet-id", subnet_id,
            "--node-id", node_id,
        ], default_chain)
        return json.dumps(result)

    print(f"[platform] Registered 11 P-Chain tools (L1, staking, transfers)", file=sys.stderr)
