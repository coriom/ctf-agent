# ctf_agent/agents/llm_hacker.py
from __future__ import annotations

import json
from typing import Any, Dict

from openai import OpenAI

from ..llm.jsonio import must_json
from ..llm.prompts import load_prompt
from ..llm.openai_gateway import call_text


class LLMHacker:
    """
    Hybrid mode:
    - LLM chooses ONE local action (JSON) according to prompts/hacker_system.txt
    - Orchestrator executes it locally and feeds results back via state/last_exec
    """

    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model
        self.system = load_prompt("hacker_system.txt")

    def attempt(self, manager_instruction: str, state: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "manager_instruction": manager_instruction,
            "state": state,
        }

        out = call_text(
            client=self.client,
            model=self.model,
            system=self.system,
            user=json.dumps(payload),
        )
        return must_json(out)
