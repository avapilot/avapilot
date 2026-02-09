"""
Contract Knowledge Pipeline — analyze a contract and push knowledge to ElevenLabs agent.

Usage:
    uv run python backend/eleven_agent/knowledge_pipeline.py 0xContractAddress
"""

import os
import sys
import json
import requests as http_requests

# Add orchestrator to path for reuse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from dotenv import load_dotenv

load_dotenv()

from network_config import NETWORK_NAME, EXPLORER_API_URL, EXPLORER_API_KEY
from tools import get_contract_abi_impl, get_source_code_impl
from contract_analyzer import identify_contract_type

# Local storage for knowledge docs
KB_DIR = os.path.join(os.path.dirname(__file__), "knowledge_base")


def analyze_contract(contract_address: str) -> str:
    """Analyze a contract and return a knowledge document as text."""

    print(f"[KB] Analyzing {contract_address} on {NETWORK_NAME}...")

    # 1. Fetch ABI
    abi_json = get_contract_abi_impl(contract_address)
    if abi_json.startswith("Error"):
        raise RuntimeError(f"Failed to fetch ABI: {abi_json}")

    abi = json.loads(abi_json)
    contract_type = identify_contract_type(abi)

    # 2. Extract functions
    functions = []
    for item in abi:
        if item.get("type") != "function":
            continue
        inputs = ", ".join(f"{i['type']} {i.get('name', '')}" for i in item.get("inputs", []))
        mutability = item.get("stateMutability", "nonpayable")
        functions.append(f"  - {item['name']}({inputs}) [{mutability}]")

    events = [
        item["name"] for item in abi if item.get("type") == "event"
    ]

    # 3. Try to get source code
    source_code = get_source_code_impl(contract_address)
    has_source = source_code and not source_code.startswith("Error")

    # 4. Build knowledge doc
    doc = f"""# Smart Contract Knowledge: {contract_address}

## Network
{NETWORK_NAME}

## Contract Type
{contract_type['type'].replace('_', ' ').title()} (confidence: {int(contract_type['confidence'] * 100)}%)

## Functions ({len(functions)})
{chr(10).join(functions)}

## Events ({len(events)})
{chr(10).join(f'  - {e}' for e in events)}

## Verification
{"Verified — source code available" if has_source else "Unverified — ABI only"}
"""

    if has_source:
        truncated = source_code[:8000] if len(source_code) > 8000 else source_code
        doc += f"""
## Source Code (truncated)
```solidity
{truncated}
```
"""

    print(f"[KB] Generated {len(doc)} chars of knowledge")
    return doc


def save_local(contract_address: str, knowledge_text: str) -> str:
    """Save knowledge doc as .md file locally."""
    os.makedirs(KB_DIR, exist_ok=True)
    short = f"{contract_address[:6]}_{contract_address[-4:]}"
    filepath = os.path.join(KB_DIR, f"{short}.md")
    with open(filepath, "w") as f:
        f.write(knowledge_text)
    print(f"[KB] Saved locally: {filepath}")
    return filepath


def push_to_elevenlabs(
    contract_address: str,
    knowledge_text: str,
    agent_id: str = None,
) -> str:
    """Push knowledge doc to ElevenLabs agent via REST API."""

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key or api_key == "ROTATE_ME":
        raise RuntimeError("Set ELEVENLABS_API_KEY in .env")

    agent_id = agent_id or os.getenv("ELEVENLABS_AGENT_ID")
    if not agent_id:
        raise RuntimeError("Set ELEVENLABS_AGENT_ID in .env")

    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    base = "https://api.elevenlabs.io"

    short_addr = f"{contract_address[:6]}...{contract_address[-4:]}"
    doc_name = f"Contract: {short_addr}"

    # 1. Create document from text
    print(f"[KB] Creating document '{doc_name}'...")
    resp = http_requests.post(
        f"{base}/v1/convai/knowledge-base/text",
        headers=headers,
        json={"text": knowledge_text, "name": doc_name},
    )
    resp.raise_for_status()
    doc_id = resp.json()["id"]
    print(f"[KB] Created document: {doc_id}")

    # 2. Get current agent knowledge base
    print(f"[KB] Fetching agent {agent_id}...")
    resp = http_requests.get(f"{base}/v1/convai/agents/{agent_id}", headers=headers)
    resp.raise_for_status()
    agent_data = resp.json()

    existing_kb = []
    try:
        kb_list = agent_data["conversation_config"]["agent"]["prompt"]["knowledge_base"]
        existing_kb = [{"id": kb["id"], "type": kb["type"], "name": kb["name"]} for kb in kb_list]
    except (KeyError, TypeError):
        pass

    existing_kb.append({"id": doc_id, "type": "text", "name": doc_name})

    # 3. Patch agent with updated knowledge base
    print(f"[KB] Linking {len(existing_kb)} docs to agent...")
    resp = http_requests.patch(
        f"{base}/v1/convai/agents/{agent_id}",
        headers=headers,
        json={
            "conversation_config": {
                "agent": {
                    "prompt": {
                        "knowledge_base": existing_kb,
                    }
                }
            }
        },
    )
    if resp.status_code >= 400:
        print(f"[KB] ERROR: {resp.status_code} — {resp.text}")
        resp.raise_for_status()

    print(f"[KB] Agent updated — {len(existing_kb)} knowledge docs linked")
    return doc_id


def run(contract_address: str, agent_id: str = None) -> dict:
    """Full pipeline: analyze contract → save locally → push to ElevenLabs."""
    knowledge_text = analyze_contract(contract_address)
    local_path = save_local(contract_address, knowledge_text)
    doc_id = push_to_elevenlabs(contract_address, knowledge_text, agent_id)
    return {
        "document_id": doc_id,
        "contract": contract_address,
        "local_file": local_path,
        "chars": len(knowledge_text),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python backend/eleven_agent/knowledge_pipeline.py 0xContractAddress")
        sys.exit(1)

    addr = sys.argv[1]
    agent = sys.argv[2] if len(sys.argv) > 2 else None
    result = run(addr, agent)
    print(f"\nDone: {json.dumps(result, indent=2)}")
