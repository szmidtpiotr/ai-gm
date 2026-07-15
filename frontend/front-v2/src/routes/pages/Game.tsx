import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CircleNotch, Hourglass, MoonStars, Path, Warning } from "@phosphor-icons/react";
import {
  useBuildCamp,
  useCampaignDetail,
  useCampaigns,
  useCharacter,
  useLocalMap,
  useResolveSkillTest,
  useRestLong,
  useSubmitTurn,
  useSuggestedActions,
  useTravel,
  useTravelResume,
  useTurnStream,
  useWait,
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
  isVisiblePlayerText,
  normalizeChips,
  readStats,
  readVitals,
  rollFromResult,
  skillTestCard,
  type Chip,
  type LogBlock,
} from "@/lib/game";
import type { RollCardData, SkillTestPending, TurnResponse } from "@/lib/types";
import { NarrationLog } from "@/components/game/NarrationLog";
import { Composer } from "@/components/game/Composer";
import { VitalsRail } from "@/components/game/Vitals";
import { GameRail } from "@/components/game/GameRail";
import { WorldMap } from "@/components/game/WorldMap";
import { LocalMap } from "@/components/game/LocalMap";
import { EndedCampaignScreen } from "@/components/game/outcomes/EndedCampaignScreen";
import { Journal } from "@/components/game/journal/Journal";
import { ShopOverlay } from "@/components/game/ShopOverlay";
import { ServicesOverlay } from "@/components/game/ServicesOverlay";
import { CraftingOverlay } from "@/components/game/CraftingOverlay";
import { CommandPalette } from "@/components/game/CommandPalette";
import { BugReportFab } from "@/components/game/BugReportFab";
import { RecapOverlay } from "@/components/game/RecapOverlay";
import { CharacterSheet } from "@/components/sheet/CharacterSheet";
import { CombatView } from "@/components/game/combat/CombatView";
import { EnemyRevealVisual } from "@/components/game/combat/EnemyRevealVisual";
import { Dice3DOverlay, type DiceJob } from "@/components/game/combat/Dice3DOverlay";
import { DungeonView } from "@/components/game/dungeon/DungeonView";
import { MpGame } from "@/components/game/mp/MpGame";
import { AdvancementScreen } from "@/components/game/outcomes/AdvancementScreen";
import { useCombatState } from "@/hooks/useCombat";
import { useCharacterRecipes } from "@/hooks/useCrafting";
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
  const openServices = useAppStore((s) => s.openServices);
  const openCrafting = useAppStore((s) => s.openCrafting);
  const openAdvancement = useAppStore((s) => s.openAdvancement);
  const openWait = useAppStore((s) => s.openWait);
  const closeWait = useAppStore((s) => s.closeWait);
  const waitOpen = useAppStore((s) => s.waitOpen);
  const setFinishFlow = useAppStore((s) => s.setFinishFlow);

  const gameTab = useAppStore((s) => s.gameTab);
  const setGameTab = useAppStore((s) => s.setGameTab);

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
  const recipesGate = useCharacterRecipes(characterId ?? undefined); // #1375 gating zakładki
  const stream = useTurnStream(campaignId);
  const submit = useSubmitTurn(campaignId);
  // #1299: narracyjny test umiejętności — kość 3D jak w walce (Dice3DOverlay).
  const resolveSkill = useResolveSkillTest(campaignId);
  // F-80 (#1268): mechaniczne akcje po przerwaniu podróży (omijają narratora).
  const travelResume = useTravelResume(campaignId);
  const buildCamp = useBuildCamp(campaignId);
  const restLong = useRestLong(campaignId, characterId, currentUser?.id);
  const waitMutation = useWait(campaignId, characterId, currentUser?.id);
  const travel = useTravel(campaignId);
  const { toast } = useToast();
  // FE9 (#1236): stan walki — poll tylko gdy aktywna. Aktywna → ekran walki.
  const combatState = useCombatState(campaignId);
  const combatSnap = combatState.data?.combat ?? null;
  const activeCombat =
    combatState.data?.active && combatSnap?.status === "active"
      ? combatSnap
      : null;
  // #1348 T4: koniec walki może przyjść pollem (GET /combat zwraca teraz snapshot ended).
  // Trzymaj ekran walki ZAMONTOWANY przez stan ended, aż gracz obsłuży wynik (modal
  // zwycięstwa/lootu/śmierci lub toast). Bez tego przejście active→ended odmontowywało
  // CombatView zanim modal się pokazał → cichy powrót do chatu, zero lootu.
  const [ackCombatId, setAckCombatId] = useState<number | null>(null);
  const endedCombat =
    combatSnap && combatSnap.status === "ended" && combatSnap.id != null && combatSnap.id !== ackCombatId
      ? combatSnap
      : null;
  const combatForView = activeCombat ?? endedCombat;
  // FE15 (#1264): tryb drużynowy → rundy MP zamiast solowego turn-flow (walka MP osobno).
  const isMp = campaign.data?.mode === "multiplayer";
  // FE16 (#1265): tryb lochu → eksploracja kafelkowa (HUD/d-pad/mapa) + walka + boss.
  const isDungeon = campaign.data?.mode === "dungeon";

  // F-77 (#1268): bramka finału. Widoczna gdy cel osiągnięty; w MP tylko gospodarz.
  const finaleAllowed =
    !!campaign.data?.finale_available &&
    (!isMp || campaign.data?.host_user_id == null || campaign.data?.host_user_id === currentUser?.id);

  // #1080 — is this the onboarding tutorial? (flag lives on the list endpoint)
  const isTutorial = !!campaigns.data?.find((c) => c.id === campaignId)?.is_tutorial;

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
  // #1299: kość 3D dla narracyjnego testu umiejętności (ten sam silnik co walka).
  // skillJob steruje overlayem; skillPendingRef trzyma id testu do resolve po animacji.
  const [skillJob, setSkillJob] = useState<DiceJob | null>(null);
  const skillJobSeq = useRef(0);
  const skillPendingRef = useRef<string | null>(null);
  // #1086 port: ulotne bąbelki ukończenia questa/beatu — nie są zapisywane w historii tur.
  const [completionBlocks, setCompletionBlocks] = useState<LogBlock[]>([]);
  const completionSeq = useRef(0);
  // Optimistyczne echo akcji gracza: dymek pojawia się NATYCHMIAST po wysłaniu,
  // nie czeka na odpowiedź LLM (wcześniej znikał aż do narracji GM — a przy teście
  // umiejętności bywał gubiony na dobre). Zdejmowany dopiero, gdy tura utrwali się
  // w strumieniu (dedup po tekście); przy błędzie tury — cofany.
  const [optimistic, setOptimistic] = useState<{ id: number; text: string }[]>([]);
  const optSeq = useRef(0);
  // FAZA ML: mapa lokalna osady. Domyślnie pokazujemy ją w hubie z sub-lokacjami;
  // forceWorldMap = gracz kliknął „Świat" i chce zobaczyć mapę świata.
  const [forceWorldMap, setForceWorldMap] = useState(false);
  const localMap = useLocalMap(campaignId, gameTab === "map");
  // #1309 — użycie przedmiotu-mapy odsłania heksy: PanelInventory przełącza na
  // zakładkę Mapa i ustawia mapReveal; tu wymuszamy mapę ŚWIATA (nie lokalną osadę),
  // by gracz zobaczył wjeżdżające nowe heksy.
  const mapReveal = useAppStore((s) => s.mapReveal);
  // #1196 — „Użyj" mapy skarbu wymusza mapę świata deterministycznie (czytane
  // wprost w renderze, bez wyścigu z efektem forceWorldMap / cache mapy lokalnej).
  const mapView = useAppStore((s) => s.mapView);
  const setMapView = useAppStore((s) => s.setMapView);
  useEffect(() => {
    if (mapReveal) setForceWorldMap(true);
  }, [mapReveal]);
  // Wyjście z mapy zwalnia pin świata — następne otwarcie mapy działa normalnie.
  useEffect(() => {
    if (gameTab !== "map" && mapView === "world") setMapView("auto");
  }, [gameTab, mapView, setMapView]);
  // PM4: wybór trasy (na wprost / traktem) jako modal z 2 przyciskami zamiast
  // pytania tekstem. Wypełniany, gdy tura zwróci suggested_actions type=route_choice.
  const [routeChoice, setRouteChoice] = useState<
    { label: string; action: string; icon?: string }[] | null
  >(null);

  function applyResponse(resp: TurnResponse) {
    // #1292: deterministyczny skrót tekstowy ("zamawiam nocleg" itp.) przechwycony
    // PRZED wysłaniem do LLM — backend nie narrował, nie ma tury do zastosowania,
    // tylko otwórz modal Usług.
    if (resp.open_services) {
      openServices(resp.open_services);
      return;
    }
    // #1338 BL-C3: deterministyczny skrót → otwórz modal Rzemiosła (bez LLM).
    if (resp.open_crafting) {
      openCrafting(resp.open_crafting);
      return;
    }
    // #1299: silnik zdecydował o narracyjnym rzucie — backend zwraca skill_test_pending
    // (proza null). Odpal kość 3D jak w walce; wynik rozwiąże się po animacji (onSkillDiceDone).
    const stp = resp.skill_test_pending as SkillTestPending | null | undefined;
    if (stp?.skill_test_id) {
      const { card, committed } = skillTestCard(stp);
      skillJobSeq.current += 1;
      skillPendingRef.current = stp.skill_test_id;
      // Baner „KRYTYCZNE TRAFIENIE" jest walczny — dla testu zostawiamy tylko poświatę
      // karty (card.crit/fumble), więc job.crit/fumble = false.
      setSkillJob({
        id: skillJobSeq.current,
        notation: "1d20",
        forced: [committed],
        face: committed,
        card,
        actor: "player",
      });
      return;
    }
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
    // #1086 port: dymki ukończenia questa/beatu (nie zapisywane w historii tur).
    // #1379: backend zwraca `system_events` = konwersja pól legacy (beats/quests/
    // items/gold) + nowe komunikaty (XP, strata złota, kondycje, durability, noc…).
    // Gdy pole jest obecne — jest SUPERSETEM, więc renderujemy TYLKO je (inaczej
    // podwójne dymki). Starszy backend bez tego pola → fallback na gałęzie legacy.
    let newBlocks: LogBlock[];
    if (resp.system_events && resp.system_events.length) {
      newBlocks = resp.system_events.map((ev) => ({
        kind: "completion" as const,
        id: `sys-${completionSeq.current++}`,
        text: ev.icon ? `${ev.icon} ${ev.text}` : ev.text,
        tone: ev.tone,
        icon: ev.icon,
      }));
    } else {
      newBlocks = [
        ...(resp.completed_beats ?? []).map((b) => ({
          kind: "completion" as const,
          id: `cmp-${completionSeq.current++}`,
          text: `✓ Cel wykonany: ${b.label ?? b.key}`,
        })),
        ...(resp.completed_quests ?? []).map((q) => ({
          kind: "completion" as const,
          id: `cmp-${completionSeq.current++}`,
          text: q.xp ? `✓ Quest: ${q.title} — +${q.xp} XP` : `✓ Quest: ${q.title}`,
        })),
        // #1312: dostany przedmiot — ten sam zielony dymek co ukończenie beatu/questa.
        ...(resp.granted_items ?? []).map((it) => ({
          kind: "completion" as const,
          id: `cmp-${completionSeq.current++}`,
          text: `🎒 Otrzymano: ${it.label}`,
        })),
        // C12 (#1101): dymki transakcji złotem (SPEND_GOLD success events).
        ...(resp.gold_events ?? []).map((ev) => ({
          kind: "gold" as const,
          id: `gold-${completionSeq.current++}`,
          delta: ev.delta,
          label: ev.label,
        })),
      ];
    }
    // Żyją tylko do końca TEJ tury — trwały zapis jest w Dzienniku (Zadania/Wątki/
    // Kronika), więc nadpisujemy (nie doklejamy), inaczej stary dymek wisi w oknie
    // czatu w nieskończoność, przesuwając się pod każdą kolejną turę.
    setCompletionBlocks(newBlocks);
  }

  function send(text: string) {
    if (!characterId) return;
    // Echo widocznej akcji gracza od razu (pomijamy sentinele/rzuty `__…`/`[…]`).
    const echo = text.trim();
    const optId = isVisiblePlayerText(echo) ? ++optSeq.current : null;
    if (optId !== null) setOptimistic((o) => [...o, { id: optId, text: echo }]);
    submit.mutate(
      { characterId, text },
      {
        onSuccess: applyResponse,
        onError: (err) => {
          if (optId !== null) setOptimistic((o) => o.filter((e) => e.id !== optId));
          submitError(err);
        },
      },
    );
  }

  // #1378: turn submission previously had no onError anywhere — an LLM failure
  // (budget exhausted, timeout, provider down) just left the composer stuck
  // with no feedback. Backend now returns a reason-specific Polish message
  // (see api.ts extractMessage), surfaced here as a toast.
  function submitError(err: unknown) {
    toast(err instanceof Error ? err.message : "Nie udało się wysłać akcji.", "danger");
  }

  // #1299: animacja kości skończona → rozwiąż test na serwerze (autorytatywny
  // committed_d20). Narracja GM wpadnie do logu przez invalidację turn-stream;
  // tu tylko odświeżamy chipy (bramka przewagi po sukcesie Skradania) + lektor.
  function onSkillDiceDone() {
    const skillTestId = skillPendingRef.current;
    const committed = skillJob?.forced?.[0] ?? 10;
    skillPendingRef.current = null;
    setSkillJob(null);
    if (!skillTestId || !characterId) return;
    resolveSkill.mutate(
      { characterId, skillTestId, d20: committed },
      {
        onSuccess: (r) => {
          const gate = r.advantage_gate?.options;
          setChips(normalizeChips(gate && gate.length ? gate : r.suggested_actions));
          if (typeof r.prose === "string" && r.prose.trim()) voice.speak(r.prose);
        },
        onError: (e) =>
          toast(e instanceof Error ? e.message : "Nie udało się rozwiązać testu.", "danger"),
      },
    );
  }

  // #1292: po zamknięciu modala Usług — ukryta tura prosi narratora o krótki opis
  // odbioru (zakup już opłacony mechanicznie w modalu, ta tura tylko narruje).
  const servicesReceiptPending = useAppStore((s) => s.servicesReceiptPending);
  const setServicesReceiptPending = useAppStore((s) => s.setServicesReceiptPending);
  useEffect(() => {
    if (servicesReceiptPending && characterId) {
      submit.mutate({ characterId, text: servicesReceiptPending }, { onSuccess: applyResponse, onError: submitError });
      setServicesReceiptPending(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [servicesReceiptPending, characterId]);

  // Po zamknięciu modalu zwycięstwa — ukryta tura prosi narratora o epilog walki
  // (mechanika już rozliczona przez /combat; bez tej tury po walce panuje cisza).
  const combatEpiloguePending = useAppStore((s) => s.combatEpiloguePending);
  const setCombatEpiloguePending = useAppStore((s) => s.setCombatEpiloguePending);
  useEffect(() => {
    if (combatEpiloguePending && characterId) {
      submit.mutate({ characterId, text: combatEpiloguePending }, { onSuccess: applyResponse, onError: submitError });
      setCombatEpiloguePending(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combatEpiloguePending, characterId]);

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
        onSuccess: (r) => {
          setChips(normalizeChips(r.suggested_actions));
          // Encounter: wznowienie rozpoczęło walkę — przejdź do Opowieści (walka tam),
          // inaczej gracz zostałby na mapie i przegapił rozpoczętą walkę.
          if (r.combat_started) {
            setGameTab("story");
            toast("Spotkanie zagradza drogę — walka!", "danger");
          }
        },
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
    if (act === "WAIT:open") {
      openWait();
      return;
    }
    // #1292: modal Usług — deterministyczny, zero LLM. Klucz lokacji zaszyty w akcji.
    if (act.startsWith("OPEN_SERVICES:")) {
      openServices(act.slice("OPEN_SERVICES:".length));
      return;
    }
    // #1338 BL-C3: modal Rzemiosła — deterministyczny, klucz lokacji w akcji.
    if (act.startsWith("OPEN_CRAFTING:")) {
      openCrafting(act.slice("OPEN_CRAFTING:".length));
      return;
    }
    if (act.startsWith("WAIT:")) {
      const target = act.slice(5); // e.g. "dawn", "next_dawn", "hours:6"
      const hoursMatch = target.match(/^hours:(\d+)$/);
      const params = hoursMatch
        ? { hours: Number(hoursMatch[1]) }
        : { target };
      waitMutation.mutate(params, {
        onSuccess: (r) => {
          toast(`Czas mija — minęło ${r.delta_hours} h. Teraz: ${r.new_clock.display}.`, "success");
        },
        onError: (err: unknown) => {
          const msg = (err as { message?: string })?.message ?? "Błąd czekania";
          if (msg.includes("not_safe_for_rest")) toast("Czekaj w bezpiecznym miejscu (karczma, osada).", "info");
          else if (msg.includes("in_combat")) toast("Nie możesz czekać w trakcie walki.", "danger");
          else toast(msg, "danger");
        },
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
        { onSuccess: applyResponse, onError: submitError },
      );
    }
  }, [characterId, stream.isSuccess, stream.data, submit]);

  const persistedBlocks = useMemo(
    () => buildLog(stream.data?.turns ?? []),
    [stream.data?.turns],
  );
  // Teksty akcji już utrwalone w strumieniu — echo optymistyczne dla nich zdejmujemy,
  // by nie dublować dymka. To, czego backend nie zapisał (np. tor testu umiejętności
  // gubi słowa gracza), zostaje widoczne jako echo.
  const persistedPlayerTexts = useMemo(() => {
    const s = new Set<string>();
    for (const b of persistedBlocks) if (b.kind === "player") s.add(b.text);
    return s;
  }, [persistedBlocks]);
  const shownOptimistic = useMemo(
    () => optimistic.filter((e) => !persistedPlayerTexts.has(e.text)),
    [optimistic, persistedPlayerTexts],
  );
  // Przytnij stan (nie tylko widok), gdy tura się utrwaliła — inaczej tablica rośnie.
  useEffect(() => {
    setOptimistic((o) => {
      const next = o.filter((e) => !persistedPlayerTexts.has(e.text));
      return next.length === o.length ? o : next;
    });
  }, [persistedPlayerTexts]);
  const blocks = useMemo(
    () => [...persistedBlocks, ...completionBlocks],
    [persistedBlocks, completionBlocks],
  );
  // Widok Opowieści: echo akcji gracza dopisane pod narracją (nowa akcja = najniżej).
  const storyBlocks = useMemo<LogBlock[]>(
    () => [
      ...blocks,
      ...shownOptimistic.map((e) => ({ kind: "player" as const, id: `opt-${e.id}`, text: e.text })),
    ],
    [blocks, shownOptimistic],
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
  // #1381 — gdy trwa animacja przeskoku pina na mapie, wstrzymaj modal zasadzki,
  // żeby nie wyskoczył PRZED końcem animacji. WorldMap gasi flagę i unieważnia
  // suggested-actions po animacji → efekt re-uruchamia się i modal pojawia się na czas.
  const travelAnimating = useAppStore((s) => s.travelAnimating);
  useEffect(() => {
    if (!travelNotice) {
      ackInterrupt.current = null;
      return;
    }
    if (travelAnimating) return; // modal poczeka na koniec animacji hop
    const key = `${travelNotice.reason}:${travelNotice.step}`;
    if (ackInterrupt.current === key) return;
    ackInterrupt.current = key;
    setInterruptModal(travelNotice);
  }, [travelNotice, travelAnimating]);
  // WALKA-T1-FIX (#1355): gdy modal zasadzki (reason=encounter Z KONKRETNYM wrogiem)
  // się pojawił, karta „Nieznany napastnik" (EnemyRevealCard) dla walki, która zaraz
  // wystartuje, ma się NIE pokazać (dublet overlayów). Wyliczamy wyciszenie
  // SYNCHRONICZNIE w renderze (useMemo, nie useEffect) — dzięki temu prop jest już
  // PRAWDZIWY przy montowaniu CombatView. #1349 robił to w useEffect rodzica, który
  // odpalał PO efekcie reveal w dziecku (race) → karta zdążyła się pokazać.
  const armedEncounterRef = useRef(false);
  useEffect(() => {
    // Uzbrajamy na obecnym WROGU (travelNotice.enemy), nie na samym reason=encounter —
    // inaczej przy nieznanym wrogu (modal nic nie pokazał) karta byłaby błędnie tłumiona.
    if (
      travelNotice &&
      String(travelNotice.reason).startsWith("encounter") &&
      travelNotice.enemy
    ) {
      armedEncounterRef.current = true;
    }
  }, [travelNotice?.reason, travelNotice?.step, travelNotice?.enemy]);
  useEffect(() => {
    // Reset uzbrojenia po zakończeniu walki (cid→null), by kolejna walka z NARRACJI
    // nie była błędnie wyciszona. Odpala się tylko przy ZMIANIE activeCombat?.id.
    if (!activeCombat?.id) armedEncounterRef.current = false;
  }, [activeCombat?.id]);
  const suppressRevealCombatId = useMemo(() => {
    const cid = activeCombat?.id;
    if (!cid) return null;
    // Uzbrojone w POPRZEDNIM cyklu (modal zasadzki pokazał wroga) — ref jest już truthy
    // zanim CombatView się zamontuje.
    if (armedEncounterRef.current) return cid;
    // Fallback: travelNotice i combat pojawiły się w TYM SAMYM renderze (efekt
    // uzbrajający jeszcze nie zdążył) — czytamy travelNotice wprost.
    if (
      travelNotice &&
      String(travelNotice.reason).startsWith("encounter") &&
      travelNotice.enemy
    ) {
      return cid;
    }
    return null;
  }, [activeCombat?.id, travelNotice]);
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
  // Priorytet: grounded pille z /suggested-actions (deterministyczne, zawsze zgodne
  // z bieżącą lokacją — NPC/wyjścia/podróż/rest/interrupt/route). Dopiero gdy endpoint
  // pusty — pille z submitu/strumienia (LLM bywa niezgodny z lokacją: „kuźnia Brunna"
  // przy Rudniku). suggested-actions jest inwalidowany po każdej turze/podróży.
  const baseChips = fetchedChips.length
    ? fetchedChips
    : chips.length
      ? chips
      : streamChips;
  // #1291 WAIT-4 — dodaj chip Czekaj gdy safe_for_rest i nie ma walki (deterministyczny,
  // nie pochodzi z LLM — zawsze obecny w bezpiecznej lokacji).
  const shownChips = useMemo(() => {
    const safeHere = character.data?.safe_for_rest === true && !activeCombat;
    if (!safeHere) return baseChips;
    const hasWait = baseChips.some((c) => (c.action ?? c.text ?? "").startsWith("WAIT"));
    if (hasWait) return baseChips;
    return [...baseChips, { label: "⏳ Czekaj…", text: "WAIT:open", action: "WAIT:open", enabled: true }];
  }, [baseChips, character.data?.safe_for_rest, activeCombat]);
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

      {/* #1291 WAIT-4: modal wyboru pory czekania. */}
      {waitOpen && (
        <WaitModal
          onPick={(act) => { closeWait(); onChip({ label: "Czekaj", text: act, action: act }, shownChips); }}
          onClose={closeWait}
        />
      )}

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
      <GameMenu finaleAllowed={finaleAllowed} isTutorial={isTutorial} campaignId={campaignId} />
      <FinaleFlow
        campaignId={campaignId!}
        heroId={characterId}
        heroName={character.data?.name ?? "Bohater"}
        heroLevel={vitals.level}
        turnCount={lastTurn || undefined}
      />

      {/* FE12 (#1261): sklep NPC — overlay nad grą, otwierany narracyjnie */}
      <ShopOverlay />

      {/* #1292: modal Usług — deterministyczny (chip "Usługi" / skrót tekstowy), omija LLM */}
      <ServicesOverlay />

      {/* #1338 BL-C3: modal Rzemiosła — deterministyczny (chip "Rzemiosło"), omija LLM */}
      <CraftingOverlay />

      {/* FE14 (#1263): paleta komend (Ctrl+/) · recap przy wejściu · FAB testera */}
      <CommandPalette />
      <RecapOverlay campaignId={campaignId} />
      <BugReportFab campaignId={campaignId} turnNumber={lastTurn || undefined} screen={screenLabel} />

      {/* #1299: kość 3D narracyjnego testu umiejętności — ten sam overlay co walka,
          fixed inset-0 z-50, więc leży nad grą niezależnie od zakładki. */}
      {skillJob && <Dice3DOverlay job={skillJob} onDone={onSkillDiceDone} />}

      {/* Desktop: lewy pionowy rail przełącza Opowieść ↔ panele karty postaci */}
      <GameRail hasMana={vitals.hasMana} hasRecipes={!!recipesGate.data?.has_any} />

      {gameTab === "map" ? (
        // FAZA ML: w osadzie z sub-lokacjami domyślnie mapa lokalna; „Świat"/„Osada"
        // przełącza. F-43 mapa świata + podróż (#1235) — własny nagłówek + cinematyka.
        localMap.data?.has_local_map && !forceWorldMap && mapView !== "world" ? (
          <LocalMap campaignId={campaignId!} onWorld={() => setForceWorldMap(true)} />
        ) : (
          <WorldMap
            campaignId={campaignId!}
            characterId={characterId}
            localAvailable={!!localMap.data?.has_local_map}
            onOpenLocal={() => { setForceWorldMap(false); setMapView("auto"); }}
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
      ) : gameTab === "story" && combatForView ? (
        // FE9 walka (#1236): baner + pasek akcji + reakcja SF10 + kość 3D.
        // #1348: `combatForView` = aktywna LUB świeżo zakończona (do potwierdzenia) walka.
        <CombatView
          campaignId={campaignId!}
          character={character.data}
          combat={combatForView}
          blocks={blocks}
          typing={submit.isPending}
          vitals={vitals}
          stats={stats}
          onSend={send}
          sending={submit.isPending}
          onEnded={(id) => setAckCombatId(id)}
          suppressRevealCombatId={suppressRevealCombatId}
        />
      ) : gameTab === "story" ? (
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex min-h-0 min-w-0 flex-1">
            <div className="min-w-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <NarrationLog
                blocks={storyBlocks}
                pendingRoll={pendingRoll}
                typing={submit.isPending || resolveSkill.isPending}
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
            disabled={submit.isPending || !!skillJob || resolveSkill.isPending}
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
  // Spotkanie w drodze = zasadzka → przycisk WALCZ (startuje walkę); obóz/odpoczynek
  // nie mają sensu pod atakiem. onResume dla encountera inicjuje walkę (backend).
  // WYŁĄCZNIE exact "encounter" (PRZED walką) — "encounter_prompted" to stan PO
  // wygranej walce: normalny układ Kontynuuj/Odpocznij/Rozbij obóz (bez tego modal
  // wyglądał jak nowa zasadzka z jednym przyciskiem „Walcz", który wznawiał podróż).
  const isEncounter = notice.reason === "encounter";
  // Odpoczynek możliwy tylko w bezpiecznym miejscu (karczma/osada) lub po obozie.
  const canRest = !isEncounter && (alreadyCamped || notice.can_rest === true);
  // Obóz oferujemy, gdy tu NIE bezpiecznie i jeszcze nie rozbity (to on odblokuje rest).
  const canCamp = !isEncounter && !alreadyCamped && !canRest;
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
        {/* WALKA-T1 (#1349): zasadzka z danymi wroga → obrazek + badge zagrożenia
            (współdzielony z EnemyRevealCard). Karta „Nieznany napastnik" wyciszona (Game). */}
        {notice.enemy && (
          <EnemyRevealVisual
            name={notice.enemy.label || notice.enemy.key}
            imageUrl={notice.enemy.image_url}
            threat={notice.relative_threat ?? null}
            restCount={Math.max(0, (notice.enemy.count ?? 1) - 1)}
          />
        )}
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
              disabled={!isEncounter && !notice.can_resume}
              onClick={onResume}
              className="flex items-center justify-center gap-2 rounded-md px-3 py-3 font-ui text-body font-semibold text-white disabled:opacity-40 disabled:shadow-none"
              style={{
                background: isEncounter
                  ? "linear-gradient(135deg, #c0392b, var(--danger, #e8604f))"
                  : "linear-gradient(135deg, #d1602c, var(--ember))",
                boxShadow: isEncounter
                  ? "0 0 16px rgba(232,96,79,.4)"
                  : "0 0 16px rgba(255,122,61,.35)",
              }}
              title={!isEncounter && !notice.can_resume ? "Padłeś ze zmęczenia — najpierw odpocznij." : undefined}
            >
              {isEncounter ? "⚔ Walcz" : "🧭 Kontynuuj podróż"}
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

// #1291 WAIT-4 — modal wyboru pory czekania.
const WAIT_OPTIONS = [
  { label: "Do świtu", action: "WAIT:next_dawn", icon: "🌅" },
  { label: "Do południa", action: "WAIT:day", icon: "☀️" },
  { label: "Do zmroku", action: "WAIT:dusk", icon: "🌇" },
  { label: "Do nocy", action: "WAIT:next_night", icon: "🌙" },
  { label: "2 godziny", action: "WAIT:hours:2", icon: "⌛" },
  { label: "6 godzin", action: "WAIT:hours:6", icon: "⌛" },
];

function WaitModal({ onPick, onClose }: { onPick: (act: string) => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[58] flex items-center justify-center p-6" data-testid="wait-modal">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-[2] w-full max-w-[380px] overflow-hidden rounded-xl border border-line bg-surface shadow-2xl">
        <div className="flex items-center gap-3 border-b border-line bg-surface px-5 py-4">
          <Hourglass weight="fill" size={22} className="text-ember-glow" />
          <div className="min-w-0">
            <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.18em] text-text-3">
              Czekanie
            </div>
            <div className="font-serif text-title font-semibold text-text">Jak długo czekasz?</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 p-4">
          {WAIT_OPTIONS.map((o) => (
            <button
              key={o.action}
              type="button"
              onClick={() => onPick(o.action)}
              className="flex items-center gap-2 rounded-md border border-line bg-bg px-3 py-2.5 font-ui text-body font-semibold text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
            >
              <span aria-hidden>{o.icon}</span>
              {o.label}
            </button>
          ))}
        </div>
        <div className="border-t border-line px-5 pb-4 pt-2 text-center font-ui text-micro text-text-3">
          Czekanie nie leczy HP. Wymaga bezpiecznej lokacji.
        </div>
      </div>
    </div>
  );
}
