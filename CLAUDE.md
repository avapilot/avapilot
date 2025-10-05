# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AvaPilot is a B2B AI agent system designed to simplify dApp interactions through natural language. It uses an Orchestrator Agent model with LangGraph as its core framework for managing conversational AI workflows.

## Development Commands

### Setup and Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start Flask web server
python app.py  # or flask run
```

## Architecture Overview

The system follows an Orchestrator Model with these key components:

1. **Orchestrator Agent**: Central brain that manages conversations, maintains state, and coordinates tool execution using LangGraph
2. **Agent Toolkit**: Collection of specialized tools:
   - **dApp Tool**: Analyzes and explains dApps (`get_dapp_explanation`, `get_dapp_schema`)
   - **Action Tool**: Constructs blockchain transactions (`generate_transaction`)
   - **Web Tool**: Fetches and processes web content (`browse_webpage`)
3. **Frontend Widget**: User interface that sends messages and handles transaction signing

## Key Technical Details

- **Framework**: LangGraph for orchestration, Flask for web server
- **Blockchain**: Web3.py for Ethereum/Avalanche interactions
- **AI**: Google Generative AI and Google Cloud AI Platform integration
- **API**: Single `/chat` endpoint for conversational interactions
- **Response Types**: Text explanations or unsigned transaction objects

## Data Flow

1. User sends natural language message via Frontend Widget
2. Orchestrator processes with ASR → NLU → Planning → Tool Selection
3. Tools execute and return results to Orchestrator
4. Orchestrator sends response (text or transaction) back to Frontend
5. For transactions, Frontend prompts wallet for non-custodial signing

## Important Files and Directories

- `requirements.txt`: Python dependencies including LangGraph, Flask, web3, and Google AI libraries
- `docs/`: Technical documentation including architecture details and API specifications
- API follows OpenAPI 3.0 specification with conversation state management