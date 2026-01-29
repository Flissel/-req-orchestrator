"""
Configuration for MCP Server.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MCPConfig:
    """Configuration settings for the MCP server."""

    # Server settings
    server_name: str = "req-orchestrator"
    server_version: str = "1.0.0"

    # Backend connection (for REST+SSE operations)
    backend_url: str = field(default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8087"))
    arch_team_url: str = field(default_factory=lambda: os.getenv("ARCH_TEAM_URL", "http://localhost:8000"))

    # Timeouts
    request_timeout: int = 300  # 5 minutes for long operations
    stream_timeout: int = 600   # 10 minutes for streaming

    # LLM settings
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "gpt-4o-mini"))
    openrouter_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))

    # Qdrant settings (for direct imports)
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost"))
    qdrant_port: int = field(default_factory=lambda: int(os.getenv("QDRANT_PORT", "6401")))
    qdrant_api_key: Optional[str] = field(default_factory=lambda: os.getenv("QDRANT_API_KEY"))

    # Processing settings
    default_chunk_size: int = 1000
    default_chunk_overlap: int = 200
    validation_threshold: float = 0.7
    duplicate_threshold: float = 0.85
    max_concurrent_validations: int = 5

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Create config from environment variables."""
        return cls()

    def get_llm_api_key(self) -> Optional[str]:
        """Get the LLM API key (prefer OpenRouter, fallback to OpenAI)."""
        return self.openrouter_api_key or self.openai_api_key


# Global config instance
config = MCPConfig.from_env()
