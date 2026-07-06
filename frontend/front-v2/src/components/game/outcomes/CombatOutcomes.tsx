// FE10 (#1237) — orkiestrator modali końca walki. Zależnie od `ended_reason`:
//  • victory  → F-30/F-31 Koniec walki + łup → (rzadki drop F-32) → (loch: F-29)
//  • player_dead → F-28 Ekran śmierci (epitafium + wskrzeszenie/nowa/inny bohater)
//  • fled     → nic (CombatView robi toast)
// Każdy modal wywoływany właściwym zdarzeniem silnika (stan zakończonej walki +
// dungeon-run + death-summary), zero wymyślonych danych.
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useEquipItem } from "@/hooks/useSheetData";
import { useCampaignClock } from "@/hooks/useGameData";
import {
  useBossChoice,
  useClaimLoot,
  useDeathSummary,
  useDungeonRun,
  useResurrect,
  useResurrectPreview,
  useXpSnapshot,
} from "@/hooks/useOutcomes";
import { lootPool } from "@/lib/outcomes";
import { readVitals } from "@/lib/game";
import type { CharacterDetail, CombatState, DropComparison } from "@/lib/types";
import { CombatEndModal } from "./CombatEndModal";
import { DeathScreen } from "./DeathScreen";
import { DungeonVictoryModal } from "./DungeonVictoryModal";
import { DropCelebration } from "./DropCelebration";

export function CombatOutcomes({
  campaignId,
  heroId,
  character,
  reason,
  endedCombat,
  xpGain,
  goldGain,
  onDismiss,
}: {
  campaignId: number;
  heroId: number | undefined;
  character: CharacterDetail | undefined;
  reason: "victory" | "player_dead" | "fled" | string;
  endedCombat: CombatState;
  xpGain: number;
  goldGain: number;
  onDismiss: () => void;
}) {
  const navigate = useNavigate();
  const characterId = character?.id;
  const isVictory = reason === "victory";
  const isDeath = reason === "player_dead";

  const claim = useClaimLoot(campaignId);
  const boss = useBossChoice();
  const equip = useEquipItem(characterId);
  const xpSnap = useXpSnapshot(characterId, isVictory);
  const dungeon = useDungeonRun(campaignId, isVictory);
  const clock = useCampaignClock(campaignId);
  const deathSummary = useDeathSummary(campaignId, isDeath);
  const revivePreview = useResurrectPreview(characterId, isDeath);
  const revive = useResurrect(characterId);

  const [stage, setStage] = useState<"end" | "dungeon">("end");
  const [drops, setDrops] = useState<DropComparison[]>([]);

  const loot = useMemo(() => lootPool(endedCombat), [endedCombat]);
  const vit = readVitals(character?.sheet_json);
  const lifetime = xpSnap.data?.xp_lifetime_earned ?? 0;
  const bossPending = !!dungeon.data?.dungeon_run?.boss_choice_pending;

  // Nazwy pokonanych + rundy dla podtytułu.
  const defeated = useMemo(() => {
    const cs = Array.isArray(endedCombat.combatants) ? endedCombat.combatants : [];
    return cs
      .filter((c) => c.type === "enemy" || c.type === "summon")
      .map((c) => String(c.name || "Wróg"));
  }, [endedCombat]);
  const rounds = Number(endedCombat.round || 1);

  // ── victory: koniec walki + łup ────────────────────────────────────────────
  function afterLoot() {
    if (bossPending) setStage("dungeon");
    else onDismiss();
  }

  async function takeAll() {
    if (!characterId || loot.length === 0) return afterLoot();
    try {
      const res = await claim.mutateAsync({
        characterId,
        selectedIndexes: loot.map((_, i) => i),
      });
      const specials = (res.data?.claimed ?? [])
        .map((c) => c.comparison)
        .filter((c): c is DropComparison => !!c && !!c.is_special);
      if (specials.length) {
        setDrops(specials); // drop celebration → afterLoot po zamknięciu
        return;
      }
    } catch {
      /* nieudany claim — i tak domknij */
    }
    afterLoot();
  }

  function closeDrop() {
    setDrops((d) => {
      const rest = d.slice(1);
      if (rest.length === 0) afterLoot();
      return rest;
    });
  }

  // ── death ──────────────────────────────────────────────────────────────────
  const reviveEnabled = !!revivePreview.data?.enabled;
  const reviveDesc = reviveDescLabel(revivePreview.data);

  async function doRevive() {
    try {
      await revive.mutateAsync();
    } catch {
      /* cooldown/limit — zostań na ekranie */
      return;
    }
    onDismiss();
  }

  if (isDeath) {
    const d = deathSummary.data;
    return (
      <DeathScreen
        heroName={d?.character_name || character?.name || "Bohater"}
        epitaph={d?.epitaph || ""}
        level={d?.level ?? vit.level}
        turns={d?.stats?.turn_count ?? 0}
        days={clock.data?.day ?? 0}
        reviveEnabled={reviveEnabled}
        reviveDesc={reviveDesc}
        reviving={revive.isPending}
        onRevive={doRevive}
        onNewAdventure={() =>
          navigate(heroId ? `/bohaterowie/${heroId}/kampanie` : "/bohaterowie")
        }
        onOtherHero={() => navigate("/bohaterowie")}
      />
    );
  }

  if (!isVictory) return null;

  // Drop celebration ma najwyższy priorytet (overlay na modalu końca walki).
  if (drops.length > 0) {
    return (
      <DropCelebration
        drop={drops[0]}
        equipping={equip.isPending}
        onEquip={(inv, slot) => equip.mutate({ inventoryId: inv, slot }, { onSuccess: closeDrop })}
        onClose={closeDrop}
      />
    );
  }

  if (stage === "dungeon") {
    const run = dungeon.data?.dungeon_run;
    return (
      <DungeonVictoryModal
        title={run?.label ? String(run.label) : "Krypta oczyszczona"}
        subtitle="Boss legł u twych stóp. Loch milknie."
        xpGain={xpGain}
        goldGain={goldGain}
        defeated={Number(run?.enemies_defeated ?? defeated.length)}
        rooms={Number(run?.rooms_cleared ?? run?.cycle ?? 1)}
        busy={boss.isPending}
        onDeeper={() => boss.mutate("go_deeper", { onSuccess: onDismiss })}
        onExit={() => boss.mutate("exit", { onSuccess: onDismiss })}
      />
    );
  }

  return (
    <CombatEndModal
      title="Walka wygrana"
      subtitle={`${defeated.join(" i ") || "Wrogowie"} pokonani · ${rounds} ${roundWord(rounds)}`}
      xpGain={xpGain}
      goldGain={goldGain}
      hp={vit.hp}
      maxHp={vit.maxHp}
      lifetime={lifetime}
      loot={loot}
      claiming={claim.isPending}
      onTake={takeAll}
      onSkip={afterLoot}
    />
  );
}

function roundWord(n: number): string {
  if (n === 1) return "runda";
  const last = n % 10;
  const teen = n % 100;
  return last >= 2 && last <= 4 && !(teen >= 12 && teen <= 14) ? "rundy" : "rund";
}

function reviveDescLabel(preview: ReturnType<typeof useResurrectPreview>["data"]): string {
  if (!preview?.enabled) return "Wskrzeszenie niedostępne";
  const cost = preview.cost as Record<string, unknown> | null | undefined;
  if (cost?.free) return "Powrót w miejscu śmierci · bez kosztu";
  if (cost && "gold" in cost) return `Powrót w miejscu śmierci · koszt ${cost.gold} złota`;
  if (cost && "xp" in cost) return `Powrót w miejscu śmierci · kara ${cost.xp} XP`;
  return "Powrót w miejscu śmierci";
}
