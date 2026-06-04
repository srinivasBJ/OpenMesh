# OpenMesh FAQ

## What is OpenMesh?

OpenMesh is a terminal-first observability layer for AI agent ecosystems.

## Do I need API keys?

No. `openmesh simulate` and `openmesh run -- <command>` work locally without API
keys. Real LLM demos require configured provider keys or a running local model
server.

## Do I need Docker or Postgres?

No. SQLite is the validated first-user path.

## Why does an integration say "Not installed"?

OpenMesh ships plugin metadata and lightweight integration code, but optional
framework packages such as LangGraph, CrewAI, AutoGen, and OpenHands are not
installed by default.

## Why does `run-demo research` fail?

It calls a real configured provider. Set `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, or start Ollama, LM Studio, or vLLM
before using that command.

## What should I run first?

```bash
openmesh doctor
openmesh simulate --agents 12 --events 180 --nodes 4
openmesh graph --details
```

## Is the dashboard required?

No. The CLI and TUI are the primary OpenMesh surfaces. The frontend is a browser
visualization layer over the same API and database.

## Which Python version should I use?

Use Python 3.11, 3.12, or 3.13. Python 3.14 is not supported in this alpha.
