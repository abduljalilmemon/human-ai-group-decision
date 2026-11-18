import { useEffect, useRef, useState, type FormEvent } from "react";
import { m } from "motion/react";
import { MAX_CHAT_CHARS, type ChatMessage, type ServerState } from "../useSession";
import { Avatar, ErrorLine, PhaseHeader } from "../ui";

const ERROR_TEXT: Record<string, string> = {
  chat_closed: "The discussion has ended.",
  empty_message: "Type a message first.",
  message_too_long: `Messages can be at most ${MAX_CHAT_CHARS} characters.`,
  invalid_message: "That message could not be sent.",
};

const COUNTER_FROM = MAX_CHAT_CHARS - 100; // show the character counter only near the limit
const STICK_PX = 96; // auto-scroll only when the reader is already near the bottom

// One entrance for every message, whoever sent it. Only the side (and so the origin) differs for your own.
const ENTER = {
  initial: { opacity: 0, y: 12, scale: 0.96 },
  animate: { opacity: 1, y: 0, scale: 1 },
  transition: { type: "spring", stiffness: 520, damping: 34, mass: 0.8 },
} as const;

interface Props {
  state: ServerState;
  messages: ChatMessage[];
  error: string | null;
  onSend: (text: string) => boolean;
}

// Every message renders through the same markup and animation; only "you" vs "others" differs.
// The sender line is shown when the sender changes, by the same rule for everyone.
// Text is a React text node, never HTML, with whitespace collapsed so no sender's line breaks stand out.
// No typing indicators, by design.
function Bubble({ message, mine, first }: { message: ChatMessage; mine: boolean; first: boolean }) {
  return (
    <m.li
      {...ENTER}
      style={{ transformOrigin: mine ? "100% 100%" : "0% 100%" }}
      className={`flex items-end gap-2 ${mine ? "flex-row-reverse" : ""} ${first ? "mt-3 first:mt-0" : "mt-1"}`}
    >
      {mine ? null : first ? <Avatar label={message.from} /> : <span className="w-7 shrink-0" aria-hidden />}
      <div className={`flex max-w-[80%] flex-col ${mine ? "items-end" : "items-start"}`}>
        {first && <span className="mb-1 px-1 text-xs font-medium text-muted">{mine ? "You" : message.from}</span>}
        {!first && <span className="sr-only">{mine ? "You" : message.from}:</span>}
        <p
          className={`rounded-2xl px-3.5 py-2 text-[0.9375rem] leading-relaxed break-words whitespace-normal ${
            mine
              ? "rounded-br-md bg-accent text-white"
              : "rounded-bl-md bg-track text-ink"
          }`}
        >
          {message.text}
        </p>
      </div>
    </m.li>
  );
}

function EmptyHint() {
  return (
    <li className="flex h-full animate-enter flex-col items-center justify-center gap-3 px-6 text-center">
      <svg viewBox="0 0 32 32" className="h-9 w-9 text-accent/70" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
        <path d="M6 8.5A3.5 3.5 0 0 1 9.5 5h13A3.5 3.5 0 0 1 26 8.5v9a3.5 3.5 0 0 1-3.5 3.5H14l-5.5 5v-5h0A3.5 3.5 0 0 1 6 17.5z" strokeLinejoin="round" />
        <path d="M11 11.5h10M11 15.5h6" strokeLinecap="round" />
      </svg>
      <p className="text-sm text-muted">
        <span className="block font-medium text-ink">No messages yet</span>
        Start the discussion: who would make a good Decision Maker, and why?
      </p>
    </li>
  );
}

export default function Discussion({ state, messages, error, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const log = useRef<HTMLOListElement>(null);
  const stick = useRef(true);

  // Scroll the log itself, not the page, so the composer never jumps on mobile. Follow new
  // messages only if the reader was at the bottom, or the newest message is their own.
  useEffect(() => {
    const el = log.current;
    if (!el) return;
    const last = messages[messages.length - 1];
    if (!stick.current && last?.from !== state.you) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages, state.you]);

  const onScroll = () => {
    const el = log.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX;
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    if (onSend(draft)) setDraft("");
  };

  return (
    <div className="flex flex-col">
      <PhaseHeader state={state} title={`Round ${state.round} discussion`} hint="Discuss who should be the Decision Maker." />

      <ol
        ref={log}
        onScroll={onScroll}
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
        aria-relevant="additions"
        className="-mx-6 mt-5 h-[min(24rem,calc(100dvh-24rem))] min-h-60 overflow-y-auto border-y border-line px-6 py-4 sm:-mx-8 sm:px-8"
      >
        {messages.length === 0 && <EmptyHint />}
        {messages.map((m, i) => (
          <Bubble key={m.id} message={m} mine={m.from === state.you} first={i === 0 || messages[i - 1].from !== m.from} />
        ))}
      </ol>

      <form onSubmit={submit} className="mt-3 flex gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Message
        </label>
        <input
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={MAX_CHAT_CHARS}
          placeholder="Type a message…"
          autoComplete="off"
          autoFocus
          className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-4 py-2.5 text-[0.9375rem] text-ink transition-[border-color,box-shadow] duration-200 placeholder:text-muted hover:border-muted/40 focus:border-accent focus:outline-none focus-visible:ring-4 focus-visible:ring-accent-soft"
        />
        <button
          type="submit"
          disabled={!draft.trim()}
          className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition duration-150 hover:bg-accent-hover active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100 sm:px-5"
        >
          Send
          <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            <path d="M2.5 8h10M9 4.5L12.5 8 9 11.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
      <div className="mt-2 flex min-h-5 items-start justify-between gap-3">
        <div>{error && <ErrorLine>{ERROR_TEXT[error] ?? error}</ErrorLine>}</div>
        {draft.length >= COUNTER_FROM && (
          <span className="text-xs text-muted tabular-nums">{MAX_CHAT_CHARS - draft.length} characters left</span>
        )}
      </div>
    </div>
  );
}
