#!/usr/bin/env sh
# One-shot: copy env if missing, then build & start the full stack.
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit GEMINI_API_KEY and MISTRAL_API_KEY, then re-run."
  exit 1
fi

docker compose up --build "$@"
