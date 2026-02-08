"""
Centralized Agent Configuration
Single source of truth — provider auto-detected from API key.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


def _detect_provider() -> str:
    """Auto-detect LLM provider from available API keys."""
    explicit = os.getenv("LLM_PROVIDER")
    if explicit:
        return explicit.lower()
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise EnvironmentError(
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
    )


# Default models per provider
_MODEL_DEFAULTS = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
}


class AgentConfig:
    """Centralized configuration for all agents."""

    # --- Provider ---
    LLM_PROVIDER: str = _detect_provider()

    # --- Per-agent models (override via env) ---
    _default_model: str = _MODEL_DEFAULTS.get(LLM_PROVIDER, "claude-sonnet-4-5-20250929")

    AGENT_MODELS: Dict[str, str] = {
        "chat_agent": os.getenv("CHAT_MODEL", _default_model),
        "transaction_agent": os.getenv("TRANSACTION_MODEL", _default_model),
        "analysis_agent": os.getenv("ANALYSIS_MODEL", _default_model),
    }

    AGENT_TEMPERATURES: Dict[str, float] = {
        "chat_agent": 0.3,
        "transaction_agent": 0.1,
        "analysis_agent": 0.2,
    }

    # --- Limits ---
    RECURSION_LIMITS: Dict[str, int] = {
        "chat_agent": int(os.getenv("CHAT_RECURSION_LIMIT", "50")),
        "transaction_agent": int(os.getenv("TX_RECURSION_LIMIT", "50")),
        "analysis_agent": int(os.getenv("ANALYSIS_RECURSION_LIMIT", "50")),
    }
    ITERATION_LIMITS: Dict[str, int] = {
        "chat_agent": int(os.getenv("CHAT_ITERATION_LIMIT", "40")),
        "transaction_agent": int(os.getenv("TX_ITERATION_LIMIT", "40")),
        "analysis_agent": int(os.getenv("ANALYSIS_ITERATION_LIMIT", "40")),
    }

    # --- Memory ---
    MESSAGE_TRIM_LIMIT: int = int(os.getenv("MESSAGE_TRIM_LIMIT", "50"))
    MESSAGE_HISTORY_LIMIT: int = int(os.getenv("MESSAGE_HISTORY_LIMIT", "100"))

    # --- Rate limiting ---
    RATE_LIMITS: Dict[str, Dict[str, int]] = {
        "free": {
            "requests_per_minute": int(os.getenv("FREE_RPM", "20")),
            "requests_per_day": int(os.getenv("FREE_RPD", "500")),
        },
        "paid": {
            "requests_per_minute": int(os.getenv("PAID_RPM", "100")),
            "requests_per_day": int(os.getenv("PAID_RPD", "10000")),
        },
    }

    # --- Validation ---
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
    MAX_CONVERSATION_ID_LENGTH: int = 100
    MAX_API_KEY_LENGTH: int = 100

    # --- Logging ---
    VERBOSE_LOGGING: bool = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"

    # ============================
    # Model factory
    # ============================

    @classmethod
    def create_model(cls, agent_name: str, tools: list = None, structured_output=None):
        """Create a configured LLM for the given agent."""
        model_name = cls.AGENT_MODELS.get(agent_name)
        if not model_name:
            raise ValueError(f"Unknown agent: {agent_name}")

        temperature = cls.AGENT_TEMPERATURES.get(agent_name, 0.3)

        print(f"[{agent_name.upper()}] {cls.LLM_PROVIDER}:{model_name} temp={temperature}")

        if cls.LLM_PROVIDER == "anthropic":
            from langchain_anthropic import ChatAnthropic
            model = ChatAnthropic(
                model=model_name,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                temperature=temperature,
                max_tokens=8192,
            )
        elif cls.LLM_PROVIDER == "openai":
            from langchain_openai import ChatOpenAI
            model = ChatOpenAI(
                model=model_name,
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=temperature,
            )
        else:
            raise ValueError(f"Unknown provider: {cls.LLM_PROVIDER}")

        if tools:
            model = model.bind_tools(tools)
        if structured_output:
            model = model.with_structured_output(structured_output)

        return model

    # ============================
    # Helpers
    # ============================

    @classmethod
    def get_recursion_limit(cls, agent_name: str) -> int:
        return cls.RECURSION_LIMITS.get(agent_name, 50)

    @classmethod
    def get_iteration_limit(cls, agent_name: str) -> int:
        return cls.ITERATION_LIMITS.get(agent_name, 40)

    @classmethod
    def print_config(cls):
        print("\n" + "=" * 60)
        print("AGENT CONFIGURATION")
        print("=" * 60)
        print(f"Provider: {cls.LLM_PROVIDER}")
        print(f"Models: {cls.AGENT_MODELS}")
        print(f"Temperatures: {cls.AGENT_TEMPERATURES}")
        print(f"Recursion Limits: {cls.RECURSION_LIMITS}")
        print(f"Message Trim: {cls.MESSAGE_TRIM_LIMIT}")
        print(f"Rate Limits: {cls.RATE_LIMITS}")
        print("=" * 60 + "\n")


config = AgentConfig()
