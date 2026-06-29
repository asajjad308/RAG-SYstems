import json
import uuid
from pathlib import Path

BOTS_FILE = Path("chatbots.json")


def _load() -> dict:
    if not BOTS_FILE.exists():
        return {}
    return json.loads(BOTS_FILE.read_text())


def _save(data: dict):
    BOTS_FILE.write_text(json.dumps(data, indent=2))


def create_bot(tenant_id: str, name: str, system_prompt: str = "", accent_color: str = "#5b7bf5") -> dict:
    bot_id = uuid.uuid4().hex[:10]
    bot = {
        "id": bot_id,
        "name": name,
        "tenant_id": tenant_id,
        "system_prompt": system_prompt or f"You are {name}, a helpful AI assistant. Answer questions using only the provided context. Be concise and accurate.",
        "accent_color": accent_color,
        "doc_ids": [],
    }
    data = _load()
    data[bot_id] = bot
    _save(data)
    return bot


def get_bot(bot_id: str) -> dict | None:
    return _load().get(bot_id)


def list_bots(tenant_id: str) -> list[dict]:
    return [b for b in _load().values() if b["tenant_id"] == tenant_id]


def delete_bot(bot_id: str, tenant_id: str) -> bool:
    data = _load()
    if bot_id not in data or data[bot_id]["tenant_id"] != tenant_id:
        return False
    del data[bot_id]
    _save(data)
    return True


def add_doc_to_bot(bot_id: str, tenant_id: str, doc_id: str) -> dict | None:
    data = _load()
    bot = data.get(bot_id)
    if not bot or bot["tenant_id"] != tenant_id:
        return None
    bot.setdefault("doc_ids", [])
    if doc_id not in bot["doc_ids"]:
        bot["doc_ids"].append(doc_id)
    _save(data)
    return bot


def remove_doc_from_bot(bot_id: str, tenant_id: str, doc_id: str) -> dict | None:
    data = _load()
    bot = data.get(bot_id)
    if not bot or bot["tenant_id"] != tenant_id:
        return None
    bot["doc_ids"] = [d for d in bot.get("doc_ids", []) if d != doc_id]
    _save(data)
    return bot
