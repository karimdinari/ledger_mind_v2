<p align="center">
  <img src="docs/banner.jpg" alt="LedgerMind — AI-Powered Tax Assistant" width="100%"/>
</p>

<h1 align="center">LedgerMind</h1>

<p align="center">
  <strong>AI-powered tax assistant for French creators & freelancers</strong><br/>
  From your first question to your last declaration — intelligently guided, never transmitted.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React_19-61DAFB?logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/TanStack_Start-FF4154?logo=react&logoColor=white" alt="TanStack"/>
  <img src="https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white" alt="MongoDB"/>
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/Mistral_AI-5A67D8?logo=data:image/svg+xml;base64,&logoColor=white" alt="Mistral"/>
  <img src="https://img.shields.io/badge/Gemini-4285F4?logo=google&logoColor=white" alt="Gemini"/>
  <img src="https://img.shields.io/badge/Pinecone-00A98F?logo=pinecone&logoColor=white" alt="Pinecone"/>
</p>

---

## 🎬 Demo

<!-- ▶️ Replace the URL below with your actual video link (YouTube, Loom, etc.) -->
<!-- The video thumbnail will appear directly in the README -->

<p align="center">
  <a href="https://YOUR_VIDEO_LINK_HERE">
    <img src="https://img.shields.io/badge/▶_Watch_Demo-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="Watch Demo" height="50"/>
  </a>
</p>

<p align="center"><em>👆 Click to watch the full product walkthrough</em></p>

---

## ✨ What is LedgerMind?

LedgerMind is an **intelligent fiscal assistant** designed for French micro-entrepreneurs, freelancers, and content creators. It covers the entire fiscal lifecycle — from your very first question (*"Do I need to register?"*) to preparing all five regulatory declarations — powered by a multi-agent Generative AI architecture.

> **The core promise:** LedgerMind helps you understand and prepare. It **never transmits** anything to the tax authorities on your behalf.

---

## 🧠 Generative AI at the Core

LedgerMind isn't just another form-filler — it's built around a **multi-agent GenAI architecture** where each AI agent specializes in a specific fiscal domain.

### Multi-LLM Strategy

| Provider | AI Capabilities | Why |
|---|---|---|
| **Mistral AI** | Conversational guidance, fiscal Q&A, regulatory monitoring, document OCR & extraction, embeddings | High-quality French language understanding at scale |
| **Google Gemini** | Identity verification, profile understanding, registry document analysis | Multimodal reasoning for complex document interpretation |

### Intelligent Agents — 14 Specialized AI Modules

| Agent | What It Does | AI-Powered? |
|---|---|---|
| **Guidance** | Conversational diagnostic — builds your fiscal profile from natural language | ✅ Mistral |
| **Intake** | Verifies your business identity against public registries, asks smart follow-up questions | ✅ Gemini |
| **Pedagogue** | Answers any tax question with cited sources (BOFiP, Légifrance, URSSAF) via **RAG** | ✅ Mistral + RAG |
| **Capture** | Reads uploaded documents (invoices, transfers, contracts, gifts) using a **LangGraph** pipeline with human-in-the-loop | ✅ Mistral + LangGraph |
| **Veille** | Monitors regulatory changes and personalizes alerts per user profile | ✅ Mistral (one-shot qualification) |
| **Referral** | Finds nearby accountants and drafts personalized contact emails | ✅ Mistral |
| **Product RAG** | Public chatbot answering questions about LedgerMind itself | ✅ Mistral + Pinecone |
| **Impôts** | Computes all tax amounts (deductions, income tax, social contributions) | ❌ Fully deterministic |
| **Rapport Fiscal** | Generates fiscal reports on cash-basis revenue with bank reconciliation | ❌ Deterministic |
| **Declarations** | Prepares all 5 regulatory declaration drafts | ❌ Deterministic |
| **Facture** | Complete invoicing lifecycle (draft → issued → credit note → settled) | ❌ Deterministic |
| **Échéancier** | Fiscal calendar with obligation tracking | ❌ Deterministic |
| **Orchestrator** | State machine routing between all agents | ❌ Deterministic |
| **Scenarios** | "What-if" tax simulations with NL interpretation | ✅ Mistral (interpretation only) |

### RAG (Retrieval-Augmented Generation) — Dual Corpus

| Corpus | Content | Storage | Purpose |
|---|---|---|---|
| **Fiscal** | BOFiP, Légifrance, URSSAF, impots.gouv | MongoDB (cosine similarity) | Sourced tax answers with legal citations |
| **Product** | LedgerMind documentation | Pinecone (dense vectors) | Public landing page chatbot |

> The two corpora are **deliberately separated** — a product question must never return a tax article, and vice versa.

### AI Transparency — EU AI Act Compliance (Article 50)

LedgerMind implements full AI Act transparency: visible labels on all AI-generated content, machine-readable metadata in exported PDFs, C2PA signatures for media assets, and `X-AI-Generated` HTTP headers on every API response. An audit endpoint (`GET /api/ai-act/transparence`) documents the live state of all transparency mechanisms.

---

## 🚀 Key Features

| Feature | Description |
|---|---|
| 🎯 **Smart Onboarding** | Two paths: SIREN verification (Branch A) or conversational diagnostic (Branch B) |
| 💬 **AI Tax Q&A** | Ask any fiscal question — get sourced, cited answers from official legal databases |
| 📄 **Document Intelligence** | Upload invoices, transfers, contracts — AI reads, classifies, and extracts structured data |
| 🧾 **Invoicing** | Full lifecycle: draft → issued → credit note → settled, with legal compliance |
| 📊 **Fiscal Reports** | Cash-basis reports with bank reconciliation and full audit trail |
| 📋 **5 Declarations** | URSSAF, 2042-C-PRO, DES, TVA, CFE — prepared as drafts, never transmitted |
| 🔮 **Scenario Simulator** | "What if" comparisons: different revenue, category changes, VAT thresholds |
| 📅 **Fiscal Calendar** | Personalized obligation deadlines with regulatory source links |
| 📡 **Regulatory Watch** | AI-monitored regulatory changes, personalized to your profile |
| 🏢 **Accountant Finder** | Geolocated search with personalized contact email drafts |
| 🎁 **Gift-in-Kind Handler** | Two-step estimation → declaration flow for taxable gifts |
| 🔒 **Privacy by Design** | httpOnly JWT cookies, GDPR pages, no analytics trackers |

---

## 🏗️ Architecture

```
┌──────────────────────────────┐       HTTP/JSON       ┌─────────────────────────────────────┐
│  Frontend                    │  ←────────────────→   │  Backend — FastAPI                  │
│  TanStack Start · React 19   │  :3000  ↔  :8000      │                                     │
│  Tailwind 4 · shadcn/ui      │                       │  api/       16 HTTP routers         │
│                              │                       │  agents/    14 AI agents             │
└──────────────────────────────┘                       │  rag/       Fiscal corpus (MongoDB)  │
                                                       │  veille/    Regulatory monitoring    │
                                                       │  mcp/       Official source access   │
                                                       │  product_rag/ Pinecone chatbot       │
                                                       └─────────────────────────────────────┘
                                                              │           │            │
                                                              ▼           ▼            ▼
                                                          MongoDB    Mistral/Gemini  Pinecone
                                                                     + MCP Servers
                                                         (Légifrance · BOFiP · INSEE · URSSAF)
```

---

## ⚡ Quick Start

### Prerequisites

- **Python 3.11+** · **Node.js 20+** · **MongoDB**
- API Keys: **Mistral AI** + **Google Gemini** (minimum)
- Optional: **Pinecone** (product chatbot) · **PISTE** (Légifrance)

### Setup

```bash
# 1. Clone & install backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

# 2. Configure environment
copy backend\.env.example .env    # then fill in your API keys

# 3. Start backend
cd backend
uvicorn app.main:app --reload --port 8000

# 4. Start frontend (new terminal)
cd frontend
npm install
npm run dev
```

- 🟢 Backend health: [http://localhost:8000/health](http://localhost:8000/health)
- 📖 API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🖥️ App: [http://localhost:3000](http://localhost:3000)

### Seed the Knowledge Base

```bash
python -m backend.scripts.seed_corpus              # Fiscal corpus → MongoDB
python -m backend.scripts.index_product_knowledge   # Product corpus → Pinecone
```

---

## 🧪 Testing

```bash
# 741 tests — no API keys needed (mocked)
pytest backend/tests -q
```

Key test coverage: fiscal calculations, declaration integrity, document capture, invoicing lifecycle, guidance flows, scenario simulations, regulatory watch, and AI Act compliance.

---

## 📁 Project Structure

```
ledgermind/
├── backend/
│   ├── app/
│   │   ├── agents/          # 14 specialized AI agents
│   │   ├── api/             # 16 FastAPI routers (no business logic)
│   │   ├── rag/             # Fiscal RAG corpus (MongoDB)
│   │   ├── product_rag/     # Product RAG (Pinecone)
│   │   ├── veille/          # Regulatory watch engine
│   │   ├── mcp/             # MCP client (official sources)
│   │   ├── llm/             # Mistral & Gemini clients
│   │   └── core/            # MongoDB, auth, sessions, JWT
│   ├── mcp_servers/         # Légifrance, BOFiP, INSEE, web
│   └── tests/               # 741 tests
├── frontend/
│   └── src/
│       ├── routes/          # File-based routing (TanStack)
│       ├── components/lm/   # Business components
│       └── lib/             # API clients, entitlements, utils
├── data/                    # Regulatory values (YAML, sourced & dated)
├── docs/                    # Architecture & compliance docs
└── docker-compose.yml       # Container orchestration
```

---

## 🔑 Design Principles

1. **No fiscal amount is computed twice** — a single tax engine (`agents/impots`), called by everyone
2. **No hardcoded thresholds** — all regulatory values live in `data/*.yaml` with source URLs
3. **What can't be computed stays `None`** — never display "€0" when data is missing
4. **Nothing is transmitted** — documents are preparation aids; the user files on official portals
5. **Human overrides machine** — every AI extraction can be manually corrected
6. **Every number carries its provenance** — full audit trail from declaration back to source invoice

---

## 🛡️ Privacy & Security

- **httpOnly JWT cookies** — tokens are invisible to JavaScript
- **No analytics, no trackers** — all storage is strictly necessary (GDPR exempt)
- **GDPR compliance pages** — `/confidentialite`, `/cookies`, `/mes-donnees`
- **Origin-checked CSRF protection** on all write endpoints
- **EU AI Act Article 50** — full transparency markings on all AI-generated content

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

<p align="center">
  <sub>Built with ❤️ using Generative AI — Mistral, Gemini, LangGraph, and RAG</sub>
</p>
