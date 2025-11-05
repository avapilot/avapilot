from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Union

class Transaction(BaseModel):
    """Blockchain transaction object"""
    to: str = Field(description="Contract address to interact with")
    value: str = Field(description="Amount of AVAX to send in hex (e.g., '0x2386f26fc10000')")
    data: str = Field(description="Encoded function call data")

class TransactionResult(BaseModel):
    """Result of transaction generation"""
    status: Literal["success", "error"] = Field(
        description="Whether transaction was successfully generated"
    )
    transaction: Optional[Transaction] = Field(
        default=None,
        description="Transaction object if successful, null if error"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is 'error'"
    )
    explanation: str = Field(
        description="Human-readable explanation of what the transaction does"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "transaction": {
                    "to": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
                    "value": "0x2386f26fc10000",
                    "data": "0xa2a1623d..."
                },
                "explanation": "Swap 0.01 AVAX for USDC with minimum output of 10 USDC"
            }
        }

class TransactionPlan(BaseModel):
    """
    Structured output for transaction planning
    """
    function_name: str = Field(
        description="Exact function name from contract ABI"
    )
    function_args: List[Union[int, str, bool, List[str]]] = Field(
        description="Function arguments matching ABI signature exactly. Use lists for array parameters."
    )
    value_in_avax: float = Field(
        default=0.0,
        description="Amount of AVAX to send with transaction (0.0 for non-payable)"
    )
    contract_address: str = Field(
        description="Target contract address"
    )
    reasoning: str = Field(
        description="Brief explanation of what this transaction does"
    )
    
    class Config:
        # ✅ ADD: Allow arbitrary types (fixes Gemini compatibility)
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "function_name": "swapExactAVAXForTokens",
                "function_args": [1, ["0x1d30...", "0x5425..."], "0xe2C3...", 1760049674],
                "value_in_avax": 0.01,
                "contract_address": "0x60aE...",
                "reasoning": "User wants to swap 0.01 AVAX for USDC using exact input swap"
            }
        }