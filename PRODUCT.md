# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Two audiences with equal weight:

- **Study participants.** People who join one session of a 3-person group decision experiment, use it once, and have no prior context. They chat for two short rounds, vote twice, and see the result. They must never be able to tell which of the other two players are humans and which are AI agents.
- **MPIB evaluators.** Reviewers at the Center for Humans and Machines (Max Planck Institute for Human Development) assessing this take-home for a Student Research Assistant (Full-Stack) role. They run it locally with Docker, usually in several browser tabs at once, during a 5-minute demo, and read the code and README.

## Product Purpose
A lightweight real-time platform for a 3-participant human/AI group decision experiment. Three players (Player A/B/C) discuss for two rounds of about one minute each and vote after each round for who should be the "Decision Maker" for a later, imaginary experiment. A final results screen names the Decision Maker.

Success: the core flow works end to end in every condition, the blind condition holds, and the build shows clean architecture and pragmatic judgment under a roughly 4-hour time box.

## Positioning
A research instrument, not a consumer chat app. What sets it apart is that the blind condition is enforced structurally: human and AI participants share one chat path, one payload builder, identical rendering and timing, and no interface element shows participant type.

## Operating Context
- Phases: waiting room → discussion (round 1) → vote → anonymous tally → discussion (round 2) → vote → final results.
- Conditions are switched in `config.yml`: 3 humans, 2 humans + 1 AI, 1 human + 2 AI.
- The server owns all timers and phase changes. Clients only render state and a visible countdown.
- Each browser tab is a separate participant (token in sessionStorage). A refresh reconnects.
- Run locally with `docker compose up --build`. Primary device is a desktop browser, often several tabs side by side for the demo. Phone layouts should still work but are not the main target.

## Capabilities and Constraints
- Stack is fixed: React + Vite + TypeScript + Tailwind, FastAPI with WebSockets, PostgreSQL, Docker Compose (`app` + `db`).
- Plain React with small components and logic in hooks. No router, no component library. At most one small animation library, and only if it clearly saves time.
- No typing indicators. The waiting room shows no participant counts and adds a random delay in every condition.
- Human and AI messages must look, animate, and arrive the same way. No styling, timing, or wording may reveal participant type.
- Round 1 shows an anonymous tally only. Ballots are secret and self-votes are allowed. Missing votes count as abstentions.
- UI polish is one time-boxed slice (about 30 min) after the core flow works. CLAUDE.md rules win over design guidance.
- Terminology: "Player A/B/C", "Round", "Decision Maker", "waiting room", "vote".

## Brand Commitments
No brand identity, logo, or name beyond the neutral experiment framing. Voice is neutral and plain, like a research instrument: instructions are clear and short, and the copy never steers votes or hints at who is human or AI.

## Evidence on Hand
- Assessment brief: `docs/brief.md`. Build plan: `PLAN.md`. Experiment parameters: `config.yml`.
- No testimonials, users, study data, or institutional endorsements exist. Do not invent any, and do not imply MPIB branding or affiliation in the UI.

## Product Principles
1. The blind condition wins every trade-off. Any visual or behavioral difference between human and AI is a defect.
2. Neutral does not mean careless. The interface must not bias decisions, but it must feel intentional and trustworthy.
3. The phase is always clear. A participant should always know which phase they are in, how much time is left, and what to do next.
4. The server is the truth. The UI renders state; it never predicts or invents it.
5. Working core flow first, polish last and time-boxed.

## Accessibility & Inclusion
Target WCAG 2.2 AA: sufficient contrast, full keyboard operation (chat input and vote choices), visible focus, countdowns and phase changes announced to assistive tech without being noisy, and support for prefers-reduced-motion.

## Visual Direction
Dark, premium, calm: a deep ink-navy background with a few large soft glow orbs that drift slowly,
and frosted glass panels (translucent fill, 1px light border, backdrop blur, soft shadow). Rounded corners,
pill chips, small wide-tracked uppercase labels, and an accent that glows on focus and on primary actions.
This is a style choice only. It must not use sparkle icons, "AI"/"assistant" wording, online/status
indicators, or any element that differs between human and AI participants. Text must keep WCAG AA contrast
over glass, with a solid fallback when blur or transparency is unavailable or reduced.
