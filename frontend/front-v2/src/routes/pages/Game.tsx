import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CircleNotch } from "@phosphor-icons/react";
import {
  useBuildCamp,
  useCampaignDetail,
  useCampaigns,
  useCharacter,
  useRestLong,
  useSubmitTurn,
  useSuggestedActions,
  useTravel,
  useTravelResume,
  useTurnStream,
} from "@/hooks/useGameData";
import { useAppStore } from "@/store/appStore";
import { useToast } from "@/components/ui/toast";
import { voice } from "@/lib/voice";
import { GameMenu } from "@/components/game/GameMenu";
import { FinaleCard, FinaleFlow } from "@/components/game/FinaleFlow";
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
import { Journal } from "@/components/game/journal/Journal";
import { ShopOverlay } from "@/components/game/ShopOverlay";
import { CommandPalette } from "@/components/game/CommandPalette";
import { BugReportFab } from "@/components/game/BugReportFab";
import { RecapOverlay } from "@/components/game/RecapOverlay";
import { CharacterSheet } from "@/components/sheet/CharacterSheet";
import { CombatView } from "@/components/game/combat/CombatView";
import { DungeonView } from "@/components/game/dungeon/DungeonView";
import { MpGame } from "@/components/game/mp/MpGame";
import { AdvancementScreen } from "@/components/game/outcomes/AdvancementScreen";
import { useCombatState } from "@/hooks/useCombat";
import { detectShop } from "@/lib/game";

// FE14 (#1263): czytelne nazwy ekranów do auto-kontekstu bug-reportu.
const SCREEN_LABELS: Record<string, string> = {
  story: "opowieść",
  character: "karta postaci",
  skills: "umiejętności",
  spells: "czary",
  inventory: "ekwipunek",
  reputation: "reputacja",
  map: "mapa świata",
  journal: "dziennik",
};

// F-12 ekran gry (KROK 4 #1233): narracja + composer + rzuty + paski, wg makiety zar4/zar3.
// Topbar (zegar/quest) i dolne paski HP/Mana + tabbar renderuje shell (czyta store).
export default function Game() {
  const { campaignId: raw } = useParams();
  const campaignId = raw ? Number(raw) : undefined;
  const setCampaign = useAppStore((s) => s.setCampaign);
  const setHero = useAppStore((s) => s.setHero);
  const currentUser = useAppStore((s) => s.currentUser);
  const openShop = useAppStore((s) => s.openShop);
  const setFinishFlow = useAppStore((s) => s.setFinishFlow);

  const gameTab = useAppStore((s) => s.gameTab);

  const campaign = useCampaignDetail(campaignId);
  // Detail endpoint nie zwraca character_id — bierzemy aktywnego bohatera z listy
  // kampanii (subquery is_active), więc działa też po odświeżeniu / deep-linku.
  const campaigns = useCampaigns();
  const storeHeroId = useAppStore((s) => s.currentHeroId);
  // Loch tworzy świeżą kampanię — lista może być chwilowo nieświeża (staleTime),
  // więc dla trybu lochu bierzemy bohatera ze store jako fallback (ustawiony przy wejściu).
  const listCharacterId =
    campaigns.data?.find((c) => c.id === campaignId)?.character_id ?? undefined;
  const characterId = listCharacterId ?? storeHeroId ?? undefined;
  const character = useCharacter(characterId ?? undefined);
  const stream = useTurnStream(campaignId);
  const submit = useSubmitTurn(campaignId);
  // F-80 (#1268): mechaniczne akcje po przerwaniu podróży (omijają narratora).
  const travelResume = useTravelResume(campaignId);
  const buildCamp = useBuildCamp(campaignId);
  const restLong = useRestLong(campaignId, characterId, currentUser?.id);
  const travel = useTravel(campaignId);
  const { toast } = useToast();
  // FE9 (#1236): stan walki — poll tylko gdy aktywna. Aktywna → ekran walki.
  const combatState = useCombatState(campaignId);
  const activeCombat =
    combatState.data?.active && combatState.data.combat?.status === "active"
      ? combatState.data.combat
      : null;
  // FE15 (#1264): tryb drużynowy → rundy MP zamiast solowego turn-flow (walka MP osobno).
  const isMp = campaign.data?.mode === "multiplayer";
  // FE16 (#1265): tryb lochu → eksploracja kafelkowa (HUD/d-pad/mapa) + walka + boss.
  const isDungeon = campaign.data?.mode === "dungeon";

  // F-77 (#1268): bramka finału. Widoczna gdy cel osiągnięty; w MP tylko gospodarz.
  const finaleAllowed =
    !!campaign.data?.finale_available &&
    (!isMp || campaign.data?.host_user_id == null || campaign.data?.host_user_id === currentUser?.id);

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
    // FE12 (#1261): narracja mogła otworzyć sklep ([OPEN_SHOP] / open_shop) — overlay.
    const shop = detectShop(resp);
    if (shop) openShop(shop);
    // F-72 (#1267): lektor czyta świeżą narrację GM (no-op gdy TTS wyłączony).
    if (typeof resp.prose === "string" && resp.prose.trim()) voice.speak(resp.prose);
  }

  function send(text: string) {
    if (!characterId) return;
    submit.mutate({ characterId, text }, { onSuccess: applyResponse });
  }

  // F-80 (#1268): klik w chip. Mechaniczne akcje (podróż/obóz/odpoczynek) omijają
  // narratora i wołają dedykowane endpointy; reszta idzie jako akcja tury.
  function chipError(err: unknown) {
    toast(err instanceof Error ? err.message : "Nie udało się wykonać akcji.", "danger");
  }
  function onChip(c: Chip, current: Chip[]) {
    if (!characterId) return;
    const act = (c.action || c.text || c.label || "").trim();
    if (act === "TRAVEL_RESUME") {
      travelResume.mutate(undefined, {
        onSuccess: (r) => setChips(normalizeChips(r.suggested_actions)),
        onError: chipError,
      });
      return;
    }
    if (act === "BUILD_CAMP") {
      // Po rozbiciu obozu: usuń „Rozbij obóz", odblokuj „Odpocznij" (parytet ze starym UI).
      buildCamp.mutate(undefined, {
        onSuccess: () =>
          setChips(
            current
              .filter((x) => (x.action || x.text) !== "BUILD_CAMP")
              .map((x) =>
                (x.action || x.text) === "REST:long"
                  ? { ...x, enabled: true, reason: undefined }
                  : x,
              ),
          ),
        onError: chipError,
      });
      return;
    }
    if (act === "REST:long") {
      restLong.mutate(undefined, { onSuccess: () => setChips([]), onError: chipError });
      return;
    }
    if (act.startsWith("TRAVEL:")) {
      const [, q, r] = act.split(":");
      const qq = Number(q);
      const rr = Number(r);
      if (Number.isFinite(qq) && Number.isFinite(rr)) {
        travel.mutate({ characterId, q: qq, r: rr }, { onSuccess: () => setChips([]), onError: chipError });
        return;
      }
    }
    // Domyślnie: strukturalny ciąg akcji lub wolny tekst jako tura.
    send(act);
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
  // Chipy: świeże z ostatniego submitu, inaczej z ostatniej tury w strumieniu,
  // a gdy tura ich nie niosła (backend nie zapisuje suggested_actions per-tura) —
  // dobierz z bieżącego stanu kampanii (/suggested-actions), by pille były
  // widoczne od razu po wejściu/odświeżeniu (w tym „Rozbij obóz"/„Odpocznij").
  const streamChips = useMemo(
    () => chipsFromTurns(stream.data?.turns ?? []),
    [stream.data?.turns],
  );
  const suggested = useSuggestedActions(campaignId, characterId, !activeCombat);
  const fetchedChips = useMemo(
    () => normalizeChips(suggested.data),
    [suggested.data],
  );
  const shownChips = chips.length
    ? chips
    : streamChips.length
      ? streamChips
      : fetchedChips;
  const vitals = useMemo(
    () => readVitals(character.data?.sheet_json),
    [character.data?.sheet_json],
  );
  const stats = useMemo(
    () => readStats(character.data?.sheet_json),
    [character.data?.sheet_json],
  );

  // FE14 (#1263): auto-kontekst zgłoszenia buga — ostatnia tura + nazwa ekranu.
  const lastTurn = useMemo(
    () =>
      (stream.data?.turns ?? []).reduce(
        (m, t) => Math.max(m, t.turn_number ?? 0),
        0,
      ),
    [stream.data?.turns],
  );
  const screenLabel = activeCombat
    ? "walka"
    : SCREEN_LABELS[gameTab] ?? "gra";

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
      {/* F-27 V2 (TASK_25 [D12]): awans RĘCZNY (przycisk ⬆️ Awansuj) — bez auto-modala. */}
      <AdvancementScreen
        characterId={characterId}
        userId={currentUser?.id}
        inCombat={!!activeCombat}
      />

      {/* FE18/FE19 (#1267/#1268): menu ☰ (głos + finał) + bramka finału (modal/zwycięstwo). */}
      <GameMenu finaleAllowed={finaleAllowed} />
      <FinaleFlow
        campaignId={campaignId!}
        heroId={characterId}
        heroName={character.data?.name ?? "Bohater"}
        heroLevel={vitals.level}
        turnCount={lastTurn || undefined}
      />

      {/* FE12 (#1261): sklep NPC — overlay nad grą, otwierany narracyjnie */}
      <ShopOverlay />

      {/* FE14 (#1263): paleta komend (Ctrl+/) · recap przy wejściu · FAB testera */}
      <CommandPalette />
      <RecapOverlay campaignId={campaignId} />
      <BugReportFab campaignId={campaignId} turnNumber={lastTurn || undefined} screen={screenLabel} />

      {/* Desktop: lewy pionowy rail przełącza Opowieść ↔ panele karty postaci */}
      <GameRail hasMana={vitals.hasMana} />

      {gameTab === "map" ? (
        // F-43 Mapa świata + podróż (KROK 4 #1235) — własny nagłówek + cinematyka.
        <WorldMap campaignId={campaignId!} characterId={characterId} />
      ) : gameTab === "journal" ? (
        // FE13 Dziennik + Kronika bohatera (#1262) — zakładka gry.
        <Journal campaignId={campaignId!} characterId={characterId} />
      ) : gameTab === "story" && isDungeon ? (
        // FE16 (#1265): tryb lochu — eksploracja + walka + boss/śmierć/porzucenie.
        <DungeonView campaignId={campaignId!} characterId={characterId} />
      ) : gameTab === "story" && isMp ? (
        // FE15 (#1264): sesja drużynowa — rundy MP + party chat + whispery.
        <MpGame
          campaignId={campaignId!}
          character={character.data}
          vitals={vitals}
          stats={stats}
        />
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
              {/* F-77: karta bramki finału w logu (cel osiągnięty). */}
              {finaleAllowed && <FinaleCard onFinish={() => setFinishFlow("confirm")} />}
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
            onChip={(c) => onChip(c, shownChips)}
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
