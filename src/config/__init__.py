"""Configuration management for Video Brain.

Handles loading and accessing environment variables and app settings.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


# Load .env file at import time
load_dotenv()


@dataclass
class OllamaConfig:
    """Configuration for Ollama integration."""
    
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.getenv("OLLAMA_MODEL", "llama2")
    timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "300"))
    
    def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            import requests
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


@dataclass
class AppConfig:
    """Main application configuration."""
    
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    temp_upload_dir: str = os.getenv("TEMP_UPLOAD_DIR", "temp_uploads")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    def __post_init__(self):
        """Ensure temp upload directory exists."""
        os.makedirs(self.temp_upload_dir, exist_ok=True)


# Global config instance
config = AppConfig()
