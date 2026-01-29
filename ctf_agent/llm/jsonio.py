import json

def must_json(s: str) -> dict:
    s = s.strip()
    if not s.startswith("{"):
        i = s.find("{")
        j = s.rfind("}")
        if i >= 0 and j > i:
            s = s[i : j + 1]
    return json.loads(s)
