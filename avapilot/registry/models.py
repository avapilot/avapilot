"""Data models for the service registry."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ServiceContract:
    """A single contract within a registered service."""
    address: str
    chain: str
    label: str  # e.g. "router", "factory", "token"
    abi: list = field(default_factory=list)
    contract_type: str = ""  # "DEX_ROUTER", "ERC20_TOKEN", "LENDING", etc.
    read_functions: list[str] = field(default_factory=list)
    write_functions: list[str] = field(default_factory=list)


@dataclass
class Service:
    """A registered service (one or more contracts) on the platform."""
    id: str
    name: str
    description: str = ""
    category: str = ""  # "DeFi", "NFT", "Gaming", "Token", "Infrastructure"
    contracts: list[ServiceContract] = field(default_factory=list)
    owner: str = ""
    website: str = ""
    created_at: float = 0.0
    total_read_tools: int = 0
    total_write_tools: int = 0
