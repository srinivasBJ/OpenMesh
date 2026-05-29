#!/bin/bash
# OpenMeshAI — Full Project Scaffold Script
# Run: bash scaffold.sh
# Creates the entire openmeshai/ monorepo with all folders and empty files.

set -e
echo "🚀 Scaffolding OpenMeshAI..."

mkdir -p openmeshai
cd openmeshai

# ─── ROOT ────────────────────────────────────────────────────────────────────
touch docker-compose.yml docker-compose.prod.yml .env.example .gitignore README.md

# ─── GITHUB ACTIONS ──────────────────────────────────────────────────────────
mkdir -p .github/workflows
touch .github/workflows/ci.yml

# ─── BACKEND (Python / FastAPI) ───────────────────────────────────────────────
mkdir -p backend/src/{agents/{prompts,tools},api/{routes,schemas},core,db,jobs,services,websocket}
mkdir -p backend/tests/{unit,integration}

touch backend/requirements.txt
touch backend/Dockerfile
touch backend/.env.example
touch backend/alembic.ini

# DB layer
touch backend/src/db/__init__.py
touch backend/src/db/models.py
touch backend/src/db/session.py

# Agent intelligence
touch backend/src/agents/__init__.py
touch backend/src/agents/brain.py       # Claude-powered agent cognition
touch backend/src/agents/simulator.py   # Simulation engine / tick loop
touch backend/src/agents/prompts/base.py

# API
touch backend/src/api/__init__.py
touch backend/src/api/routes/__init__.py
touch backend/src/api/routes/main.py
touch backend/src/api/schemas/__init__.py
touch backend/src/api/schemas/agent.py
touch backend/src/api/schemas/post.py
touch backend/src/api/schemas/wiki.py

# Core / services
touch backend/src/core/__init__.py
touch backend/src/services/__init__.py
touch backend/src/services/scheduler.py  # APScheduler tick jobs
touch backend/src/services/seeder.py     # Founding agents + guilds

# WebSocket
touch backend/src/websocket/__init__.py
touch backend/src/websocket/manager.py

# Background jobs
touch backend/src/jobs/__init__.py
touch backend/src/jobs/tick.py

# Entry point
touch backend/src/__init__.py
touch backend/src/main.py

# Tests
touch backend/tests/unit/test_brain.py
touch backend/tests/unit/test_simulator.py
touch backend/tests/integration/test_api.py

# ─── FRONTEND (React / TypeScript) ───────────────────────────────────────────
mkdir -p frontend/src/{api,components/{feed,agents,agentpedia,guilds,shared,layout},pages,hooks,store,types,lib,styles}
mkdir -p frontend/public

touch frontend/index.html
touch frontend/vite.config.ts
touch frontend/tsconfig.json
touch frontend/tailwind.config.ts
touch frontend/postcss.config.js
touch frontend/package.json

# API layer
touch frontend/src/api/index.ts

# Components
touch frontend/src/components/feed/PostCard.tsx
touch frontend/src/components/feed/FeedFilter.tsx
touch frontend/src/components/agents/AgentCard.tsx
touch frontend/src/components/agents/SpawnModal.tsx
touch frontend/src/components/agents/AgentStatBar.tsx
touch frontend/src/components/agentpedia/WikiCard.tsx
touch frontend/src/components/guilds/GuildCard.tsx
touch frontend/src/components/guilds/CreateGuildModal.tsx
touch frontend/src/components/shared/AgentAvatar.tsx
touch frontend/src/components/shared/LiveTicker.tsx
touch frontend/src/components/shared/StatCard.tsx
touch frontend/src/components/shared/LoadingSpinner.tsx
touch frontend/src/components/layout/AppLayout.tsx
touch frontend/src/components/layout/Sidebar.tsx

# Pages
touch frontend/src/pages/FeedPage.tsx
touch frontend/src/pages/AgentsPage.tsx
touch frontend/src/pages/AgentProfilePage.tsx
touch frontend/src/pages/GuildsPage.tsx
touch frontend/src/pages/WikiPage.tsx
touch frontend/src/pages/WikiArticlePage.tsx
touch frontend/src/pages/HistoryPage.tsx
touch frontend/src/pages/ObservatoryPage.tsx

# Hooks
touch frontend/src/hooks/useAgents.ts
touch frontend/src/hooks/useFeed.ts
touch frontend/src/hooks/useWiki.ts
touch frontend/src/hooks/useGuilds.ts

# Store
touch frontend/src/store/wsStore.ts

# Types
touch frontend/src/types/agent.ts
touch frontend/src/types/post.ts
touch frontend/src/types/wiki.ts
touch frontend/src/types/guild.ts

# Lib / utils
touch frontend/src/lib/utils.ts
touch frontend/src/styles/globals.css

# Entry
touch frontend/src/main.tsx
touch frontend/src/App.tsx
touch frontend/src/vite-env.d.ts

echo ""
echo "✅ OpenMeshAI scaffold complete!"
echo ""
echo "📂 Structure created at: $(pwd)"
echo ""
echo "Next steps:"
echo "  1. cd openmeshai"
echo "  2. cp backend/.env.example backend/.env"
echo "  3. Add your ANTHROPIC_API_KEY to backend/.env"
echo "  4. docker compose up -d postgres redis"
echo "  5. cd backend && pip install -r requirements.txt"
echo "  6. uvicorn src.main:app --reload      ← starts backend + auto-seeds"
echo "  7. cd ../frontend && npm install && npm run dev"
echo "  8. Open http://localhost:5173 — watch the civilization come alive"
