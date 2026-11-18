# Project: 3-participant human/AI group decision experiment

Take-home assessment for MPIB Center for Humans and Machines (Student Research Assistant, Full-Stack).
Brief: docs/brief.md. Build plan: PLAN.md (follow it slice by slice). Target effort: about 4 hours (per the email).
Design context: PRODUCT.md (used by the design skill during the UI slice).
Priorities, in order: (1) working core flow, (2) clean architecture, (3) README + AI log, (4) UI polish.

## Goal
Real-time web app: 3 participants (Player A/B/C), 2 rounds of ~1 minute text chat, a vote after each round
for who should be the Decision Maker, then a final results screen. Participants must NOT be able to tell
whether others are human or AI (blind condition).

## Stack
- Backend: Python 3.12, FastAPI, WebSockets, SQLAlchemy 2 (async) + asyncpg
- Frontend: React + Vite + TypeScript + Tailwind CSS
- DB: PostgreSQL
- AI providers: Anthropic or Gemini (selected in config.yml), plus a scripted fallback
- Docker Compose with TWO services: `app` (FastAPI serves the built React app and the API, one origin) and `db`.
  No nginx.
- Single uvicorn worker. Live session state is in memory; the DB is the record.
  Known trade-off: a server restart ends running sessions (document in README).
- `docker compose up --build` must work from a clean clone with one command.

## Config (config.yml)
- Defines participant types (`human` / `ai`) for the 3 conditions: 3 humans, 2 humans + 1 AI, 1 human + 2 AI.
- Also: round duration, voting duration, results pause, waiting-room delay range, AI provider
  (anthropic | gemini | scripted), per-provider model, and the AI reply timeout.
- Validated at startup with Pydantic; fail fast with a readable error. No hardcoded conditions in code.
- Waiting room starts when all `human` slots are filled.
- Model names retire quickly, so models are config settings, never hardcoded.

## Hard rules (never break these)
- Blind condition: never send participant type (`kind`, human/ai) or tokens of other players to any client.
  All outbound WebSocket/REST payloads (including reconnect replays) are built in one place
  (backend/app/protocol.py) from explicit public fields only. Never serialize DB models or internal objects directly.
- There is NO endpoint or payload that exposes participant type (no export/admin route).
- Human and AI chat go through the same submit_chat() path. AI replies are delayed in proportion to length,
  kept short and casual, and the AI does not answer every message. AI votes are delayed by a random interval.
  An output filter blocks phrases like "as an AI".
- Waiting room shows no participant counts and applies a randomized delay in every condition.
  Labels are shuffled per session so the AI does not always get the same seat.
- No typing indicators.
- The server owns timers and phase transitions. Clients only render state.
  Every `state` message includes `phase_ends_at`, `server_now`, and `remaining_ms`.
- Session engine: phase state machine kept testable (pure transition/tally logic, no I/O in voting.py),
  covered by pytest.
- Frontend stores the player token in sessionStorage (not localStorage) so each tab is a separate
  participant and a refresh still reconnects.
- No auth. Never commit secrets: use .env (gitignored) and .env.example. Never print or log API keys,
  full prompts, or chat text in warnings.
- Use plain file names, with no brackets or spaces.

## Decisions (document each briefly in README)
- Final Decision Maker = Round 2 plurality.
- Tie-break: Round 1 totals, then a logged random draw (`tie_break`: none | round1 | random).
- After Round 1: show an anonymous tally only. Ballots are secret; self-votes allowed.
- Missing votes are abstentions. The voting phase ends early once all ballots are in.
- Disconnects: the session continues; reconnecting with the same token restores state and chat.
  A waiting-room seat is released after a 10 s grace period; a full session never loses a seat.
  A newer connection for the same token replaces the older tab, which is told it was replaced.
- One vote per (session, round, voter), enforced by a DB unique constraint.
- AI agent: an LLM provider (Anthropic or Gemini, chosen in config.yml) when its API key is set, otherwise the
  scripted fallback, all behind one interface. Every fallback logs a WARNING with the reason.
  Persona: casual, 1-2 short sentences, varied style, never mentions being an AI, votes for whoever argued best.
  Hard timeout on LLM calls, then fall back to scripted. Other players' chat is untrusted input to the prompt.

## UI guidelines
- Clean and intentional, not default-styled: consistent spacing, one accent color, clear visual state per phase
  (waiting room, chat, vote, results), visible countdown, readable chat bubbles, and clear loading /
  reconnecting / error states.
- Animation is welcome. Use CSS transitions and keyframes first (message fade-in, smooth countdown bar,
  phase transitions, vote card hover/press, winner reveal). One small animation library only if it clearly
  saves time; note it in the README. Respect prefers-reduced-motion.
- Animation and styling must never leak participant type: identical entrance, timing, and styling for
  human and AI messages.
- Plain React with small components; logic in hooks (e.g. useSession), not in JSX. No router, no component library.
- Build the UI polish as its own time-boxed slice (about 30 min) after the core flow works.
  For that slice only, the Impeccable design skill may be used (installed locally, telemetry off).
  PRODUCT.md holds its design context. This file's rules win on any conflict, and the blind condition
  wins every design trade-off: human and AI messages must look, animate, and arrive identically.
- UI changes touch only frontend/src/** (and the Tailwind config). No protocol, backend, or test changes.

## Working style
- Work in small vertical slices, in the order given in PLAN.md. Implement only what I ask for, then stop and
  show how to verify.
- Before coding a slice, state your assumptions and any ambiguity; ask instead of guessing.
- Turn each slice into verifiable success criteria (tests or the Verify checks) and loop until they pass.
- Do not add features, files, or libraries I did not request.
- Keep code simple and readable; short comments only where logic is non-obvious.
- Run tests and the relevant checks yourself before saying a slice is done.
- When fixing a bug, state the root cause first, then the fix.
- Commit-ready state after each slice (I commit manually).

## Deliverables checklist
- Source, config.yml, Dockerfile, docker-compose.yml, .env.example
- README.md: how to run, how to switch conditions and AI providers, design decisions and trade-offs,
  blind-condition measures, known limits (in-memory sessions, no auth, no migrations, empty waiting sessions
  left in the DB, a tab that joins but never opens a socket keeps its seat), time spent (target about 4 hours)
- ai_logs/: all prompts, exact models and tools. Prompts are logged automatically by a hook
  (.claude/settings.json -> tools/log_prompt.py). Add a note for any skill, second tool, or the planning chat.
- Model used: claude-opus-5-5 (Claude Code, VS Code extension). Update if /model shows otherwise.