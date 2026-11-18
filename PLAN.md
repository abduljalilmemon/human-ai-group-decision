# Development Plan: Multi-Participant Human-AI Experiment Platform

This plan is self-contained. Follow it slice by slice, with or without an AI coding assistant, starting from the repo root.
Rules for the assistant live in CLAUDE.md; if the two ever disagree, CLAUDE.md wins.

## 1. What we are building

A small web app that runs a **3-participant group decision experiment**:

- Three participants with neutral names (Player A, Player B, Player C). Each is a human or an AI agent.
- **Blind condition:** participants must not be able to tell whether the others are human or AI.
- Humans wait in a **waiting room** until every human slot is filled, then the session starts.
- **2 rounds** of real-time text discussion, about 1 minute each. The goal is to elect one of the three as "Decision Maker".
- Participants **vote** at the end of each round. Final results are shown to everyone.
- A **`config.yml`** switches between three conditions without code changes: 3 humans, 2 humans + 1 AI, 1 human + 2 AI.

Required stack: React frontend, Python FastAPI backend, PostgreSQL, Docker, started with a single command.

Required deliverables: source code, `config.yml`, Docker setup, a concise `README.md`, and an **AI usage log**
containing every prompt plus the exact model and tool used.

Scope: the email allows 4 hours (the brief header says 2, its README section says 4). Target about 4 hours and say so in the README.

## 2. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Docker with Compose v2 | Docker 24+ | `docker compose version` |
| git | any recent | `git --version` |
| Node.js (local dev only) | 20+ | `node --version` |
| Python (local tests only) | 3.12+ | `python3 --version` |

Optional: an LLM API key for the AI agent. Without one, the app falls back to a scripted agent and still runs.

## 3. How to work through this plan

1. Do **one slice at a time**, in order. Do not start a later slice early.
2. After each slice, run its **Verify** checks before moving on.
3. After each slice, write down what was built and why. Those notes become the README and the interview slides.
4. Every prompt is logged automatically to `ai_logs/prompts.md` by the hook. After long pasted prompts, skim the log and remove stray tags.
5. Commit after every slice, with a message naming it.
6. Prompt template for each slice:
   `Follow CLAUDE.md and PLAN.md. Implement ONLY slice N: <name>. Do not start other slices. Run the Verify checks and show me how to verify. Stop when done.`

## 4. Architecture

```
Browser (React + Vite + TypeScript + Tailwind)
   │  REST: POST /api/join          WebSocket: /ws?token=…
   ▼
FastAPI  (single process, also serves the built React app)     → http://localhost:8000
   ├─ config.yml → validated settings
   ├─ Lobby              fills human slots, starts sessions
   ├─ SessionEngine      phase state machine + asyncio timers
   ├─ ConnectionManager  WebSocket fan-out per session
   ├─ protocol.py        the only place outbound payloads are built
   └─ AI agents          same interface as a human; LLM or scripted
   ▼
PostgreSQL  (sessions, participants, messages, votes, events)
```

Docker Compose has two services, `app` and `db`. A multi-stage Dockerfile builds the frontend with Node,
then copies `frontend/dist` into the Python image, where FastAPI serves it (API and WebSocket routes registered first).

### Target file layout

```
.
├── docker-compose.yml
├── Dockerfile               # multi-stage: build frontend, run backend
├── config.yml
├── .env.example
├── .gitignore
├── CLAUDE.md
├── PLAN.md
├── README.md
├── ai_logs/prompts.md
├── docs/brief.md
├── tools/log_prompt.py
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # app factory, startup, static files
│   │   ├── config.py        # config.yml loader + validation
│   │   ├── db.py            # engine and session factory
│   │   ├── models.py        # tables
│   │   ├── protocol.py      # builds ALL outbound payloads (public fields only)
│   │   ├── lobby.py         # waiting room and matchmaking
│   │   ├── engine.py        # phase state machine and timers
│   │   ├── ws.py            # WebSocket endpoint and connection manager
│   │   ├── voting.py        # tally and tie-break (pure functions)
│   │   ├── routes.py        # REST endpoints
│   │   └── agents/
│   │       ├── base.py      # agent interface
│   │       ├── llm.py       # LLM-backed agent
│   │       └── scripted.py  # fallback agent
│   └── tests/
└── frontend/
    ├── package.json
    └── src/
        ├── App.tsx
        ├── useSession.ts    # join + WebSocket hook
        └── views/           # Waiting, Discussion, Voting, Results
```

## 5. Design decisions

| Decision | Choice | Why |
|---|---|---|
| Real-time transport | WebSockets | Chat is bidirectional; FastAPI supports it natively. |
| Source of truth | Server-authoritative | The server owns phases and timers; nobody can extend a round or vote twice. |
| Deployment | One app container + Postgres | Fewer moving parts than a separate proxy; one origin, no CORS or WebSocket proxy config. |
| Database | PostgreSQL | Relational data that researchers can query with SQL. |
| Live state | In memory, DB as the record | Simple for one process. A restart loses live sessions; scaling out would need Redis. |
| Schema setup | Create tables at startup | No migration tool. Fine for a prototype; stated as a trade-off. |
| AI agent | LLM with a scripted fallback | The app must run for someone with no API key. |
| Identity | Random token in `sessionStorage` | No login needed. Each tab is a separate participant, and refresh reconnects. |
| Final decision | Round 2 vote decides | Round 1 is a straw poll; its tally is shown before Round 2. |
| Tie-break | Round 1 totals, then a logged random draw | Deterministic first; transparent when it falls to chance. |
| Ballots | Secret; self-votes allowed; a missed vote is an abstention | Matches "vote for one of the 3" and never stalls a session. |
| Voting window | Ends early once all ballots are in | Keeps sessions moving. |
| Data access | No export or admin endpoint | Any endpoint that returns participant type would break the blind condition. Researchers use SQL on the DB. |

## 6. Keeping the blind condition

Hiding a label is not enough. These are the ways the condition leaks, and the defence for each:

| Leak | Defence |
|---|---|
| With 1 human + 2 AI, the session starts the instant the human joins. | The waiting room shows no participant counts and applies a short randomized wait in every condition. |
| The AI always gets the same seat. | Labels are shuffled per session. |
| AI replies arrive instantly and are long and polished. | Replies are delayed in proportion to length, kept short and casual, and the agent does not answer every message. |
| The participant type appears in an API or WebSocket payload. | `protocol.py` builds every payload from an explicit allow-list of public fields. A test asserts no payload key or value reveals type. |
| An endpoint reveals participant type. | There is no such endpoint. |
| The AI says "as an AI…". | The prompt forbids it and an output filter catches that phrasing. |
| AI votes arrive instantly. | Votes are delayed by a random interval. |
| UI differences between human and AI messages. | Identical rendering, timing and animation for every message. No typing indicators. |

## 7. Specifications

### 7.1 `config.yml`

```yaml
experiment:
  rounds: 2
  discussion_seconds: 60
  voting_seconds: 20
  results_pause_seconds: 8      # how long the round-1 tally is shown
  show_round_results: true
  min_wait_seconds: [3, 8]      # random waiting-room delay, all conditions

labels: [Player A, Player B, Player C]

# Change only this block to switch condition.
participants:
- type: human
- type: human
- type: ai

ai:
  provider: anthropic           # anthropic | scripted
  model: claude-haiku-5-5       # confirm the current model ID in the provider's docs
  reply_timeout_seconds: 8
```

Validation rules: exactly 3 participants; each type is `human` or `ai`; at least 1 human; all durations positive; exactly 3 unique labels.

| Condition | `participants` |
|---|---|
| 3 humans | `human, human, human` |
| 2 humans + 1 AI | `human, human, ai` |
| 1 human + 2 AI | `human, ai, ai` |

### 7.2 Phases

```
WAITING → DISCUSSION (round 1) → VOTING (round 1) → ROUND_RESULT
        → DISCUSSION (round 2) → VOTING (round 2) → FINAL
```

### 7.3 REST endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| POST | `/api/join` | Returns `{ token }`; places the caller in the open session |

### 7.4 WebSocket messages (`/ws?token=…`)

Server to client:

| Type | Payload |
|---|---|
| `state` | `phase`, `round`, `phase_ends_at`, `server_now`, `remaining_ms`, `you` (own label), `players` (labels), `has_voted` |
| `message` | `id`, `from` (label), `text`, `sent_at` |
| `round_result` | `round`, `tallies` (label → count) |
| `final_result` | `decision_maker`, `tallies_by_round`, `tie_break` (`none`, `round1`, `random`) |
| `error` | `reason` |

Client to server:

| Type | Payload |
|---|---|
| `chat` | `text` |
| `vote` | `target` (label) |

No payload ever contains a participant's type or another player's token.

### 7.5 Database tables

| Table | Columns |
|---|---|
| `sessions` | `id`, `status`, `condition`, `config_snapshot` (JSON), `created_at`, `started_at`, `ended_at`, `decision_maker_id`, `tie_break` |
| `participants` | `id`, `session_id`, `label`, `kind` (human/ai), `token`, `joined_at` |
| `messages` | `id`, `session_id`, `participant_id`, `round`, `text`, `created_at` |
| `votes` | `id`, `session_id`, `round`, `voter_id`, `target_id` (null = abstain), `created_at`; unique on (`session_id`, `round`, `voter_id`) |
| `events` | `id`, `session_id`, `type`, `payload` (JSON), `created_at` |

## 8. Roadmap (target about 4 hours)

### Slice 1: Scaffold, Docker, config, schema (about 25 min)

- **What:** Repo layout, multi-stage Dockerfile, `docker-compose.yml` (`app`, `db`), health endpoint, placeholder React page served by FastAPI, `config.yml` with Pydantic validation, and the five tables created at startup.
- **Why:** The single-command start is a hard requirement, and everything else depends on config and schema.
- **How:** Minimal FastAPI app. Vite React-TS app with Tailwind. Postgres with a healthcheck; the app waits for it. Mount `config.yml` read-only so switching needs a restart, not a rebuild. SQLAlchemy 2 async with asyncpg.
- **Files:** `docker-compose.yml`, `Dockerfile`, `backend/requirements.txt`, `backend/app/main.py`, `config.py`, `db.py`, `models.py`, `backend/tests/test_config.py`, `frontend/`, `.env.example`.
- **Verify:**
  - `docker compose up --build` starts both containers with no errors.
  - http://localhost:8000 shows the placeholder page and `/api/health` returns `{"status":"ok"}`.
  - `docker compose exec db psql -U postgres -d experiment -c '\dt'` lists five tables.
  - `pytest backend/tests/test_config.py` passes; a config with 4 participants stops startup with a clear error.

### Slice 2: Join and waiting room (about 20 min)

- **What:** `POST /api/join`, the WebSocket connection, lobby logic and the waiting screen.
- **Why:** First end-to-end slice: three tabs reach "session started".
- **How:** Join creates a participant with a random token in the open session, or opens a new session. The frontend stores the token in `sessionStorage` and opens the WebSocket. When all human slots are filled, the lobby shuffles labels, waits the randomized delay, marks the session started and broadcasts `state`. The waiting screen shows no counts. All payloads go through `protocol.py`.
- **Files:** `backend/app/lobby.py`, `ws.py`, `routes.py`, `protocol.py`, `frontend/src/useSession.ts`, `views/Waiting.tsx`.
- **Verify:**
  - With the 3-human config, three tabs leave the waiting room together.
  - A fourth tab lands in a new waiting room.
  - Each tab shows a different player label.

### Slice 3: Session engine and countdown (about 30 min)

- **What:** The phase state machine in 7.2.
- **Why:** The core of the experiment; chat, voting and the AI all hang off it.
- **How:** One asyncio task per session walks the phases, sleeping until each deadline. Each change is saved to `events` and broadcast as `state` with `phase_ends_at`, `server_now` and `remaining_ms`. The client counts down from `remaining_ms`.
- **Files:** `backend/app/engine.py`, `backend/tests/test_engine.py`, `frontend/src/App.tsx`, a countdown component.
- **Verify:**
  - Set short durations in `config.yml` (for example 10 and 5 seconds).
  - All three tabs advance through every phase in sync and end on FINAL.
  - The `events` table has one row per phase change; engine tests pass.

### Slice 4: Real-time chat (about 20 min)

- **What:** Sending, broadcasting and persisting messages through one `submit_chat()` path.
- **Why:** The discussion is the experimental stimulus.
- **How:** Accept `chat` only during DISCUSSION. Trim and cap length (for example 500 characters). Save, then broadcast as `message` with the sender's label.
- **Files:** `backend/app/ws.py`, `engine.py`, `frontend/src/views/Discussion.tsx`.
- **Verify:**
  - A message typed in one tab appears in all three with the right label.
  - Sending during VOTING returns an `error` and nothing is stored.
  - Rows appear in `messages` with the correct round.

### Slice 5: Voting and results (about 25 min)

- **What:** Ballots, tallies, the tie-break and the interim and final screens.
- **Why:** This produces the experiment's outcome.
- **How:** Accept one `vote` per participant per round during VOTING. End the phase early when all ballots are in. Tally and tie-break are pure functions in `voting.py`: Round 2 plurality wins; if tied, the tied player with more Round 1 votes wins; if still tied, a random draw, recorded in `sessions.tie_break`. Missing ballots are stored as abstentions. Show tallies only, never who voted for whom.
- **Files:** `backend/app/voting.py`, `backend/tests/test_voting.py`, `engine.py`, `frontend/src/views/Voting.tsx`, `views/Results.tsx`.
- **Verify:**
  - `pytest backend/tests/test_voting.py` covers clear majority, tie resolved by Round 1, tie resolved by draw, and abstentions.
  - A full manual 3-human run ends with the same Decision Maker on all three screens.
  - A second vote in the same round is rejected.

### Slice 6: AI agent and blind defences (about 30 min)

- **What:** AI participants that chat and vote, plus the section 6 defences.
- **Why:** Enables the two mixed conditions.
- **How:** An agent implements the same interface the engine uses for humans: it receives messages and phase changes and may emit a chat line or a vote. AI slots are filled by the lobby at session start. The LLM agent gets the transcript and a persona prompt, with a hard timeout; on timeout, error or missing key it falls back to the scripted agent. Apply every defence in section 6. Read the API key from `.env`; never commit it. Check the provider's docs for the current model ID and SDK usage before coding.
- **Files:** `backend/app/agents/base.py`, `llm.py`, `scripted.py`, `lobby.py`, `backend/tests/test_blind.py`, `.env.example`.
- **Verify:**
  - 2 humans + 1 AI: two tabs start a session and the third player chats and votes.
  - 1 human + 2 AI: one tab starts a session after the randomized wait.
  - Both conditions work with the API key removed (scripted fallback).
  - `pytest backend/tests/test_blind.py` confirms no payload contains the participant type.
  - Across several sessions the AI's label changes.

### Slice 7: Reconnect and disconnects (about 20 min)

- **What:** Refresh and reconnect handling, and disconnected participants.
- **Why:** A demo that breaks on a page refresh is a bad demo.
- **How:** Reconnecting with the same token replays the current `state` and the chat so far. A disconnected human does not stop the session; their missed votes are abstentions. The UI shows a reconnecting banner.
- **Files:** `backend/app/ws.py`, `frontend/src/useSession.ts`.
- **Verify:**
  - Refresh a tab mid-round: it returns to the same phase with the chat history.
  - Close a tab mid-session: the others finish normally.

### Slice 8: UI polish (about 30 min, time-boxed)

- **What:** A clean, intentional UI with tasteful animation across all views.
- **Why:** The demo is the first impression; the core flow is already working.
- **How:** Tailwind only. Waiting room, chat bubbles with neutral player colors assigned by label, a smooth countdown bar, large clear vote cards, a results screen with a winner reveal, phase transitions, and reconnecting/error states. CSS transitions and keyframes first; respect `prefers-reduced-motion`. Identical styling and animation for every message. Do not change the protocol or backend. The frontend-design skill may be used here.
- **Files:** `frontend/src/**` only.
- **Verify:**
  - Run all three conditions in three side-by-side tabs; nothing looks different for human vs AI messages.
  - Mobile-width and desktop-width layouts both work.
  - Slice 1 to 7 checks still pass.

### Slice 9: README, AI log and final check (about 20 min)

- **What:** The README, the finished prompt log and a slide outline.
- **Why:** These are graded deliverables.
- **How:** README covers: how to run, how to switch conditions, design decisions from section 5, blind-condition measures from section 6, known limitations, and time spent (target about 4 hours). Confirm `ai_logs/prompts.md` is complete, clean of stray tags, and names the model, tool and any skill used. Draft a 5-minute slide outline: problem breakdown, how the AI was steered, issues hit (with at least one correction of the AI), trade-offs, what you would do with more time.
- **Files:** `README.md`, `ai_logs/prompts.md`.
- **Verify:**
  - Clone the repo into a fresh folder and run `docker compose up --build`.
  - Run each of the three conditions end to end.
  - Push to a public GitHub repository and open the link in a private browser window.

If time runs short, cut in this order: UI animations, extra blind defences beyond the type-leak test, disconnect handling. Never cut the clean-clone Docker check or the README.

## 9. Known limitations to state in the README

- Live session state is in memory in a single backend process. A restart ends running sessions.
- No authentication; anyone with the URL can join.
- No database migrations; tables are created at startup.
- One open waiting room at a time; participants are grouped in arrival order.
- The scripted fallback agent is much less convincing than the LLM agent.
- No export endpoint, by design: it could expose participant type. Data is read directly from PostgreSQL.

## 10. Progress tracker

| Slice | Title | Status |
|---|---|---|
| 1 | Scaffold, Docker, config, schema | Done |
| 2 | Join and waiting room | Done |
| 3 | Session engine and countdown | Done |
| 4 | Real-time chat | Done |
| 5 | Voting and results | Done |
| 6 | AI agent and blind defences | Done |
| 7 | Reconnect and disconnects | Not started |
| 8 | UI polish | Not started |
| 9 | README, AI log and final check | Not started |
