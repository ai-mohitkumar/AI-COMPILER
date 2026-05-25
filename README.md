# AI Application Compiler

This project implements a compiler-style pipeline that turns natural language into a validated, repairable, executable mini application.

## Live Demo

- App: https://ai-compiler-a56o.onrender.com
- Health check: https://ai-compiler-a56o.onrender.com/healthz
- API docs: https://ai-compiler-a56o.onrender.com/docs

## What it does

1. Extracts structured intent from a prompt.
2. Builds an intermediate application architecture.
3. Generates separate DB, API, UI, and auth schemas.
4. Validates cross-layer consistency.
5. Repairs only the broken components.
6. Emits a runnable SQLite-backed app served by FastAPI.

## Architecture

```text
Prompt
  -> Intent Extractor
  -> Architect
  -> Schema Generator
  -> Validator
  -> Repair Engine
  -> Runtime Builder
  -> Executable Generated App
```

The system is deliberately modular and deterministic. It uses typed intermediate representations instead of a single freeform generation step.

## Project layout

```text
app/
  pipeline/
  schemas/
  prompts/
  runtime/
  evaluation/
  main.py
generated/
  apps/
tests/
```

## Running locally

```bash
pip install -r requirements-dev.txt
python -m app.server
```

Open `http://127.0.0.1:8000` for the demo UI.

## Environment variables

The app is now deployment-friendly and reads its runtime settings from environment variables.

```text
HOST=0.0.0.0
PORT=8000
APP_ENV=production
LOG_LEVEL=info
WEB_CONCURRENCY=1
GENERATED_APPS_DIR=/data/apps
```

`GENERATED_APPS_DIR` is the most important one for production. Generated apps, manifests, and SQLite files are written there, so it should point at a persistent mounted volume.

## Health check

```bash
curl http://127.0.0.1:8000/healthz
```

This endpoint is intended for container platforms and managed hosts.

## Compile an app

```bash
curl -X POST http://127.0.0.1:8000/compile \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"Build a CRM with login, contacts, tasks, and analytics\"}"
```

The response includes:

- stage outputs
- validation report
- repair log
- generated runtime URLs
- artifact paths

## Evaluation

```bash
python -m app.evaluation.benchmark
```

The benchmark runs normal and edge-case prompts, then reports success rate, repair rate, and latency metrics.

## Notes

- The default generation backend is deterministic and offline-friendly.
- The prompts in `app/prompts/` are included so an LLM-backed provider can be added without changing the compiler stages.
- The runtime is config-driven to prioritize reliability over brittle one-shot code generation.

## Deploying with Docker

Build the image:

```bash
docker build -t ai-app-compiler .
```

Run it with persistent storage:

```bash
docker run -p 8000:8000 \
  -e APP_ENV=production \
  -e GENERATED_APPS_DIR=/data/apps \
  -v ai-app-compiler-data:/data \
  ai-app-compiler
```

Or use Compose:

```bash
docker compose up --build
```

## Managed hosting

- `render.yaml` is included for Render deployment with a persistent disk mounted at `/data`.
- The server entrypoint is `python -m app.server`, which reads `PORT` automatically from the hosting environment.
