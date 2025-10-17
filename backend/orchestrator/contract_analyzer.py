"""
Contract Analyzer - Identifies contract types and explains functions
"""

def identify_contract_type(abi: list) -> dict:
    """
    Identifies contract type by analyzing function signatures
    
    Returns:
    {
        "type": "DEX_ROUTER" | "ERC20" | "ERC721" | "ERC1155" | "STAKING" | "UNKNOWN",
        "confidence": 0.95,
        "functions_found": ["swap", "addLiquidity", ...]
    }
    """
    functions = [item['name'] for item in abi if item.get('type') == 'function']
    
    # ERC20 Detection (highest confidence)
    erc20_sigs = {'balanceOf', 'transfer', 'approve', 'allowance', 'totalSupply'}
    if erc20_sigs.issubset(set(functions)):
        return {
            "type": "ERC20_TOKEN",
            "confidence": 0.95,
            "functions_found": list(erc20_sigs)
        }
    
    # DEX Router Detection
    dex_sigs = {'swapExactTokensForTokens', 'addLiquidity', 'removeLiquidity'}
    if len(dex_sigs.intersection(set(functions))) >= 2:
        return {
            "type": "DEX_ROUTER",
            "confidence": 0.85,
            "functions_found": list(dex_sigs.intersection(set(functions)))
        }
    
    # ERC721 Detection
    erc721_sigs = {'ownerOf', 'safeTransferFrom', 'tokenURI'}
    if len(erc721_sigs.intersection(set(functions))) >= 2:
        return {
            "type": "ERC721_NFT",
            "confidence": 0.90,
            "functions_found": list(erc721_sigs.intersection(set(functions)))
        }
    
    return {"type": "UNKNOWN", "confidence": 0.0, "functions_found": []}


def explain_contract(contract_type: str, functions: list) -> str:
    """
    Generates human-readable explanation
    """
    explanations = {
        "ERC20_TOKEN": """This is an ERC20 token contract. It represents a cryptocurrency or digital asset on Avalanche.

**What you can do:**
- Check your balance: balanceOf(yourAddress)
- Transfer tokens: transfer(recipient, amount)
- Approve spending: approve(spender, amount)
- Check allowances: allowance(owner, spender)

**Common functions:**
- balanceOf: Check how many tokens an address owns
- transfer: Send tokens to another address
- approve: Allow another address to spend your tokens
- allowance: Check how much someone is allowed to spend""",

        "DEX_ROUTER": """This is a DEX (Decentralized Exchange) Router contract. It enables token swapping and liquidity provision.

**What you can do:**
- Swap tokens (e.g., AVAX → USDC)
- Add liquidity to earn trading fees
- Remove liquidity to get your tokens back
- Check token prices

**Common functions:**
- swapExactAVAXForTokens: Swap exact AVAX for tokens
- swapExactTokensForTokens: Swap exact tokens for other tokens
- addLiquidity: Add token pairs to earn fees
- removeLiquidity: Withdraw your liquidity
- getAmountsOut: Calculate output amounts for a swap""",

        "ERC721_NFT": """This is an ERC721 NFT (Non-Fungible Token) contract. Each token is unique.

**What you can do:**
- Check who owns an NFT: ownerOf(tokenId)
- Transfer NFTs: safeTransferFrom(from, to, tokenId)
- View NFT metadata: tokenURI(tokenId)
- Approve NFT transfers: approve(to, tokenId)

**Common functions:**
- ownerOf: Check who owns a specific NFT
- tokenURI: Get the metadata URL for an NFT
- safeTransferFrom: Safely transfer an NFT to another address
- approve: Allow someone to transfer a specific NFT""",

        "UNKNOWN": """This contract's type could not be automatically identified. 

**Available functions:**
{}

You can ask me about specific functions or use them directly."""
    }
    
    explanation = explanations.get(contract_type, explanations["UNKNOWN"])
    
    if contract_type == "UNKNOWN":
        # List all available functions
        function_list = "\n".join([f"- {fn}" for fn in functions[:20]])  # Limit to 20
        explanation = explanation.format(function_list)
    
    return explanation