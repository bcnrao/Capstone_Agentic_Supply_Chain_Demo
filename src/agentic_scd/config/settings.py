"""Environment-backed configuration.

Loads variables from a ``.env`` file (via ``python-dotenv``) and the process
environment. Every variable is documented in ``.env.example``. Missing optional
variables degrade gracefully — in particular, with no ``GROQ_API_KEY`` the LLM
wrapper falls back to a deterministic mock so the scaffold runs fully offline.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

# Default large reasoning/generation model — Groq GPT-OSS-120B (see
# specs/tech-stack.md). ``openai/gpt-oss-120b`` is the Groq API model id.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean-ish environment variable ("1/true")."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true"}


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration."""

    groq_api_key: str | None
    groq_model: str
    use_mock_llm: bool

    @property
    def llm_is_mock(self) -> bool:
        """True when no real provider call should be made.

        Either the user forced mock mode, or no API key is configured.
        """
        return self.use_mock_llm or not self.groq_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from ``.env`` + the environment.

    ``load_dotenv`` does not override variables already set in the real
    environment, so explicit env vars win over the ``.env`` file.
    """
    load_dotenv()
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        use_mock_llm=env_flag("USE_MOCK_LLM", default=False),
    )
