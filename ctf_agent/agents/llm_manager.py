from __future__ import annotations

import json
from typing import Any, Dict

from ..llm.jsonio import must_json
from ..llm.prompts import load_prompt
from ..llm.openai_gateway import call_manager
from openai import OpenAI


class LLMManager:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model
        self.system = load_prompt("manager_system.txt")

    def decide(self, state: Dict[str, Any]) -> Dict[str, Any]:
        out = call_manager(
            client=self.client,
            model=self.model,
            system=self.system,
            user=json.dumps({"state": state}),
        )
        return must_json(out)
