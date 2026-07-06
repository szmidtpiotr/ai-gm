import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CircleNotch } from "@phosphor-icons/react";
import {
  useCampaignDetail,
  useCampaigns,
  useCharacter,
  useSubmitTurn,
  useTurnStream,
} from "@/hooks/useGameData";
import { useAppStore } from "@/store/appStore";
import {
  buildLog,
  chipsFromTurns,
  normalizeChips,
  readStats,
  readVitals,
  rollFromResult,
  type Chip,
} from "@/lib/game";
import type { RollCardData, TurnResponse } from "@/lib/types";
import { NarrationLog } from "@/components/game/NarrationLog";
import { Composer } from "@/components/game/Composer";
import { VitalsRail } from "@/components/game/Vitals";
import { GameRail } from "@/components/game/GameRail";
import { WorldMap } from "@/components/game/WorldMap";
import { CharacterSheet } from "@/components/sheet/CharacterSheet";
import { CombatView } from "@/components/game/combat/CombatView";
import { useCombatState } from "@/hooks/useCombat";

// F-12 ekran gry (KROK 4 #1233): narracja + composer + rzuty + paski, wg makiety zar4/zar3.
// Topbar (zegar/quest) i dolne paski HP/Mana + tabbar renderuje shell (czyta store).
export default function Game() {
  const { campaignId: raw } = useParams();
  const campaignId = raw ? Number(raw) : undefined;
  const setCampaign = useAppStore((s) => s.setCampaign);
  const setHero = useAppStore((s) => s.setHero);

  const gameTab = useAppStore((s) => s.gameTab);

  const campaign = useCampaignDetail(campaignId);
  // Detail endpoint nie zwraca character_id — bierzemy aktywnego bohatera z listy
  // kampanii (subquery is_active), więc działa też po odświeżeniu / deep-linku.
  const campaigns = useCampaigns();
  const characterId =
    campaigns.data?.find((c) => c.id === campaignId)?.character_id ?? undefined;
  const character = useCharacter(characterId ?? undefined);
  const stream = useTurnStream(campaignId);
  const submit = useSubmitTurn(campaignId);
  // FE9 (#1236): stan walki — poll tylko gdy aktywna. Aktywna → ekran walki.
  const combatState = useCombatState(campaignId);
  const activeCombat =
    combatState.data?.active && combatState.data.combat?.status === "active"
      ? combatState.data.combat
      : null;

  // Zsynchronizuj store, by topbar/tabbar mogły czytać zegar/quest/HP.
  useEffect(() => {
    if (campaignId) setCampaign(campaignId);
  }, [campaignId, setCampaign]);
  useEffect(() => {
    if (characterId) setHero(characterId);
  }, [characterId, setHero]);

  // Ostatnia karta rzutu + chipy z odpowiedzi tury (strumień ich nie niesie).
  const [pendingRoll, setPendingRoll] = useState<RollCardData | null>(null);
  const [chips, setChips] = useState<Chip[]>([]);

  function applyResponse(resp: TurnResponse) {
    setPendingRoll(rollFromResult(resp));
    setChips(normalizeChips(resp.suggested_actions));
  }

  function send(text: string) {
    if (!characterId) return;
    submit.mutate({ characterId, text }, { onSuccess: applyResponse });
  }

  // Bootstrap: aktywna kampania bez tur → odpal scenę otwierającą raz.
  const openedRef = useRef(false);
  useEffect(() => {
    if (
      !openedRef.current &&
      characterId &&
      stream.isSuccess &&
      (stream.data?.turns?.length ?? 0) === 0 &&
      !submit.isPending
    ) {
      openedRef.current = true;
      submit.mutate(
        { characterId, text: "__AI_GM_OPEN" },
        { onSuccess: applyResponse },
      );
    }
  }, [characterId, stream.isSuccess, stream.data, submit]);

  const blocks = useMemo(
    () => buildLog(stream.data?.turns ?? []),
    [stream.data?.turns],
  );
  // Chipy: świeże z ostatniego submitu, inaczej z ostatniej tury w strumieniu.
  const streamChips = useMemo(
    () => chipsFromTurns(stream.data?.turns ?? []),
    [stream.data?.turns],
  );
  const shownChips = chips.length ? chips : streamChips;
  const vitals = useMemo(
    () => readVitals(character.data?.sheet_json),
    [character.data?.sheet_json],
  );
  const stats = useMemo(
    () => readStats(character.data?.sheet_json),
    [character.data?.sheet_json],
  );

  if (
    campaign.isLoading ||
    campaigns.isLoading ||
    (stream.isLoading && !stream.data)
  ) {
    return <FullLoader />;
  }
  if (!characterId) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center font-serif text-prose text-text-2">
        Ta kampania nie ma przypisanego bohatera. Wróć do listy kampanii i wybierz postać.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Desktop: lewy pionowy rail przełącza Opowieść ↔ panele karty postaci */}
      <GameRail hasMana={vitals.hasMana} />

      {gameTab === "map" ? (
        // F-43 Mapa świata + podróż (KROK 4 #1235) — własny nagłówek + cinematyka.
        <WorldMap campaignId={campaignId!} characterId={characterId} />
      ) : gameTab === "story" && activeCombat ? (
        // FE9 walka (#1236): baner + pasek akcji + reakcja SF10 + kość 3D.
        <CombatView
          campaignId={campaignId!}
          character={character.data}
          combat={activeCombat}
          blocks={blocks}
          typing={submit.isPending}
          vitals={vitals}
          stats={stats}
          onSend={send}
          sending={submit.isPending}
        />
      ) : gameTab === "story" ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1">
            <div className="min-w-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <NarrationLog
                blocks={blocks}
                pendingRoll={pendingRoll}
                typing={submit.isPending}
                heroName={character.data?.name}
              />
            </div>
            <VitalsRail
              v={vitals}
              stats={stats}
              locationLabel={character.data?.current_location_label}
            />
          </div>

          <Composer
            onSend={send}
            disabled={submit.isPending}
            chips={shownChips}
            onChip={(c) => send(c.text || c.label)}
          />
        </div>
      ) : (
        // Panele karty postaci (F-21/F-54..F-58/F-76/F-78) — zakładki w grze.
        <CharacterSheet characterId={characterId} />
      )}
    </div>
  );
}

function FullLoader() {
  return (
    <div className="flex h-full items-center justify-center gap-2 text-text-3">
      <CircleNotch className="animate-spin" size={22} />
      <span className="font-ui text-body">Wczytywanie gry…</span>
    </div>
  );
}
