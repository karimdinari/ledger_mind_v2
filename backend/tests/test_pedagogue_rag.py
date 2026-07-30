"""Tests for pedagogue RAG (standalone education agent)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.pedagogue import answer


@pytest.mark.asyncio
async def test_pedagogue_empty_corpus():
    with patch("app.agents.pedagogue.agent.search") as mock_search:
        mock_search.return_value = {
            "hits": [],
            "corpus_vide": True,
            "au_moins_un_perime": False,
        }
        result = await answer("Qu'est-ce que la micro-entreprise ?")
    assert result["corpus_vide"] is True
    assert "vide" in result["reponse"].lower()


@pytest.mark.asyncio
async def test_pedagogue_with_hits():
    hits = [
        {
            "texte": "La micro-entreprise permet un régime simplifié.",
            "titre": "Guide micro",
            "source": "URSSAF",
            "url": "https://example.com",
            "date_publication": "2026-01-01",
            "similarite": 0.9,
            "score": 0.9,
            "perime": False,
        }
    ]
    with (
        patch("app.agents.pedagogue.agent.search") as mock_search,
        patch("app.agents.pedagogue.agent._chat", new_callable=AsyncMock) as mock_chat,
    ):
        mock_search.return_value = {
            "hits": hits,
            "corpus_vide": False,
            "au_moins_un_perime": False,
        }
        mock_chat.return_value = (
            "## Micro\n\nLa **micro-entreprise** est un régime simplifié "
            '[URSSAF — Guide micro].\n\n- point un\n- point deux'
        )
        result = await answer("C'est quoi la micro ?")
    assert result["corpus_vide"] is False
    assert "micro" in result["reponse"].lower()
    assert "#" not in result["reponse"]
    assert "**" not in result["reponse"]
    assert len(result["sources"]) == 1


def test_nettoyer_reponse_strips_markdown():
    from app.agents.pedagogue.agent import _nettoyer_reponse

    raw = '## Titre\n\n""Bonjour"" **monde** et `code`\n- item'
    clean = _nettoyer_reponse(raw)
    assert "#" not in clean
    assert "**" not in clean
    assert "`" not in clean
    assert '""' not in clean
    assert "Bonjour" in clean
    assert "monde" in clean
