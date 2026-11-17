---
name: blind-condition-check
description: Use when changing WebSocket payloads, REST routes, protocol.py, AI agents, lobby logic, or any UI that renders messages or players. Checks that nothing reveals whether a participant is human or AI.
---

# Blind condition check

The experiment is invalid if a participant can tell who is AI. Run this checklist after any change that touches payloads, agents, lobby or UI.

1. Payloads: every outbound message is built in backend/app/protocol.py from explicit public fields.
   No DB model or `kind` field is ever serialized. Grep for `kind`, `token`, and `participant_type` in protocol.py, ws.py and routes.py.
2. Endpoints: no route returns participant type (no export or admin route).
3. Tests: run `pytest backend/tests/test_blind.py`. If you added a payload field, extend the test.
4. Timing: AI replies and votes are delayed (length-proportional for chat, random for votes). The AI does not answer every message.
5. Text: AI output passes the filter (no "as an AI", "language model", etc.).
6. Seats: labels are shuffled per session; the AI is not always the same label.
7. UI: human and AI messages render identically, with the same animation and timing. No typing indicators.
8. Waiting room: shows no participant counts and uses a randomized delay in every condition.

Report each item as pass or fail with the file and line. Fix failures before finishing the slice.