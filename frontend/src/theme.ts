import { useCallback, useEffect, useState } from "react";

// The theme is a per-browser display preference. It stays in localStorage and on <html data-theme>,
// and is never sent to the server, logged, or stored with participant data.
export type ThemeChoice = "dark" | "light" | "auto";

const KEY = "theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function readThemeChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return v === "dark" || v === "light" ? v : "auto";
  } catch {
    return "auto";
  }
}

function writeThemeChoice(choice: ThemeChoice) {
  try {
    if (choice === "auto") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    // storage unavailable: the choice lasts until the tab is closed
  }
}

function systemDark(): boolean {
  return window.matchMedia?.(DARK_QUERY).matches ?? true;
}

export function applyTheme(choice: ThemeChoice) {
  const resolved = choice === "auto" ? (systemDark() ? "dark" : "light") : choice;
  document.documentElement.dataset.theme = resolved;
}

/** Current choice plus a setter. Auto follows the device setting and updates live. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(readThemeChoice);

  useEffect(() => {
    applyTheme(choice);
    if (choice !== "auto") return;
    const mq = window.matchMedia(DARK_QUERY);
    const onChange = () => applyTheme("auto");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [choice]);

  const set = useCallback((next: ThemeChoice) => {
    writeThemeChoice(next);
    setChoice(next);
  }, []);

  return { choice, setChoice: set };
}
