# Operations Runbook — Office Platform

Audience: on-call / platform engineers. Covers deploy, rollback, backup/restore,
scaling, observability, secret rotation, and pre-go-live hardening.

---

## 1. Components

| Component | What it is | Scales by |
|---|---|---|
| `api` | FastAPI app (stateless) | replicas / `WEB_CONCURRENCY` |
| `worker` | Celery worker (OCR, parsing, embeddings) | replicas / `--concurrency` |
| `frontend` | nginx serving the SPA + `/api` proxy | replicas |
| PostgreSQL + pgvector | system of record + vector index | vertical / managed HA |
| Redis | cache, rate-limit store, Celery broker | managed / cluster |
| S3 / MinIO | document object storage | managed |

Health surfaces (api): `GET /health` (liveness), `GET /ready` (DB + Redis),
`GET /metrics` (Prometheus). Logs are JSON on stdout; every line carries
`request_id`.

---

## 2. Configuration & secrets

All config is environment-driven (12-factor). Templates:
`backend/.env.example`, `deploy/compose/.env.example`.

- **Never** commit real secrets. In prod, source them from a secrets manager
  (Vault, AWS Secrets Manager, SOPS) into the process environment.
- `JWT_SECRET` must be ≥32 chars in prod (validated at startup); `DEBUG` must be
  `false` (validated). Startup fails fast otherwise.

---

## 3. Deploy — single host (Docker Compose)

```bash
cd deploy/compose
cp .env.example .env            # fill in real values
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

The `api` container's entrypoint runs `alembic upgrade head` and (when
`SEED_ON_START=true`) seeds initial data before serving. Put TLS termination in
front (host nginx / Caddy / cloud LB) targeting the `frontend` service on :80.

**Verify:** `curl -fsS https://<host>/api/v1/openapi.json >/dev/null` and
`docker compose -f docker-compose.prod.yml ps` (all healthy).

## 4. Deploy — Kubernetes (Helm)

Postgres (with pgvector) and Redis are expected to be provided externally
(managed services or in-cluster operators); pass their URLs as secrets.

```bash
helm upgrade --install office deploy/helm/office-platform \
  --namespace office --create-namespace \
  --set image.tag=<release-sha> \
  --set-string secrets.JWT_SECRET="$JWT_SECRET" \
  --set-string secrets.DATABASE_URL="$DATABASE_URL" \
  --set-string secrets.REDIS_URL="$REDIS_URL" \
  --set-string secrets.S3_ACCESS_KEY="$S3_ACCESS_KEY" \
  --set-string secrets.S3_SECRET_KEY="$S3_SECRET_KEY" \
  --set-string secrets.ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --set ingress.host=office.example.com
```

Migrations run automatically as a **pre-install/pre-upgrade Helm hook Job**
(`alembic upgrade head`) that must succeed before pods roll. The api `HPA`
scales on CPU (3→10 by default).

**Seed once** (first install): `kubectl exec deploy/office-office-platform-api
-n office -- python -m app.initial_data`.

---

## 5. Rollback

**Kubernetes:**
```bash
helm history office -n office
helm rollback office <PREVIOUS_REVISION> -n office
```
If the new release added a migration, roll the DB back **first** (see below)
only if the schema change is incompatible; forward-fix is usually safer.

**Compose:** redeploy the previous image tag (pin tags, don't use `latest`):
```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

**Database migration rollback (use with care — may drop columns/data):**
```bash
# inside an api/worker container or a shell with the env:
alembic downgrade -1          # one step back
alembic downgrade <revision>  # to a specific revision
```

---

## 6. Backups & restore (PostgreSQL)

**Backup (nightly cron / managed snapshots):**
```bash
pg_dump --format=custom --no-owner "$DATABASE_PG_URL" > office_$(date +%F).dump
# store off-host (S3 with versioning + lifecycle). Test restores monthly.
```

**Restore:**
```bash
# 1. Stop the app (api + worker) to avoid writes during restore.
# 2. Recreate the database, ensure the pgvector extension exists.
psql "$ADMIN_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
pg_restore --no-owner --dbname "$DATABASE_PG_URL" office_YYYY-MM-DD.dump
# 3. Run migrations to reconcile, then restart.
alembic upgrade head
```

**Object storage:** enable S3/MinIO bucket versioning; documents are
re-embeddable from source via `POST /api/v1/documents/{id}/reindex` if chunks
are lost.

> RPO/RTO: tune backup frequency to your RPO. Always validate a restore into a
> scratch environment — an untested backup is not a backup.

---

## 7. Scaling & performance

- **API**: stateless — add replicas; HPA handles CPU spikes. Tune
  `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` so `replicas × pool ≤ Postgres max_connections`
  (use PgBouncer if you approach the limit).
- **Workers**: ingestion is CPU-bound (embeddings/OCR). Scale `worker` replicas
  and `--concurrency`; watch the Redis queue depth.
- **pgvector**: the IVFFlat index uses `lists=100`. As the corpus grows, rebuild
  with `lists ≈ sqrt(rows)` and `ANALYZE`. Consider HNSW for large corpora.
- **Redis**: caching + rate limiting + broker. Separate broker from cache if hot.

---

## 8. Observability & on-call

- **Metrics**: scrape `/metrics`. Watch request latency/error rate, worker task
  failures/retries, DB pool saturation, queue depth.
- **Tracing**: set `OTEL_EXPORTER_ENDPOINT` to enable OTLP traces.
- **Errors**: set `SENTRY_DSN`.
- **Logs**: JSON to stdout; filter by `request_id` to follow one request across
  api + worker.

**Common issues**

| Symptom | Likely cause | Action |
|---|---|---|
| `/ready` 503 | DB or Redis down | check those services; api will recover |
| Documents stuck `processing`/`uploaded` | worker down or broker unreachable | check worker + Redis; `POST /documents/{id}/reindex` |
| Document `failed` | parse/OCR error (corrupt file) | inspect `error` field on the document; re-upload |
| 401 storms | refresh-token reuse detected (possible theft) | the affected token family is auto-revoked; user must re-login |
| 429s | rate limit hit | tune `RATE_LIMIT_DEFAULT` / per-route limits |

---

## 9. Secret rotation

- **JWT_SECRET**: rotating it invalidates all live access tokens (≤15 min TTL)
  and refresh tokens (clients re-login). Roll during a low-traffic window.
- **DB / S3 / Anthropic credentials**: update in the secrets manager, then
  `helm upgrade` (re-renders the Secret) or recreate compose containers.
- Revoke a single user's sessions: they call `POST /auth/logout`, or an admin
  deactivates the user (`is_active=false`) — inactive users fail auth on refresh.

---

## 10. Hardening checklist

Done in code: input validation, parameterized queries, refresh rotation + reuse
detection, Argon2id, security headers, CORS allow-list, rate limiting, audit log,
soft deletes, injection-safe approval triggers, RAG prompt-injection guard,
non-root containers, health/readiness probes.

Do before go-live:

- [ ] Real **secrets manager** (Vault/AWS SM/SOPS); remove all dev defaults.
- [ ] **TLS** everywhere; HSTS is emitted in non-dev — terminate TLS at the edge.
- [ ] **PII at rest**: encrypt HR ID documents / receipts (bucket SSE-KMS) and
      restrict access; audit every read of sensitive docs.
- [ ] **S3/MinIO IAM** scoped to the one bucket; rotate keys; enable versioning.
- [ ] **DB**: enforce TLS, least-privilege role, `max_connections` sizing,
      automated + tested backups, PITR if available.
- [ ] **Dependency scanning** gated (flip `pip-audit`/Trivy to fail on HIGH).
- [ ] **WAF/CDN** in front; tune body-size limits (uploads capped at 25 MB).
- [ ] **Load-test** embedding workers; size worker pool to expected ingest rate.
- [ ] Review **CORS origins**, cookie domain, and CSP for your real domains.
- [ ] Pin and scan container base images; enable image signing if required.
