"""
Transaction Tool - Wraps the transaction agent as a LangChain tool
"""

from langchain_core.tools import tool
import json
from transaction_agent import run_transaction_agent


@tool
def generate_blockchain_transaction(
    action_description: str,
    contract_address: str,
    user_address: str
) -> str:
    """
    Generates a blockchain transaction for the user.
    
    Use this when user wants to PERFORM AN ACTION like:
    - Swapping tokens
    - Transferring assets  
    - Approving spending
    - Staking/unstaking
    - Any blockchain action
    
    Args:
        action_description: What the user wants (e.g., "swap 0.01 AVAX for USDC")
        contract_address: Target contract address
        user_address: User's wallet address
        
    Returns:
        JSON string with transaction object or error
    """
    print(f"\n{'='*60}")
    print(f"[TRANSACTION TOOL] Called")
    print(f"{'='*60}")
    print(f"  Action: {action_description}")
    print(f"  Contract: {contract_address}")
    print(f"  User: {user_address}")
    
    result = run_transaction_agent(
        message=action_description,
        user_address=user_address,
        contract_address=contract_address
    )
    
    print(f"\n[TRANSACTION TOOL] Result:")
    print(f"  Type: {result['type']}")
    
    if result["type"] == "transaction":
        print(f"  ✓ Transaction generated successfully")
        print(f"  Transaction keys: {list(result['transaction'].keys())}")
        print(f"{'='*60}\n")
        return json.dumps(result["transaction"])
    else:
        print(f"  ✗ Error: {result['message']}")
        print(f"{'='*60}\n")
        return json.dumps({"error": result["message"]})