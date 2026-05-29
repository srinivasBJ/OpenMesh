# Contributing To OpenMeshAI

Thanks for helping build OpenMeshAI. The project is early, and thoughtful structure matters as much as new features right now.

## What We Are Building

OpenMeshAI is an open-source platform for observing, understanding, and managing AI agent ecosystems.

The current app is a working prototype with simulated agents. The long-term platform is an agent mesh: identity, runtime, social, observability, and collaboration layers for AI systems.

When contributing, clearly separate:

- Existing behavior
- Incremental implementation work
- Future-facing design

## Best First Contributions

Good starter areas:

- Improve docs and examples.
- Add tests around existing behavior.
- Split large files into clearer modules.
- Add TypeScript types for API responses.
- Improve error states and empty states in the UI.
- Replace outdated AgentVerse wording.
- Improve local setup reliability.

See [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md).

## Development Setup

### Backend

```bash
cp backend/.env.example backend/.env
docker compose up -d postgres redis
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Use offline mode for low-friction local development:

```env
LLM_MODE=offline
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Before Opening A Pull Request

Run the checks that apply to your change.

Backend:

```bash
cd backend
ruff check src/
```

Frontend:

```bash
cd frontend
npm run build
```

If you add tests, include the test command in your PR description.

## Coding Guidelines

### Backend

- Keep route handlers small when touching API code.
- Prefer domain modules over growing `backend/src/api/routes/main.py`.
- Keep provider-specific model calls out of simulator logic once the provider abstraction exists.
- Use structured schemas for request and response shapes.
- Add tests when changing persistence, security, scheduler behavior, or event emission.
- Preserve `LLM_MODE=offline`.

### Frontend

- Follow the existing React, Vite, TanStack Query, Zustand, and Tailwind setup.
- Avoid broad visual rewrites unless the issue is specifically design-related.
- Add reusable types for API responses instead of spreading `any` further.
- Keep screens useful for operators: dense, inspectable, and clear.

### Documentation

- Be explicit about what exists today and what is planned.
- Avoid implying that mesh, CLI, SDK, external agents, or provider registry features exist before they are implemented.
- Prefer examples that contributors can run locally.

## Pull Request Checklist

- The change has a clear purpose.
- Documentation was updated if behavior or setup changed.
- Current functionality and planned functionality are not mixed together.
- Relevant checks were run locally.
- New environment variables were added to `backend/.env.example`.
- New API endpoints are listed in README or architecture docs if public.

## Community Standards

Participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
