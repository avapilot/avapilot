from __future__ import annotations
"""SQLite-backed registry for marketplace listings."""

import json
import os
import sqlite3
import time
import uuid
from .models import Listing, ListingCreate

DB_PATH = os.path.join(os.path.dirname(__file__), "marketplace.db")


def _get_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            contracts TEXT DEFAULT '[]',
            chain TEXT DEFAULT 'avalanche',
            repo_url TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            contract_type TEXT DEFAULT '',
            read_tools INTEGER DEFAULT 0,
            write_tools INTEGER DEFAULT 0,
            upvotes INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def create_listing(data: ListingCreate, db_path: str = DB_PATH) -> Listing:
    conn = _get_db(db_path)
    listing = Listing(**data.model_dump())
    conn.execute(
        """INSERT INTO listings 
           (id, name, description, contracts, chain, repo_url, tags, contract_type, read_tools, write_tools, upvotes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            listing.id, listing.name, listing.description,
            json.dumps(listing.contracts), listing.chain, listing.repo_url,
            json.dumps(listing.tags), listing.contract_type,
            listing.read_tools, listing.write_tools, listing.upvotes, listing.created_at,
        ),
    )
    conn.commit()
    conn.close()
    return listing


def list_listings(chain: str = None, search: str = None, db_path: str = DB_PATH) -> list[Listing]:
    conn = _get_db(db_path)
    query = "SELECT * FROM listings"
    params = []
    conditions = []
    
    if chain:
        conditions.append("chain = ?")
        params.append(chain)
    if search:
        conditions.append("(name LIKE ? OR description LIKE ? OR tags LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY upvotes DESC, created_at DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    listings = []
    for row in rows:
        d = dict(row)
        d["contracts"] = json.loads(d["contracts"])
        d["tags"] = json.loads(d["tags"])
        listings.append(Listing(**d))
    return listings


def get_listing(listing_id: str, db_path: str = DB_PATH) -> "Listing | None":
    conn = _get_db(db_path)
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["contracts"] = json.loads(d["contracts"])
    d["tags"] = json.loads(d["tags"])
    return Listing(**d)


def upvote_listing(listing_id: str, db_path: str = DB_PATH) -> bool:
    conn = _get_db(db_path)
    cursor = conn.execute("UPDATE listings SET upvotes = upvotes + 1 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
