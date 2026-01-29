import json
from typing import Any, Dict, Optional

from ..llm.openai_gateway import call_text
from ..llm.prompts import load_prompt
from ..llm.jsonio import must_json

class LLMHacker:
    def __init__(self, model: str):
        self.model = model
        self.system = load_prompt("hacker_system.txt")

    def pick_action(self, manager_msg: str, state: Dict[str, Any], last_tool_output: Optional[str]) -> Dict[str, Any]:
        user = {
            "manager_message": manager_msg,
            "state": state,
            "last_tool_output": last_tool_output,
        }
        out = call_text(self.model, self.system, json.dumps(user))
        return must_json(out)
