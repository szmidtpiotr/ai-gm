/**
 * Game Settings Manager
 * Handles user preferences and settings persistence
 */

export interface GameSettings {
  soundEnabled: boolean;
  musicEnabled: boolean;
  vibrationEnabled: boolean;
  fontSize: "small" | "medium" | "large";
  autoScroll: boolean;
}

const DEFAULT_SETTINGS: GameSettings = {
  soundEnabled: true,
  musicEnabled: true,
  vibrationEnabled: true,
  fontSize: "medium",
  autoScroll: true,
};

const SETTINGS_KEY = "aigm_settings";

export function getSettings(): GameSettings {
  if (typeof localStorage === "undefined") return DEFAULT_SETTINGS;

  const stored = localStorage.getItem(SETTINGS_KEY);
  if (!stored) return DEFAULT_SETTINGS;

  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: Partial<GameSettings>): void {
  if (typeof localStorage === "undefined") return;

  const current = getSettings();
  const updated = { ...current, ...settings };
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(updated));
}

export function resetSettings(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(SETTINGS_KEY);
}
