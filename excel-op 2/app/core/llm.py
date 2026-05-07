"""LLM initialization for LangChain / CrewAI agents."""

from __future__ import annotations

from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import get_settings


def get_chat_llm(temperature: float = 0.0, model_name: Optional[str] = None) -> ChatOpenAI:
    """
    Return a ChatOpenAI instance configured from settings.

    For now we standardize on OpenAI; later this can be extended to support
    Anthropic or other providers behind a unified interface.
    """

    settings = get_settings()

    if settings.llm_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not configured. Set it in your environment or .env file."
            )
        return ChatOpenAI(
            model=model_name or settings.openrouter_chat_model,
            temperature=temperature,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            max_retries=10,
        )

    if settings.llm_provider == "nvidia":
        if not settings.nvidia_api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY not configured. Set it in your environment or .env file."
            )
        return ChatOpenAI(
            model=model_name or settings.nvidia_chat_model,
            temperature=temperature,
            api_key=settings.nvidia_api_key,
            base_url="https://integrate.api.nvidia.com/v1",
            max_retries=10,
            model_kwargs={"extra_body": {"chat_template_kwargs": {"thinking": True}}},
        )

    if settings.llm_provider == "ollama_cloud":
        if not settings.ollama_cloud_api_key:
            raise RuntimeError(
                "OLLAMA_CLOUD_API_KEY not configured. Set it in your environment or .env file."
            )
        return ChatOpenAI(
            model=model_name or settings.ollama_cloud_chat_model,
            temperature=temperature,
            api_key=settings.ollama_cloud_api_key,
            base_url="https://api.ollama.com/v1",
            max_retries=10,
        )

    if settings.llm_provider != "openai":
        # Simple fallback: still return OpenAI but this is a hook for future branching.
        # Agents can inspect settings.llm_provider if they need specific behaviour.
        pass

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not configured. Set it in your environment or .env file."
        )

    return ChatOpenAI(
        model=model_name or settings.openai_chat_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
        max_retries=10,
    )


def get_embedding_model() -> OpenAIEmbeddings:
    """Return an embedding model instance for use with LangChain tools."""

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not configured. Set it in your environment or .env file."
        )

    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )

