import type { ReactNode } from "react";
import { useSession, type ServerState } from "./useSession";
import { ErrorLine, Spinner } from "./ui";
import Discussion from "./views/Discussion";
import { FinalResults, RoundTally } from "./views/Results";
import Voting from "./views/Voting";
import Waiting from "./views/Waiting";

const SESSION_GONE = "Your previous session is no longer available.";

// `screenKey` re-mounts the card content on a phase change, which plays one shared entrance.
function Card({ children, wide = false, screenKey }: { children: ReactNode; wide?: boolean; screenKey: string }) {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-8 text-ink sm:px-6">
      <div
        className={`w-full ${wide ? "max-w-2xl p-5 sm:p-7" : "max-w-md p-7 sm:p-9"} rounded-3xl bg-surface shadow-[0_1px_2px_oklch(26%_0.025_262/0.06),0_12px_32px_-12px_oklch(26%_0.025_262/0.14)] ring-1 ring-line`}
      >
        <div key={screenKey} className="animate-enter">
          {children}
        </div>
      </div>
    </main>
  );
}

function Join({ onJoin, busy, error }: { onJoin: () => void; busy: boolean; error: string | null }) {
  const sessionGone = error === SESSION_GONE;
  return (
    <div className="text-center">
      <h1 className="text-2xl font-semibold text-balance">Group Decision Study</h1>
      <p className="mx-auto mt-2 max-w-[40ch] text-muted">
        You will chat with two other participants for two short rounds and vote for a Decision Maker.
      </p>
      {sessionGone && (
        <p role="status" className="mt-5 rounded-xl bg-canvas px-4 py-3 text-sm text-muted ring-1 ring-line">
          Your previous session is no longer available. You can join a new one.
        </p>
      )}
      {error && !sessionGone && (
        <div className="mt-5 flex justify-center">
          <ErrorLine>{error}</ErrorLine>
        </div>
      )}
      <button
        onClick={onJoin}
        disabled={busy}
        className="mt-7 inline-flex min-w-36 items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 font-semibold text-white transition duration-150 hover:bg-accent-hover active:scale-[0.97] disabled:cursor-wait disabled:opacity-70"
      >
        {busy && <Spinner />}
        {busy ? "Joining…" : sessionGone ? "Join a new session" : "Join"}
      </button>
    </div>
  );
}

// Shown over the current view while the socket is down; the view stays so nothing jumps on return.
function ReconnectingBanner() {
  return (
    <div role="status" className="pointer-events-none fixed inset-x-0 top-0 z-10 flex justify-center p-3">
      <p className="flex animate-enter items-center gap-2 rounded-full bg-warn-bg px-4 py-2 text-sm font-medium text-warn-ink shadow-[0_4px_14px_-6px_oklch(38%_0.08_70/0.4)] ring-1 ring-warn-ink/20">
        <Spinner /> Connection lost. Reconnecting…
      </p>
    </div>
  );
}

const PHASE_ANNOUNCE: Record<ServerState["phase"], (round: number) => string> = {
  WAITING: () => "Waiting room.",
  DISCUSSION: (r) => `Round ${r} discussion has started.`,
  VOTING: (r) => `Round ${r} vote is open.`,
  ROUND_RESULT: (r) => `Round ${r} results.`,
  FINAL: () => "Final results.",
};

export default function App() {
  const session = useSession();
  const { state } = session;
  return (
    <>
      {session.status === "reconnecting" && state && <ReconnectingBanner />}
      {/* Changes only on a phase change, so screen readers hear each phase once. */}
      <p className="sr-only" aria-live="polite">
        {state ? PHASE_ANNOUNCE[state.phase](state.round) : ""}
      </p>
      <Screen session={session} />
    </>
  );
}

function Screen({ session }: { session: ReturnType<typeof useSession> }) {
  const { status, state, error, messages, roundResult, finalResult, join, sendChat, sendVote } = session;

  if (status === "idle" || status === "joining" || (status === "error" && !state)) {
    return (
      <Card screenKey="join">
        <Join onJoin={join} busy={status === "joining"} error={error} />
      </Card>
    );
  }
  if (status === "replaced") {
    return (
      <Card screenKey="replaced">
        <div className="text-center">
          <svg viewBox="0 0 24 24" className="mx-auto mb-4 h-10 w-10 text-muted" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
            <rect x="3" y="6" width="13" height="12" rx="2" />
            <path d="M8 3h11a2 2 0 0 1 2 2v9" strokeLinecap="round" />
          </svg>
          <h1 className="text-xl font-semibold">Opened in another tab</h1>
          <p className="mx-auto mt-2 max-w-[40ch] text-muted">
            This session is now running in another tab or window. Please continue there and close this one.
          </p>
        </div>
      </Card>
    );
  }
  if (!state) {
    return (
      <Card screenKey="connecting">
        <p role="status" className="flex items-center justify-center gap-2 text-muted">
          <Spinner /> {status === "reconnecting" ? "Connection lost. Reconnecting…" : "Connecting…"}
        </p>
      </Card>
    );
  }
  const key = `${state.phase}-${state.round}`;
  switch (state.phase) {
    case "WAITING":
      return (
        <Card screenKey={key}>
          <Waiting />
        </Card>
      );
    case "DISCUSSION":
      return (
        <Card wide screenKey={key}>
          <Discussion state={state} messages={messages} error={error} onSend={sendChat} />
        </Card>
      );
    case "VOTING":
      return (
        <Card wide screenKey={key}>
          <Voting key={state.round} state={state} error={error} onVote={sendVote} />
        </Card>
      );
    case "ROUND_RESULT":
      return (
        <Card screenKey={key}>
          <RoundTally state={state} result={roundResult} />
        </Card>
      );
    case "FINAL":
      return (
        <Card screenKey={key}>
          <FinalResults state={state} result={finalResult} />
        </Card>
      );
  }
}
