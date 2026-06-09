import ast
import json
from typing import Any, Dict, List


def _is_message_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _unwrap_transcript_container(parsed: Any) -> List[Dict[str, Any]]:
    """Extract message list from common transcript wrappers."""
    if _is_message_list(parsed):
        return parsed

    if isinstance(parsed, dict):
        for key in ("turns", "chat", "messages", "transcript"):
            nested = parsed.get(key)
            if _is_message_list(nested):
                return nested

    return []


def normalize_transcript(data: Any) -> List[Dict[str, Any]]:
    """
    Normalize transcript input to List[Dict[str, Any]].

    Supports:
    - list of message dicts (role/content or speaker/text)
    - dict wrappers: {"turns": [...]}, {"chat": [...]}, {"messages": [...]}
    - JSON or Python-literal strings of the above
    """
    if data is None or (isinstance(data, float) and str(data) == "nan"):
        return []

    if isinstance(data, str):
        s = data.strip()
        if not s or s.lower() == "nan":
            return []
        try:
            parsed = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            try:
                parsed = ast.literal_eval(s)
            except (ValueError, SyntaxError):
                return []
        return _unwrap_transcript_container(parsed)

    return _unwrap_transcript_container(data)
