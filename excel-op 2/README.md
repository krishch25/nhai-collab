# Continuous Learning Taxonomy Classification System

Agentic AI system for classifying raw materials into L0/L1/L2 taxonomy using FastAPI, CrewAI, SQLAlchemy, and ChromaDB.

## Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Data:** Pandas, openpyxl
- **Relational DB:** SQLAlchemy + PostgreSQL (or SQLite for local dev)
- **Vector DB:** ChromaDB
- **Agents:** CrewAI + LangChain

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # or `\.venv\Scripts\activate` on Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## API

- `POST /api/upload/training` — Upload Excel with raw material + L0/L1/L2 and trigger rule training
- `POST /api/upload/inference` — Upload Excel with raw material only and trigger classification
- `GET /api/download/{batch_id}` — Download classified Excel for a batch
- `GET /api/rules` — List taxonomy rules
- `GET /api/status` — List recent training/inference batches
- `GET /health` — Health check

## Project Structure

```
app/
├── main.py           # FastAPI app and wiring
├── api/              # Routers (upload, download, rules, status)
├── agents/           # CrewAI agents and orchestration
├── core/             # Config, LLM and logging
├── db/               # SQLAlchemy models, session, vector store
└── services/         # Excel I/O, rule engine, classification services

alembic/              # Alembic migrations (env.py + versions/)
data/uploads          # Local uploaded files (optional)
data/exports          # Local exported files (optional)
tests/                # Pytest suite
```
