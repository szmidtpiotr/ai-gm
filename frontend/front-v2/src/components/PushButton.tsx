import { useState } from "react";
import { BellRinging, Stethoscope } from "@phosphor-icons/react";
import { enablePush, pushDiagnostics, pushSupported, type PushStep } from "@/lib/push";

// FE17 (#1266 · F-73) — przycisk włączania powiadomień push + diagnostyka.
// id="enable-push-btn" zachowane dla parytetu ze starym frontem / QA.
export function PushButton() {
  const [steps, setSteps] = useState<PushStep[]>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  if (!pushSupported()) {
    return (
      <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-ui text-micro text-text-3">
        Ta przeglądarka nie obsługuje powiadomień push.
      </p>
    );
  }

  async function onEnable() {
    setBusy(true);
    // requestPermission() musi ruszyć w geście — enablePush() robi to synchronicznie.
    const trail = await enablePush(setSteps);
    setSteps(trail);
    setDone(trail.some((s) => s.step === "Zapis na serwer" && s.ok));
    setBusy(false);
  }

  async function onDiag() {
    setBusy(true);
    setSteps(await pushDiagnostics());
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-line-soft bg-surface p-3.5">
      <div className="flex items-center gap-2.5">
        <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2">
          <BellRinging size={18} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-ui text-body font-semibold text-text">Powiadomienia push</span>
          <span className="block font-ui text-micro text-text-3">Info o swojej turze i zaproszeniach</span>
        </span>
      </div>

      <button
        type="button"
        id="enable-push-btn"
        data-clog="enable_push_button"
        disabled={busy}
        onClick={onEnable}
        className="inline-flex items-center justify-center gap-2 rounded-md border border-line-ember bg-ember/[0.08] py-2.5 font-ui text-body font-semibold text-ember-glow disabled:opacity-50"
      >
        <BellRinging size={16} /> {done ? "Powiadomienia włączone ✓" : "Włącz powiadomienia"}
      </button>

      {steps.length > 0 && (
        <ol className="m-0 flex flex-col gap-0.5 pl-1 font-mono text-[11px] leading-relaxed text-text-3">
          {steps.map((s, i) => (
            <li key={i}>
              {s.ok === true ? "✅" : s.ok === false ? "❌" : "⏳"} {s.step}
              {s.detail ? <span className="text-text-3"> — {s.detail}</span> : null}
            </li>
          ))}
        </ol>
      )}

      <button
        type="button"
        id="push-diag-btn"
        data-clog="push_diag_button"
        disabled={busy}
        onClick={onDiag}
        className="inline-flex items-center gap-1.5 self-start font-ui text-micro text-text-3 disabled:opacity-50"
      >
        <Stethoscope size={13} /> Uruchom diagnostykę
      </button>
    </div>
  );
}
