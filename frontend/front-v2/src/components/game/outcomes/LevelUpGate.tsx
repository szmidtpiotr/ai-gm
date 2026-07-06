// FE10 (#1237) — F-27 wykrywanie awansu. Nasłuchuje wzrostu sheet.level (próg XP
// przekroczony DOWOLNYM źródłem XP: walka, questy, odpoczynek) i pokazuje modal
// awansu z przyrostami + rozdziałem punktu cechy (PD) + odblokowanymi czarami.
import { useEffect, useRef, useState } from "react";
import { readStats, readVitals } from "@/lib/game";
import { tierUnlockLevel } from "@/lib/outcomes";
import { useSpells, useSpellCatalog } from "@/hooks/useSheetData";
import { useSpendStat, useXpSnapshot } from "@/hooks/useOutcomes";
import type { CharacterDetail } from "@/lib/types";
import { LevelUpModal, type StatPick } from "./LevelUpModal";

// Cechy pokazywane w rozdziale (bez LCK — parytet z makietą zar9-levelup).
const PICK_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"] as const;

export function LevelUpGate({
  character,
  userId,
}: {
  character: CharacterDetail | undefined;
  userId: number | undefined;
}) {
  const characterId = character?.id;
  const vit = readVitals(character?.sheet_json);
  const level = vit.level;

  const prevRef = useRef<number | null>(null);
  const [shownLevel, setShownLevel] = useState<number | null>(null);

  // Pierwszy odczyt = baseline (nie świętuj poziomu, na którym wchodzimy).
  useEffect(() => {
    if (prevRef.current == null) {
      prevRef.current = level;
      return;
    }
    if (level > prevRef.current) setShownLevel(level);
    prevRef.current = level;
  }, [level]);

  const active = shownLevel != null;
  const xpSnap = useXpSnapshot(characterId, active);
  const spells = useSpells(active ? characterId : undefined);
  const isScholar =
    String((character?.sheet_json?.archetype ?? character?.sheet_json?.class) || "").toLowerCase() ===
    "scholar";
  const catalog = useSpellCatalog(active && isScholar);
  const spend = useSpendStat(characterId, userId);

  if (!active || shownLevel == null) return null;

  const statsRaw = readStats(character?.sheet_json);
  const statMap = new Map(statsRaw.map((s) => [s.k, s.v]));
  const conMod = mod(statMap.get("CON") ?? 10);
  const intMod = mod(statMap.get("INT") ?? 10);

  const costs = xpSnap.data?.stat_point_costs ?? {};
  const ceiling = xpSnap.data?.stat_value_ceiling ?? 19;
  const pdAvail = xpSnap.data?.xp_available ?? 0;

  const stats: StatPick[] = PICK_STATS.map((k) => {
    const v = statMap.get(k) ?? 10;
    const newV = v + 1;
    const cost = Number(costs[String(newV)] ?? costs[newV] ?? Infinity);
    return { k, v, newV, affordable: newV <= ceiling && pdAvail >= cost };
  });
  const anyAffordable = stats.some((s) => s.affordable);

  // Czary odblokowane DOKŁADNIE na tym poziomie (tier gate) i jeszcze nieznane.
  const knownKeys = new Set((spells.data ?? []).map((s) => s.spell_key));
  const unlocked = isScholar
    ? (catalog.data ?? [])
        .filter((c) => !knownKeys.has(c.key) && tierUnlockLevel(Number(c.tier || 1)) === shownLevel)
        .map((c) => ({ label: c.label, tier: Number(c.tier || 1) }))
    : [];

  function confirm(pickedStat: string | null) {
    if (pickedStat) {
      spend.mutate(pickedStat, { onSuccess: () => setShownLevel(null) });
    } else {
      setShownLevel(null);
    }
  }

  return (
    <LevelUpModal
      level={shownLevel}
      hpGain={Math.max(1, conMod)}
      manaGain={isScholar ? Math.max(0, intMod) : 0}
      arcaneGain={isScholar ? 1 : 0}
      stats={stats}
      pointsAvailable={anyAffordable ? 1 : 0}
      unlockedSpells={unlocked}
      committing={spend.isPending}
      onConfirm={confirm}
    />
  );
}

function mod(v: number): number {
  return Math.floor((v - 10) / 2);
}
