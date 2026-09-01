"""Pytest configuration — minimal env so Settings() loads in CI/local without .env."""
from __future__ import annotations

import os

os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("MISTRAL_API_KEY", "test-mistral-key")
