"""SQLite-backed service registry — register dApps, auto-generate tool definitions."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid

from .models import Service, ServiceContract


_DEFAULT_DB_DIR = os.path.join(os.path.expanduser("~"), ".avapilot")
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "registry.db")


class ServiceRegistry:
    """Persistent registry of services (dApps / contracts) on Avalanche."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    # ── public API ──────────────────────────────────────────────

    def _load_cached_abi(self, address: str, name: str = "") -> list:
        """Load ABI from cached files shipped with the package."""
        import json as _json
        from pathlib import Path
        abis_dir = Path(__file__).parent / "abis"
        if not abis_dir.exists():
            return []
        prefix = address[:10]
        for f in abis_dir.glob(f"{prefix}*.json"):
            try:
                return _json.loads(f.read_text())
            except Exception:
                continue
        return []

    def register(
        self,
        name: str,
        contract_address: str | None = None,
        chain: str = "avalanche",
        description: str = "",
        category: str = "",
        owner: str = "",
        website: str = "",
        contracts: list[dict] | None = None,
    ) -> Service:
        """Register a service. Auto-fetches ABI and analyses the contract(s).

        For a single contract:
            register("USDC", "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E")

        For multiple contracts:
            register("Trader Joe", contracts=[
                {"address": "0x...", "label": "router"},
                {"address": "0x...", "label": "factory"},
            ])
        """
        from avapilot.generator.abi_fetcher import fetch_contract_data
        from avapilot.generator.analyzer import identify_contract_type, categorize_functions

        # Normalise input — single address or list of dicts
        if contracts is None:
            if contract_address is None:
                raise ValueError("Provide contract_address or contracts list")
            contracts = [{"address": contract_address, "label": "main"}]

        service_contracts: list[ServiceContract] = []
        total_read = 0
        total_write = 0

        for entry in contracts:
            addr = entry["address"]
            label = entry.get("label", "main")
            api_key = os.getenv("SNOWTRACE_API_KEY", "")

            try:
                data = fetch_contract_data(addr, chain, api_key)
                abi = data["abi"]
            except Exception:
                # Fallback: try cached ABI from repo
                abi = self._load_cached_abi(addr, name)

            if abi:
                ct = identify_contract_type(abi)
                cats = categorize_functions(abi)
                read_names = [f["name"] for f in cats["read"]]
                write_names = [f["name"] for f in cats["write"]]
            else:
                ct = {"type": "UNKNOWN", "confidence": 0.0}
                read_names = []
                write_names = []

            sc = ServiceContract(
                address=addr,
                chain=chain,
                label=label,
                abi=abi,
                contract_type=ct["type"],
                read_functions=read_names,
                write_functions=write_names,
            )
            service_contracts.append(sc)
            total_read += len(read_names)
            total_write += len(write_names)

        service = Service(
            id=uuid.uuid4().hex[:8],
            name=name,
            description=description,
            category=category,
            contracts=service_contracts,
            owner=owner,
            website=website,
            created_at=time.time(),
            total_read_tools=total_read,
            total_write_tools=total_write,
        )

        self._save(service)
        return service

    def list_services(self, category: str | None = None, search: str | None = None) -> list[Service]:
        """List registered services, optionally filtered."""
        conn = self._connect()
        query = "SELECT data FROM services WHERE 1=1"
        params: list = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._deserialize(row[0]) for row in rows]

    def get_service(self, name_or_id: str) -> Service | None:
        """Get a service by name (case-insensitive) or ID."""
        conn = self._connect()
        row = conn.execute(
            "SELECT data FROM services WHERE id = ? OR LOWER(name) = LOWER(?)",
            (name_or_id, name_or_id),
        ).fetchone()
        conn.close()
        return self._deserialize(row[0]) if row else None

    def remove_service(self, name_or_id: str) -> bool:
        """Remove a service by name or ID."""
        conn = self._connect()
        cur = conn.execute(
            "DELETE FROM services WHERE id = ? OR LOWER(name) = LOWER(?)",
            (name_or_id, name_or_id),
        )
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def get_tools_for_service(self, name_or_id: str) -> list[dict]:
        """Get auto-generated tool definitions for a service."""
        service = self.get_service(name_or_id)
        if not service:
            return []
        return _build_tool_defs(service)

    # ── internals ───────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at REAL DEFAULT 0,
                data TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_services_name ON services (name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_services_category ON services (category)")
        conn.commit()
        conn.close()

    def _save(self, service: Service):
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO services (id, name, category, description, created_at, data) VALUES (?, ?, ?, ?, ?, ?)",
            (service.id, service.name, service.category, service.description, service.created_at, self._serialize(service)),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _serialize(service: Service) -> str:
        contracts = []
        for c in service.contracts:
            contracts.append({
                "address": c.address,
                "chain": c.chain,
                "label": c.label,
                "abi": c.abi,
                "contract_type": c.contract_type,
                "read_functions": c.read_functions,
                "write_functions": c.write_functions,
            })
        return json.dumps({
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "category": service.category,
            "contracts": contracts,
            "owner": service.owner,
            "website": service.website,
            "created_at": service.created_at,
            "total_read_tools": service.total_read_tools,
            "total_write_tools": service.total_write_tools,
        })

    @staticmethod
    def _deserialize(raw: str) -> Service:
        d = json.loads(raw)
        contracts = [
            ServiceContract(
                address=c["address"],
                chain=c["chain"],
                label=c["label"],
                abi=c["abi"],
                contract_type=c["contract_type"],
                read_functions=c["read_functions"],
                write_functions=c["write_functions"],
            )
            for c in d["contracts"]
        ]
        return Service(
            id=d["id"],
            name=d["name"],
            description=d["description"],
            category=d["category"],
            contracts=contracts,
            owner=d["owner"],
            website=d["website"],
            created_at=d["created_at"],
            total_read_tools=d["total_read_tools"],
            total_write_tools=d["total_write_tools"],
        )


# ── tool definition helpers ─────────────────────────────────────


def _build_tool_defs(service: Service) -> list[dict]:
    """Build MCP-style tool definitions from a service's contracts."""
    from avapilot.generator.analyzer import solidity_type_to_python, function_to_tool_name

    tools = []
    prefix = service.name.lower().replace(" ", "_").replace("-", "_")

    for contract in service.contracts:
        label_suffix = f" ({contract.label})" if len(service.contracts) > 1 else ""

        for item in contract.abi:
            if item.get("type") != "function":
                continue
            is_read = item.get("stateMutability") in ("view", "pure")
            func_name = item["name"]
            tool_name = f"{prefix}_{function_to_tool_name(func_name)}"

            params = []
            for inp in item.get("inputs", []):
                params.append({
                    "name": inp["name"] or f"arg{len(params)}",
                    "type": solidity_type_to_python(inp["type"]),
                    "solidity_type": inp["type"],
                })

            tools.append({
                "tool_name": tool_name,
                "function_name": func_name,
                "contract_address": contract.address,
                "chain": contract.chain,
                "label": contract.label,
                "is_read": is_read,
                "parameters": params,
                "description": f"{service.name}{label_suffix}: {func_name}",
                "abi_item": item,
            })
    return tools

