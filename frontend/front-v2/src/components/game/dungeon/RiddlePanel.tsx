// FE16 loch (#1265) — panel zagadki (parytet dungeon-riddle-panel). Tekst + pole
// odpowiedzi + podpowiedź. Enter lub przycisk wysyła. ŻAR: karta mechaniki (złoto).
import { useState } from "react";
import { Lightbulb, PaperPlaneRight } from "@phosphor-icons/react";

export function RiddlePanel({
  text,
  hint,
  busy,
  onAnswer,
  onHint,
}: {
  text: string;
  hint: string | null;
  busy: boolean;
  onAnswer: (answer: string) => void;
  onHint: () => void;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const v = value.trim();
    if (!v) return;
    setValue("");
    onAnswer(v);
  }

  return (
    <div
      className="mx-3 mb-2 shrink-0 rounded-lg border border-line-mech bg-mech-card p-3"
      data-testid="dungeon-riddle-panel"
    >
      <div className="mb-1 font-ui text-micro font-bold uppercase tracking-[0.14em] text-gold">
        Zagadka
      </div>
      <p className="mb-2.5 font-serif text-label italic text-text-2">{text}</p>
      {hint && (
        <p className="mb-2 flex items-start gap-1.5 font-ui text-micro text-gold-glow">
          <Lightbulb weight="fill" size={13} className="mt-0.5 flex-none" />
          {hint}
        </p>
      )}
      <div className="flex items-center gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Twoja odpowiedź…"
          disabled={busy}
          className="min-w-0 flex-1 rounded-md border border-line bg-bg px-2.5 py-1.5 font-ui text-label text-text placeholder:text-text-3 focus:border-line-mech focus:outline-none disabled:opacity-50"
        />
        <button
          type="button"
          onClick={onHint}
          disabled={busy}
          title="Podpowiedź"
          className="flex h-8 w-8 items-center justify-center rounded-md border border-line-mech text-gold transition-colors hover:bg-gold/[0.08] disabled:opacity-50"
        >
          <Lightbulb size={15} />
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-line-mech bg-gold/[0.1] text-gold transition-colors hover:bg-gold/[0.18] disabled:opacity-50"
        >
          <PaperPlaneRight weight="fill" size={15} />
        </button>
      </div>
    </div>
  );
}
