import { useEffect, useRef, type ReactNode } from "react";
import { AnimatePresence, LazyMotion, MotionConfig, domAnimation, m } from "motion/react";
import Aurora from "./Aurora";
import { AvatarDeal } from "./avatars/Avatar";
import { useTheme } from "./theme";
import { useSession, type ServerState } from "./useSession";
import { Banner, ErrorLine, Spinner, Stepper, ThemeSwitch } from "./ui";
import Discussion from "./views/Discussion";
import { FinalResults, RoundTally } from "./views/Results";
import Voting from "./views/Voting";
import Waiting from "./views/Waiting";

const SESSION_GONE = "Your previous session is no longer available.";

const PHASE_ANNOUNCE: Record<ServerState["phase"], (round: number) => string> = {
  WAITING: () => "Waiting room.",
  DISCUSSION: (r) => `Round ${r} discussion has started.`,
  VOTING: (r) => `Round ${r} vote is open.`,
  ROUND_RESULT: (r) => `Round ${r} results.`,
  FINAL: () => "Final results.",
};

const STEPS_JOIN = ["Two short rounds of chat", "A secret vote after each round", "The final vote picks the Decision Maker"];

function Join({ onJoin, busy, error }: { onJoin: () => void; busy: boolean; error: string | null }) {
  const sessionGone = error === SESSION_GONE;
  return (
    <div className="text-center">
      <h1 className="text-3xl font-semibold tracking-tight text-balance">Group Decision Study</h1>
      <p className="mx-auto mt-3 max-w-[42ch] text-muted">
        You will chat with two other participants for two short rounds and vote for a Decision Maker.
      </p>
      <ol className="mx-auto mt-7 flex max-w-md flex-wrap justify-center gap-2 text-sm">
        {STEPS_JOIN.map((s, i) => (
          <li key={s} className="flex items-center gap-3 rounded-full bg-surface py-2 pr-4 pl-2 ring-1 ring-line">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text">
              {i + 1}
            </span>
            <span className="text-ink">{s}</span>
          </li>
        ))}
      </ol>
      {sessionGone && (
        <p role="status" className="mt-6 animate-enter rounded-2xl bg-warn-bg px-4 py-3 text-sm text-warn-ink ring-1 ring-warn-ink/25">
          Your previous session is no longer available. You can join a new one.
        </p>
      )}
      {error && !sessionGone && (
        <div className="mt-6 flex justify-center">
          <ErrorLine>{error}</ErrorLine>
        </div>
      )}
      <button
        onClick={onJoin}
        disabled={busy}
        className="btn-primary mt-8 inline-flex min-w-44 items-center justify-center gap-2 rounded-full px-7 py-3 font-semibold transition duration-150 hover:-translate-y-px active:translate-y-0 active:scale-[0.97] disabled:cursor-wait disabled:opacity-70"
      >
        {busy && <Spinner />}
        {busy ? "Joining…" : sessionGone ? "Join a new session" : "Join"}
      </button>
    </div>
  );
}

export default function App() {
  const session = useSession();
  const theme = useTheme();
  const { status, state } = session;
  const replaced = status === "replaced";
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (panel.current) panel.current.inert = replaced; // React 18 has no inert prop
  }, [replaced]);
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">
        <Aurora />
        <AnimatePresence>
          {status === "reconnecting" && state && (
            <Banner key="reconnecting" tone="warn">
              <Spinner /> Connection lost. Reconnecting…
            </Banner>
          )}
          {replaced && (
            <Banner key="replaced" tone="info">
              Opened in another tab. Please continue there and close this one.
            </Banner>
          )}
        </AnimatePresence>
        {/* Changes only on a phase change, so screen readers hear each phase once. */}
        <p className="sr-only" aria-live="polite">
          {state ? PHASE_ANNOUNCE[state.phase](state.round) : ""}
        </p>

        <div className="min-h-dvh px-4 pt-[6vh] pb-12 text-ink sm:px-6 sm:pt-[9vh]">
          <div className="mx-auto w-full max-w-xl">
            {state && (
              <div className="mb-5 px-2">
                <Stepper phase={state.phase} round={state.round} />
              </div>
            )}
            {/* A replaced tab keeps its last screen, dimmed and inert, under the banner. */}
            <main
              ref={panel}
              className={`glass panel relative overflow-hidden p-6 transition-opacity duration-300 sm:p-8 ${replaced && state ? "opacity-50" : ""}`}
            >
              <AnimatePresence mode="popLayout" initial={false}>
                <m.div
                  key={screenKey(session)}
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8, transition: { duration: 0.15 } }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                >
                  <AvatarDeal seed={state?.avatar_seed ?? null} labels={state?.players ?? []}>
                    <Screen session={session} />
                  </AvatarDeal>
                </m.div>
              </AnimatePresence>
            </main>
            <div className="mt-6 flex justify-center">
              <ThemeSwitch choice={theme.choice} onChange={theme.setChoice} />
            </div>
          </div>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}

type Session = ReturnType<typeof useSession>;

function screenKey({ status, state }: Session): string {
  if (status === "idle" || status === "joining" || (status === "error" && !state)) return "join";
  if (!state) return status === "replaced" ? "replaced" : "connecting";
  return `${state.phase}-${state.round}`;
}

function Screen({ session }: { session: Session }): ReactNode {
  const { status, state, error, messages, roundResult, finalResult, join, sendChat, sendVote } = session;

  if (status === "idle" || status === "joining" || (status === "error" && !state)) {
    return <Join onJoin={join} busy={status === "joining"} error={error} />;
  }
  if (!state) {
    if (status === "replaced") {
      return (
        <div className="text-center">
          <h1 className="text-xl font-semibold">Opened in another tab</h1>
          <p className="mx-auto mt-2 max-w-[40ch] text-muted">
            This session is now running in another tab or window. Please continue there and close this one.
          </p>
        </div>
      );
    }
    return (
      <p role="status" className="flex items-center justify-center gap-2 py-6 text-muted">
        <Spinner /> {status === "reconnecting" ? "Connection lost. Reconnecting…" : "Connecting…"}
      </p>
    );
  }
  switch (state.phase) {
    case "WAITING":
      return <Waiting />;
    case "DISCUSSION":
      return (
        <Discussion state={state} messages={messages} error={error} onSend={sendChat} />
      );
    case "VOTING":
      return <Voting key={state.round} state={state} error={error} onVote={sendVote} />;
    case "ROUND_RESULT":
      return <RoundTally state={state} result={roundResult} />;
    case "FINAL":
      return <FinalResults state={state} result={finalResult} />;
  }
}
