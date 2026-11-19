import { useCallback, useEffect, useRef, useState } from "react";

export type Phase = "WAITING" | "DISCUSSION" | "VOTING" | "ROUND_RESULT" | "FINAL";

export interface ServerState {
  phase: Phase;
  round: number;
  phase_ends_at: number | null; // epoch ms
  server_now: number;
  remaining_ms: number | null;
  you: string | null;
  players: string[];
  has_voted: boolean;
  avatar_seed: string | null; // random per session, same for every player; null in the waiting room
}

export interface ChatMessage {
  id: number;
  from: string; // player label
  text: string;
  sent_at: number; // epoch ms
}

export type Tallies = Record<string, number>; // label -> votes; never who voted for whom

export interface RoundResult {
  round: number;
  tallies: Tallies;
}

export interface FinalResult {
  decision_maker: string;
  tallies_by_round: Record<string, Tallies>; // keyed "1", "2"
  tie_break: "none" | "round1" | "random";
}

export const MAX_CHAT_CHARS = 500; // mirrors the server limit

// reconnecting: the socket dropped and a retry is scheduled. replaced: this token was opened in
// another tab, which now owns the seat.
export type Status = "idle" | "joining" | "connecting" | "connected" | "reconnecting" | "replaced" | "error";

// Server close codes that must not trigger a reconnect (see backend/app/ws.py).
const CLOSE_UNKNOWN_TOKEN = 4404;
const CLOSE_REPLACED = 4409;
const BACKOFF_MS = [500, 1000, 2000, 4000, 8000]; // then 8 s per retry until it works

// sessionStorage, not localStorage: each tab is its own participant, and a refresh keeps the seat.
const TOKEN_KEY = "playerToken";

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable: the session still works until the tab is refreshed
  }
}

export function useSession() {
  const [token, setToken] = useState<string | null>(readToken);
  const [status, setStatus] = useState<Status>(token ? "connecting" : "idle");
  const [state, setState] = useState<ServerState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [roundResult, setRoundResult] = useState<RoundResult | null>(null);
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);
  const socket = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;
    let disposed = false;
    let attempt = 0;
    let retry: number | undefined;
    let stop = false; // set by the server's unknown_token or replaced answer

    const connect = () => {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${scheme}://${location.host}/ws?token=${encodeURIComponent(token)}`);
      socket.current = ws;

      ws.onmessage = (event) => {
        if (disposed) return;
        const msg = JSON.parse(event.data);
        if (msg.type === "state") {
          attempt = 0; // the server accepted us and replayed the session
          setStatus("connected");
          setState(msg as ServerState);
          setError(null); // state arrives on phase changes; an old chat error no longer applies
        } else if (msg.type === "message") {
          const m: ChatMessage = { id: msg.id, from: msg.from, text: msg.text, sent_at: msg.sent_at };
          // A reconnect replays the whole chat, so skip lines this tab already has.
          setMessages((list) => (list.some((x) => x.id === m.id) ? list : [...list, m]));
        } else if (msg.type === "round_result") {
          setRoundResult({ round: msg.round, tallies: msg.tallies });
        } else if (msg.type === "final_result") {
          setFinalResult({
            decision_maker: msg.decision_maker,
            tallies_by_round: msg.tallies_by_round,
            tie_break: msg.tie_break,
          });
        } else if (msg.type === "error" && msg.reason === "unknown_token") {
          // The seat is gone (server restart, or released after leaving the waiting room): join again.
          stop = true;
          writeToken(null);
          setToken(null);
          setState(null);
          setMessages([]);
          setRoundResult(null);
          setFinalResult(null);
          setStatus("error");
          setError("Your previous session is no longer available.");
        } else if (msg.type === "error" && msg.reason === "replaced") {
          stop = true;
          setStatus("replaced");
        } else if (msg.type === "error") {
          setError(msg.reason);
        }
      };
      ws.onclose = (event) => {
        if (socket.current === ws) socket.current = null;
        if (disposed || stop) return;
        if (event.code === CLOSE_UNKNOWN_TOKEN || event.code === CLOSE_REPLACED) return;
        setStatus("reconnecting");
        retry = window.setTimeout(connect, BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]);
        attempt += 1;
      };
    };

    setStatus("connecting");
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(retry);
      socket.current?.close();
      socket.current = null;
    };
  }, [token]);

  const join = useCallback(async () => {
    setStatus("joining");
    setError(null);
    try {
      const res = await fetch("/api/join", { method: "POST" });
      if (!res.ok) throw new Error(`Could not join (HTTP ${res.status}).`);
      const body: { token: string } = await res.json();
      writeToken(body.token);
      setToken(body.token);
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : "Could not join.");
    }
  }, []);

  // The server validates and may answer with an error; the message only appears once it is broadcast.
  const sendChat = useCallback((text: string): boolean => {
    const ws = socket.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    setError(null);
    ws.send(JSON.stringify({ type: "chat", text }));
    return true;
  }, []);

  // The server confirms an accepted vote with a state message where has_voted is true.
  const sendVote = useCallback((target: string): boolean => {
    const ws = socket.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    setError(null);
    ws.send(JSON.stringify({ type: "vote", target }));
    return true;
  }, []);

  return { status, state, error, messages, roundResult, finalResult, join, sendChat, sendVote };
}
