// F-27 V2 (TASK_25_XP_PROGRESSION_V2 [D12]) — ekran awansu (WFRP direct-spend).
// BRAK auto-modala: awans ręczny przez przycisk ⬆️ Awansuj. 3 zakładki:
// Statystyki / Umiejętności / Magia. Wydawanie PD natychmiast (bez potwierdzeń).
import { useState } from "react";
import type { ReactNode } from "react";
import { X, ArrowFatUp, Sparkle, CaretDown } from "@phosphor-icons/react";
import { useAppStore } from "@/store/appStore";
import { useCharacter } from "@/hooks/useGameData";
import {
  useXpSnapshot,
  useSpendStat,
  useSpendSkill,
  useSpendSpellLearn,
  useSpendSpellUpgrade,
} from "@/hooks/useOutcomes";
import { usePublicSkills, useSpells, useSpellCatalog } from "@/hooks/useSheetData";
import { readStats } from "@/lib/game";
import { canRaceLearnSpell } from "@/lib/spells";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import type { HeroSheet } from "@/lib/types";

const STAT_LABEL: Record<string, string> = {
  STR: "Siła", DEX: "Zręczność", CON: "Kondycja", INT: "Intelekt",
  WIS: "Roztropność", CHA: "Charyzma", LCK: "Szczęście",
};
// Opisy 7 zablokowanych cech (lustro _CREATOR_STATS w backend/app/api/mechanics.py).
const STAT_DESC: Record<string, string> = {
  STR: "Obrażenia wręcz, atletyka, dźwiganie, forsowanie drzwi.",
  DEX: "Inicjatywa, skradanie, uniki, ataki finezyjne i dystansowe.",
  CON: "Punkty życia, odporność na trucizny i ból, wytrzymałość.",
  INT: "Magia arkanów, wiedza, badanie, alchemia.",
  WIS: "Percepcja, przetrwanie, medycyna, odporność na strach.",
  CHA: "Perswazja, zastraszanie, negocjacje, przywództwo.",
  LCK: "Rzuty losowe, jakość łupów, szanse ucieczki i zdarzenia losowe.",
};
const SPELL_LEARN_COST = 75;
const SPELL_UPGRADE_COST: Record<number, number> = { 2: 50, 3: 100 };
const SPELL_MAX_RANK = 3;

type Tab = "stats" | "skills" | "magic";

export function AdvancementScreen({
  characterId,
  userId,
  inCombat,
}: {
  characterId: number | undefined;
  userId: number | undefined;
  inCombat: boolean;
}) {
  const open = useAppStore((s) => s.advancementOpen);
  const close = useAppStore((s) => s.closeAdvancement);
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("stats");

  const character = useCharacter(open ? characterId : undefined);
  const xp = useXpSnapshot(characterId, open);
  const sheet = character.data?.sheet_json as HeroSheet | undefined;
  const isScholar =
    String((sheet?.archetype ?? sheet?.class) || "").toLowerCase() === "scholar";

  const spendStat = useSpendStat(characterId, userId);
  const spendSkill = useSpendSkill(characterId);
  const learnSpell = useSpendSpellLearn(characterId, userId);
  const upgradeSpell = useSpendSpellUpgrade(characterId, userId);
  const busy =
    spendStat.isPending || spendSkill.isPending || learnSpell.isPending || upgradeSpell.isPending;

  if (!open) return null;

  const avail = xp.data?.xp_available ?? 0;
  const onErr = (e: unknown) =>
    toast(e instanceof Error ? e.message : "Nie udało się awansować.", "danger");

  const tabs: { key: Tab; label: string }[] = [
    { key: "stats", label: "Statystyki" },
    { key: "skills", label: "Umiejętności" },
    ...(isScholar ? [{ key: "magic" as Tab, label: "Magia" }] : []),
  ];

  return (
    <div className="fixed inset-0 z-[55]" data-testid="advancement-screen">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={close} />
      <div
        className="absolute inset-x-0 bottom-0 top-auto flex max-h-[90%] flex-col rounded-t-2xl border-t border-line bg-surface shadow-2xl lg:inset-y-0 lg:right-0 lg:left-auto lg:w-[440px] lg:max-h-full lg:rounded-none lg:border-l lg:border-t-0"
        style={{ paddingTop: "var(--sa-top)" }}
      >
        {/* nagłówek + dostępne PD */}
        <div className="flex items-center gap-3 border-b border-line px-4 py-3">
          <ArrowFatUp weight="fill" className="text-ember" size={20} />
          <span className="font-serif text-title text-text">Awans</span>
          <span className="ml-auto flex items-center gap-1.5 rounded-pill border border-line-ember bg-ember/[0.08] px-3 py-1">
            <span className="font-ui text-micro uppercase tracking-wide text-text-3">Dostępne PD</span>
            <span className="font-mono text-body font-semibold text-ember-glow">{avail}</span>
          </span>
          <button aria-label="Zamknij" onClick={close} className="text-text-3 hover:text-text">
            <X size={20} />
          </button>
        </div>

        {inCombat && (
          <div className="border-b border-line-danger bg-danger/[0.08] px-4 py-2 font-ui text-micro text-danger-glow">
            Nie możesz awansować podczas walki.
          </div>
        )}

        {/* zakładki */}
        <div className="flex shrink-0 border-b border-line px-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex-1 border-b-2 px-2 py-2.5 font-ui text-label font-semibold transition-colors",
                tab === t.key
                  ? "border-ember text-ember-glow"
                  : "border-transparent text-text-3 hover:text-text-2",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {xp.isLoading ? (
            <p className="py-8 text-center font-ui text-body text-text-3">Wczytywanie…</p>
          ) : tab === "stats" ? (
            <StatsTab
              sheet={sheet}
              costs={xp.data?.stat_point_costs ?? {}}
              ceiling={xp.data?.stat_value_ceiling ?? 20}
              avail={avail}
              disabled={busy || inCombat}
              onBuy={(k) => spendStat.mutate(k, { onError: onErr })}
            />
          ) : tab === "skills" ? (
            <SkillsTab
              characterId={characterId}
              sheet={sheet}
              costs={xp.data?.rank_up_costs ?? {}}
              ceiling={xp.data?.skill_rank_ceiling ?? 3}
              avail={avail}
              disabled={busy || inCombat}
              onBuy={(k) => spendSkill.mutate(k, { onError: onErr })}
            />
          ) : (
            <MagicTab
              characterId={characterId}
              race={character.data?.race}
              avail={avail}
              disabled={busy || inCombat}
              onLearn={(k) => learnSpell.mutate(k, { onError: onErr })}
              onUpgrade={(k) => upgradeSpell.mutate(k, { onError: onErr })}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function mod(v: number): number {
  return Math.floor((v - 10) / 2);
}
function fmtMod(m: number): string {
  return (m >= 0 ? "+" : "") + m;
}

// ── Statystyki ────────────────────────────────────────────────────────────────
function StatsTab({
  sheet, costs, ceiling, avail, disabled, onBuy,
}: {
  sheet: HeroSheet | undefined;
  costs: Record<string, number>;
  ceiling: number;
  avail: number;
  disabled: boolean;
  onBuy: (statKey: string) => void;
}) {
  const stats = readStats(sheet);
  return (
    <div className="flex flex-col gap-2">
      {stats.map((s) => {
        const newV = s.v + 1;
        const cost = Number(costs[String(newV)] ?? Infinity);
        const atMax = s.v >= ceiling;
        const canBuy = !disabled && !atMax && Number.isFinite(cost) && avail >= cost;
        return (
          <ExpandRow key={s.k} desc={STAT_DESC[s.k] ?? null}>
            <span className="w-9 font-mono text-label font-semibold text-text-3">{s.k}</span>
            <span className="flex-1 font-ui text-label text-text">{STAT_LABEL[s.k] ?? s.k}</span>
            <span className="font-mono text-body font-semibold text-text">{s.v}</span>
            <span className="w-9 text-right font-mono text-micro text-text-3">{fmtMod(mod(s.v))}</span>
            <BuyBtn
              cost={atMax ? null : cost}
              can={canBuy}
              atMax={atMax}
              onClick={() => onBuy(s.k)}
            />
          </ExpandRow>
        );
      })}
    </div>
  );
}

// ── Umiejętności ──────────────────────────────────────────────────────────────
function SkillsTab({
  characterId, sheet, costs, ceiling, avail, disabled, onBuy,
}: {
  characterId: number | undefined;
  sheet: HeroSheet | undefined;
  costs: Record<string, number>;
  ceiling: number;
  avail: number;
  disabled: boolean;
  onBuy: (skillKey: string) => void;
}) {
  const catalog = usePublicSkills(true, characterId);
  const owned = (sheet?.skills && typeof sheet.skills === "object"
    ? (sheet.skills as Record<string, number>)
    : {}) as Record<string, number>;
  const list = (catalog.data ?? [])
    .map((c) => ({ ...c, rank: Number(owned[c.key] ?? 0), cap: c.rank_ceiling || ceiling }))
    .sort((a, b) => b.rank - a.rank || a.label.localeCompare(b.label, "pl"));

  if (catalog.isLoading)
    return <p className="py-8 text-center font-ui text-body text-text-3">Wczytywanie…</p>;

  return (
    <div className="flex flex-col gap-2">
      {list.map((s) => {
        const nextRank = s.rank + 1;
        const cost = Number(costs[String(nextRank)] ?? Infinity);
        const atMax = s.rank >= s.cap;
        const canBuy = !disabled && !atMax && Number.isFinite(cost) && avail >= cost;
        return (
          <ExpandRow key={s.key} desc={s.description || null}>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-ui text-label text-text">{s.label}</span>
              <span className="font-mono text-[10px] text-text-3">{s.linked_stat}</span>
            </span>
            <div className="flex gap-1">
              {Array.from({ length: s.cap }).map((_, i) => (
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
            <BuyBtn cost={atMax ? null : cost} can={canBuy} atMax={atMax} onClick={() => onBuy(s.key)} />
          </ExpandRow>
        );
      })}
    </div>
  );
}

// ── Magia (Scholar) ───────────────────────────────────────────────────────────
function MagicTab({
  characterId, race, avail, disabled, onLearn, onUpgrade,
}: {
  characterId: number | undefined;
  race: string | undefined;
  avail: number;
  disabled: boolean;
  onLearn: (spellKey: string) => void;
  onUpgrade: (spellKey: string) => void;
}) {
  const known = useSpells(characterId);
  const catalog = useSpellCatalog(true, characterId);
  if (known.isLoading || catalog.isLoading)
    return <p className="py-8 text-center font-ui text-body text-text-3">Wczytywanie…</p>;

  const knownMap = new Map((known.data ?? []).map((k) => [k.spell_key, k.rank]));
  const rows = (catalog.data ?? [])
    // #975 R6 — tylko czary uczalne przez rasę bohatera (lustro backendu).
    .filter((sp) => canRaceLearnSpell(race, sp.race_lock))
    .map((sp) => ({ ...sp, rank: knownMap.get(sp.key) ?? 0 }))
    .sort((a, b) => Number(b.rank > 0) - Number(a.rank > 0) || (a.tier - b.tier) || (a.mana_cost - b.mana_cost));

  return (
    <div className="flex flex-col gap-2">
      {rows.map((sp) => {
        const isKnown = sp.rank > 0;
        const nextRank = sp.rank + 1;
        const cost = isKnown ? SPELL_UPGRADE_COST[nextRank] : SPELL_LEARN_COST;
        const atMax = isKnown && sp.rank >= SPELL_MAX_RANK;
        const canBuy = !disabled && !atMax && !!cost && avail >= cost;
        return (
          <ExpandRow key={sp.key} desc={sp.description || null}>
            <Sparkle size={16} className={isKnown ? "shrink-0 text-ember" : "shrink-0 text-text-3"} />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-ui text-label text-text">{sp.label}</span>
              <span className="font-mono text-[10px] text-text-3">
                T{sp.tier} · {sp.mana_cost} many
                {sp.damage_die && <span className="text-danger"> · {sp.damage_die} obr.</span>}
                {sp.heal_die && <span className="text-success"> · {sp.heal_die} lecz.</span>}
                {isKnown ? ` · R${sp.rank}` : " · nieznane"}
              </span>
            </span>
            <BuyBtn
              cost={atMax ? null : cost ?? null}
              can={canBuy}
              atMax={atMax}
              label={isKnown ? undefined : "Ucz"}
              onClick={() => (isKnown ? onUpgrade(sp.key) : onLearn(sp.key))}
            />
          </ExpandRow>
        );
      })}
    </div>
  );
}

// ── Wiersz z rozwijanym opisem ────────────────────────────────────────────────
// Tap w karetkę rozwija opis cechy/umiejętności/czaru (wzór: PanelSkills F-54).
function ExpandRow({ desc, children }: { desc: string | null; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-md border border-line-soft bg-bg">
      <div className="flex items-center gap-3 px-3.5 py-2.5">
        {children}
        {desc && (
          <button
            type="button"
            aria-label={open ? "Zwiń opis" : "Rozwiń opis"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="shrink-0 text-text-3 transition-colors hover:text-text-2"
          >
            <CaretDown size={13} className={cn("transition-transform", open && "rotate-180")} />
          </button>
        )}
      </div>
      {desc && open && (
        <p className="border-t border-line-soft bg-surface px-3.5 py-2.5 font-serif text-micro leading-relaxed text-text-2">
          {desc}
        </p>
      )}
    </div>
  );
}

// ── Przycisk kupna ────────────────────────────────────────────────────────────
function BuyBtn({
  cost, can, atMax, label, onClick,
}: {
  cost: number | null;
  can: boolean;
  atMax: boolean;
  label?: string;
  onClick: () => void;
}) {
  if (atMax)
    return <span className="w-[76px] text-right font-ui text-micro text-text-3">maks.</span>;
  return (
    <button
      type="button"
      disabled={!can}
      onClick={onClick}
      className={cn(
        "flex w-[76px] shrink-0 items-center justify-center gap-1 rounded-md border px-2 py-1.5 font-ui text-micro font-semibold transition-colors",
        can
          ? "border-line-ember bg-ember/[0.08] text-ember-glow hover:bg-ember/[0.16]"
          : "border-line text-text-3 opacity-50",
      )}
    >
      <ArrowFatUp weight="fill" size={12} />
      {label ?? cost} {label ? cost : "PD"}
    </button>
  );
}
