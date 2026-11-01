"""Load only validated Daeloryn profiles, never agents from reviewed checkouts."""
import hashlib
from agents import SLUG, catalog, format_copilot


def resolve_agent(name):
    if not isinstance(name, str) or not SLUG.fullmatch(name):
        raise ValueError("invalid agent name")
    matches = [(meta, body) for meta, body in catalog() if meta["name"] == name]
    if len(matches) != 1:
        raise ValueError("unknown agent")
    meta, body = matches[0]
    source = format_copilot(meta, body)
    return {"name": name, "description": meta["description"], "body": body,
            "source": source, "sha256": hashlib.sha256(source.encode()).hexdigest()}
