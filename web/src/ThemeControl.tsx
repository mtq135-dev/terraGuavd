import type { ThemePreference } from "./theme";

export function ThemeControl({
  preference,
  onChange,
}: {
  preference: ThemePreference;
  onChange: (preference: ThemePreference) => void;
}) {
  return (
    <label className="theme-control">
      <span className="theme-icon" aria-hidden="true">
        ◐
      </span>
      <select
        aria-label="Appearance theme"
        value={preference}
        onChange={(event) => onChange(event.target.value as ThemePreference)}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
