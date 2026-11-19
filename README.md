# Human-AI Group Decision Experiment

A real-time web app for a 3-participant group decision experiment. Three players (Player A, B, C) chat for two rounds of about a minute each, vote after each round for who should be the group's Decision Maker, and then all see the final result. Each seat is filled by a human or an AI agent, as set in `config.yml`.

Built as a take-home assessment for the Center for Humans and Machines (MPIB).

**Blind condition.** Participants must not be able to tell whether the others are human or AI. The server never sends a participant's type to any client. Every outbound payload is built in one file (`backend/app/protocol.py`) from an explicit list of public fields, and no endpoint exposes type. Beyond hiding the label, the app removes behavioural tells. The waiting room shows no counts and always waits a random time. Seat labels are shuffled per session. AI chat goes through the same path as human chat, with human-like delays, short casual lines, no reply to every message and a filter on phrases like "as an AI". AI votes arrive after a random delay. Every message looks and animates the same.

## Quick start

Requires Docker with Compose v2.

```bash
docker compose up --build
```

Open http://localhost:8000. Health check: http://localhost:8000/api/health returns `{"status":"ok"}`.

- **No `.env` is needed.** Without one, Postgres uses the default credentials and AI seats use the scripted agent.
- **Optional `.env`** (copy `.env.example`): `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, `APP_PORT`.
- **Port taken?** Set the host port with `APP_PORT`: `APP_PORT=8001 docker compose up --build` (PowerShell: `$env:APP_PORT=8001; docker compose up --build`), or put `APP_PORT=8001` in `.env`.

Each browser tab is one participant: open as many tabs as the condition has human seats.

## Switch condition

Edit the `participants` block in `config.yml`:

| Condition | `participants` |
|---|---|
| 3 humans | `human, human, human` |
| 2 humans + 1 AI | `human, human, ai` |
| 1 human + 2 AI | `human, ai, ai` |

```yaml
participants:
- type: human
- type: human
- type: ai
```

Then restart the app. `config.yml` is mounted read-only into the container, so no rebuild is needed:

```bash
docker compose restart app
```

The config is validated with Pydantic at startup. An invalid file (for example 4 participants, no human, or duplicate labels) stops the app with a readable error. The same file also sets the round, voting and results-pause durations and the waiting-room delay range.

## Switch AI provider

```yaml
ai:
  provider: gemini                     # anthropic | gemini | scripted
  model: claude-haiku-5-5              # used when provider is anthropic (ANTHROPIC_API_KEY)
  gemini_model: gemini-3.5-flash-lite  # used when provider is gemini (GEMINI_API_KEY)
  reply_timeout_seconds: 8
```

- `anthropic`: Anthropic Messages API. Needs `ANTHROPIC_API_KEY` in `.env`.
- `gemini`: Google Gemini (`google-genai`). Needs `GEMINI_API_KEY` in `.env`.
- `scripted`: no API at all. Canned casual lines chosen to fit the last message.

**Fallback.** If the selected provider's key is not set, every AI seat uses the scripted agent, and the app logs a WARNING-level line at startup: `gemini agent fell back to scripted: GEMINI_API_KEY is not set`. With a key, any single call that times out (`reply_timeout_seconds`), errors, gets rate limited, is cut off or is blocked by the output filter falls back to a scripted line, with a WARNING naming the reason. Keys, prompts and chat text are never logged. See the logs with `docker compose logs app`.

Model names are config settings, not code, because provider model IDs are retired quickly. Change them in `config.yml` and restart.

## Architecture

```
Browser (React + Vite + TypeScript + Tailwind)
   │  REST: POST /api/join → { token }      WebSocket: /ws?token=…
   ▼
FastAPI, one uvicorn worker (also serves the built React app)   → http://localhost:8000
   ├─ config.py      config.yml → validated settings (fail fast)
   ├─ lobby.py       waiting room: seats humans, shuffles labels, random delay, adds AI seats
   ├─ engine.py      phase state machine + asyncio timers; submit_chat() / submit_vote()
   ├─ voting.py      tally and tie-break (pure functions, no I/O)
   ├─ ws.py          WebSocket endpoint, one live socket per token, per-session fan-out
   ├─ protocol.py    the ONLY place outbound payloads are built (public fields only)
   └─ agents/        AI seats: Anthropic, Gemini or scripted behind one interface
   ▼
PostgreSQL  (sessions, participants, messages, votes, events)
```

- Docker Compose runs two services, `app` and `db`. A multi-stage Dockerfile builds the frontend with Node and copies it into the Python image, where FastAPI serves it from the same origin as the API and WebSocket. There is no nginx, no CORS and no proxy config.
- The server owns all timers and phase changes. Every `state` message carries `phase_ends_at`, `server_now` and `remaining_ms`, and the client only renders it.
- Live session state lives in memory in the single process, and the database is the record. Tables are created at startup (no migration tool).
- Phases: `WAITING → DISCUSSION (1) → VOTING (1) → ROUND_RESULT → DISCUSSION (2) → VOTING (2) → FINAL`. Each change is written to `events`.
- There is no export or admin endpoint. Researchers query the data directly, e.g. `docker compose exec db psql -U postgres -d experiment`.

## Experiment flow and design decisions

1. **Join.** `POST /api/join` returns a random token, which the frontend keeps in `sessionStorage`. Each tab is a separate participant, and a refresh keeps the seat. There is one open waiting room at a time, and humans are grouped in arrival order.
2. **Waiting room.** Once every human seat is filled, the session starts after a random delay from `min_wait_seconds`. The delay applies in every condition. AI seats take the remaining labels.
3. **Discussion.** Text chat, accepted only during the discussion phase. Messages are trimmed and capped at 500 characters, then saved and broadcast with the sender's label.
4. **Vote.** Each participant votes for one of the three players. Ballots are secret and self-votes are allowed. The phase ends early once all ballots are in.
5. **Round 1 result.** Only an anonymous tally (votes per player) is shown, never who voted for whom.
6. **Round 2 and final.** The Round 2 plurality decides the Decision Maker.

| Decision | Choice |
|---|---|
| Final decision | Round 2 plurality. Round 1 is a straw poll. |
| Tie-break | The tied player with more Round 1 votes wins. If still tied, a random draw. The method (`none`, `round1`, `random`) is stored in `sessions.tie_break` and shown on the results screen. |
| Missing vote | Counted as an abstention and stored as a vote with no target. A session never stalls. |
| One vote per round | Checked by the engine and enforced by a DB unique constraint on (session, round, voter). |
| Disconnect | The session continues without the player, and their missed votes are abstentions. Reconnecting with the same token replays the current state, the chat so far and any results already shown. |
| Waiting-room seat | A human who leaves the open waiting room keeps the seat for 10 s, so a refresh doesn't lose it. After that the seat is released. Once a session is full, no seat is ever released. |
| Two tabs, one token | The newer connection replaces the older one, which is told it was replaced and stops reconnecting. |
| Server authority | The server owns phases and deadlines. Clients can't extend a round or vote twice. |

## Blind-condition measures

| Leak | Defence |
|---|---|
| Participant type in an API or WebSocket payload | `protocol.py` builds every payload, including reconnect replays, from an explicit allow-list of public fields. Tests assert that no payload contains type or another player's token (`test_blind.py`, `test_protocol.py`). |
| An endpoint that reveals type | None exists: only `/api/health`, `/api/join` and `/ws`. |
| With 1 human + 2 AI, the session starts the instant the human joins | The waiting room shows no counts or labels, and the random delay applies in every condition. |
| The AI always gets the same seat | Labels are shuffled per session. Humans take them in arrival order, and AI seats take the rest. |
| Seat order leaks type (humans join first) | Player lists and tallies are always sent sorted by label, never in seat order. |
| Instant, long or polished AI replies | Lines are capped at 220 characters and the persona asks for 1-2 casual sentences. Each reply waits for a "reading" time (1.5-4 s) plus typing time proportional to its length, between 2 and 14 s in total. |
| The AI answers everything | It answers another player's message with a 60% chance (90% when named), writes at most 3 lines per round, and doesn't always open a round. |
| The AI says "as an AI" | The persona forbids it, and an output filter drops any line containing words such as "AI", "bot", "assistant", "language model" or a provider name. A dropped line falls back to a scripted line. |
| Instant AI votes | Each vote lands at a random point between 25% and 65% of the voting window. |
| Prompt injection via chat | Other players' chat goes into the prompt as untrusted content inside `<chat>` tags, with angle brackets neutralised. |
| UI differences | Every message has the same component, styling, entrance animation and timing. There are no typing indicators. |

Human and AI chat share one `submit_chat()` path, and votes share one `submit_vote()` path.

## Testing

The tests use fakes, not the database, so they run inside the app container or locally:

```bash
docker compose exec app python -m pytest -q
```

Locally (Python 3.12): `pip install -r backend/requirements.txt`, then `cd backend && python -m pytest -q`.

They cover config validation, the phase state machine, chat rules, voting and tie-breaks, agent behaviour and the output filter, the Gemini adapter, reconnect replay, and the blind-condition checks on every payload.

## AI tooling and process

- **Tool and model:** Claude Code (VS Code extension), model `claude-opus-5-5`.
- **Process:** `PLAN.md` splits the build into nine vertical slices, done one at a time, each with its own Verify checks. `CLAUDE.md` holds the standing rules for the assistant (hard rules for the blind condition, stack, working style).
- **Skills:**
  - `claude-api` (bundled with Claude Code): used to confirm the current Anthropic model ID and SDK usage before writing `agents/llm.py`.
  - `blind-condition-check` (my own, `.claude/skills/blind-condition-check/SKILL.md`): an 8-point checklist run after every slice that touched payloads, agents, the lobby or the UI.
  - **Impeccable** design skill, used only for the UI polish slice. It is installed locally (gitignored, not part of the repo) with telemetry off. Its design context is in `PRODUCT.md`.
- **Gemini provider:** added as a second LLM provider (`agents/gemini.py`). It shares the persona, filter, timeout and fallback with the Anthropic agent, and was written against the installed `google-genai` 3.5.0 SDK.
- **Prompt log:** every prompt is logged automatically to `ai_logs/prompts.md` by a `UserPromptSubmit` hook (`.claude/settings.json` → `tools/log_prompt.py`), with timestamp, tool and model. Notes on skills used are added below the relevant prompts.
- **Planning chat:** the planning chat held before coding is logged in `ai_logs/`. TODO-PLANNING-CHAT: add the file.

## UI notes

- React with small components and logic in hooks (`useSession.ts`). Tailwind CSS, no router and no component library. The look is dark glass with one accent colour.
- **`motion` is the only animation library.** It is loaded through `LazyMotion` with the `domAnimation` feature set (strict mode) to keep the bundle small. CSS transitions and keyframes cover the rest.
- **Accessibility:** the chat is a `role="log"` live region, the countdown is a `role="timer"` with a separate polite announcement, status and error messages use `role="status"`/`role="alert"`, and there are visible focus rings.
- **Reduced motion:** `prefers-reduced-motion` turns off CSS animations and transitions, and `MotionConfig reducedMotion="user"` does the same for motion.
- **Reduced transparency:** `prefers-reduced-transparency`, or a browser without `backdrop-filter`, gets solid panels instead of glass, and the background orbs are hidden.
- **Trade-off:** the polished, "premium" look suits a demo, but in a real study a striking interface could itself influence how people behave. A plain, neutral theme would be preferable for actual research.

## Known limitations

- Live session state is in memory in a single backend process. A server restart ends running sessions, and their tokens stop working.
- No authentication: anyone with the URL can join.
- No database migrations: tables are created at startup.
- Waiting sessions that never fill are left in the database with status `waiting`.
- A tab that joins but never opens a WebSocket keeps its waiting-room seat. The 10 s release only starts when a socket closes.
- The 10 s seat grace period is a constant in `lobby.py`, not a config setting.
- The scripted fallback agent is much less convincing than an LLM agent.
- One open waiting room at a time, and participants are grouped in arrival order.
- No export endpoint, by design. Data is read directly from PostgreSQL.

## Time spent

TODO-TIME (target: about 4 hours, per the assessment email).
