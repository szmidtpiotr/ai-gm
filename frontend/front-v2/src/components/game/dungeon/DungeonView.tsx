// FE16 loch (#1265) — orkiestrator trybu lochu. Spina eksplorację (HUD + narracja +
// composer + D-pad + mapa + zagadka + skrzynia) oraz walkę (CombatView) i modale
// L13 (śmierć-checkpoint / porzucenie / ukończenie). Boss → CombatView→CombatOutcomes
// (F-29). Model wierny app.js: run trzymany lokalnie, patchowany po move, refetch po
// resolve-tile i po zakończeniu walki. Mechanika 1:1 — to warstwa prezentacji ŻAR.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { CircleNotch } from "@phosphor-icons/react";
import { useToast } from "@/components/ui/toast";
import {
  useCharacter,
  useSubmitTurn,
  useTurnStream,
} from "@/hooks/useGameData";
import { useCombatState } from "@/hooks/useCombat";
import {
  useDungeonRunFull,
  useDungeonMove,
  useDungeonResolveTile,
  useDungeonExit,
  useDeleteDungeonCampaign,
  useDungeonDeath,
  type DungeonTileResult,
} from "@/hooks/useDungeon";
import { apiFetch } from "@/lib/api";
import { buildLog, readVitals, readStats, type LogBlock } from "@/lib/game";
import {
  currentNode,
  currentNodeId,
  hasRiddle,
  riddleText,
  visitedCount,
  inCombatTile,
  type Dir,
  type DungeonNode,
  type DungeonRun,
} from "@/lib/dungeon";
import { NarrationLog } from "../NarrationLog";
import { Composer } from "../Composer";
import { VitalsRail } from "../Vitals";
import { CombatView } from "../combat/CombatView";
import { DungeonHud } from "./DungeonHud";
import { DPad } from "./DPad";
import { DungeonMap } from "./DungeonMap";
import { RiddlePanel } from "./RiddlePanel";
import { TileImageModal } from "./TileImageModal";
import { ChestResultModal } from "./ChestResultModal";
import { AbandonModal, DeathCheckpointModal } from "./DungeonModals";

let _ephemeralSeq = 0;

export function DungeonView({
  campaignId,
  characterId,
}: {
  campaignId: number;
  characterId: number;
}) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const character = useCharacter(characterId);
  const stream = useTurnStream(campaignId);
  const submit = useSubmitTurn(campaignId);
  const runQ = useDungeonRunFull(campaignId);
  const combatState = useCombatState(campaignId);
  const activeCombat =
    combatState.data?.active && combatState.data.combat?.status === "active"
      ? combatState.data.combat
      : null;

  const move = useDungeonMove(campaignId);
  const resolve = useDungeonResolveTile(campaignId);
  const exit = useDungeonExit(campaignId);
  const deleteCampaign = useDeleteDungeonCampaign();
  const death = useDungeonDeath(campaignId);

  // Run trzymany lokalnie (parytet `_activeDungeonRun`): seed z query, patch po move.
  const [run, setRun] = useState<DungeonRun | undefined>(undefined);
  useEffect(() => {
    const r = runQ.data?.dungeon_run;
    if (r) setRun((prev) => prev ?? (r as DungeonRun));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runQ.data]);

  async function refetchRun(): Promise<DungeonRun | undefined> {
    const res = await qc.fetchQuery({
      queryKey: ["dungeon-run-full", campaignId],
      queryFn: () =>
        apiFetch<{ dungeon_run?: DungeonRun | null }>(
          `/campaigns/${campaignId}/dungeon-run`,
        ),
    });
    const r = res?.dungeon_run || undefined;
    if (r) setRun(r);
    return r;
  }

  // Bloki narracji ulotnej (opisy komnat/akcji nie są turami) — parytet appendMessage.
  const [extra, setExtra] = useState<LogBlock[]>([]);
  function pushGm(text: string) {
    if (!text) return;
    setExtra((p) => [...p, { kind: "gm", id: `d${_ephemeralSeq++}`, text, turn: 0 }]);
  }

  // Overlaye eksploracji.
  const [mapOpen, setMapOpen] = useState(false);
  const [mapAutoClose, setMapAutoClose] = useState(false);
  const [tileModal, setTileModal] = useState<DungeonNode | null>(null);
  const [chestResult, setChestResult] = useState<DungeonTileResult | null>(null);
  const [riddleHint, setRiddleHint] = useState<string | null>(null);
  const [abandonOpen, setAbandonOpen] = useState(false);
  const [deathState, setDeathState] = useState<{ cooldown: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  const seenTiles = useRef<Set<string>>(new Set());
  const openedRef = useRef(false);
  const wasCombatRef = useRef(false);

  const node = currentNode(run, characterId);
  const vitals = useMemo(
    () => readVitals(character.data?.sheet_json),
    [character.data?.sheet_json],
  );
  const stats = useMemo(
    () => readStats(character.data?.sheet_json),
    [character.data?.sheet_json],
  );

  const blocks = useMemo(
    () => [...buildLog(stream.data?.turns ?? []), ...extra],
    [stream.data?.turns, extra],
  );

  // Bootstrap: brak tur → odpal scenę otwierającą raz (parytet enterGame __AI_GM_OPEN).
  useEffect(() => {
    if (
      !openedRef.current &&
      stream.isSuccess &&
      (stream.data?.turns?.length ?? 0) === 0 &&
      !submit.isPending
    ) {
      openedRef.current = true;
      submit.mutate({ characterId, text: "__AI_GM_OPEN" });
    }
  }, [stream.isSuccess, stream.data, submit, characterId]);

  // Pierwsza wizyta kafla z grafiką → popup obrazu (parytet renderTileScene).
  useEffect(() => {
    const id = currentNodeId(run, characterId);
    if (!id || !node) return;
    if (node.content?.image_url && !seenTiles.current.has(id)) {
      seenTiles.current.add(id);
      setTileModal(node);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, characterId]);

  // Po zakończeniu walki (active→brak): odśwież run (kafel czyszczony / boss go_deeper).
  useEffect(() => {
    const isActive = !!activeCombat;
    if (wasCombatRef.current && !isActive) {
      refetchRun();
    }
    wasCombatRef.current = isActive;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCombat]);

  // Auto-domknięcie mapy (parytet openDungeonMap(true) → 3.5s).
  useEffect(() => {
    if (mapOpen && mapAutoClose) {
      const t = setTimeout(() => {
        setMapOpen(false);
        setMapAutoClose(false);
      }, 3500);
      return () => clearTimeout(t);
    }
  }, [mapOpen, mapAutoClose]);

  // ── Ruch (parytet _dungeonMove) → { stop } dla auto-marszu ──────────────────
  async function stepMove(dir: Dir, opts: { silent?: boolean } = {}): Promise<{ stop: boolean }> {
    const silent = !!opts.silent;
    try {
      const r = await move.mutateAsync({ characterId, direction: dir });
      if (!r.ok) {
        toast(r.reason || `Brak drzwi ${dir}`, "info");
        return { stop: true };
      }
      if (r.narrative && !silent) pushGm(r.narrative);

      // Patch lokalnego run (endpoint zwraca węzeł docelowy, nie cały run).
      setRun((prev) => {
        if (!prev?.graph?.nodes || !r.node_id) return prev;
        const nodes = { ...prev.graph.nodes };
        if (r.node) nodes[r.node_id] = r.node as unknown as DungeonNode;
        return {
          ...prev,
          graph: { ...prev.graph, nodes },
          positions: { ...(prev.positions || {}), [String(characterId)]: r.node_id },
        };
      });

      const combatStarted = !!(r.combat && !(r.combat as { error?: string }).error);
      if (r.combat) {
        qc.invalidateQueries({ queryKey: ["combat", campaignId] });
      }

      // Auto-otwarcie mapy przy 2. odkrytym kaflu (#869: nie w trakcie auto-marszu).
      if (!silent && !combatStarted) {
        const vc = visitedCount({
          ...run,
          graph: run?.graph,
        } as DungeonRun);
        // po patchu policz na świeżo w następnym ticku — użyj r.node visited
        if (vc + 1 === 2) {
          setMapAutoClose(true);
          setMapOpen(true);
        }
      }

      const content = (r.content || {}) as { riddle?: unknown };
      const pendingRiddle = !r.is_cleared && !!content.riddle;
      const stop = combatStarted || pendingRiddle;
      return { stop };
    } catch (e) {
      toast((e as Error).message || "Błąd ruchu", "danger");
      return { stop: true };
    }
  }

  // Auto-marsz BFS (parytet _dungeonAutoWalk): krok po kroku, stop na zdarzeniu.
  async function autoWalk(path: Dir[]) {
    setBusy(true);
    try {
      for (let i = 0; i < path.length; i++) {
        const isLast = i === path.length - 1;
        const res = await stepMove(path[i], { silent: !isLast });
        if (res.stop) break;
      }
    } finally {
      setBusy(false);
    }
  }

  async function onMove(dir: Dir) {
    setBusy(true);
    try {
      await stepMove(dir);
    } finally {
      setBusy(false);
    }
  }

  // ── Akcje kafla (parytet _dungeonResolveTile) ───────────────────────────────
  async function resolveTile(
    action: "open_chest" | "answer_riddle" | "riddle_hint" | "rest",
    payload?: Record<string, unknown>,
  ) {
    setBusy(true);
    try {
      const r = await resolve.mutateAsync({ characterId, action, payload });
      if (r.narrative) pushGm(r.narrative);
      if (r.hint) setRiddleHint(r.hint);
      await refetchRun();

      if (action === "rest") {
        if (r.blocked) toast(r.narrative || "Najpierw pokonaj wrogów.", "info");
        else if (r.no_charges) toast("Brak sił na kolejny odpoczynek.", "info");
        else {
          const hp = typeof r.hp_after === "number" ? ` — HP: ${r.hp_after}` : "";
          toast(`Odpoczynek${hp}`, "success");
        }
      }
      if (action === "answer_riddle") {
        if (r.solved) {
          setRiddleHint(null);
          toast("Zagadka rozwiązana!", "success");
        } else if (r.failed_permanently) {
          setRiddleHint(null);
          toast("Zagadka zamknięta na zawsze.", "danger");
        }
      }
      if (action === "open_chest") {
        setChestResult(r);
      }
    } catch (e) {
      toast((e as Error).message || "Błąd akcji", "danger");
    } finally {
      setBusy(false);
    }
  }

  // ── Wyjście / porzucenie (parytet _exitDungeon / _doExitDungeon) ────────────
  async function requestExit() {
    const atCheckpoint = run?.at_checkpoint || false;
    const isCompleted = run?.completed || false;
    if (run && !isCompleted && !atCheckpoint) {
      setAbandonOpen(true);
      return;
    }
    await doExit();
  }

  async function doExit() {
    setBusy(true);
    try {
      let prevId: number | null | undefined;
      try {
        const res = await exit.mutateAsync(characterId);
        prevId = res.relinked_campaign_id ?? res.previous_campaign_id;
      } catch {
        /* i tak sprzątamy kampanię */
      }
      try {
        await deleteCampaign.mutateAsync(campaignId);
      } catch {
        /* noop */
      }
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["heroes"] });
      if (prevId) navigate(`/gra/${prevId}`);
      else navigate("/bohaterowie");
    } finally {
      setBusy(false);
    }
  }

  // ── Śmierć w lochu (parytet showDungeonDeathModal) ──────────────────────────
  async function onDungeonDeath() {
    try {
      const r = await death.mutateAsync(characterId);
      await refetchRun();
      setDeathState({ cooldown: r.cooldown_until ?? null });
    } catch {
      setDeathState({ cooldown: null });
    }
  }

  if (character.isLoading || runQ.isLoading) return <Loader />;

  // Walka w lochu → CombatView (boss/łup przez CombatOutcomes; śmierć → checkpoint).
  if (activeCombat) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <DungeonHud run={run} charId={characterId} onOpenMap={() => setMapOpen(true)} onExit={requestExit} />
        <div className="min-h-0 flex-1">
          <CombatView
            campaignId={campaignId}
            character={character.data}
            combat={activeCombat}
            blocks={blocks}
            typing={submit.isPending}
            vitals={vitals}
            stats={stats}
            onSend={(t) => submit.mutate({ characterId, text: t })}
            sending={submit.isPending}
            dungeon
            onDungeonDeath={onDungeonDeath}
          />
        </div>
        {mapOpen && (
          <DungeonMap
            run={run}
            charId={characterId}
            onClose={() => { setMapOpen(false); setMapAutoClose(false); }}
            onWalk={autoWalk}
            onStep={onMove}
          />
        )}
        {deathState && (
          <DeathCheckpointModal
            run={run}
            cooldownUntil={deathState.cooldown}
            busy={busy}
            onExit={doExit}
          />
        )}
      </div>
    );
  }

  const showRiddle = hasRiddle(node);
  const explorationBlocked = inCombatTile(node);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <DungeonHud run={run} charId={characterId} onOpenMap={() => setMapOpen(true)} onExit={requestExit} />

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <NarrationLog blocks={blocks} typing={submit.isPending} heroName={character.data?.name} />
        </div>
        <VitalsRail v={vitals} stats={stats} locationLabel={run?.dungeon_label} />
      </div>

      {showRiddle && (
        <RiddlePanel
          text={riddleText(node)}
          hint={riddleHint}
          busy={busy}
          onAnswer={(a) => resolveTile("answer_riddle", { answer: a })}
          onHint={() => resolveTile("riddle_hint")}
        />
      )}

      <Composer
        onSend={(t) => submit.mutate({ characterId, text: t })}
        disabled={submit.isPending}
        chips={[]}
        onChip={() => {}}
        placeholder="Zbadaj komnatę…"
      />

      {/* D-pad ukryty w trakcie walki-kafla (jak updateDungeonNav) */}
      {!explorationBlocked && (
        <DPad
          node={node}
          disabled={busy || move.isPending}
          onMove={onMove}
          onOpenMap={() => setMapOpen(true)}
          onChest={() => resolveTile("open_chest")}
          onRest={() => resolveTile("rest")}
        />
      )}

      {/* overlaye */}
      {mapOpen && (
        <DungeonMap
          run={run}
          charId={characterId}
          onClose={() => { setMapOpen(false); setMapAutoClose(false); }}
          onWalk={autoWalk}
          onStep={onMove}
        />
      )}
      {tileModal && <TileImageModal node={tileModal} onClose={() => setTileModal(null)} />}
      {chestResult && (
        <ChestResultModal resp={chestResult} onClose={() => setChestResult(null)} />
      )}
      {abandonOpen && (
        <AbandonModal
          run={run}
          busy={busy}
          onCancel={() => setAbandonOpen(false)}
          onConfirm={() => { setAbandonOpen(false); doExit(); }}
        />
      )}
      {deathState && (
        <DeathCheckpointModal
          run={run}
          cooldownUntil={deathState.cooldown}
          busy={busy}
          onExit={doExit}
        />
      )}
    </div>
  );
}

function Loader() {
  return (
    <div className="flex h-full items-center justify-center gap-2 text-text-3">
      <CircleNotch className="animate-spin" size={22} />
      <span className="font-ui text-body">Wczytywanie lochu…</span>
    </div>
  );
}
