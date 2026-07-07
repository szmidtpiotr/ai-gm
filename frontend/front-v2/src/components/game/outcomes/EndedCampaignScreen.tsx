// Kampania zakończona (status='ended') a gracz wchodzi/odświeża — poza aktywną
// walką CombatOutcomes nie renderuje ekranu końca, więc czat „milczał" (POST /turns
// → 410). Ten ekran pokazuje śmierć (epitafium + wskrzeszenie) albo zwycięstwo.
import { useNavigate } from "react-router-dom";
import { useDeathSummary, useResurrectPreview, useResurrect } from "@/hooks/useOutcomes";
import { useCampaignClock } from "@/hooks/useGameData";
import { readVitals } from "@/lib/game";
import type { CharacterDetail } from "@/lib/types";
import { DeathScreen } from "./DeathScreen";
import { VictoryScreen } from "./VictoryScreen";

export function EndedCampaignScreen({
  campaignId,
  heroId,
  character,
}: {
  campaignId: number;
  heroId: number | undefined;
  character: CharacterDetail | undefined;
}) {
  const navigate = useNavigate();
  const characterId = character?.id;
  const summary = useDeathSummary(campaignId, true);
  const clock = useCampaignClock(campaignId);
  const revivePreview = useResurrectPreview(characterId, true);
  const revive = useResurrect(characterId);
  const vit = readVitals(character?.sheet_json);

  // Zwycięstwo (finisz przygody) → triumfalny wariant.
  if (summary.data?.outcome === "victory") {
    return (
      <VictoryScreen
        campaignId={campaignId}
        heroId={heroId}
        heroName={character?.name ?? "Bohater"}
        heroLevel={vit.level}
        onClose={() => navigate(heroId ? `/bohaterowie/${heroId}/kampanie` : "/bohaterowie")}
      />
    );
  }

  // Domyślnie (śmierć / brak danych) — ekran śmierci z opcją wskrzeszenia.
  const d = summary.data;
  const reviveEnabled = !!revivePreview.data?.enabled;
  const cost = revivePreview.data?.cost as Record<string, unknown> | null | undefined;
  const reviveDesc = !reviveEnabled
    ? "Wskrzeszenie niedostępne"
    : cost?.free
      ? "Powrót w miejscu śmierci · bez kosztu"
      : cost && "gold" in cost
        ? `Powrót w miejscu śmierci · koszt ${cost.gold} złota`
        : cost && "xp" in cost
          ? `Powrót w miejscu śmierci · kara ${cost.xp} XP`
          : "Powrót w miejscu śmierci";

  async function doRevive() {
    try {
      await revive.mutateAsync();
    } catch {
      return; // cooldown/limit — zostań na ekranie
    }
    navigate(heroId ? `/bohaterowie/${heroId}/kampanie` : "/bohaterowie");
  }

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
