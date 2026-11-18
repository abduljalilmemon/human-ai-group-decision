import { useEffect, useRef, useState, type FormEvent } from "react";
import { MAX_CHAT_CHARS, type ChatMessage, type ServerState } from "../useSession";
import { Avatar, ErrorLine, PhaseHeader } from "../ui";

const ERROR_TEXT: Record<string, string> = {
  chat_closed: "The discussion has ended.",
  empty_message: "Type a message first.",
  message_too_long: `Messages can be at most ${MAX_CHAT_CHARS} characters.`,
  invalid_message: "That message could not be sent.",
};

const COUNTER_FROM = MAX_CHAT_CHARS - 100; // show the character counter only near the limit

interface Props {
  state: ServerState;
  messages: ChatMessage[];
  error: string | null;
  onSend: (text: string) => boolean;
}

// Every message renders through the same markup and animation; only "you" vs "others" differs.
// The sender line is shown when the sender changes, by the same rule for everyone.
// Text is rendered as a React text node, never as HTML. No typing indicators, by design.
function Bubble({ message, mine, first }: { message: ChatMessage; mine: boolean; first: boolean }) {
  return (
    <li className={`flex animate-enter items-end gap-2 ${mine ? "flex-row-reverse" : ""} ${first ? "mt-3 first:mt-0" : "mt-1"}`}>
      {mine ? null : first ? <Avatar label={message.from} /> : <span className="w-7 shrink-0" aria-hidden />}
      <div className={`flex max-w-[80%] flex-col ${mine ? "items-end" : "items-start"}`}>
        {first && <span className="mb-1 px-1 text-xs font-medium text-muted">{mine ? "You" : message.from}</span>}
        {!first && <span className="sr-only">{mine ? "You" : message.from}:</span>}
        <p
          className={`rounded-2xl px-3.5 py-2 text-[0.9375rem] leading-relaxed break-words whitespace-pre-wrap ${
            mine ? "rounded-br-md bg-accent text-white" : "rounded-bl-md bg-surface text-ink ring-1 ring-line"
          }`}
        >
          {message.text}
        </p>
      </div>
    </li>
  );
}

export default function Discussion({ state, messages, error, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const log = useRef<HTMLOListElement>(null);

  // Scroll the log itself, not the page, so the composer never jumps on mobile.
  useEffect(() => {
    const el = log.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages.length]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    if (onSend(draft)) setDraft("");
  };

  return (
    <div className="flex flex-col">
      <PhaseHeader state={state} hint="Discuss who should be the Decision Maker." />

      <ol
        ref={log}
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
        aria-relevant="additions"
        className="mt-5 h-[min(26rem,calc(100dvh-20rem))] min-h-56 overflow-y-auto rounded-xl bg-canvas p-3 ring-1 ring-line sm:p-4"
      >
        {messages.length === 0 && (
          <li className="flex h-full items-center justify-center text-sm text-muted">
            No messages yet. Say hello to start the discussion.
          </li>
        )}
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
          className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-4 py-2.5 text-[0.9375rem] text-ink transition-colors placeholder:text-muted hover:border-muted/40 focus:border-accent focus:outline-none focus-visible:ring-3 focus-visible:ring-accent-soft"
        />
        <button
          type="submit"
          disabled={!draft.trim()}
          className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition duration-150 hover:bg-accent-hover active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100"
        >
          Send
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
