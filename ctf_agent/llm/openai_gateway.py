# ctf_agent/llm/openai_gateway.py
from __future__ import annotations

from openai import OpenAI


def make_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def call_text(client: OpenAI, model: str, system: str, user: str) -> str:
    """
    Simple text call (no tools). Used by both Manager and Hacker in hybrid mode.
    """
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.output_text
