"""Generic clickable options returned by the guidance backend (bascule micro/société)."""

from __future__ import annotations


def options_bascule(profil: dict, roadmap: dict | None) -> dict | None:
    """Options cliquables génériques — le front rend toute structure `options` renvoyée ici."""
    if not roadmap or roadmap.get("parcours") != "bascule":
        return None
    if profil.get("choix_parcours"):
        return None
    return {
        "kind": "choix_parcours",
        "prompt": "Tu peux partir sur l'un ou l'autre — que préfères-tu ?",
        "choices": [
            {"label": "Je pars sur la micro-entreprise", "value": "micro"},
            {"label": "Je pars sur une société (EURL/SASU)", "value": "societe"},
        ],
    }
