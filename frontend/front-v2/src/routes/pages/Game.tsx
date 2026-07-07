import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CircleNotch, MoonStars, Path, Warning } from "@phosphor-icons/react";
import {
  useBuildCamp,
  useCampaignDetail,
  useCampaigns,
  useCharacter,
  useLocalMap,
  useRestLong,
  useSubmitTurn,
  useSuggestedActions,
  useTravel,
  useTravelResume,
  useTurnStream,
  type TravelNotice as TravelNoticeData,
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
import { LocalMap } from "@/components/game/LocalMap";
import { EndedCampaignScreen } from "@/components/game/outcomes/EndedCampaignScreen";
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
  const openAdvancement = useAppStore((s) => s.openAdvancement);
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
  // FAZA ML: mapa lokalna osady. Domyślnie pokazujemy ją w hubie z sub-lokacjami;
  // forceWorldMap = gracz kliknął „Świat" i chce zobaczyć mapę świata.
  const [forceWorldMap, setForceWorldMap] = useState(false);
  const localMap = useLocalMap(campaignId, gameTab === "map");
  // PM4: wybór trasy (na wprost / traktem) jako modal z 2 przyciskami zamiast
  // pytania tekstem. Wypełniany, gdy tura zwróci suggested_actions type=route_choice.
  const [routeChoice, setRouteChoice] = useState<
    { label: string; action: string; icon?: string }[] | null
  >(null);

  function applyResponse(resp: TurnResponse) {
    setPendingRoll(rollFromResult(resp));
    setChips(normalizeChips(resp.suggested_actions));
    const routes = (resp.suggested_actions ?? []).filter(
      (a) => a.type === "route_choice",
    );
    if (routes.length >= 2) {
      setRouteChoice(
        routes.map((a) => ({
          label: String(a.label ?? ""),
          action: String(a.action ?? a.text ?? ""),
          icon: a.icon ?? undefined,
        })),
      );
    }
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
        onSuccess: () => {
          setChips(
            current
              .filter((x) => (x.action || x.text) !== "BUILD_CAMP")
              .map((x) =>
                (x.action || x.text) === "REST:long"
                  ? { ...x, enabled: true, reason: undefined }
                  : x,
              ),
          );
          // Feedback + kolejny krok (działa też na zakładce Mapa, gdzie nie widać
          // pili): obóz zbudowany → modal pyta „co dalej" (Odpocznij/Kontynuuj).
          toast("Obóz rozbity — teraz możesz bezpiecznie odpocząć.", "success");
          setInterruptModal({
            reason: "camped",
            severity: "warn",
            title: "Obóz rozbity",
            message: "Rozpaliłeś ognisko i rozłożyłeś posłanie. Odpocznij, by odzyskać siły — albo ruszaj dalej.",
            step: -1,
            hours_remaining: 0,
            destination_label: null,
            can_resume: true,
          });
        },
        onError: chipError,
      });
      return;
    }
    if (act === "REST:long") {
      restLong.mutate(undefined, {
        onSuccess: (r) => {
          setChips([]);
          // Rest nie tworzy tury narracji → daj widoczny feedback (inaczej „nic
          // się nie dzieje"). Awans TYLKO w trakcie odpoczynku (jak stara wersja).
          const hpA = Number(r?.hp_after ?? 0);
          const manaA = Number(r?.mana_after ?? 0);
          const hasMana = Number(r?.mana_before ?? 0) > 0 || manaA > 0;
          const lvl = r?.leveled_up ? ` · awans na poziom ${r?.new_level}!` : "";
          toast(
            `Odpoczynek zakończony — minęło 8 h, HP ${hpA}${hasMana ? `, mana ${manaA}` : ""}.${lvl}`,
            "success",
          );
          const enc = r?.camp_encounter as { triggered?: boolean } | undefined;
          if (enc?.triggered) toast("Coś zakłóciło obóz w nocy…", "danger");
          if (Number(r?.xp_available ?? 0) >= 30) openAdvancement();
        },
        onError: chipError,
      });
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
    () => normalizeChips(suggested.data?.suggested_actions),
    [suggested.data],
  );
  const travelNotice = suggested.data?.travel_notice ?? null;
  // PT7/F-80: fokalny modal w MOMENCIE przerwania podróży — raz na etap
  // (klucz reason:step). Baner nad composerem zostaje jako trwałe przypomnienie.
  const [interruptModal, setInterruptModal] = useState<TravelNoticeData | null>(null);
  const ackInterrupt = useRef<string | null>(null);
  useEffect(() => {
    if (!travelNotice) {
      ackInterrupt.current = null;
      return;
    }
    const key = `${travelNotice.reason}:${travelNotice.step}`;
    if (ackInterrupt.current === key) return;
    ackInterrupt.current = key;
    setInterruptModal(travelNotice);
  }, [travelNotice]);
  // PM4: modal wyboru trasy również po wejściu/odświeżeniu (pending_travel_choice
  // przetrwa jako suggested_actions type=route_choice), nie tylko po submicie tury.
  const routeAck = useRef<string | null>(null);
  useEffect(() => {
    const routes = (suggested.data?.suggested_actions ?? []).filter(
      (a) => a.type === "route_choice",
    );
    if (routes.length < 2) {
      routeAck.current = null;
      return;
    }
    const key = routes.map((r) => r.action ?? r.label).join("|");
    if (routeAck.current === key) return;
    routeAck.current = key;
    setRouteChoice(
      routes.map((a) => ({
        label: String(a.label ?? ""),
        action: String(a.action ?? a.text ?? ""),
        icon: a.icon ?? undefined,
      })),
    );
  }, [suggested.data]);
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
  // Kampania zakończona (śmierć / finisz) — pokaż ekran końca zamiast martwego
  // czatu (POST /turns zwraca 410). Poza aktywną walką nic tego nie renderowało.
  if (campaign.data?.status === "ended") {
    return (
      <EndedCampaignScreen
        campaignId={campaignId!}
        heroId={characterId}
        character={character.data}
      />
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

      {/* PT7/F-80: fokalny modal przerwania podróży (zmierzch / padasz z sił). */}
      {interruptModal && (
        <TravelInterruptModal
          notice={interruptModal}
          onResume={() => { setInterruptModal(null); onChip({ label: "Kontynuuj podróż", text: "TRAVEL_RESUME", action: "TRAVEL_RESUME" }, shownChips); }}
          onRest={() => { setInterruptModal(null); onChip({ label: "Odpocznij", text: "REST:long", action: "REST:long" }, shownChips); }}
          onCamp={() => { setInterruptModal(null); onChip({ label: "Rozbij obóz", text: "BUILD_CAMP", action: "BUILD_CAMP" }, shownChips); }}
          onClose={() => setInterruptModal(null)}
        />
      )}

      {/* PM4: modal wyboru trasy (na wprost / traktem) — 2 przyciski zamiast tekstu. */}
      {routeChoice && (
        <RouteChoiceModal
          options={routeChoice}
          onPick={(action) => { setRouteChoice(null); send(action); }}
          onClose={() => setRouteChoice(null)}
        />
      )}

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
        // FAZA ML: w osadzie z sub-lokacjami domyślnie mapa lokalna; „Świat"/„Osada"
        // przełącza. F-43 mapa świata + podróż (#1235) — własny nagłówek + cinematyka.
        localMap.data?.has_local_map && !forceWorldMap ? (
          <LocalMap campaignId={campaignId!} onWorld={() => setForceWorldMap(true)} />
        ) : (
          <WorldMap
            campaignId={campaignId!}
            characterId={characterId}
            localAvailable={!!localMap.data?.has_local_map}
            onOpenLocal={() => setForceWorldMap(false)}
            onRest={() => onChip({ label: "Odpocznij", text: "REST:long", action: "REST:long" }, shownChips)}
            onCamp={() => onChip({ label: "Rozbij obóz", text: "BUILD_CAMP", action: "BUILD_CAMP" }, shownChips)}
            onResume={() => onChip({ label: "Kontynuuj podróż", text: "TRAVEL_RESUME", action: "TRAVEL_RESUME" }, shownChips)}
          />
        )
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

          {/* PT7/F-80: deterministyczny baner podróży (zmierzch / padasz z sił) —
              niezależny od narracji LLM; znika po Odpocznij/Rozbij obóz. */}
          {travelNotice && <TravelNotice notice={travelNotice} />}

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

// PM4 — modal wyboru trasy do celu: „na wprost" (szybciej/groźniej) vs „traktem"
// (dłużej/bezpieczniej). Klik = wysyła odpowiedź tekstową, którą rozpoznaje backend.
function RouteChoiceModal({
  options,
  onPick,
  onClose,
}: {
  options: { label: string; action: string; icon?: string }[];
  onPick: (action: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[57] flex items-center justify-center p-6" data-testid="route-choice">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-[2] w-full max-w-[420px] overflow-hidden rounded-xl border border-line-ember bg-surface shadow-2xl">
        <div className="flex items-center gap-3 border-b border-line bg-ember/[0.07] px-5 py-4">
          <Path weight="fill" size={24} className="text-ember-glow" />
          <div className="min-w-0">
            <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.18em] text-text-3">
              Wybór drogi
            </div>
            <div className="font-serif text-title font-semibold text-text">Którą drogą ruszasz?</div>
          </div>
        </div>
        <div className="flex flex-col gap-2 p-4">
          {options.map((o, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onPick(o.action)}
              className="flex items-center gap-3 rounded-md border border-line-ember bg-ember/[0.06] px-3.5 py-3 text-left transition-colors hover:border-ember hover:bg-ember/[0.12]"
            >
              {o.icon && <span className="shrink-0 text-lg" aria-hidden>{o.icon}</span>}
              <span className="font-ui text-body font-semibold text-text">{o.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// PT7/F-80 — fokalny modal przerwania podróży: wyjaśnia CO i DLACZEGO + 3 decyzje
// (Kontynuuj / Odpocznij / Rozbij obóz). Pojawia się raz na etap; baner zostaje.
function TravelInterruptModal({
  notice,
  onResume,
  onRest,
  onCamp,
  onClose,
}: {
  notice: TravelNoticeData;
  onResume: () => void;
  onRest: () => void;
  onCamp: () => void;
  onClose: () => void;
}) {
  const danger = notice.severity === "danger";
  const Icon = danger ? Warning : MoonStars;
  // Ukryj surowy koordynat („hex (12,-6)") — pokaż cel tylko gdy ma prawdziwą nazwę.
  const rawDest = notice.destination_label || "";
  const dest = /^hex \(|^\(-?\d+,-?\d+\)$/.test(rawDest) ? null : rawDest || null;
  const hrs = Math.round(notice.hours_remaining || 0);
  const alreadyCamped = notice.reason === "camped";
  // Odpoczynek możliwy tylko w bezpiecznym miejscu (karczma/osada) lub po obozie.
  const canRest = alreadyCamped || notice.can_rest === true;
  // Obóz oferujemy, gdy tu NIE bezpiecznie i jeszcze nie rozbity (to on odblokuje rest).
  const canCamp = !alreadyCamped && !canRest;
  return (
    <div className="fixed inset-0 z-[58] flex items-center justify-center p-6" data-testid="travel-interrupt">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-[2] w-full max-w-[420px] overflow-hidden rounded-xl border border-line-ember bg-surface shadow-2xl">
        <div className={"flex items-center gap-3 border-b border-line px-5 py-4 " + (danger ? "bg-danger/[0.08]" : "bg-ember/[0.07]")}>
          <Icon weight="fill" size={26} className={danger ? "text-danger" : "text-ember-glow"} />
          <div className="min-w-0">
            <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.18em] text-text-3">
              Podróż przerwana
            </div>
            <div className={"font-serif text-title font-semibold " + (danger ? "text-danger-glow" : "text-text")}>
              {notice.title}
            </div>
          </div>
        </div>
        <div className="px-5 py-4">
          <p className="font-serif text-prose leading-relaxed text-text-2">{notice.message}</p>
          {dest && (
            <p className="mt-2 font-ui text-micro text-text-3">
              Cel: <span className="text-text-2">{dest}</span>
              {hrs > 0 ? ` · zostało ~${hrs} h drogi` : ""}
            </p>
          )}
          <div className="mt-4 flex flex-col gap-2">
            <button
              type="button"
              disabled={!notice.can_resume}
              onClick={onResume}
              className="flex items-center justify-center gap-2 rounded-md px-3 py-3 font-ui text-body font-semibold text-white disabled:opacity-40 disabled:shadow-none"
              style={{ background: "linear-gradient(135deg, #d1602c, var(--ember))", boxShadow: "0 0 16px rgba(255,122,61,.35)" }}
              title={notice.can_resume ? undefined : "Padłeś ze zmęczenia — najpierw odpocznij."}
            >
              🧭 Kontynuuj podróż
            </button>
            {(canRest || canCamp) && (
              <div className="flex gap-2">
                {canRest && (
                  <button
                    type="button"
                    onClick={onRest}
                    className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line-ember bg-ember/[0.06] px-3 py-2.5 font-ui text-body font-semibold text-ember-glow transition-colors hover:bg-ember/[0.14]"
                  >
                    😴 Odpocznij
                  </button>
                )}
                {canCamp && (
                  <button
                    type="button"
                    onClick={onCamp}
                    className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line bg-bg px-3 py-2.5 font-ui text-body font-semibold text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
                  >
                    🔥 Rozbij obóz
                  </button>
                )}
              </div>
            )}
            {canCamp && (
              <p className="mt-1 text-center font-ui text-micro text-text-3">
                Odpoczniesz dopiero po rozbiciu obozu albo w bezpiecznym miejscu.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// PT7/F-80 — baner podróży: „musisz odpocząć / zapada zmierzch". Deterministyczny
// (z travel_plan.interrupt_reason), nie zależy od tego, czy narrator go opisze.
function TravelNotice({ notice }: { notice: TravelNoticeData }) {
  const danger = notice.severity === "danger";
  const Icon = danger ? Warning : MoonStars;
  return (
    <div
      className={
        "mx-auto mb-2 flex max-w-[660px] items-start gap-2.5 rounded-md border px-3.5 py-2.5 " +
        (danger
          ? "border-line-danger bg-danger/[0.08]"
          : "border-line-ember bg-ember/[0.07]")
      }
      role="status"
    >
      <Icon
        weight="fill"
        size={17}
        className={"mt-px shrink-0 " + (danger ? "text-danger" : "text-ember-glow")}
      />
      <div className="min-w-0">
        <div
          className={
            "font-ui text-label font-semibold " +
            (danger ? "text-danger-glow" : "text-ember-glow")
          }
        >
          {notice.title}
        </div>
        <div className="font-serif text-micro leading-relaxed text-text-2">{notice.message}</div>
      </div>
    </div>
  );
}
