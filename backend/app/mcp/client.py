"""MCP client: spawns source servers as stdio subprocesses and calls their tools."""
from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings

_PYTHON = sys.executable
_BASE_DIR = Path(__file__).resolve().parents[2]


def _srv(script: str) -> list[str]:
    return [str(_BASE_DIR / "mcp_servers" / script)]


SERVERS = {
    "legifrance": _srv("legifrance_server.py"),
    "bofip": _srv("bofip_server.py"),
    "web-sources": _srv("web_sources_server.py"),
    "entreprises": _srv("entreprises_server.py"),
    "docs-officiels": _srv("docs_officiels_server.py"),
}


@asynccontextmanager
async def _session(server: str):
    if server not in SERVERS:
        raise ValueError(f"Serveur MCP inconnu : {server}")
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if settings.piste_client_id and settings.piste_client_secret:
        env.setdefault("PISTE_CLIENT_ID", settings.piste_client_id)
        env.setdefault("PISTE_CLIENT_SECRET", settings.piste_client_secret)
    params = StdioServerParameters(
        command=_PYTHON,
        args=SERVERS[server],
        env=env,
        cwd=str(_BASE_DIR),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_tools(server: str) -> list[dict]:
    async with _session(server) as s:
        resp = await s.list_tools()
        return [{"name": t.name, "description": t.description} for t in resp.tools]


async def call_tool(server: str, tool: str, arguments: dict) -> dict:
    async with _session(server) as s:
        result = await s.call_tool(tool, arguments=arguments)
        if getattr(result, "structuredContent", None):
            return result.structuredContent
        textes = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        brut = "\n".join(textes)
        if not brut:
            return {}
        try:
            parsed = json.loads(brut)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return {"texte": brut}
