// F-21 · Postać — żywotność (HP/Mana/XP) + atrybuty (7, z modyfikatorami) + stan.
// Makieta: zar2-postac.html (sekcje Żywotność / Atrybuty / Stan).
import { cn } from "@/lib/utils";
import { readConditions, readStatMods } from "@/lib/sheet";
import { readVitals } from "@/lib/game";
import type { HeroSheet } from "@/lib/types";
import { SecHead, PanelScroll } from "./sheetUi";

const STAT_KEYS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"] as const;

function pct(v: number, max: number) {
  return max > 0 ? Math.max(0, Math.min(100, (v / max) * 100)) : 0;
}
function fmtMod(m: number) {
  return (m >= 0 ? "+" : "") + m;
}

export function PanelCharacter({ sheet }: { sheet: HeroSheet | undefined }) {
  const v = readVitals(sheet);
  const mods = readStatMods(sheet);
  const conditions = readConditions(sheet);
  // Podświetlamy atrybuty z najwyższym modyfikatorem (jak w makiecie).
  const maxMod = Math.max(0, ...STAT_KEYS.map((k) => mods[k] ?? 0));

  return (
    <PanelScroll>
      <section className="mb-6">
        <SecHead>Żywotność</SecHead>
        <BigBar label="Zdrowie" value={`${v.hp} / ${v.maxHp}`} pct={pct(v.hp, v.maxHp)} kind="hp" />
        {v.hasMana && (
          <BigBar
            label="Mana"
            value={`${v.mana} / ${v.maxMana}`}
            pct={pct(v.mana, v.maxMana)}
            kind="mana"
          />
        )}
        {v.maxXp > 0 && (
          <BigBar
            label={`Doświadczenie · do poziomu ${v.level + 1}`}
            value={`${v.xp} / ${v.maxXp}`}
            pct={pct(v.xp, v.maxXp)}
            kind="xp"
          />
        )}
      </section>

      <section className="mb-6">
        <SecHead>Atrybuty</SecHead>
        <div className="grid grid-cols-4 gap-2 lg:grid-cols-7">
          {STAT_KEYS.map((k) => {
            const val = readStatValue(sheet, k);
            const mod = mods[k] ?? 0;
            const hi = maxMod > 0 && mod === maxMod;
            return (
              <div
                key={k}
                className={cn(
                  "rounded-md border px-1 py-2.5 text-center",
                  hi
                    ? "border-line-ember bg-gradient-to-b from-[rgba(255,122,61,0.08)] to-transparent"
                    : "border-line bg-surface",
                )}
              >
                <div className="text-[9.5px] font-bold uppercase tracking-[0.16em] text-text-3">
                  {k}
                </div>
                <div className="mt-0.5 font-mono text-[19px] font-medium text-text">{val}</div>
                <div className={cn("font-mono text-[11px]", hi ? "text-ember-glow" : "text-text-3")}>
                  {fmtMod(mod)}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <SecHead>Stan</SecHead>
        {conditions.length === 0 ? (
          <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
            Bohater jest w pełni sił — brak aktywnych efektów.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {conditions.map((c) => (
              <div
                key={c.key}
                className="flex items-start gap-3 rounded-md border border-line-danger border-l-[3px] border-l-danger bg-[rgba(232,96,79,0.06)] px-3.5 py-3"
              >
                <span className="mt-0.5 text-[15px]">🩹</span>
                <div className="min-w-0">
                  <div className="font-ui text-label font-semibold text-text">
                    {c.label}
                    {c.level > 0 && <span className="text-text-3"> · poz. {c.level}</span>}
                  </div>
                  <div className="mt-0.5 font-ui text-micro text-text-2">{c.desc}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </PanelScroll>
  );
}

function readStatValue(sheet: HeroSheet | undefined, k: string): number {
  const stats = (((sheet ?? {}) as Record<string, unknown>).stats ?? {}) as Record<
    string,
    unknown
  >;
  const raw = stats[k] ?? stats[k.toLowerCase()];
  const n = typeof raw === "string" ? Number(raw) : (raw as number);
  return Number.isFinite(n) ? n : 0;
}

function BigBar({
  label,
  value,
  pct,
  kind,
}: {
  label: string;
  value: string;
  pct: number;
  kind: "hp" | "mana" | "xp";
}) {
  return (
    <div className="mb-3">
      <div className="mb-1.5 flex justify-between text-label text-text-2">
        <span>{label}</span>
        <b className="font-mono font-medium text-text">{value}</b>
      </div>
      <div className="h-2 overflow-hidden rounded-[4px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
        <div
          className={cn(
            "h-full rounded-[4px] transition-[width] duration-500",
            kind === "hp" && "bg-gradient-to-r from-[#c14a2b] to-ember shadow-[0_0_9px_rgba(255,122,61,.55)]",
            kind === "mana" && "bg-gradient-to-r from-[#5f74e8] to-mana shadow-[0_0_9px_rgba(130,167,199,.5)]",
            kind === "xp" && "bg-text-3",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
