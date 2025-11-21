# -*- coding: utf-8 -*-
"""
Central Port Configuration Module

This module provides a single source of truth for all service port configurations.
All services should import from this module instead of hardcoding port numbers.

Environment Variables (with defaults):
- FRONTEND_PORT=3000          # Vite dev server
- BACKEND_PORT=8087           # FastAPI main backend
- ARCH_TEAM_PORT=8000         # Arch team Flask service
- AGENT_WORKER_PORT=8090      # Distributed agent worker
- QDRANT_PORT=6333            # Qdrant vector database (primary)
- QDRANT_PORT_FALLBACK=6401   # Qdrant fallback port (docker-compose)

Legacy variable support (deprecated, will be removed):
- API_PORT → BACKEND_PORT
- APP_PORT → ARCH_TEAM_PORT
- PORT → AGENT_WORKER_PORT
"""
from __future__ import annotations
import os
import warnings
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


class ServicePorts:
    """Central configuration for all service ports with environment variable support."""

    def __init__(self):
        # Frontend
        self.FRONTEND_PORT = self._get_port("FRONTEND_PORT", 3000)

        # Backend services with legacy fallbacks
        self.BACKEND_PORT = self._get_port_with_legacy("BACKEND_PORT", "API_PORT", 8087)
        self.ARCH_TEAM_PORT = self._get_port_with_legacy("ARCH_TEAM_PORT", "APP_PORT", 8000)
        self.AGENT_WORKER_PORT = self._get_port_with_legacy("AGENT_WORKER_PORT", "PORT", 8090)

        # Qdrant vector database
        self.QDRANT_PORT = self._get_port("QDRANT_PORT", 6333)
        self.QDRANT_PORT_FALLBACK = self._get_port("QDRANT_PORT_FALLBACK", 6401)

        # Host configurations
        self.QDRANT_HOST = os.environ.get("QDRANT_HOST", "http://localhost")
        self.QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost")  # Legacy

        # Environment detection
        self.CONFIG_ENV = os.environ.get("CONFIG_ENV", "dev")  # dev|docker-compose|production

        # Build service URLs
        self._build_service_urls()

    def _get_port(self, var_name: str, default: int) -> int:
        """Get port from environment with default fallback."""
        value = os.environ.get(var_name)
        if value:
            try:
                return int(value)
            except ValueError:
                warnings.warn(f"Invalid port value for {var_name}={value}, using default {default}")
        return default

    def _get_port_with_legacy(self, new_var: str, legacy_var: str, default: int) -> int:
        """Get port with legacy variable support and deprecation warning."""
        # Check new variable first
        value = os.environ.get(new_var)
        if value:
            try:
                return int(value)
            except ValueError:
                warnings.warn(f"Invalid port value for {new_var}={value}, checking legacy variable")

        # Check legacy variable
        legacy_value = os.environ.get(legacy_var)
        if legacy_value:
            warnings.warn(
                f"Using deprecated environment variable {legacy_var}. "
                f"Please migrate to {new_var}. Support for {legacy_var} will be removed in a future version."
            )
            try:
                return int(legacy_value)
            except ValueError:
                warnings.warn(f"Invalid port value for {legacy_var}={legacy_value}, using default {default}")

        return default

    def _build_service_urls(self):
        """Build service URLs based on environment and port configuration."""
        if self.CONFIG_ENV == "docker-compose":
            # Docker compose uses container DNS names
            self.BACKEND_URL = f"http://backend:{self.BACKEND_PORT}"
            self.ARCH_TEAM_URL = f"http://arch_team:{self.ARCH_TEAM_PORT}"
            self.AGENT_WORKER_URL = f"http://agent_worker:{self.AGENT_WORKER_PORT}"
            self.FRONTEND_URL = f"http://frontend:{self.FRONTEND_PORT}"
            # Qdrant in docker-compose uses host.docker.internal or service name
            self.QDRANT_FULL_URL = f"{self.QDRANT_HOST}:{self.QDRANT_PORT}"
        elif self.CONFIG_ENV == "production":
            # Production uses environment-specific URLs
            self.BACKEND_URL = os.environ.get("BACKEND_BASE_URL", f"https://api.example.com:{self.BACKEND_PORT}")
            self.ARCH_TEAM_URL = os.environ.get("ARCH_TEAM_BASE_URL", f"https://mining.example.com:{self.ARCH_TEAM_PORT}")
            self.AGENT_WORKER_URL = os.environ.get("AGENT_WORKER_BASE_URL", f"http://worker:{self.AGENT_WORKER_PORT}")
            self.FRONTEND_URL = os.environ.get("FRONTEND_BASE_URL", f"https://app.example.com")
            self.QDRANT_FULL_URL = os.environ.get("QDRANT_FULL_URL", f"{self.QDRANT_HOST}:{self.QDRANT_PORT}")
        else:
            # Development uses localhost
            self.BACKEND_URL = f"http://localhost:{self.BACKEND_PORT}"
            self.ARCH_TEAM_URL = f"http://localhost:{self.ARCH_TEAM_PORT}"
            self.AGENT_WORKER_URL = f"http://localhost:{self.AGENT_WORKER_PORT}"
            self.FRONTEND_URL = f"http://localhost:{self.FRONTEND_PORT}"
            self.QDRANT_FULL_URL = self._compose_qdrant_url(self.QDRANT_URL, self.QDRANT_PORT)

    def _compose_qdrant_url(self, base_url: str, port: int) -> str:
        """
        Build a Qdrant URL with port if not already included.

        Examples:
          - http://localhost + 6333 -> http://localhost:6333
          - http://127.0.0.1 + 6401 -> http://127.0.0.1:6401
          - http://host:6333 + 6333 -> http://host:6333 (unchanged)
        """
        base = str(base_url or "http://localhost").rstrip("/")
        try:
            hostpart = base.split("://", 1)[-1]
            if ":" in hostpart:
                return base
            return f"{base}:{int(port)}"
        except Exception:
            return f"{base}:{int(port)}"

    def get_qdrant_url_with_fallback(self) -> str:
        """
        Get Qdrant URL with automatic fallback support.
        Returns primary URL, caller should handle fallback to QDRANT_PORT_FALLBACK on connection failure.
        """
        return self.QDRANT_FULL_URL

    def to_dict(self) -> Dict[str, any]:
        """Export port configuration as dictionary for logging/debugging."""
        return {
            "config_env": self.CONFIG_ENV,
            "ports": {
                "frontend": self.FRONTEND_PORT,
                "backend": self.BACKEND_PORT,
                "arch_team": self.ARCH_TEAM_PORT,
                "agent_worker": self.AGENT_WORKER_PORT,
                "qdrant": self.QDRANT_PORT,
                "qdrant_fallback": self.QDRANT_PORT_FALLBACK
            },
            "service_urls": {
                "backend": self.BACKEND_URL,
                "arch_team": self.ARCH_TEAM_URL,
                "agent_worker": self.AGENT_WORKER_URL,
                "frontend": self.FRONTEND_URL,
                "qdrant": self.QDRANT_FULL_URL
            }
        }

    def __repr__(self) -> str:
        return f"ServicePorts(env={self.CONFIG_ENV}, backend={self.BACKEND_PORT}, arch_team={self.ARCH_TEAM_PORT})"


# Global singleton instance
_ports_instance: Optional[ServicePorts] = None


def get_ports() -> ServicePorts:
    """Get the global ServicePorts singleton instance."""
    global _ports_instance
    if _ports_instance is None:
        _ports_instance = ServicePorts()
    return _ports_instance


# Convenience exports for backward compatibility
def get_backend_port() -> int:
    """Get the main backend port (FastAPI)."""
    return get_ports().BACKEND_PORT


def get_arch_team_port() -> int:
    """Get the arch_team service port (Flask)."""
    return get_ports().ARCH_TEAM_PORT


def get_qdrant_port() -> int:
    """Get the primary Qdrant port."""
    return get_ports().QDRANT_PORT


def get_qdrant_url() -> str:
    """Get the full Qdrant URL with port."""
    return get_ports().QDRANT_FULL_URL


# Module-level constants for simple imports
PORTS = get_ports()
