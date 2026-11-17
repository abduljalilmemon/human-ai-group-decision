# Human-AI Group Decision Experiment

A real-time web app that simulates a 3-participant group decision experiment. Three players (Player A/B/C) discuss for two rounds, vote for a Decision Maker after each, and see the final result. Participants cannot tell whether the others are human or AI.

Built as a take-home assessment for the Center for Humans and Machines (MPIB). Work in progress: see PLAN.md for the build roadmap.

## Stack
FastAPI (Python), React + Vite + TypeScript + Tailwind, PostgreSQL, Docker Compose.

## Run
```bash
docker compose up --build
```
Open http://localhost:8000 (health check: http://localhost:8000/api/health).
If port 8000 is taken, use another host port: `APP_PORT=8001 docker compose up --build`
(PowerShell: `$env:APP_PORT=8001; docker compose up --build`).

## Switch condition
Edit the `participants` block in `config.yml`, then restart the app (no rebuild needed):

| Condition | participants |
|---|---|
| 3 humans | human, human, human |
| 2 humans + 1 AI | human, human, ai |
| 1 human + 2 AI | human, ai, ai |

```bash
docker compose restart app
```
The config is validated at startup; an invalid file stops the app with a readable error.

## Tests
```bash
docker compose exec app python -m pytest -q
```

## AI usage
All prompts, models, and tools are logged in `ai_logs/prompts.md`.