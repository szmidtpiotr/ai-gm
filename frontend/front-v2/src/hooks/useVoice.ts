// F-72 (#1267) — React binding do singletona `voice`. Subskrybuje stan (przez
// useSyncExternalStore, jedno źródło prawdy) i inicjalizuje kontroler raz.
import { useEffect, useSyncExternalStore } from "react";
import { voice, type VoiceState } from "@/lib/voice";

export function useVoice(): VoiceState & {
  speak: (text: string) => void;
  stopPlayback: () => void;
  setTtsEnabled: (next: boolean, opts?: { unlock?: boolean }) => void;
  setAutosend: (next: boolean) => void;
  toggleStt: () => void;
} {
  const state = useSyncExternalStore(
    (cb) => voice.subscribe(cb),
    () => voice.getState(),
    () => voice.getState(),
  );

  useEffect(() => {
    void voice.init();
  }, []);

  return {
    ...state,
    speak: (t) => void voice.speak(t),
    stopPlayback: () => voice.stopPlayback(),
    setTtsEnabled: (n, o) => voice.setTtsEnabled(n, o),
    setAutosend: (n) => voice.setAutosend(n),
    toggleStt: () => void voice.toggleStt(),
  };
}
