// F-21/F-54 · Postać + Umiejętności — żywotność, atrybuty, stan, wyuczone skille.
// Umiejętności wchłonięte z osobnej zakładki (jedna zakładka = mniej przełączeń).
import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { readConditions, readStatMods, readSkills, PROFICIENCY_RANK } from "@/lib/sheet";
import { readVitals } from "@/lib/game";
import { usePublicSkills } from "@/hooks/useSheetData";
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
  // #1302: pasywne bonusy z założonych reliktów (staty), by pokazać wartość efektywną.
  const relicStats = readRelicStatBonus(sheet);
  // Podświetlamy atrybuty z najwyższym modyfikatorem (jak w makiecie).
  const maxMod = Math.max(0, ...STAT_KEYS.map((k) => mods[k] ?? 0));

  // Umiejętności — tylko wyuczone (ranga ≥ 1), tap rozwija opis.
  const skills = readSkills(sheet).filter((s) => s.rank >= 1);
  const catalog = usePublicSkills();
  const descOf = (key: string) => catalog.data?.find((c) => c.key === key)?.description ?? null;
  const [openSkills, setOpenSkills] = useState<Set<string>>(new Set());
  const toggleSkill = (key: string) =>
    setOpenSkills((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

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
            const bonus = relicStats[k] ?? 0;
            const effVal = val + bonus;
            const mod = bonus ? Math.floor((effVal - 10) / 2) : mods[k] ?? 0;
            const hi = maxMod > 0 && mod === maxMod;
            return (
              <div
                key={k}
                className={cn(
                  "rounded-md border px-1 py-2.5 text-center",
                  bonus
                    ? "border-line-ember bg-gradient-to-b from-[rgba(255,122,61,0.12)] to-transparent"
                    : hi
                      ? "border-line-ember bg-gradient-to-b from-[rgba(255,122,61,0.08)] to-transparent"
                      : "border-line bg-surface",
                )}
              >
                <div className="text-[9.5px] font-bold uppercase tracking-[0.16em] text-text-3">
                  {k}
                </div>
                <div className="mt-0.5 font-mono text-[19px] font-medium text-text">
                  {effVal}
                  {bonus > 0 && (
                    <span className="ml-0.5 align-super text-[9px] text-ember-glow">
                      +{bonus}
                    </span>
                  )}
                </div>
                <div className={cn("font-mono text-[11px]", hi || bonus ? "text-ember-glow" : "text-text-3")}>
                  {fmtMod(mod)}
                </div>
                {bonus > 0 && (
                  <div className="mt-0.5 text-[8px] font-medium uppercase tracking-wide text-ember">
                    z ekwipunku
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section className="mb-6">
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

      <section>
        <SecHead>
          Umiejętności <span className="ml-1 font-normal normal-case tracking-normal text-text-3">★ = biegłość (+2)</span>
        </SecHead>
        {skills.length === 0 ? (
          <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
            Brak wyuczonych umiejętności.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2 lg:gap-x-4">
            {skills.map((s) => {
              const desc = descOf(s.key);
              const isOpen = openSkills.has(s.key);
              return (
                <div
                  key={s.key}
                  className="overflow-hidden rounded-md border border-line-soft bg-surface"
                >
                  <button
                    type="button"
                    onClick={() => desc && toggleSkill(s.key)}
                    className={cn(
                      "flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left",
                      desc && "transition-colors hover:bg-inset",
                    )}
                    aria-expanded={desc ? isOpen : undefined}
                  >
                    <span className="flex-1 text-label font-medium text-text">
                      {s.label}
                      {s.proficient && <span className="ml-1.5 align-[2px] text-[10px] text-ember">★</span>}
                    </span>
                    <span className="font-mono text-[10px] tracking-wide text-text-3">{s.stat}</span>
                    <div className="flex gap-1">
                      {Array.from({ length: PROFICIENCY_RANK }).map((_, i) => (
                        <span
                          key={i}
                          className={cn(
                            "h-2 w-2 rounded-full",
                            i < s.rank
                              ? "bg-ember shadow-[0_0_6px_rgba(255,122,61,.6)]"
                              : "bg-inset shadow-[inset_0_0_0_1px_var(--line)]",
                          )}
                        />
                      ))}
                    </div>
                    <span className="w-9 text-right font-mono text-label font-medium text-ember-glow">
                      {(s.bonus >= 0 ? "+" : "") + s.bonus}
                    </span>
                    {desc && (
                      <CaretDown
                        size={13}
                        className={cn(
                          "shrink-0 text-text-3 transition-transform",
                          isOpen && "rotate-180",
                        )}
                      />
                    )}
                  </button>
                  {desc && isOpen && (
                    <p className="border-t border-line-soft bg-bg px-3.5 py-2.5 font-serif text-micro leading-relaxed text-text-2">
                      {desc}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </PanelScroll>
  );
}

// #1302: {STAT: punkty} bonusu z założonych reliktów (backend: sheet.equipment_bonuses.stats).
function readRelicStatBonus(sheet: HeroSheet | undefined): Record<string, number> {
  const eq = (((sheet ?? {}) as Record<string, unknown>).equipment_bonuses ?? {}) as Record<
    string,
    unknown
  >;
  const stats = (eq.stats ?? {}) as Record<string, unknown>;
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(stats)) {
    const n = Number(v);
    if (Number.isFinite(n) && n !== 0) out[k.toUpperCase()] = n;
  }
  return out;
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
