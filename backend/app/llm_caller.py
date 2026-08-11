"""LLM caller with provider abstraction.

Reads .env (LLM_PROVIDER=gemini|muse|deepseek) and calls the matching
provider. Every call returns a validated Pydantic model with automatic
retry when the model emits invalid JSON.

  gemini   -> google-genai SDK (GEMINI_API_KEY / GEMINI_MODEL)
  muse     -> OpenAI-compatible (MUSE_API_KEY / MUSE_MODEL / MUSE_BASE_URL)
  deepseek -> OpenAI-compatible (DEEPSEEK_API_KEY / DEEPSEEK_MODEL)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("llm")

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

T = TypeVar("T", bound=BaseModel)

PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite")
MUSE_MODEL = os.environ.get("MUSE_MODEL", "muse-spark-1.2-contributor")
MUSE_BASE_URL = os.environ.get("MUSE_BASE_URL", "https://api.meta.ai/v1")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

_gemini_client = None
_openai_client = None


def _extract_json(text: str) -> str:
    """Pull a JSON object/array out of an LLM reply (strips fences/banners)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min(
        [i for i in (text.find("{"), text.find("[")) if i != -1] or [0]
    )
    end = max(
        [i for i in (text.rfind("}"), text.rfind("]")) if i != -1] or [len(text)]
    )
    if start != -1 and end > start:
        text = text[start : end + 1]
    return text


def _call_gemini(system: str, user: dict) -> str:
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing in .env")
        _gemini_client = genai.Client(api_key=api_key)

    payload = json.dumps(user, indent=2)
    resp = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=payload,
        config={
            "system_instruction": system,
            "response_mime_type": "application/json",
        },
    )
    return resp.text or ""


def _call_openai_compatible(system: str, user: dict, base_url: str, api_key: str, model: str) -> str:
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=api_key, base_url=base_url)
    payload = json.dumps(user, indent=2)
    resp = _openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": payload},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def raw_call(system: str, user: dict) -> str:
    """Lowest-level call. Returns raw text. Used by tests/debug."""
    logger.info("LLM call provider=%s model=%s system=%s...", PROVIDER, _current_model(), system[:60])
    if PROVIDER == "muse":
        return _call_openai_compatible(
            system, user, MUSE_BASE_URL, os.environ.get("MUSE_API_KEY", ""), MUSE_MODEL
        )
    if PROVIDER == "deepseek":
        return _call_openai_compatible(
            system, user, DEEPSEEK_BASE_URL, os.environ.get("DEEPSEEK_API_KEY", ""), DEEPSEEK_MODEL
        )
    return _call_gemini(system, user)


def _current_model() -> str:
    if PROVIDER == "muse":
        return MUSE_MODEL
    if PROVIDER == "deepseek":
        return DEEPSEEK_MODEL
    return GEMINI_MODEL


def call_json(system: str, user: dict, response_model: Type[T], retries: int = 3) -> T:
    """Call the LLM and coerce output into ``response_model``.

    Retries with a corrective hint when JSON or validation fails.
    """
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            text = raw_call(system, user)
            parsed = json.loads(_extract_json(text))
            return response_model.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            logger.warning("LLM bad output attempt %d/%d err=%s", attempt, retries, e)
            user = {**user, "_retry_hint": f"Previous output was invalid JSON or schema. Err: {e}. Output ONLY valid JSON matching the schema."}
    raise RuntimeError(f"LLM failed after {retries} retries: {last_err}")


def available_provider() -> str:
    return PROVIDER
