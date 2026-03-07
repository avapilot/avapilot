"""Pydantic models for marketplace listings."""

from pydantic import BaseModel
from typing import Optional
import time
import uuid


class ListingCreate(BaseModel):
    name: str
    description: str = ""
    contracts: list[str] = []
    chain: str = "avalanche"
    repo_url: str = ""
    tags: list[str] = []
    contract_type: str = ""
    read_tools: int = 0
    write_tools: int = 0


class Listing(ListingCreate):
    id: str = ""
    created_at: float = 0
    upvotes: int = 0
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = time.time()
