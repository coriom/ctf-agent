import os
from openai import OpenAI

def get_client() -> OpenAI:
    # Uses OPENAI_API_KEY env var by default
    return OpenAI()

def call_text(model: str, system: str, user: str) -> str:
    client = get_client()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    # SDK exposes aggregated text output
    return resp.output_text
