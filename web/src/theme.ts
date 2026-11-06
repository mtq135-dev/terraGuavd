import { useEffect, useLayoutEffect, useState } from "react";

export const themePreferenceKey = "terraguavd.theme";
const darkScheme = "(prefers-color-scheme: dark)";

export type ThemePreference = "system" | "light" | "dark";
type Theme = Exclude<ThemePreference, "system">;

function readPreference(): ThemePreference {
  try {
    const saved = window.localStorage.getItem(themePreferenceKey);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.(darkScheme).matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

export function initializeTheme() {
  const saved = readPreference();
  applyTheme(saved === "system" ? systemTheme() : saved);
}

export function useTheme() {
  const [preference, setPreference] = useState(readPreference);
  const [system, setSystem] = useState(systemTheme);
  const theme = preference === "system" ? system : preference;

  useLayoutEffect(() => applyTheme(theme), [theme]);
  useEffect(() => {
    const query = window.matchMedia?.(darkScheme);
    if (!query) return;
    const sync = () => setSystem(query.matches ? "dark" : "light");
    query.addEventListener("change", sync);
    sync();
    return () => query.removeEventListener("change", sync);
  }, []);

  function changePreference(next: ThemePreference) {
    setPreference(next);
    try {
      window.localStorage.setItem(themePreferenceKey, next);
    } catch {
      // The current tab can still change theme when storage is unavailable.
    }
  }

  return { preference, theme, changePreference };
}
