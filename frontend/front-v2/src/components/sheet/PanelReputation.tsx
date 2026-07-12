// F-57/F-58 · Reputacja & opis (scalone) — standing per region + tożsamość
// (wygląd, osobowość, więzi, skaza, sekret). Makieta: zar2-postac sekcja Reputacja.
import { cn } from "@/lib/utils";
import {
  prettyRegion,
  readIdentity,
  repTierLabel,
  type ReputationRow,
} from "@/lib/sheet";
import type { HeroSheet } from "@/lib/types";
import { SecHead, PanelScroll } from "./sheetUi";

const TIER_CLASS: Record<string, string> = {
  exalted: "border-[rgba(232,193,90,0.4)] bg-[rgba(232,193,90,0.08)] text-gold",
  friendly: "border-[rgba(168,201,131,0.35)] bg-[rgba(168,201,131,0.08)] text-success",
  neutral: "border-line text-text-3",
  disliked: "border-[rgba(232,96,79,0.3)] bg-[rgba(232,96,79,0.06)] text-danger",
  hated: "border-line-danger bg-[rgba(232,96,79,0.1)] text-danger-glow",
};

export function PanelReputation({
  sheet,
  reputation,
}: {
  sheet: HeroSheet | undefined;
  reputation: ReputationRow[] | undefined;
}) {
  const id = readIdentity(sheet);
  const reps = reputation ?? [];

  return (
    <PanelScroll>
      <section className="mb-6">
        <SecHead>Reputacja</SecHead>
        {reps.length === 0 ? (
          <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
            Twoje czyny nie odbiły się jeszcze echem w żadnym regionie.
          </p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {reps.map((r) => (
              <div
                key={`${r.scope_type}:${r.scope_key}`}
                className="flex items-center gap-3 rounded-md border border-line-soft bg-surface px-3.5 py-2.5"
              >
                <span className="flex-1 text-label font-medium text-text">
                  {prettyRegion(r.scope_key)}
                </span>
                <span className="font-mono text-label text-text-2">
                  {r.value >= 0 ? "+" : ""}
                  {r.value}
                </span>
                <span
                  className={cn(
                    "rounded-pill border px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-[0.12em]",
                    TIER_CLASS[r.tier] ?? TIER_CLASS.neutral,
                  )}
                >
                  {repTierLabel(r.tier)}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <SecHead>Opis postaci</SecHead>
        <div className="flex flex-col gap-3">
          <Field label="Wygląd" value={id.appearance} />
          <Field label="Osobowość" value={id.personality} />
          {id.bonds.length > 0 && <ListField label="Więzi" values={id.bonds} />}
          <Field label="Skaza" value={id.flaw} />
          <Field label="Sekret" value={id.secret} muted />
        </div>
      </section>
    </PanelScroll>
  );
}

function Field({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  const empty = !value.trim();
  return (
    <div className="rounded-md border border-line-soft bg-surface px-3.5 py-3">
      <div className="mb-1 font-ui text-[10px] font-bold uppercase tracking-[0.14em] text-ember">
        {label}
      </div>
      <p
        className={cn(
          "font-serif text-prose leading-relaxed",
          empty ? "text-text-3 italic" : muted ? "text-text-2" : "text-text",
        )}
      >
        {empty ? "— nieokreślone —" : value}
      </p>
    </div>
  );
}

function ListField({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-md border border-line-soft bg-surface px-3.5 py-3">
      <div className="mb-1.5 font-ui text-[10px] font-bold uppercase tracking-[0.14em] text-ember">
        {label}
      </div>
      <ul className="flex flex-col gap-1.5">
        {values.map((v, i) => (
          <li key={i} className="flex gap-2 font-serif text-prose leading-relaxed text-text">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-ember" />
            {v}
          </li>
        ))}
      </ul>
    </div>
  );
}
