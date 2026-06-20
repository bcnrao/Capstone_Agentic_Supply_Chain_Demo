"""Single entrypoint for LLM completions.

Centralizing provider calls here lets later phases swap models without touching
agent logic (see specs/tech-stack.md). For Phase 0 the real Groq call is left as
a clearly marked seam; when no API key is configured (or ``USE_MOCK_LLM`` is set)
``completion`` returns a deterministic mock so the scaffold runs offline with no
network access and no exceptions.
"""

import hashlib

from groq import Groq

from agentic_scd.config import Settings, get_settings


def mock_completion(prompt: str) -> str:
    """Deterministic stand-in response derived from the prompt.

    Stable across runs (hash of the prompt) so tests and demos are repeatable.
    """
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
    return f"[MOCK-LLM:{digest}] offline mock for a {len(prompt)}-char prompt"


def completion(
    prompt: str,
    *,
    system: str | None = None,
    settings: Settings | None = None,
    **kwargs: object,
) -> str:
    """Return a completion for ``prompt``.

    Args:
        prompt: The user prompt.
        system: Optional system instruction (used by the real provider call).
        settings: Override settings (defaults to the cached process settings).
        **kwargs: Forwarded to the provider call in later phases (e.g. temperature).

    Returns:
        The model's text response, or a deterministic mock when no provider is
        configured.
    """
    settings = settings or get_settings()

    if settings.llm_is_mock:
        return mock_completion(prompt)

    # --- Real provider seam (wired up in Phase 3/7) -------------------------
    client = Groq(api_key=settings.groq_api_key)
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content or ""
