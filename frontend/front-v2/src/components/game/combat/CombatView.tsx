// FE9 walka (#1236) — orkiestrator ekranu walki. Spina baner (F-53) + log z kartami
// rzutów (F-52) + pasek akcji (F-24) + composer prozy + overlaye: arkusz czarów (F-26),
// reakcja SF10, kość 3D (F-70). Pętla: akcja gracza → rzut 3D → wynik; tura wroga → SF10.
//
// Model wierny front/combat_ui.js: poll stanu (useCombatState, tylko gdy aktywna),
// auto-driver tury wroga, okno reakcji wstrzymuje pętlę, combat_state ze świeżej mutacji
// od razu ląduje w cache (setQueryData) → UI nie czeka na kolejny poll.
import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import type { CombatState, CharacterDetail, DefenseReaction } from "@/lib/types";
import type { LogBlock } from "@/lib/game";
import type { Vitals } from "@/lib/game";
import {
  readCombat,
  livingEnemies,
  rollFromPlayerAttack,
  rollFromEnemyAttack,
  rollFromEnemyZoneChange,
  buildCombatEpilogueText,
  rollFromReaction,
  toHitStageCard,
} from "@/lib/combat";
import type { RollCardData } from "@/lib/types";
import { useAppStore } from "@/store/appStore";
import {
  useCombatState,
  useResolveAttack,
  useZoneChange,
  useFlee,
  useEnemyTurn,
  useResolveReaction,
} from "@/hooks/useCombat";
import { useSpells, useSpellCatalog } from "@/hooks/useSheetData";
import { canRaceLearnSpell } from "@/lib/spells";
import { NarrationLog } from "../NarrationLog";
import { Composer } from "../Composer";
import { VitalsRail } from "../Vitals";
import { CombatBanner } from "./CombatBanner";
import { CombatActionBar } from "./CombatActionBar";
import { ActionSheet, type PotionAction, type SheetMode, type SpellAction } from "./ActionSheet";
import { useInventory, useUseItem } from "@/hooks/useSheetData";
import { ReactionModal, type ReactionChoice, type ReactionData } from "./ReactionModal";
import { Dice3DOverlay, type DiceJob } from "./Dice3DOverlay";
import { EnemyRevealCard } from "./EnemyRevealCard";
import { useEnemyReveal } from "./useEnemyReveal";
import { InitiativeCard } from "./InitiativeCard";
import { useInitiativeCard } from "./useInitiativeCard";
import { CombatOutcomes } from "../outcomes/CombatOutcomes";

export function CombatView({
  campaignId,
  character,
  combat,
  blocks,
  typing,
  vitals,
  stats,
  onSend,
  sending,
  dungeon = false,
  onDungeonDeath,
  onEnded,
  suppressRevealCombatId = null,
}: {
  campaignId: number;
  character: CharacterDetail | undefined;
  combat: CombatState; // aktywny LUB świeżo zakończony snapshot (#1348: Game trzyma zamontowane do ack)
  blocks: LogBlock[];
  typing: boolean;
  vitals: Vitals;
  stats: Array<{ k: string; v: number }>;
  onSend: (text: string) => void;
  sending: boolean;
  // FE16 (#1265): w lochu śmierć = przywrócenie punktu kontrolnego, nie ekran śmierci.
  dungeon?: boolean;
  onDungeonDeath?: () => void;
  // #1348 T4: sygnał do Game.tsx że gracz obsłużył koniec walki (modal zamknięty /
  // toast pokazany) → dopiero teraz rodzic może odmontować ekran walki. Bez tego
  // przejście active→ended odmontowywało CombatView ZANIM modal wyniku zdążył się pokazać.
  onEnded?: (combatId: number) => void;
  // WALKA-T1 (#1349): id walki, dla której karta pojawienia wroga (EnemyRevealCard)
  // ma być wyciszona — bo modal zasadzki w drodze już pokazał wroga (dedup overlayów).
  suppressRevealCombatId?: number | null;
}) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const characterId = character?.id;
  const showPlayerDice = useAppStore((s) => s.gamePrefShowPlayerDice);
  const showEnemyDice  = useAppStore((s) => s.gamePrefShowEnemyDice);
  const setCombatEpiloguePending = useAppStore((s) => s.setCombatEpiloguePending);

  // Query pollowany co 2s (tylko gdy aktywna) — Game.tsx już go trzyma, tu współdzielony.
  const combatQ = useCombatState(campaignId);
  const live = combatQ.data?.combat ?? combat;

  // Zamrożenie WYŚWIETLANEGO HP na czas animacji kości: cache trzyma świeży stan
  // (logika tury, poll), ale banner + rail pokazują HP sprzed ciosu, aż do modalu
  // obrażeń. Snapshot = mapa id→hp_current sprzed mutacji; zwalniany po ostatnim etapie.
  const [hpFreeze, setHpFreeze] = useState<Map<string, number> | null>(null);
  const view = useMemo(() => {
    let cs = live;
    if (cs && hpFreeze) {
      cs = {
        ...cs,
        combatants: (cs.combatants ?? []).map((c) =>
          c?.id != null && hpFreeze.has(String(c.id))
            ? { ...c, hp_current: hpFreeze.get(String(c.id))! }
            : c,
        ),
      };
    }
    return readCombat(cs);
  }, [live, hpFreeze]);

  // Snapshot HP z aktualnego cache (PRZED mutacją) — do zamrożenia wyświetlania.
  function snapshotHp(): Map<string, number> {
    const cs =
      qc.getQueryData<{ combat?: CombatState }>(["combat", campaignId])?.combat ?? live;
    const m = new Map<string, number>();
    for (const c of cs?.combatants ?? []) {
      if (c?.id != null) m.set(String(c.id), Number(c.hp_current ?? 0));
    }
    return m;
  }

  // HP na pasku żywotności (prawy rail) MUSI zgadzać się z banerem walki: podczas
  // walki źródłem prawdy jest combatant (sheet_json bywa nieodświeżony do końca
  // walki). Bez tego rail pokazywał pełne HP mimo obrażeń w walce (rozjazd).
  const combatVitals = useMemo(() => {
    const p = view?.player;
    if (!p || typeof p.hp_current !== "number") return vitals;
    return { ...vitals, hp: p.hp_current, maxHp: p.hp_max ?? vitals.maxHp };
  }, [view?.player, vitals]);

  const attack = useResolveAttack(campaignId);
  const zoneChange = useZoneChange(campaignId);
  const flee = useFlee(campaignId);
  const enemyTurn = useEnemyTurn(campaignId);
  const reactionMut = useResolveReaction(campaignId);
  // Mikstury w arkuszu czarów: zużywalne z plecaka (can_use), bez komponentów
  // rzemieślniczych. Użycie NIE zjada tury — parytet z zakładką Ekwipunek.
  const inventory = useInventory(characterId);
  const useItem = useUseItem(characterId);
  const potionActions: PotionAction[] = useMemo(
    () =>
      (inventory.data ?? [])
        .filter(
          (i) =>
            i.can_use && i.item_type === "consumable" && i.quantity > 0 && !i.is_component,
        )
        .map((i) => ({ id: i.id, label: i.label, quantity: i.quantity })),
    [inventory.data],
  );

  async function doUsePotion(inventoryId: number, label: string) {
    setSheet(null);
    setBusy(true);
    try {
      await useItem.mutateAsync(inventoryId);
      // HP z mikstury musi dojechać do banera walki (combatant hp_current jest
      // źródłem prawdy w walce — loot_service synchronizuje, my odświeżamy odczyt).
      qc.invalidateQueries({ queryKey: ["combat", campaignId] });
      toast(`${label} — użyto.`, "success");
    } catch {
      toast("Nie udało się użyć przedmiotu.", "danger");
    } finally {
      setBusy(false);
    }
  }

  // Lista czarów bojowych (znane × katalog), koszt/ranga/afford.
  const spells = useSpells(characterId);
  const catalog = useSpellCatalog(vitals.hasMana);
  const spellActions: SpellAction[] = useMemo(() => {
    const known = new Map((spells.data ?? []).map((k) => [k.spell_key, k]));
    return (catalog.data ?? [])
      .filter((c) => known.has(c.key))
      // #1372 — krasnolud rzuca wyłącznie Rdzeń-magię; ludzkie czary z legacy-grantów
      // (złe dane sprzed race-gate) nie mogą wpaść do arkusza walki. Lustro sheetu.
      .filter((c) => canRaceLearnSpell(character?.race, c.race_lock))
      .map((c) => {
        const k = known.get(c.key)!;
        return {
          key: c.key,
          label: c.label,
          mana_cost: c.mana_cost,
          rank: k.rank || 1,
          damage_die: c.damage_die,
          heal_die: c.heal_die,
          spell_type: c.spell_type,
          // WALKA-T3 (#1353): opis czaru dojeżdża do sheetu (dotąd wycinany).
          description: c.description ?? null,
          affordable: vitals.mana >= c.mana_cost,
        };
      })
      .sort((a, b) => a.mana_cost - b.mana_cost);
  }, [spells.data, catalog.data, vitals.mana, character?.race]);

  // ── stan UI walki ──
  const [rolls, setRolls] = useState<RollCardData[]>([]);
  const [diceJob, setDiceJob] = useState<DiceJob | null>(null);
  const [reaction, setReaction] = useState<ReactionData | null>(null);
  const [sheet, setSheet] = useState<SheetMode | null>(null);
  const [targetId, setTargetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // FE10 (#1237): modal wyniku walki (victory/player_dead) + akumulatory nagród.
  const [outcome, setOutcome] = useState<{ reason: string; combat: CombatState } | null>(null);
  const jobSeq = useRef(0);
  const pendingDmgStageRef = useRef<DiceJob | null>(null);
  const pendingReactionRef = useRef<ReactionData | null>(null);
  // Kolejne okno reakcji (multiattack) do otwarcia PO animacji testu uniku/bloku.
  const pendingReactionNextRef = useRef<ReactionData | null>(null);
  const enemyTurnRef = useRef(false);
  // Race modalu końca walki: onSuccess mutacji wpisuje status=ended do cache ZANIM
  // .then ustawi diceJob — efekt końca potrafił odpalić w tym oknie (modal nad
  // kręcącymi się kośćmi). Ref ustawiany SYNCHRONICZNIE przed mutateAsync, gdy
  // wiemy że animacja nastąpi; czyszczony na każdej ścieżce bez kości oraz w
  // finalnym onDiceDone. Efekt końca czyta go obok diceJob/reaction.
  const diceIncomingRef = useRef(false);
  const endedRef = useRef(false);
  const goldAccumRef = useRef(0);
  const xpAccumRef = useRef(0);

  // Karta pojawienia wroga: pierwszy render aktywnej walki danego combat_id → odsłoń
  // portret + wskaźnik zagrożenia. Dismiss → normalny widok. Once-per-combat_id.
  // Logika w useEnemyReveal (testowalna — regresja race'u #1355).
  const { reveal, dismissReveal } = useEnemyReveal(live, suppressRevealCombatId);

  // WALKA-T5-FIX-a (#1356): karta inicjatywy na starcie walki — oba rzuty + kto zaczyna.
  // Latch once-per-combat_id; pokazujemy PO karcie pojawienia wroga (dopiero gdy reveal
  // zamknięty), by dwa overlaye się nie nakładały. Zasadzka (suppressReveal) → od razu.
  const { initiative, dismissInitiative } = useInitiativeCard(live);

  // Cel: trzymaj się żywego wroga; przeskocz na kolejnego po zabiciu.
  useEffect(() => {
    if (!view) return;
    const living = livingEnemies(view);
    if (!living.length) return;
    const stillAlive = targetId && living.some((e) => String(e.id) === targetId);
    if (!stillAlive) setTargetId(String(living[0].id));
  }, [view, targetId]);

  const selectedTarget = useMemo(() => {
    if (!view) return null;
    return livingEnemies(view).find((e) => String(e.id) === targetId) ?? null;
  }, [view, targetId]);

  const playerZone = (view?.player?.zone === "ranged" ? "ranged" : "engaged") as
    | "engaged"
    | "ranged";
  const canAct = !!view?.isPlayerTurn && !busy && !diceJob && !reaction && view.status === "active";

  function pushCombatState(cs: CombatState | null | undefined) {
    if (cs) {
      qc.setQueryData(["combat", campaignId], {
        active: cs.status === "active",
        combat: cs,
      });
    }
    qc.invalidateQueries({ queryKey: ["character"] });
  }

  // ── akcja gracza: atak / czar → rzut 3D → karta ──
  async function doAttack(spellKey?: string, title?: string) {
    if (!view) return;
    const target = selectedTarget ?? livingEnemies(view)[0];
    if (!target) return;
    setSheet(null);
    setBusy(true);
    // Zamroź wyświetlane HP zanim mutacja wpisze nowy stan do cache (onSuccess) —
    // HP na pasku/liczbach zmieni się dopiero po modalu obrażeń.
    if (showPlayerDice) {
      setHpFreeze(snapshotHp());
      diceIncomingRef.current = true; // gate modalu końca — PRZED wpisem ended do cache
    }
    // Pre-roll d20 po stronie klienta (parytet z front/: /api/gm/dice) — kość 3D
    // ląduje na tej samej wartości, którą backend liczy do trafienia (raw_d20).
    const d20 = 1 + Math.floor(Math.random() * 20);
    try {
      const r = await attack.mutateAsync({
        raw_d20: d20,
        enemy_key: target.enemy_key ?? null,
        target_id: String(target.id),
        spell_key: spellKey ?? null,
      });
      if (r.blocked) {
        toast(
          r.mana_insufficient
            ? "Za mało many na ten czar."
            : r.block_reason === "out_of_range"
              ? "Cel poza zasięgiem — zbliż się lub użyj czaru dystansowego."
              : "Akcja zablokowana.",
          "danger",
        );
        setHpFreeze(null);
        diceIncomingRef.current = false;
        setBusy(false);
        return; // tura NIE skonsumowana
      }
      // FE10: zbieraj nagrody z zabójczych ciosów (złoto/XP) na potrzeby modalu końca.
      const aoeGold = (r.aoe_hits ?? []).reduce((s, h) => s + (Number(h.gold_drop) || 0), 0);
      goldAccumRef.current += (Number(r.gold_drop) || 0) + aoeGold;
      xpAccumRef.current += Number(r.xp_granted) || 0;
      const face = Number(r.player_raw_d20 ?? d20);
      const card = rollFromPlayerAttack(
        r,
        title ?? (spellKey ? `${title ?? "CZAR"}` : "ATAK"),
      );
      // combat_state już w cache (mutacja onSuccess) — tura wroga odpali po zamknięciu kości.
      pushCombatState(r.combat_state);
      if (showPlayerDice) {
        // Czar leczący: brak testu trafienia (auto-sukces, backend nie rzuca d20) —
        // animuj od razu kość leczenia (np. 1d8) lądującą na wyniku z backendu.
        const healDie = r.heal_die ?? r.damage_die;
        if (r.spell_type === "heal" && r.heal_rolls?.length && healDie) {
          pendingDmgStageRef.current = null;
          jobSeq.current += 1;
          setDiceJob({
            id: jobSeq.current,
            notation: healDie,
            forced: r.heal_rolls,
            face: r.heal_rolls[0] ?? 1,
            card,
            actor: "player",
            stage: "damage",
          });
          return;
        }
        // Kość obrażeń (k6/k8…) jako drugi etap po d20.
        if (r.hit && !r.dodged && r.damage_rolls?.length && r.damage_die) {
          jobSeq.current += 1;
          pendingDmgStageRef.current = {
            id: jobSeq.current,
            notation: r.damage_die,
            forced: r.damage_rolls,
            face: r.damage_rolls[0] ?? 1,
            card,
            actor: "player",
            stage: "damage",
          };
        } else {
          pendingDmgStageRef.current = null;
        }
        jobSeq.current += 1;
        setDiceJob({
          id: jobSeq.current,
          notation: "1d20",
          forced: [face],
          face,
          // Etap d20 nie zdradza obrażeń — pełna karta dopiero po kości obrażeń.
          card: pendingDmgStageRef.current ? toHitStageCard(card, true) : card,
          actor: "player",
          stage: "attack",
          crit: !!r.player_nat20,
          fumble: !!r.player_nat1,
        });
      } else {
        setRolls((p) => [...p, card]);
        setBusy(false);
      }
    } catch {
      toast("Błąd akcji.", "danger");
      setHpFreeze(null);
      diceIncomingRef.current = false;
      setBusy(false);
    }
  }

  function onDiceDone() {
    // Sprawdź czy jest zakolejkowany etap kości obrażeń (tylko bez reakcji).
    const dmgStage = pendingDmgStageRef.current;
    if (dmgStage) {
      pendingDmgStageRef.current = null;
      setDiceJob(dmgStage);
      return; // karta trafi do rolls po zakończeniu etapu obrażeń
    }
    // Sprawdź czy po animacji d20 wroga czeka okno reakcji (SF10 + showEnemyDice).
    const pendingReaction = pendingReactionRef.current;
    if (pendingReaction) {
      pendingReactionRef.current = null;
      diceIncomingRef.current = false; // dalej gate'uje otwarte okno reakcji
      if (diceJob) setRolls((p) => [...p, diceJob.card]);
      setDiceJob(null);
      // Okno reakcji: HP jeszcze nietknięte (dmg pending) — zwolnij zamrożenie,
      // rozliczenie obrażeń nastąpi w resolve_reaction.
      setHpFreeze(null);
      setReaction(pendingReaction);
      return;
    }
    if (diceJob) setRolls((p) => [...p, diceJob.card]);
    setDiceJob(null);
    diceIncomingRef.current = false; // sekwencja kości domknięta — modal końca może wejść
    // Ostatni etap kości — teraz odsłoń realne HP (po modalu obrażeń).
    setHpFreeze(null);
    // Po animacji testu uniku/bloku — otwórz kolejne okno reakcji (multiattack).
    const nextReact = pendingReactionNextRef.current;
    if (nextReact) {
      pendingReactionNextRef.current = null;
      setReaction(nextReact);
    }
    // busy był true tylko dla tury gracza
    if (!diceJob || diceJob.actor !== "enemy") setBusy(false);
  }

  async function doMove() {
    setSheet(null);
    setBusy(true);
    try {
      const r = await zoneChange.mutateAsync();
      pushCombatState(r.combat_state);
    } catch {
      toast("Nie udało się zmienić dystansu.", "danger");
    } finally {
      setBusy(false);
    }
  }

  async function doFlee() {
    setBusy(true);
    try {
      const r = await flee.mutateAsync();
      pushCombatState(r.combat_state);
      if (r.fled) toast("Uciekłeś z walki.", "info");
    } catch {
      toast("Ucieczka się nie udała.", "danger");
    } finally {
      setBusy(false);
    }
  }

  async function doDeclare(rt: DefenseReaction) {
    setSheet(null);
    try {
      await import("@/lib/api").then(({ apiFetch }) =>
        apiFetch(`/campaigns/${campaignId}/combat/declare-reaction`, {
          method: "POST",
          body: { reaction_type: rt },
        }),
      );
      const label =
        rt === "dodge"
          ? "Unik"
          : rt === "shield_block"
            ? "Blok"
            : rt === "arcane_ward"
              ? "Arkanowa Bariera"
              : "Tarcza Many";
      toast(`${label} zadeklarowana.`, "success");
    } catch {
      toast("Nie można teraz zadeklarować reakcji.", "danger");
    }
  }

  // ── auto-driver tury wroga (parytet z pollCombatState → handleEnemyTurn) ──
  useEffect(() => {
    if (!view || view.status !== "active") return;
    if (view.isPlayerTurn) return;
    if (busy || diceJob || reaction || enemyTurnRef.current) return;
    enemyTurnRef.current = true;
    // Zamroź HP zanim tura wroga wpisze nowy stan do cache — pasek/liczby
    // zmienią się dopiero po modalu obrażeń wroga.
    if (showEnemyDice) {
      setHpFreeze(snapshotHp());
      diceIncomingRef.current = true; // gate modalu końca — PRZED wpisem ended do cache
    }
    enemyTurn
      .mutateAsync()
      .then((r) => {
        pushCombatState(r.combat_state);
        // Doskok/odskok melee — tura wroga BEZ ataku i bez rzutu: karta ruchu
        // zamiast fantomowego „ATAK — PUDŁO", bez animacji kości.
        if (r.zone_change) {
          pendingReactionRef.current = null;
          pendingDmgStageRef.current = null;
          diceIncomingRef.current = false;
          setHpFreeze(null);
          setRolls((p) => [...p, rollFromEnemyZoneChange(r)]);
          return;
        }
        const d20 = Number(r.raw_d20 ?? 0);
        if (r.reaction_window) {
          // SF10: okno reakcji — ale najpierw pokazujemy animację d20 wroga (gdy włączona),
          // a dopiero po jej zakończeniu otwieramy modal. Bez animacji: od razu modal.
          const reactionData: ReactionData = {
            enemyName: r.enemy_name ?? "Wróg",
            options: r.reaction_options ?? [],
            optionsDetailed: r.reaction_options_detailed, // #1359: wyszarzanie niedostępnych
            attackRoll: r.attack_roll ?? null,
            playerDefense: view.player?.defense ?? null,
          };
          if (showEnemyDice) {
            pendingReactionRef.current = reactionData;
            pendingDmgStageRef.current = null;
            jobSeq.current += 1;
            setDiceJob({
              id: jobSeq.current,
              notation: "1d20",
              forced: [d20],
              face: d20,
              card: rollFromEnemyAttack(r),
              actor: "enemy",
              stage: "attack",
              crit: d20 === 20,
              fumble: d20 === 1,
            });
          } else {
            diceIncomingRef.current = false; // gate przejmuje otwarte okno reakcji
            setReaction(reactionData);
          }
        } else {
          const enemyCard = rollFromEnemyAttack(r);
          pendingReactionRef.current = null;
          if (showEnemyDice) {
            // Kość obrażeń wroga jako drugi etap po d20.
            if (r.hit && !r.dodged && r.damage_rolls?.length && r.damage_die) {
              jobSeq.current += 1;
              pendingDmgStageRef.current = {
                id: jobSeq.current,
                notation: r.damage_die,
                forced: r.damage_rolls,
                face: r.damage_rolls[0] ?? 1,
                card: enemyCard,
                actor: "enemy",
                stage: "damage",
              };
            } else {
              pendingDmgStageRef.current = null;
            }
            jobSeq.current += 1;
            setDiceJob({
              id: jobSeq.current,
              notation: "1d20",
              forced: [d20],
              face: d20,
              // Etap d20 nie zdradza obrażeń — pełna karta dopiero po kości obrażeń.
              card: pendingDmgStageRef.current ? toHitStageCard(enemyCard, true) : enemyCard,
              actor: "enemy",
              stage: "attack",
              crit: d20 === 20,
              fumble: d20 === 1,
            });
          } else {
            setRolls((p) => [...p, enemyCard]);
          }
        }
      })
      .catch(() => {
        // #1348 T4: nie połykaj błędu tury wroga po cichu. Zwolnij zamrożenie HP,
        // pokaż komunikat i wymuś ponowny odczyt stanu (poll). Błąd/undefined NIE może
        // wyzerować activeCombat — trzymamy ostatni znany snapshot (react-query keep data).
        diceIncomingRef.current = false;
        setHpFreeze(null);
        toast("Błąd tury wroga — ponawiam odczyt stanu walki.", "danger");
        qc.invalidateQueries({ queryKey: ["combat", campaignId] });
      })
      .finally(() => {
        enemyTurnRef.current = false;
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view?.currentTurn, view?.isPlayerTurn, view?.status, busy, diceJob, reaction]);

  // ── reakcja SF10 ──
  async function onReaction(choice: ReactionChoice, auto = false) {
    // Unik/blok = test umiejętności gracza → animuj rzut jak atak (showPlayerDice).
    // „take" nie ma rzutu. Zamroź HP na czas animacji (dmg rozliczy resolve_reaction).
    const willAnimate = showPlayerDice && choice !== "take";
    if (willAnimate) {
      setHpFreeze(snapshotHp());
      diceIncomingRef.current = true; // gate modalu końca (śmierć po reakcji) — przed mutacją
    }
    // #1358: timeout okna (8s) nie może być cichy — jawny komunikat zamiast samego spadku HP.
    if (auto) toast("Czas minął — przyjąłeś cios.", "danger");
    try {
      const r = await reactionMut.mutateAsync(choice);
      pushCombatState(r.combat_state);
      setReaction(null);
      const card = rollFromReaction(r, choice, auto);
      // multiattack: kolejny cios może od razu ponownie otworzyć okno
      const nextWindow: ReactionData | null = r.reaction_window
        ? {
            enemyName: r.enemy_name ?? "Wróg",
            options: r.reaction_options ?? [],
            optionsDetailed: r.reaction_options_detailed, // #1359
            attackRoll: r.attack_roll ?? null,
            playerDefense: view?.player?.defense ?? null,
          }
        : null;
      const react = r.reaction ?? {};
      const testD20 = Number(react.d20 ?? NaN);
      // Animuj tylko gdy reakcja realnie rzuciła kością (available + jest d20).
      if (willAnimate && react.available && Number.isFinite(testD20)) {
        pendingReactionNextRef.current = nextWindow;
        jobSeq.current += 1;
        setDiceJob({
          id: jobSeq.current,
          notation: "1d20",
          forced: [testD20],
          face: testD20,
          card, // karta wyniku reakcji odsłoni się po animacji testu
          actor: "player",
          stage: choice === "dodge" ? "dodge" : "block",
        });
        return; // karta + realne HP po zakończeniu animacji (onDiceDone)
      }
      // Bez animacji (take / kość wyłączona / reakcja niedostępna) — wynik od razu.
      diceIncomingRef.current = false;
      setHpFreeze(null);
      setRolls((p) => [...p, card]);
      if (nextWindow) setReaction(nextWindow);
    } catch {
      diceIncomingRef.current = false;
      setHpFreeze(null);
      setReaction(null);
      toast("Błąd reakcji.", "danger");
    }
  }

  // ── koniec walki: modale wyników (F-27..F-32) lub toast (ucieczka) ──
  useEffect(() => {
    // Stan „ended" ląduje w cache od razu po zabójczym ciosie, gdy kości 3D
    // (d20 + kość obrażeń) jeszcze się kręcą — modal wyniku czeka aż animacje
    // i okno reakcji się domkną (diceJob → null w onDiceDone), inaczej zasłania
    // ostatni rzut i „obliczenia pod spodem".
    // diceIncomingRef domyka RACE: onSuccess mutacji wpisuje ended do cache i ten
    // efekt potrafi odpalić ZANIM .then zdąży ustawić diceJob — ref jest ustawiany
    // synchronicznie przed mutateAsync, więc gate trzyma także w tym oknie.
    if (diceJob || reaction || diceIncomingRef.current) return;
    if (view?.status === "ended" && !endedRef.current) {
      endedRef.current = true;
      const reason = view.endedReason ?? "";
      // FE16 (#1265): śmierć w lochu → przywrócenie punktu kontrolnego (nie ekran śmierci).
      const endedId = Number(live?.id ?? combat?.id ?? 0);
      if (reason === "player_dead" && dungeon && onDungeonDeath) {
        onDungeonDeath();
        onEnded?.(endedId); // brak modalu w lochu → od razu zwolnij ekran walki
      } else if (reason === "victory" || reason === "player_dead") {
        // victory / player_dead → pełny modal (CombatOutcomes); fled → tylko toast.
        // NIE wołamy onEnded tutaj — dopiero po zamknięciu modalu (onDismiss), żeby
        // rodzic nie odmontował ekranu walki zanim gracz zobaczy wynik (#1348).
        setOutcome({ reason, combat: live });
      } else {
        toast(reason === "fled" ? "Walka zakończona — ucieczka." : "Walka zakończona.", "info");
        onEnded?.(endedId); // toast-only koniec → zwolnij ekran walki od razu
      }
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
    }
    if (view?.status === "active") {
      endedRef.current = false;
      goldAccumRef.current = 0;
      xpAccumRef.current = 0;
      setOutcome(null);
    }
  }, [view?.status, view?.endedReason, campaignId, qc, toast, live, diceJob, reaction]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {view && (
        <CombatBanner
          view={view}
          selectedTargetId={targetId}
          onSelectTarget={setTargetId}
        />
      )}

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <NarrationLog
            blocks={blocks}
            combatRolls={rolls}
            typing={typing}
            heroName={character?.name}
          />
        </div>
        <VitalsRail v={combatVitals} stats={stats} locationLabel={character?.current_location_label} />
      </div>

      {/* pasek akcji walki + composer prozy (proza działa równolegle) */}
      <div className="shrink-0 border-t border-line bg-surface">
        <CombatActionBar
          playerZone={playerZone}
          hasMana={vitals.hasMana}
          disabled={!canAct}
          onAttack={() => doAttack()}
          onSpell={() => setSheet("spell")}
          onMove={doMove}
          onDefense={() => setSheet("defense")}
          onFlee={doFlee}
        />
        <Composer onSend={onSend} disabled={sending} chips={[]} onChip={() => {}} />
      </div>

      {/* overlaye */}
      {sheet && view && (
        <ActionSheet
          initialMode={sheet}
          spells={spellActions}
          mana={vitals.mana}
          maxMana={vitals.maxMana}
          playerZone={playerZone}
          targetName={selectedTarget?.name ?? null}
          busy={!canAct}
          onAttack={() => doAttack()}
          onCast={(key) => {
            const sp = spellActions.find((s) => s.key === key);
            doAttack(key, (sp?.label ?? "CZAR").toUpperCase());
          }}
          onMove={doMove}
          onDeclare={doDeclare}
          defenseOptions={view.defenseOptions}
          defenseOptionsDetailed={view.defenseOptionsDetailed}
          potions={potionActions}
          onUsePotion={doUsePotion}
          onClose={() => setSheet(null)}
        />
      )}

      {/* BL-A7 (#1344): karta pojawienia wroga (obrazek + nazwa + wskaźnik zagrożenia) */}
      {reveal && (
        <EnemyRevealCard
          enemies={reveal}
          threat={view?.relativeThreat ?? null}
          onClose={dismissReveal}
        />
      )}

      {/* WALKA-T5-FIX-a (#1356): karta inicjatywy — dopiero po zamknięciu karty pojawienia wroga */}
      {initiative && !reveal && (
        <InitiativeCard data={initiative} onClose={dismissInitiative} />
      )}

      {reaction && <ReactionModal data={reaction} onChoose={onReaction} />}

      {diceJob && <Dice3DOverlay job={diceJob} onDone={onDiceDone} />}

      {/* FE10 (#1237): modale wyników walki — koniec+łup / śmierć / loch / drop */}
      {outcome && (
        <CombatOutcomes
          campaignId={campaignId}
          heroId={character?.id}
          character={character}
          reason={outcome.reason}
          endedCombat={outcome.combat}
          xpGain={xpAccumRef.current}
          goldGain={goldAccumRef.current}
          onDismiss={() => {
            setOutcome(null);
            // Zwycięstwo poza lochem → ukryta tura-epilog: narrator opisuje pokłosie
            // walki (bez niej gra milknie po modalu, jakby walka się zbugowała).
            // Loch ma własny flow (drzwi/boss), śmierć — ekran śmierci.
            if (outcome.reason === "victory" && !dungeon) {
              const foes = (outcome.combat?.combatants ?? [])
                .filter((c) => c.type === "enemy")
                .map((c) => String(c.name || c.enemy_key || "").trim());
              setCombatEpiloguePending(buildCombatEpilogueText(foes));
            }
            // #1348 T4: teraz — po zamknięciu modalu wyniku — pozwól Game.tsx odmontować ekran walki.
            onEnded?.(Number(outcome.combat?.id ?? 0));
            qc.invalidateQueries({ queryKey: ["combat", campaignId] });
            qc.invalidateQueries({ queryKey: ["character"] });
            qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
          }}
        />
      )}
    </div>
  );
}
