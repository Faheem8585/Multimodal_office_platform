# Office Platform

A production-grade, multimodal internal platform that gives an organization's
departments (HR, Finance, IT, …) a single hub to manage workflows, documents,
and communications — with role-aware dashboards, a configurable approval engine,
document ingestion + OCR, and a department-scoped RAG assistant.

> Reference modules implemented end-to-end: **HR**, **Finance**, **IT**.
> Deployment targets provided: **single-host Docker Compose** and **Kubernetes (Helm)**.

---

## Architecture

A modular monolith (FastAPI) with a React SPA. Heavy work (OCR, parsing,
embeddings) is offloaded to Celery workers. Postgres is the single source of
truth, with `pgvector` co-located for semantic search so there is one datastore
to operate and back up.

```
                     ┌───────────────────────────┐
   Browser (SPA) ───▶│  nginx (serves SPA, /api → │
   React+TS+Tailwind │  reverse-proxy to API)     │
                     └─────────────┬──────────────┘
                                   │ JWT (access) + httpOnly refresh cookie
                     ┌─────────────▼──────────────┐      ┌──────────────────┐
                     │  FastAPI (async)            │─────▶│ PostgreSQL +      │
                     │  routers → services →       │      │ pgvector          │
                     │  repositories → models      │◀─────│ (relational +     │
                     │  RBAC · audit · rate-limit  │      │  embeddings)      │
                     └───────┬──────────────┬──────┘      └──────────────────┘
                  enqueue    │              │ cache / rate-limit / broker
                  ┌──────────▼───┐    ┌─────▼─────┐        ┌────────────────┐
                  │ Celery worker│    │  Redis     │        │ S3 / MinIO      │
                  │ OCR·parse·   │    └───────────┘        │ (docs; local    │
                  │ embed (RAG)  │───────────────────────▶ │  disk fallback) │
                  └──────────────┘                         └────────────────┘
```

Layering keeps concerns separated and testable:
`routers` (HTTP) → `services` (business logic) → `repositories` (data access) →
`models` (ORM). Department features live in pluggable `app/modules/<dept>/`.

See [docs/architecture notes in the runbook](deploy/runbook.md) for operational detail.

---

## Features

- **Auth & RBAC** — JWT access tokens + **refresh-token rotation with reuse
  detection**, Argon2id hashing, four role tiers (admin → manager → member →
  viewer) and department-scoped permissions.
- **Multimodal ingestion** — PDF / DOCX / XLSX / images, OCR (Tesseract) for
  scans, chunking, embeddings, all processed in the background with retries.
- **Semantic + full-text search** — pgvector cosine similarity and Postgres
  `tsvector`, scoped to what the caller may see.
- **Department RAG assistant** — answers grounded in a department's documents,
  with sources and a prompt-injection guard. Pluggable LLM provider.
- **Configurable approval engine** — multi-step workflows with declarative,
  injection-safe triggers (e.g. *expense > €1000*); modules plug in finalizers.
- **Role-aware dashboard**, notifications, cross-department activity feed.
- **Reports** — export expenses/budgets to XLSX and PDF.
- **Production concerns** — structured JSON logs, Prometheus metrics, optional
  OpenTelemetry tracing + Sentry, health/readiness probes, rate limiting,
  security headers, soft deletes + append-only audit log, Alembic migrations.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind, TanStack Query, React Router |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| Data | PostgreSQL 16 + pgvector; Redis |
| Async jobs | Celery |
| AI | sentence-transformers (`all-MiniLM-L6-v2`), pluggable LLM (Anthropic) |
| Storage | S3-compatible (MinIO) with local-disk fallback |
| Infra | Docker, docker-compose, Helm, GitHub Actions |

---

## Quickstart (local, Docker Compose)

```bash
# 1. Bring up Postgres+pgvector, Redis, MinIO, API, worker, and the SPA.
docker compose up --build

# 2. Seed roles, demo users, and default approval workflows.
docker compose exec api python -m app.initial_data

# 3. Open the app and the API docs.
#    SPA:       http://localhost:8080
#    API docs:  http://localhost:8000/docs
```

**Demo credentials** (change immediately outside local dev):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@example.com` | `ChangeMe!Admin123` |
| HR manager | `hr.manager@example.com` | `ChangeMe!Mgr123` |
| Finance member | `finance.member@example.com` | `ChangeMe!Mem123` |

### Run the backend without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[full,dev]"
cp .env.example .env                 # then edit
alembic upgrade head
python -m app.initial_data
uvicorn app.main:app --reload
# worker (separate shell):
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### Run the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

---

## Testing

```bash
cd backend
pip install -e ".[dev]"
pytest                 # unit tests always run
# Integration + e2e tests run automatically when a Postgres/pgvector test DB
# is reachable via DATABASE_URL; otherwise they are skipped.
```

Tooling: `ruff check app tests`, `black app tests`, `mypy app`. The full gate
runs in CI on every PR — see [.github/workflows/ci.yml](.github/workflows/ci.yml).

---

## Deployment

- **Single host** → [deploy/compose/docker-compose.prod.yml](deploy/compose/docker-compose.prod.yml)
- **Kubernetes** → [deploy/helm/office-platform](deploy/helm/office-platform)

Both are documented step-by-step, with rollback and backup/restore, in the
**[Operations Runbook](deploy/runbook.md)**.

---

## Project structure

```
backend/
  app/
    core/         config, security, logging, telemetry, deps, rate-limit
    db/           async engine/session, base + mixins
    models/       SQLAlchemy ORM (+ pgvector)
    schemas/      Pydantic v2 request/response models
    repositories/ data access (soft-delete aware, paginated)
    services/     business logic (auth, rbac, approvals, ingestion, rag, …)
    routers/      HTTP endpoints
    modules/      pluggable departments: hr/, finance/, it/
    workers/      Celery app + tasks
    middleware/   request context, security headers, audit
  migrations/     Alembic
  tests/          unit / integration / e2e
frontend/         React + TS + Tailwind SPA
deploy/           compose (prod), helm chart, runbook
.github/workflows ci.yml
```

---

## Security & hardening notes

Implemented: OWASP-aware input validation (Pydantic), parameterized queries
(SQLAlchemy), refresh-token rotation + reuse detection, Argon2id, security
headers, CORS allow-list, Redis-backed rate limiting, audit logging, secrets via
environment, injection-safe approval triggers, RAG prompt-injection guard.

**Before a real go-live**, see the hardening checklist in the
[runbook](deploy/runbook.md#hardening-checklist): wire a real secrets manager,
encrypt PII at rest (HR ID docs), tune the pgvector index for corpus size, add
WAF/CDN + TLS, scope MinIO/S3 IAM, and load-test the embedding workers.
