// F-56 · Czary — banner mana + punkty tajemne + gęsta lista per tier
// (znane wyróżnione, zablokowane wyszarzone z progiem). Tylko klasy z pulą many.
// Makieta: zar3-czary.html.
import { useState } from "react";
import { CircleNotch, Lock, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import {
  groupSpells,
  readArcanePoints,
  tierUnlockLevel,
  type SpellCatalogEntry,
  type KnownSpell,
  type SpellRow,
} from "@/lib/sheet";
import { readVitals } from "@/lib/game";
import type { HeroSheet } from "@/lib/types";
import { PanelScroll, SPELL_TYPE_ICON } from "./sheetUi";
import { SPELL_TYPE_PL } from "@/lib/spells";

function pct(v: number, max: number) {
  return max > 0 ? Math.max(0, Math.min(100, (v / max) * 100)) : 0;
}

export function PanelSpells({
  sheet,
  race,
  known,
  catalog,
  level,
  loading,
}: {
  sheet: HeroSheet | undefined;
  race: string | undefined;
  known: KnownSpell[] | undefined;
  catalog: SpellCatalogEntry[] | undefined;
  level: number;
  loading: boolean;
}) {
  const v = readVitals(sheet);
  const arcane = readArcanePoints(sheet);
  const groups = groupSpells(catalog ?? [], known ?? [], race);
  const [selected, setSelected] = useState<SpellRow | null>(null);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Banner mana + punkty tajemne — przyklejony nad listą (makieta) */}
      <div className="border-b border-line-soft bg-surface px-4 py-3.5 lg:px-8">
        <div className="mx-auto w-full max-w-[960px]">
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="font-ui text-[11px] font-bold uppercase tracking-[0.16em] text-mana">
              ◈ Mana
            </span>
            <span className="font-mono text-label text-text">
              {v.mana}
              <span className="text-text-3"> / {v.maxMana}</span>
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-[4px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
            <div
              className="h-full rounded-[4px] bg-gradient-to-r from-[#5f74e8] to-mana shadow-[0_0_9px_rgba(130,167,199,.5)] transition-[width] duration-500"
              style={{ width: `${pct(v.mana, v.maxMana)}%` }}
            />
          </div>
          <div className="mt-1.5 font-ui text-micro text-text-2">
            Punkty tajemne: <b className="font-mono text-gold">{arcane}</b> — wydaj na nowy
            czar (1) / rangę R2 (1) / R3 (2)
          </div>
        </div>
      </div>

      <PanelScroll>
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-text-3">
            <CircleNotch className="animate-spin" size={20} />
            <span className="font-ui text-body">Wczytywanie czarów…</span>
          </div>
        ) : groups.length === 0 ? (
          <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
            Ta postać nie zna żadnych czarów.
          </p>
        ) : (
          groups.map((g) => (
            <div key={g.tier} className="mb-5">
              <div className="mb-2 flex items-center gap-2.5 font-ui text-[10px] font-bold uppercase tracking-[0.18em] text-ember after:h-px after:flex-1 after:bg-line-soft after:content-['']">
                Tier {g.tier}
                <span className="font-medium normal-case tracking-normal text-text-3">
                  · znane {g.knownCount} / {g.rows.length}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2">
                {g.rows.map((sp) => (
                  <SpellRowView
                    key={sp.key}
                    sp={sp}
                    unlockLevel={tierUnlockLevel(g.tier)}
                    heroLevel={level}
                    onSelect={() => setSelected(sp)}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </PanelScroll>

      {selected && (
        <SpellDetailModal
          sp={selected}
          unlockLevel={tierUnlockLevel(selected.tier)}
          heroLevel={level}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function SpellRowView({
  sp,
  unlockLevel,
  heroLevel,
  onSelect,
}: {
  sp: SpellRow;
  unlockLevel: number;
  heroLevel: number;
  onSelect: () => void;
}) {
  const Icon = SPELL_TYPE_ICON[sp.spell_type] ?? SPELL_TYPE_ICON.narrative;
  const dmg = sp.damage_die ? `${sp.damage_die} obr.` : null;
  const heal = sp.heal_die ? `${sp.heal_die} lecz.` : null;
  const levelGated = !sp.known && heroLevel < unlockLevel;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`${sp.label} — pokaż opis`}
      className={cn(
        "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors hover:border-line-ember",
        sp.known
          ? "border-[rgba(255,122,61,0.2)] bg-player-card"
          : "border-line-soft bg-surface",
        !sp.known && "opacity-60",
      )}
    >
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border",
          sp.known
            ? "border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow"
            : "border-line bg-[rgba(130,167,199,0.1)] text-mana",
        )}
      >
        <Icon size={16} weight={sp.known ? "fill" : "regular"} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-label font-semibold text-text">
          {sp.label}
          {sp.known && (
            <span className="rounded bg-ember px-1.5 py-0.5 text-[8.5px] font-bold uppercase tracking-wide text-bg">
              rzuć
            </span>
          )}
        </div>
        <div className="mt-0.5 flex flex-wrap gap-2 font-mono text-[10.5px] text-text-3">
          <span>{SPELL_TYPE_PL[sp.spell_type] ?? sp.spell_type}</span>
          {dmg && <span className="text-danger">{dmg}</span>}
          {heal && <span className="text-success">{heal}</span>}
        </div>
      </div>
      {sp.known ? (
        <>
          <span className="shrink-0 font-mono text-label font-semibold text-mana">
            {sp.mana_cost}◈
          </span>
          <span className="shrink-0 rounded-md border border-line-ember px-1.5 py-0.5 font-mono text-[10.5px] text-ember-glow">
            R{sp.rank || 1}
          </span>
        </>
      ) : (
        <span className="flex shrink-0 items-center gap-1 font-ui text-[11px] text-text-3">
          <Lock size={11} />
          {levelGated ? `poz. ${unlockLevel}` : "1 pkt"}
        </span>
      )}
    </button>
  );
}

// Modal opisu czaru — otwierany po kliknięciu wiersza. Opis + statystyki.
function SpellDetailModal({
  sp,
  unlockLevel,
  heroLevel,
  onClose,
}: {
  sp: SpellRow;
  unlockLevel: number;
  heroLevel: number;
  onClose: () => void;
}) {
  const Icon = SPELL_TYPE_ICON[sp.spell_type] ?? SPELL_TYPE_ICON.narrative;
  const dmg = sp.damage_die ? `${sp.damage_die} obr.` : null;
  const heal = sp.heal_die ? `${sp.heal_die} lecz.` : null;
  const levelGated = !sp.known && heroLevel < unlockLevel;
  const desc = (sp.description ?? "").trim();

  return (
    <div
      className="fixed inset-0 z-[58] flex items-center justify-center bg-bg/85 p-6 backdrop-blur-sm"
      data-testid="spell-detail-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-sm rounded-xl border border-line-ember bg-surface p-4 shadow-modal">
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          className="absolute right-3 top-3 text-text-3 hover:text-text"
        >
          <X size={18} />
        </button>
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-md border",
              sp.known
                ? "border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow"
                : "border-line bg-[rgba(130,167,199,0.1)] text-mana",
            )}
          >
            <Icon size={20} weight={sp.known ? "fill" : "regular"} />
          </span>
          <div className="min-w-0">
            <div className="font-serif text-body font-semibold text-text">{sp.label}</div>
            <div className="font-ui text-micro uppercase tracking-wide text-text-3">
              Tier {sp.tier} · {SPELL_TYPE_PL[sp.spell_type] ?? sp.spell_type}
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2 font-mono text-[11px]">
          <span className="rounded border border-line-soft px-1.5 py-0.5 text-mana">
            {sp.mana_cost}◈ mana
          </span>
          {dmg && (
            <span className="rounded border border-line-soft px-1.5 py-0.5 text-danger">{dmg}</span>
          )}
          {heal && (
            <span className="rounded border border-line-soft px-1.5 py-0.5 text-success">{heal}</span>
          )}
          {sp.known ? (
            <span className="rounded border border-line-ember px-1.5 py-0.5 text-ember-glow">
              R{sp.rank || 1}
            </span>
          ) : (
            <span className="flex items-center gap-1 rounded border border-line-soft px-1.5 py-0.5 text-text-3">
              <Lock size={11} />
              {levelGated ? `poz. ${unlockLevel}` : "1 pkt"}
            </span>
          )}
        </div>

        <p className="mt-3 font-serif text-label leading-relaxed text-text-2">
          {desc || "Brak opisu tego czaru."}
        </p>
      </div>
    </div>
  );
}
