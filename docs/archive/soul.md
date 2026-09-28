# OpenMeshAI Soul Log

Last updated: May 29, 2026 (Asia/Kolkata)

## 1) What We Built So Far

We transformed OpenMeshAI from an initial prototype into a stronger, production-direction baseline with:

- GitHub private repository setup and initial code push
- Runtime bug fixes in backend simulation path
- Readiness/liveness health checks for deployment reliability
- Scheduler safety improvements for reload/restart behavior
- LLM cost-control/offline controls
- Prompt context budgeting for better small-context stability
- Write endpoint protection (API key + rate limiting)
- Docker Compose startup fix

## 2) Core Technical Changes

### A. Backend Reliability

- Added `GET /health/ready` with database verification and scheduler/security status
  - File: `backend/src/main.py`
- Added scheduler diagnostics and safe startup logic
  - `replace_existing=True` for scheduled jobs
  - Prevent duplicate starts / safe stop behavior
  - File: `backend/src/services/scheduler.py`

### B. Multi-Agent Stability + Cost Controls

- Added explicit LLM runtime modes:
  - `LLM_MODE=auto|online|offline`
  - `CLAUDE_MODEL=...`
  - File: `backend/src/agents/brain.py`
- Added centralized Claude call helper with graceful fallback
- Added bounded memory snippet injection into agent system prompt
- Added prompt context budgets and clipping in simulator
  - Files:
    - `backend/src/agents/brain.py`
    - `backend/src/agents/simulator.py`
- Added new env knobs:
  - `AGENT_CONTEXT_POSTS`
  - `AGENT_CONTEXT_CHARS_PER_POST`
  - `AGENT_CONTEXT_TOTAL_CHARS`
  - `AGENT_MEMORY_CONTEXT_ITEMS`
  - `AGENT_MEMORY_CONTEXT_CHARS`
  - File: `backend/.env.example`

### C. Security Hardening (Write Endpoints)

- Added new security module:
  - `backend/src/core/security.py`
- Features:
  - Optional write API key enforcement
  - Header support:
    - `x-api-key: ...`
    - `Authorization: Bearer ...`
  - In-memory sliding window write rate limiter
  - Production-friendly defaults
- Protected write endpoints via dependency:
  - spawn agent
  - retire agent
  - react to post
  - create guild
  - join guild
  - manual simulation tick
  - File: `backend/src/api/routes/main.py`

### D. Docker/Infra Fix

- Fixed compose validation/startup issue:
  - `backend.depends_on.redis` now uses `condition: service_started`
  - File: `docker-compose.yml`

## 3) Commit History (Newest First)

- `aac6247` Add write endpoint auth and rate limiting controls
- `114032d` Add LLM mode controls and prompt context budgeting for stable multi-agent runs
- `61fb9f0` Improve runtime readiness checks and scheduler startup safety
- `f08300a` Initial OpenMeshAI scaffold with backend/frontend and simulation tick fix

## 4) Current Runtime Status Model

OpenMeshAI now supports three LLM operating patterns:

- `offline`: no API calls, always local fallback generation, zero token spend
- `auto`: use API if key exists, fallback when unavailable
- `online`: force API usage (warn/fallback if key missing)

This gives safe demo mode + cost-managed mode + full cloud mode.

## 5) Environment Variables Added/Important

In `backend/.env`:

```env
LLM_MODE=offline
CLAUDE_MODEL=claude-sonnet-4-20250514

REQUIRE_WRITE_API_KEY=false
WRITE_API_KEY=change-this-for-prod
WRITE_RATE_LIMIT_ENABLED=true
WRITE_RATE_LIMIT_MAX_REQUESTS=30
WRITE_RATE_LIMIT_WINDOW_SECONDS=60

AGENT_CONTEXT_POSTS=5
AGENT_CONTEXT_CHARS_PER_POST=100
AGENT_CONTEXT_TOTAL_CHARS=600
AGENT_MEMORY_CONTEXT_ITEMS=5
AGENT_MEMORY_CONTEXT_CHARS=500
```

## 6) How To Run (Current Known Good)

```bash
cd /Users/trylub/Desktop/openmeshai
cp backend/.env.example backend/.env
# edit backend/.env as needed (offline recommended for zero cost)
docker compose up -d --build
docker compose ps
```

Open:

- Frontend: `http://localhost:5173`
- API health: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/health/ready`

## 7) Copy-Paste Handoff Prompt

Use this prompt to brief another engineer/agent quickly:

```text
You are taking over an in-progress project called OpenMeshAI (FastAPI + React + Postgres + Redis + WebSocket + scheduled multi-agent simulation).

Please read and continue from this exact state:

1) Repository status
- Branch: main
- Recent commits:
  - aac6247: write endpoint auth + rate limiting
  - 114032d: LLM mode controls + prompt context budgeting
  - 61fb9f0: readiness checks + scheduler safety
  - f08300a: initial scaffold + simulation tick fix

2) Critical backend changes already done
- Added /health and /health/ready endpoints with DB and scheduler/security status.
- Added scheduler_status() and idempotent scheduler startup/shutdown guards.
- Added LLM_MODE (offline/auto/online), CLAUDE_MODEL, bounded context controls.
- Added write protections:
  - API-key enforcement toggle (REQUIRE_WRITE_API_KEY)
  - WRITE_API_KEY
  - write rate limiting window + max requests
  - applied to mutating endpoints (spawn/retire/react/create guild/join guild/tick)
- Fixed docker-compose dependency condition for redis.

3) Current operating strategy
- Prefer zero-cost mode by default:
  - LLM_MODE=offline
- Use online mode only when explicitly enabled and key is provided.

4) Files to inspect first
- backend/src/main.py
- backend/src/services/scheduler.py
- backend/src/agents/brain.py
- backend/src/agents/simulator.py
- backend/src/core/security.py
- backend/src/api/routes/main.py
- backend/.env.example
- docker-compose.yml
- README.md

5) Next high-priority roadmap
- Queue-based execution (decouple long LLM calls from request cycle)
- Durable/shared rate limit store (Redis-based instead of in-memory)
- Automated tests for health/ready/protected write endpoints
- Provider abstraction for local Ollama endpoint support

Please continue implementation with production-safe defaults and concise docs updates.
```

## 8) Notes

- There is an untracked local file currently in repo root: `_edit_docx_tables.py`.
- It was not part of OpenMeshAI feature commits.

