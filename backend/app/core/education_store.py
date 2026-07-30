"""Mongo-backed education (pedagogue) conversation history."""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.mongo import get_db

_lock = threading.Lock()
_initialized = False


def _col():
    return get_db()["education_conversations"]


def _ensure() -> None:
    global _initialized
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        col = _col()
        col.create_index("id", unique=True)
        col.create_index([("user_id", 1), ("updated_at", -1)])
        _initialized = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_conversation(*, user_id: str, title: str | None = None) -> str:
    _ensure()
    cid = str(uuid.uuid4())
    now = _now()
    with _lock:
        _col().insert_one(
            {
                "id": cid,
                "user_id": user_id,
                "title": title or "Nouvelle conversation",
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }
        )
    return cid


def list_conversations(user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    _ensure()
    with _lock:
        rows = list(
            _col()
            .find({"user_id": user_id}, {"_id": 0, "messages": 0})
            .sort("updated_at", -1)
            .limit(limit)
        )
    out = []
    for row in rows:
        updated = row.get("updated_at")
        created = row.get("created_at")
        out.append(
            {
                "id": row["id"],
                "title": row.get("title") or "Conversation",
                "created_at": created.isoformat() if isinstance(created, datetime) else str(created or ""),
                "updated_at": updated.isoformat() if isinstance(updated, datetime) else str(updated or ""),
                "type": "pedagogue",
            }
        )
    return out


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    _ensure()
    with _lock:
        row = _col().find_one({"id": conversation_id}, {"_id": 0})
    if not row:
        return None
    for key in ("created_at", "updated_at"):
        val = row.get(key)
        if isinstance(val, datetime):
            row[key] = val.isoformat()
    return row


def rename_conversation(conversation_id: str, title: str) -> bool:
    _ensure()
    with _lock:
        res = _col().update_one(
            {"id": conversation_id},
            {"$set": {"title": title.strip()[:120], "updated_at": _now()}},
        )
    return res.matched_count > 0


def delete_conversation(conversation_id: str) -> bool:
    _ensure()
    with _lock:
        res = _col().delete_one({"id": conversation_id})
    return res.deleted_count > 0


def append_messages(
    conversation_id: str,
    *,
    user_content: str,
    assistant_content: str,
    sources: list[dict] | None = None,
    title_hint: str | None = None,
) -> None:
    _ensure()
    now = _now()
    user_msg = {
        "role": "user",
        "content": user_content,
        "sources": [],
        "created_at": now.isoformat(),
    }
    asst_msg = {
        "role": "assistant",
        "content": assistant_content,
        "sources": sources or [],
        "created_at": now.isoformat(),
    }
    update: dict[str, Any] = {
        "$push": {"messages": {"$each": [user_msg, asst_msg]}},
        "$set": {"updated_at": now},
    }
    if title_hint:
        update["$set"]["title"] = title_hint.strip()[:80]
    with _lock:
        _col().update_one({"id": conversation_id}, update)


async def async_create_conversation(*, user_id: str, title: str | None = None) -> str:
    return await asyncio.to_thread(create_conversation, user_id=user_id, title=title)


async def async_list_conversations(user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_conversations, user_id, limit=limit)


async def async_get_conversation(conversation_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_conversation, conversation_id)


async def async_rename_conversation(conversation_id: str, title: str) -> bool:
    return await asyncio.to_thread(rename_conversation, conversation_id, title)


async def async_delete_conversation(conversation_id: str) -> bool:
    return await asyncio.to_thread(delete_conversation, conversation_id)


async def async_append_messages(
    conversation_id: str,
    *,
    user_content: str,
    assistant_content: str,
    sources: list[dict] | None = None,
    title_hint: str | None = None,
) -> None:
    await asyncio.to_thread(
        append_messages,
        conversation_id,
        user_content=user_content,
        assistant_content=assistant_content,
        sources=sources,
        title_hint=title_hint,
    )
