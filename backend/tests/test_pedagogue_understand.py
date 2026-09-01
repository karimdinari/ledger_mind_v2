"""Tests for pedagogue query understanding (education chat follow-ups)."""
from __future__ import annotations

import pytest

from app.agents.pedagogue.understand import analyse_query


@pytest.mark.asyncio
async def test_thanks_no_rag_needed():
    r = await analyse_query("Merci beaucoup !")
    assert r.intent == "thanks"
    assert r.reponse_directe


@pytest.mark.asyncio
async def test_confused_uses_history_topic():
    hist = [
        {"role": "user", "content": "Quels sont les seuils de la micro-entreprise en 2025 ?"},
        {
            "role": "assistant",
            "content": "Les plafonds de chiffre d'affaires varient selon BNC ou BIC...",
        },
    ]
    r = await analyse_query("Je n'ai pas compris", hist)
    assert r.intent == "confused"
    assert "micro" in r.search_query.lower() or "seuil" in r.search_query.lower()
    assert r.consigne_reponse


@pytest.mark.asyncio
async def test_example_request():
    hist = [
        {"role": "user", "content": "Quand dois-je facturer la TVA ?"},
        {"role": "assistant", "content": "La franchise en base dépend de seuils..."},
    ]
    r = await analyse_query("Tu peux me donner un exemple concret ?", hist)
    assert r.intent == "example_request"
    assert "tva" in r.search_query.lower() or "franchise" in r.search_query.lower()


@pytest.mark.asyncio
async def test_new_question_without_history():
    r = await analyse_query("Quelle différence entre BIC et BNC ?")
    assert r.intent == "new_question"
    assert "BIC" in r.search_query or "BNC" in r.search_query
