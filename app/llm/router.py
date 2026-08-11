import os

from litellm import completion

from app.config import settings

# Maps our simple provider names (from .env) to the actual litellm
# model strings, which are provider-prefixed. Centralizing this here
# means the rest of the app only ever says "groq" or "gemini", never
# a raw model string.
PROVIDER_MODEL_MAP = {
    "groq": "groq/llama-3.3-70b-versatile",
    "gemini": "gemini/gemini-2.0-flash",
    "openai": "gpt-4o",
}


def _configure_environment():
    """
    litellm reads provider API keys from environment variables with
    specific expected names (GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY).
    Our Pydantic settings already loaded them from .env into `settings`,
    so here we just make sure they're also set as real OS env vars,
    since that's what litellm looks for under the hood.
    """
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key


_configure_environment()


def get_completion(
    prompt: str,
    system_prompt: str | None = None,
    provider: str | None = None,
    temperature: float = 0.1,
) -> str:
    """
    Provider-agnostic completion call.

    provider: "groq" | "gemini" | "openai". Defaults to settings.default_llm_provider.
    temperature: kept low by default (0.1) since SQL generation should be
    deterministic and precise, not creative.
    """
    chosen_provider = provider or settings.default_llm_provider
    if chosen_provider not in PROVIDER_MODEL_MAP:
        raise ValueError(
            f"Unknown provider '{chosen_provider}'. "
            f"Valid options: {list(PROVIDER_MODEL_MAP.keys())}"
        )

    model = PROVIDER_MODEL_MAP[chosen_provider]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = completion(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    return response.choices[0].message.content