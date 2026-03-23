"""AvaPilot Service Registry — register dApps, auto-generate MCP tools."""

from .store import ServiceRegistry
from .models import Service, ServiceContract

__all__ = ["ServiceRegistry", "Service", "ServiceContract"]
