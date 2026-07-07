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
import type { CombatState, CharacterDetail } from "@/lib/types";
import type { LogBlock } from "@/lib/game";
import type { Vitals } from "@/lib/game";
import {
  readCombat,
  livingEnemies,
  rollFromPlayerAttack,
  rollFromEnemyAttack,
  rollFromReaction,
} from "@/lib/combat";
import type { RollCardData } from "@/lib/types";
import {
  useCombatState,
  useResolveAttack,
  useZoneChange,
  useFlee,
  useEnemyTurn,
  useResolveReaction,
} from "@/hooks/useCombat";
import { useSpells, useSpellCatalog } from "@/hooks/useSheetData";
import { NarrationLog } from "../NarrationLog";
import { Composer } from "../Composer";
import { VitalsRail } from "../Vitals";
import { CombatBanner } from "./CombatBanner";
import { CombatActionBar } from "./CombatActionBar";
import { ActionSheet, type SheetMode, type SpellAction } from "./ActionSheet";
import { ReactionModal, type ReactionChoice, type ReactionData } from "./ReactionModal";
import { Dice3DOverlay, type DiceJob } from "./Dice3DOverlay";
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
}: {
  campaignId: number;
  character: CharacterDetail | undefined;
  combat: CombatState; // aktywny snapshot (Game.tsx wchodzi tu tylko gdy active)
  blocks: LogBlock[];
  typing: boolean;
  vitals: Vitals;
  stats: Array<{ k: string; v: number }>;
  onSend: (text: string) => void;
  sending: boolean;
  // FE16 (#1265): w lochu śmierć = przywrócenie punktu kontrolnego, nie ekran śmierci.
  dungeon?: boolean;
  onDungeonDeath?: () => void;
}) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const characterId = character?.id;

  // Query pollowany co 2s (tylko gdy aktywna) — Game.tsx już go trzyma, tu współdzielony.
  const combatQ = useCombatState(campaignId);
  const live = combatQ.data?.combat ?? combat;
  const view = useMemo(() => readCombat(live), [live]);

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

  // Lista czarów bojowych (znane × katalog), koszt/ranga/afford.
  const spells = useSpells(characterId);
  const catalog = useSpellCatalog(vitals.hasMana);
  const spellActions: SpellAction[] = useMemo(() => {
    const known = new Map((spells.data ?? []).map((k) => [k.spell_key, k]));
    return (catalog.data ?? [])
      .filter((c) => known.has(c.key))
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
          affordable: vitals.mana >= c.mana_cost,
        };
      })
      .sort((a, b) => a.mana_cost - b.mana_cost);
  }, [spells.data, catalog.data, vitals.mana]);

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
  const enemyTurnRef = useRef(false);
  const endedRef = useRef(false);
  const goldAccumRef = useRef(0);
  const xpAccumRef = useRef(0);

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
      jobSeq.current += 1;
      setDiceJob({
        id: jobSeq.current,
        notation: "1d20",
        forced: [face],
        face,
        card,
        crit: !!r.player_nat20,
        fumble: !!r.player_nat1,
      });
      // combat_state już w cache (mutacja onSuccess) — tura wroga odpali po zamknięciu kości.
      pushCombatState(r.combat_state);
    } catch {
      toast("Błąd akcji.", "danger");
      setBusy(false);
    }
  }

  function onDiceDone() {
    if (diceJob) setRolls((p) => [...p, diceJob.card]);
    setDiceJob(null);
    setBusy(false);
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

  async function doDeclare(rt: "dodge" | "shield_block") {
    setSheet(null);
    try {
      await import("@/lib/api").then(({ apiFetch }) =>
        apiFetch(`/campaigns/${campaignId}/combat/declare-reaction`, {
          method: "POST",
          body: { reaction_type: rt },
        }),
      );
      toast(rt === "dodge" ? "Unik zadeklarowany." : "Blok zadeklarowany.", "success");
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
    enemyTurn
      .mutateAsync()
      .then((r) => {
        pushCombatState(r.combat_state);
        if (r.reaction_window) {
          setReaction({
            enemyName: r.enemy_name ?? "Wróg",
            options: r.reaction_options ?? [],
            attackRoll: r.attack_roll ?? null,
            playerDefense: view.player?.defense ?? null,
          });
        } else {
          setRolls((p) => [...p, rollFromEnemyAttack(r)]);
        }
      })
      .catch(() => {})
      .finally(() => {
        enemyTurnRef.current = false;
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view?.currentTurn, view?.isPlayerTurn, view?.status, busy, diceJob, reaction]);

  // ── reakcja SF10 ──
  async function onReaction(choice: ReactionChoice) {
    try {
      const r = await reactionMut.mutateAsync(choice);
      pushCombatState(r.combat_state);
      setRolls((p) => [...p, rollFromReaction(r, choice)]);
      setReaction(null);
      // multiattack: kolejny cios może od razu ponownie otworzyć okno
      if (r.reaction_window) {
        setReaction({
          enemyName: r.enemy_name ?? "Wróg",
          options: r.reaction_options ?? [],
          attackRoll: r.attack_roll ?? null,
          playerDefense: view?.player?.defense ?? null,
        });
      }
    } catch {
      setReaction(null);
      toast("Błąd reakcji.", "danger");
    }
  }

  // ── koniec walki: modale wyników (F-27..F-32) lub toast (ucieczka) ──
  useEffect(() => {
    if (view?.status === "ended" && !endedRef.current) {
      endedRef.current = true;
      const reason = view.endedReason ?? "";
      // FE16 (#1265): śmierć w lochu → przywrócenie punktu kontrolnego (nie ekran śmierci).
      if (reason === "player_dead" && dungeon && onDungeonDeath) {
        onDungeonDeath();
      } else if (reason === "victory" || reason === "player_dead") {
        // victory / player_dead → pełny modal (CombatOutcomes); fled → tylko toast.
        setOutcome({ reason, combat: live });
      } else {
        toast(reason === "fled" ? "Walka zakończona — ucieczka." : "Walka zakończona.", "info");
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
  }, [view?.status, view?.endedReason, campaignId, qc, toast, live]);

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
          onClose={() => setSheet(null)}
        />
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
            qc.invalidateQueries({ queryKey: ["combat", campaignId] });
            qc.invalidateQueries({ queryKey: ["character"] });
            qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
          }}
        />
      )}
    </div>
  );
}
