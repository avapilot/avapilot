"""
Centralized Agent Configuration
Single source of truth for all agent settings
"""

import os
from typing import Dict, Any, Literal
from google.auth import default
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from langchain_openai import ChatOpenAI
from langchain_google_vertexai import ChatVertexAI

class AgentConfig:
    """Centralized configuration for all agents"""
    
    # ========================================
    # MODEL CONFIGURATION
    # ========================================
    
    # ✅ SIMPLIFIED: Direct per-agent model selection (no confusing DEFAULT_MODEL)
    AGENT_MODELS: Dict[str, str] = {
        "chat_agent": os.getenv("CHAT_MODEL", "gemini"),
        "transaction_agent": os.getenv("TRANSACTION_MODEL", "qwen"),
        "analysis_agent": os.getenv("ANALYSIS_MODEL", "gemini"),
    }
    
    GCP_PROJECT: str = os.getenv("GCP_PROJECT", "avapilot")
    GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "key.json")
    
    # Model-specific settings
    MODELS: Dict[str, Dict[str, Any]] = {
        "openai": {
            "region": "global",
            "endpoint": "aiplatform.googleapis.com",
            "model_name": "openai/gpt-oss-120b-maas",
            "temperature": 0.3,
        },
        "qwen": {
            "region": "us-south1",
            "endpoint": "us-south1-aiplatform.googleapis.com",
            "model_name": "qwen/qwen3-235b-a22b-instruct-2507-maas",
            "temperature": 0.3,
        },
        "gemini": {
            "region": "global",
            "location": "global",
            "model_name": "gemini-2.5-flash",
            "temperature": 0.3,
            "max_tokens": 8192,
        }
    }
    
    # ✅ Per-agent temperature overrides
    AGENT_TEMPERATURES: Dict[str, float] = {
        "chat_agent": 0.3,
        "transaction_agent": 0.1,    # More deterministic
        "analysis_agent": 0.2,
    }
    
    # ========================================
    # RECURSION & ITERATION LIMITS
    # ========================================
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
    
    # ========================================
    # MEMORY CONFIGURATION
    # ========================================
    MESSAGE_TRIM_LIMIT: int = int(os.getenv("MESSAGE_TRIM_LIMIT", "50"))
    MESSAGE_HISTORY_LIMIT: int = int(os.getenv("MESSAGE_HISTORY_LIMIT", "100"))
    
    # ========================================
    # RATE LIMITING
    # ========================================
    RATE_LIMITS: Dict[str, Dict[str, int]] = {
        "free": {
            "requests_per_minute": int(os.getenv("FREE_RPM", "20")),
            "requests_per_day": int(os.getenv("FREE_RPD", "500"))
        },
        "paid": {
            "requests_per_minute": int(os.getenv("PAID_RPM", "100")),
            "requests_per_day": int(os.getenv("PAID_RPD", "10000"))
        }
    }
    
    # ========================================
    # VALIDATION
    # ========================================
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
    MAX_CONVERSATION_ID_LENGTH: int = 100
    MAX_API_KEY_LENGTH: int = 100
    
    # ========================================
    # LOGGING & MONITORING
    # ========================================
    ERROR_TRACKING_ENABLED: bool = True
    METRICS_ENABLED: bool = True
    VERBOSE_LOGGING: bool = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"
    
    # ========================================
    # ✅ MODEL CREATION METHODS
    # ========================================
    
    @classmethod
    def _get_credentials(cls):
        """Get Google Cloud credentials (shared logic)"""
        credentials_path = cls.GOOGLE_CREDENTIALS_PATH
        
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            print(f"[AUTH] Using service account from {credentials_path}")
        else:
            credentials, _ = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            print(f"[AUTH] Using default credentials (Cloud Run)")
        
        credentials.refresh(Request())
        return credentials
    
    @classmethod
    def create_model(cls, agent_name: str, tools: list = None, structured_output=None):
        """
        Creates a configured LLM model for the specified agent.
        
        Args:
            agent_name: Name of agent (chat_agent, transaction_agent, etc.)
            tools: Optional list of tools to bind
            structured_output: Optional Pydantic model for structured output
            
        Returns:
            Configured LLM model instance
        """
        # ✅ SIMPLIFIED: Get agent's model (no DEFAULT_MODEL fallback)
        model_choice = cls.AGENT_MODELS.get(agent_name)
        
        if not model_choice:
            raise ValueError(f"Unknown agent: {agent_name}. Must be one of: {list(cls.AGENT_MODELS.keys())}")
        
        if model_choice not in cls.MODELS:
            raise ValueError(f"Unknown model: {model_choice}. Must be one of: {list(cls.MODELS.keys())}")
        
        model_config = cls.MODELS[model_choice].copy()
        
        # Apply agent-specific temperature
        if agent_name in cls.AGENT_TEMPERATURES:
            model_config['temperature'] = cls.AGENT_TEMPERATURES[agent_name]
        
        print(f"[{agent_name.upper()}] Model: {model_choice} ({model_config['model_name']})")
        print(f"[{agent_name.upper()}] Temperature: {model_config['temperature']}")
        
        # ========================================
        # CREATE MODEL BASED ON CHOICE
        # ========================================
        
        if model_choice == "openai":
            credentials = cls._get_credentials()
            base_url = f"https://{model_config['endpoint']}/v1/projects/{cls.GCP_PROJECT}/locations/{model_config['region']}/endpoints/openapi"
            
            model = ChatOpenAI(
                base_url=base_url,
                api_key=credentials.token,
                model=model_config['model_name'],
                temperature=model_config['temperature'],
            )
            
        elif model_choice == "qwen":
            credentials = cls._get_credentials()
            base_url = f"https://{model_config['endpoint']}/v1/projects/{cls.GCP_PROJECT}/locations/{model_config['region']}/endpoints/openapi"
            
            model = ChatOpenAI(
                base_url=base_url,
                api_key=credentials.token,
                model=model_config['model_name'],
                temperature=model_config['temperature'],
            )
            
        else:  # gemini
            model = ChatVertexAI(
                model=model_config['model_name'],
                project=cls.GCP_PROJECT,
                location=model_config['location'],
                temperature=model_config['temperature'],
                max_tokens=model_config.get('max_tokens', 8192)
            )
        
        # ========================================
        # BIND TOOLS & STRUCTURED OUTPUT
        # ========================================
        
        if tools:
            model = model.bind_tools(tools)
        
        if structured_output:
            model = model.with_structured_output(structured_output)
        
        return model
    
    # ========================================
    # EXISTING HELPER METHODS
    # ========================================
    
    @classmethod
    def get_recursion_limit(cls, agent_name: str) -> int:
        """Get recursion limit for specific agent"""
        return cls.RECURSION_LIMITS.get(agent_name, 50)
    
    @classmethod
    def get_iteration_limit(cls, agent_name: str) -> int:
        """Get iteration limit for specific agent"""
        return cls.ITERATION_LIMITS.get(agent_name, 40)
    
    @classmethod
    def print_config(cls):
        """Print current configuration (for debugging)"""
        print("\n" + "="*60)
        print("AGENT CONFIGURATION")
        print("="*60)
        print(f"Agent Models: {cls.AGENT_MODELS}")
        print(f"Agent Temperatures: {cls.AGENT_TEMPERATURES}")
        print(f"Project: {cls.GCP_PROJECT}")
        print(f"Recursion Limits: {cls.RECURSION_LIMITS}")
        print(f"Iteration Limits: {cls.ITERATION_LIMITS}")
        print(f"Message Trim: {cls.MESSAGE_TRIM_LIMIT}")
        print(f"Rate Limits: {cls.RATE_LIMITS}")
        print("="*60 + "\n")


# Export singleton instance
config = AgentConfig()