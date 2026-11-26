"""
FinSight AI — LLM provider layer

One interface for every supported large language model, with streaming and
native tool (function) calling:

    Provider   Transport                                   Needs
    ────────   ─────────────────────────────────────────   ──────────────────────
    gemini     OpenAI-compatible endpoint of Google AI      GOOGLE_API_KEY (free tier)
    groq       OpenAI-compatible endpoint                   GROQ_API_KEY (free tier)
    openai     OpenAI Chat Completions                      OPENAI_API_KEY
    ollama     Ollama native /api/chat (local, offline)     Ollama running + model pulled

Selection (LLM_PROVIDER=auto): cloud providers with a key first (better quality),
then local Ollama. If a provider fails before producing output, the next one is
tried. If none is available, callers fall back to the offline analyst.

Messages use a neutral internal format and are converted per transport:
    {"role": "system" | "user" | "assistant", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [{"id", "name", "arguments": dict}]}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str}
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger("finsight.llm")


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class Provider:
    name: str
    model: str
    base_url: str
    api_key: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"

    @property
    def is_local(self) -> bool:
        return self.name == "ollama"


# ── Runtime selection (changed from the Settings page, persisted to disk) ────

def _runtime_path():
    from pathlib import Path
    return Path(settings.model_storage_path).parent / "ai_settings.json"


def runtime_settings() -> dict:
    try:
        return json.loads(_runtime_path().read_text())
    except Exception:
        return {}


def save_runtime_settings(**values) -> dict:
    current = runtime_settings()
    current.update({k: v for k, v in values.items() if v is not None})
    _runtime_path().write_text(json.dumps(current, indent=2))
    return current


def ollama_model() -> str:
    return runtime_settings().get("ollama_model") or settings.ollama_model


def preferred_provider() -> str:
    return (runtime_settings().get("provider") or settings.llm_provider or "auto").lower()


# ── Discovery ────────────────────────────────────────────────────────────────

_ollama_state: Dict = {"at": 0.0, "models": None}


async def ollama_models(force: bool = False) -> Optional[List[str]]:
    """Installed Ollama models, or None if Ollama is not reachable (cached 20 s)."""
    if not force and time.monotonic() - _ollama_state["at"] < 20:
        return _ollama_state["models"]
    models = None
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception:
        models = None
    _ollama_state.update(at=time.monotonic(), models=models)
    return models


def _installed(models: List[str], wanted: str) -> bool:
    wanted = wanted.strip()
    return any(m == wanted or m == f"{wanted}:latest" for m in models)


# Cloud providers retire models regularly; if the configured one is gone, use the
# best available model from this preference list instead of failing.
GROQ_PREFERRED = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"]
_groq_state: Dict = {"at": 0.0, "model": None}


async def _resolve_groq_model() -> str:
    if time.monotonic() - _groq_state["at"] < 600 and _groq_state["model"]:
        return _groq_state["model"]
    model = settings.groq_model
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {settings.groq_api_key}"})
        if resp.status_code == 200:
            ids = {m["id"] for m in resp.json().get("data", []) if m.get("active", True)}
            if model not in ids:
                fallback = next((m for m in GROQ_PREFERRED if m in ids), None)
                if fallback:
                    logger.warning("Groq model %s is unavailable — using %s", model, fallback)
                    model = fallback
    except Exception:
        pass
    _groq_state.update(at=time.monotonic(), model=model)
    return model


async def available_providers() -> List[Provider]:
    pref = preferred_provider()
    if pref == "offline":
        return []
    found: List[Provider] = []
    if settings.google_api_key:
        found.append(Provider("gemini", settings.gemini_model, "https://generativelanguage.googleapis.com/v1beta/openai", settings.google_api_key))
    if settings.groq_api_key:
        found.append(Provider("groq", await _resolve_groq_model(), "https://api.groq.com/openai/v1", settings.groq_api_key))
    if settings.openai_api_key:
        found.append(Provider("openai", settings.openai_model, "https://api.openai.com/v1", settings.openai_api_key))
    models = await ollama_models()
    if models is not None and _installed(models, ollama_model()):
        found.append(Provider("ollama", ollama_model(), settings.ollama_base_url.rstrip("/")))
    if pref != "auto":
        found = [p for p in found if p.name == pref] + [p for p in found if p.name != pref]
    return found


async def status() -> dict:
    providers = await available_providers()
    models = await ollama_models()
    return {
        "active": providers[0].label if providers else None,
        "is_local": providers[0].is_local if providers else False,
        "providers": [p.label for p in providers],
        "mode": "llm" if providers else "offline_analyst",
        "preference": preferred_provider(),
        "ollama": {
            "reachable": models is not None,
            "model": ollama_model(),
            "installed_models": [m for m in (models or []) if "embed" not in m],
            "model_installed": bool(models and _installed(models, ollama_model())),
            "embedding_model": settings.ollama_embed_model,
            "embedding_model_installed": bool(models and _installed(models, settings.ollama_embed_model)),
        },
        "cloud_keys": {"gemini": bool(settings.google_api_key), "groq": bool(settings.groq_api_key), "openai": bool(settings.openai_api_key)},
    }


# ── Message conversion ───────────────────────────────────────────────────────

def _to_openai(messages: List[dict]) -> List[dict]:
    out = []
    for m in messages:
        if m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        elif m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content") or None,
                "tool_calls": [{"id": c["id"], "type": "function",
                                "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for c in m["tool_calls"]],
            })
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _to_ollama(messages: List[dict]) -> List[dict]:
    out = []
    for m in messages:
        if m["role"] == "tool":
            out.append({"role": "tool", "content": m["content"], "tool_name": m.get("name", "")})
        elif m.get("tool_calls"):
            out.append({"role": "assistant", "content": m.get("content") or "",
                        "tool_calls": [{"function": {"name": c["name"], "arguments": c["arguments"]}} for c in m["tool_calls"]]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _parse_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ── Streaming ────────────────────────────────────────────────────────────────

async def stream_chat(
    provider: Provider,
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> AsyncIterator[dict]:
    """Yield {"type": "token", "text"} events, then one {"type": "tool_calls", "calls"} or {"type": "end"}."""
    if provider.name == "ollama":
        gen = _stream_ollama(provider, messages, tools, temperature, max_tokens)
    else:
        gen = _stream_openai(provider, messages, tools, temperature, max_tokens)
    async for event in gen:
        yield event


async def _stream_openai(provider, messages, tools, temperature, max_tokens):
    body = {"model": provider.model, "messages": _to_openai(messages), "stream": True,
            "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        body.update(tools=tools, tool_choice="auto")
    calls: Dict[int, dict] = {}
    timeout = httpx.Timeout(settings.llm_timeout_seconds, connect=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{provider.base_url}/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {provider.api_key}"}) as resp:
            if resp.status_code != 200:
                detail = (await resp.aread()).decode(errors="ignore")[:300]
                raise LLMError(f"{provider.label} HTTP {resp.status_code}: {detail}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield {"type": "token", "text": delta["content"]}
                    for tc in delta.get("tool_calls") or []:
                        slot = calls.setdefault(tc.get("index", len(calls)), {"id": None, "name": "", "arguments": ""})
                        slot["id"] = tc.get("id") or slot["id"]
                        fn = tc.get("function") or {}
                        slot["name"] += fn.get("name") or ""
                        slot["arguments"] += fn.get("arguments") or ""
    if calls:
        yield {"type": "tool_calls", "calls": [
            {"id": c["id"] or f"call_{uuid.uuid4().hex[:8]}", "name": c["name"], "arguments": _parse_args(c["arguments"])}
            for _, c in sorted(calls.items()) if c["name"]
        ]}
    else:
        yield {"type": "end"}


async def _stream_ollama(provider, messages, tools, temperature, max_tokens):
    body = {
        "model": provider.model,
        "messages": _to_ollama(messages),
        "stream": True,
        "keep_alive": "30m",
        "options": {"temperature": temperature, "num_ctx": settings.ollama_num_ctx, "num_predict": max_tokens},
    }
    if tools:
        body["tools"] = tools
    calls: List[dict] = []
    timeout = httpx.Timeout(settings.llm_timeout_seconds * 3, connect=5)  # local models load into memory on first use
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{provider.base_url}/api/chat", json=body) as resp:
            if resp.status_code != 200:
                detail = (await resp.aread()).decode(errors="ignore")[:300]
                raise LLMError(f"{provider.label} HTTP {resp.status_code}: {detail}")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise LLMError(f"{provider.label}: {chunk['error']}")
                msg = chunk.get("message") or {}
                if msg.get("content"):
                    yield {"type": "token", "text": msg["content"]}
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        calls.append({"id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}", "name": fn["name"],
                                      "arguments": _parse_args(fn.get("arguments"))})
                if chunk.get("done"):
                    break
    yield {"type": "tool_calls", "calls": calls} if calls else {"type": "end"}


async def complete(messages: List[dict], max_tokens: int = 800, temperature: float = 0.3) -> Tuple[Optional[str], Optional[str]]:
    """Non-streaming helper with provider fallback. Returns (text, provider_label) or (None, None)."""
    for provider in await available_providers():
        try:
            parts = [e["text"] async for e in stream_chat(provider, messages, None, temperature, max_tokens) if e["type"] == "token"]
            text = "".join(parts).strip()
            if text:
                return text, provider.label
        except Exception as exc:
            logger.warning("LLM %s failed: %s", provider.label, exc)
    return None, None


# ── Embeddings (semantic search) ─────────────────────────────────────────────

async def embed(texts: List[str]) -> Optional[List[List[float]]]:
    """Dense embeddings from the local Ollama embedding model, or None if unavailable."""
    models = await ollama_models()
    if not models or not _installed(models, settings.ollama_embed_model):
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/embed",
                                     json={"model": settings.ollama_embed_model, "input": texts, "keep_alive": "30m"})
        if resp.status_code == 200:
            return resp.json().get("embeddings")
    except Exception as exc:
        logger.info("Embedding request failed: %s", exc)
    return None


async def warm_up() -> None:
    """Load the local model into memory so the first question is fast (best effort)."""
    providers = await available_providers()
    local = next((p for p in providers if p.is_local), None)
    if not local:
        return
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(f"{local.base_url}/api/chat", json={
                "model": local.model, "messages": [{"role": "user", "content": "hi"}], "stream": False,
                "keep_alive": "30m", "options": {"num_ctx": settings.ollama_num_ctx, "num_predict": 1},
            })
        await embed(["warm-up"])
        logger.info("Local LLM %s is loaded and ready", local.label)
    except Exception as exc:
        logger.info("LLM warm-up skipped: %s", exc)
