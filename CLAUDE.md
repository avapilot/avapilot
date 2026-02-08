# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AvaPilot is a B2B AI agent system that simplifies dApp interactions through natural language. It uses an Orchestrator Agent model with LangGraph for managing conversational AI workflows on Avalanche.

## Development Commands

### Setup and Dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Terminal 1 - AI Agent (port 8080)
export GOOGLE_APPLICATION_CREDENTIALS="key.json"
uv run python backend/orchestrator/main.py

# Terminal 2 - Frontend dev server (port 8000)
python3 serve.py

# Terminal 3 - Open test page
open http://localhost:8000/test-widget-local.html
```

### Testing
```bash
bash test_error_tracking.sh
bash test_message_trimming.sh
bash test_rate_limiting.sh
```

## Architecture Overview

Single Orchestrator Agent with tool-based system (not multi-agent):

1. **Orchestrator Agent** (`chat_agent.py`): Manages conversations via LangGraph StateGraph, persists state to Firestore
2. **Transaction Agent** (`transaction_agent.py`): Sub-agent for planning blockchain transactions using structured output (Pydantic schemas)
3. **Contract Analysis Agent** (`contract_analysis_agent.py`): Deep contract inspection with source code examination
4. **Agent Toolkit** (`tools.py`): Blockchain tools — `read_contract_function`, `generate_blockchain_transaction`, `analyze_contract`, `explore_contract_state`, `get_token_address`, `get_contract_abi`
5. **Frontend Widget** (`frontend/widget/`): Embeddable `<script>` tag, ethers.js wallet integration, non-custodial signing

## Key Technical Details

- **Framework**: LangGraph (orchestration) + Flask (web server, port 8080)
- **LLM Models**: Gemini 2.5 Flash (chat), Qwen 3 235B (transactions), OpenAI GPT (fallback) — all via Vertex AI
- **Blockchain**: Web3.py on Avalanche Fuji Testnet (RPC: `api.avax-test.network`)
- **Storage**: Firestore for conversation checkpoints, error logs, and metrics
- **API**: Single `POST /chat` endpoint — returns text or unsigned transaction objects
- **Frontend**: Vanilla JS widget + HTML/CSS, no build step

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | `key.json` | GCP service account path |
| `CHAT_MODEL` | `gemini` | Model for chat agent (gemini/qwen/openai) |
| `TRANSACTION_MODEL` | `qwen` | Model for transaction planning |
| `ANALYSIS_MODEL` | `gemini` | Model for contract analysis |
| `GCP_PROJECT` | `avapilot` | Google Cloud project ID |
| `VERBOSE_LOGGING` | `false` | Enable detailed logging |

## Important Files

### Backend (`backend/orchestrator/`)
- `main.py` — Flask server, `/chat` endpoint, validation, rate limiting
- `chat_agent.py` — Core orchestrator, LangGraph state management
- `transaction_agent.py` — Transaction planning with ABI discovery
- `tools.py` — All blockchain tool implementations
- `agent_config.py` — Centralized config, model factory, rate limit tiers
- `contract_analysis_agent.py` — Deep contract analysis with LLM
- `schemas.py` — Pydantic models
- `rate_limiter.py` — Per-user rate limiting (IP + API key)
- `error_tracker.py` — Error logging to Cloud Logging

### Frontend (`frontend/`)
- `widget/widget.js` — Embeddable widget loader (auto-detects prod vs localhost)
- `widget/widget-chat.html` — Chat UI (iframe-based)
- `test-widget-local.html` — Local development test page

### Config
- `requirements.txt` — Python dependencies
- `key.json` — GCP service account credentials (not committed to public repos)

## API Request/Response

```json
// POST /chat
{
  "message": "swap 1 AVAX for USDC",
  "conversation_id": "conv_12345",
  "context": {
    "user_address": "0x...",
    "allowed_contract": "0x..." or ["0x...", "0x..."],
    "api_key": "avapilot_free_alpha"
  }
}

// Response
{
  "conversation_id": "conv_12345",
  "response_type": "text|transaction|error",
  "payload": {
    "message": "...",
    "transaction": { "to": "0x...", "data": "0x...", "value": "0x..." }
  }
}
```

## Security Notes

- Contract scope enforcement: transactions blocked if target not in `allowed_contract`
- XSS/injection pattern detection on all inputs
- Ethereum address format validation
- Rate limiting: free tier (20 req/min, 500/day), paid tier (100 req/min, 10k/day)
- Non-custodial: server never holds private keys, user signs in wallet
