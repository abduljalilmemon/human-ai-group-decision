# Project: 3-participant human/AI group decision experiment

Take-home assessment for MPIB Center for Humans and Machines (Student Research Assistant, Full-Stack).
Full brief: docs/brief.md. Target effort is about 2 hours (the brief says 2, the email says 4), so keep everything minimal.
Priorities, in order: (1) working core flow, (2) clean architecture, (3) README + AI log, (4) UI polish.

## Goal
Real-time web app: 3 participants (Player A/B/C), 2 rounds of ~1 minute text chat, a vote after each round
for who should be the Decision Maker, then a final results screen. Participants must NOT be able to tell
whether others are human or AI (blind condition).

## Stack
- Backend: Python, FastAPI, WebSockets, Motor (MongoDB)
- Frontend: React (Vite) + Tailwind CSS
- DB: MongoDB
- Docker Compose: app (FastAPI serving the built React app, one origin) + mongo
- Single uvicorn worker. Session state lives in memory and is persisted to Mongo.
  Known trade-off: a server restart loses active sessions (document in README).
- `docker compose up --build` must work from a clean clone with one command.

## Config (config.yml)
- Defines participant types (`human` / `ai`) for the 3 conditions: 3 humans, 2 humans + 1 AI, 1 human + 2 AI.
- Also: round duration, vote duration, AI settings.
- No hardcoded conditions anywhere in code.
- Waiting room size = number of `human` slots. With 1 human, start immediately.

## Hard rules (never break these)
- Blind condition: never send participant type (human/ai), `kind`, or other players' `client_id` to any
  client payload. All outbound messages are built in one place (backend/app/protocol.py) from explicit
  public fields only. Never serialize internal objects directly.
- Human and AI chat go through the same submit_chat() path. AI replies get a human-like randomized delay.
- The server owns timers and phase transitions. Clients only render state.
  Every phase message includes both `ends_at` and `remaining_ms` (client clocks can drift).
- State machine is a pure class with no I/O, covered by pytest:
  WAITING -> ROUND_1 -> VOTE_1 -> ROUND_2 -> VOTE_2 -> RESULTS.
- Frontend stores `client_id` in sessionStorage (not localStorage) so multiple tabs act as different players
  and a refresh still reconnects.
- No auth. Never commit secrets: use .env (gitignored) and .env.example.
- Use plain file names, with no brackets or spaces.

## Decisions (document each briefly in README)
- Final Decision Maker = round 2 votes.
- Tie-break: round 1 tally, then random (record `decided_by` in the result).
- After round 1: show an anonymous tally only.
- Disconnects: session continues, missing votes count as abstentions, reconnect restores state.
- Unique vote per (session, round, voter).
- AI agent: LLM when ANTHROPIC_API_KEY is set, otherwise a scripted fallback, both behind one interface.
  Persona: casual, short (1-2 sentences), varied style, never mentions being an AI, votes for whoever
  argued best.

## UI guidelines
- Clean and intentional, not default-styled: consistent spacing, one accent color, clear visual state for each
  phase (waiting room, chat, vote, results), visible countdown, readable chat bubbles, and clear
  loading / reconnecting / empty states.
- Animation is welcome. Use CSS transitions and keyframes first (message fade-in, smooth countdown bar,
  phase transitions, vote card hover/press, winner reveal). One small animation library is allowed only if
  it clearly saves time; note it in the README.
- Respect prefers-reduced-motion.
- Animation and styling must never leak participant type: identical entrance, timing, and styling for
  human and AI messages. No special typing indicator for AI.
- Plain React with small components; logic in hooks (e.g. useWebSocket), not in JSX. No router, no component library.
- Build the UI after the core flow works, as a separate time-boxed polish slice (about 30 min).
  For that slice only, the frontend-design skill may be used. This file's rules still win on any conflict.

## Working style
- Work in small vertical slices. Implement only what I ask for, then stop and show how to verify.
- Do not add features, files, or libraries I did not request.
- Keep code simple and readable. Short README-friendly comments only where logic is non-obvious.
- Run tests and `docker compose up --build` yourself before saying a slice is done.
- When fixing a bug, state the root cause first, then the fix.
- Suggested slices: 1 skeleton + config + Docker, 2 state machine + tests, 3 WebSocket chat + waiting room,
  4 voting + results, 5 AI agent, 6 UI polish, 7 README + final clean-clone check.

## Deliverables checklist
- Source, config.yml, Dockerfile(s), docker-compose.yml
- README.md: how to run, how to switch configs, design decisions and trade-offs, known limits
- ai_logs/: all prompts, exact models and tools. Prompts are logged automatically by a hook
  (.claude/settings.json -> tools/log_prompt.py). Add a note for any skill or second tool used.
- Model used: claude-opus-5-5 (Claude Code, VS Code extension). Update if /model shows otherwise.