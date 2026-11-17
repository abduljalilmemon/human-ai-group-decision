
## Prompt 1 - 2026-11-17 20:14
- Tool: Claude Code (VS Code extension)
- Model: claude-opus-5-5

```text
<pasted_content id="0d0a">
I'm doing a 2-hour take-home assessment. The full brief is in docs/brief.md. Read it, plus the rules file in this repo, before answering.

Do NOT write any code yet. Propose a plan covering:

1. Repo structure (backend, frontend, docker-compose, config.yml, ai_logs)
2. The session state machine (WAITING -> ROUND_1 -> VOTE_1 -> ROUND_2 -> VOTE_2 -> RESULTS) and the WebSocket message protocol, as tables (message type, direction, payload)
3. The MongoDB schema (sessions, messages, votes)
4. How we guarantee the blind condition, so participant type (human or ai) never reaches any client payload
5. How config.yml defines the three conditions (3 humans, 2 humans + 1 AI, 1 human + 2 AI) and how the waiting room works with it

Constraints: FastAPI + React + MongoDB + Docker Compose, no auth, no dependencies beyond what's needed, minimal and pragmatic.

Finally, list the open decisions (tie-breaking, intermediate feedback after round 1, final-result rule, AI agent behavior, player disconnects) with two options each, trade-offs, and your recommended default. Keep the whole answer concise.
</pasted_content id="0d0a">
```
