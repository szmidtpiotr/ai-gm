// F-53 baner walki (#1236 / #967) — kompaktowy, jednokolumnowy. Makieta: zar7-walka.html.
// Strefy ZWARCIE/DYSTANS = lekkie nagłówki; każdy uczestnik = jedna ciasna linia z
// inline HP + pinami DEF/tarcza/warunek; aktywny aktor = amber glow; zwijanie (mobile).
import { useState } from "react";
import {
  Sword,
  CrosshairSimple,
  Target,
  CaretUp,
  CaretDown,
  ShieldCheck,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { Combatant, CombatCondition } from "@/lib/types";
import { hpPct, hpTier, isCombatantActive, type CombatView } from "@/lib/combat";

const HP_FILL: Record<string, string> = {
  hi: "bg-gradient-to-r from-[#6b9a4a] to-success",
  mid: "bg-gradient-to-r from-[#c9a24a] to-gold",
  lo: "bg-gradient-to-r from-[#b33] to-danger",
};

export function CombatBanner({
  view,
  selectedTargetId,
  onSelectTarget,
}: {
  view: CombatView;
  selectedTargetId: string | null;
  onSelectTarget: (id: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const enemyCount = view.engaged.length + view.ranged.length;
  const turnLabel = view.isPlayerTurn ? "Twoja tura" : "Tura wroga";

  return (
    <div className="shrink-0 border-b border-line-danger bg-surface">
      {/* pasek stanu walki */}
      <header className="flex items-center gap-2.5 bg-gradient-to-r from-[rgba(232,96,79,.14)] to-surface px-3.5 py-2">
        <span className="flex items-center gap-1.5 font-ui text-[12.5px] font-bold uppercase tracking-[0.08em] text-danger-glow">
          <Sword weight="fill" size={15} /> Walka
        </span>
        <span className="rounded-pill border border-line bg-bg px-2 py-0.5 font-mono text-[11px] text-text-2">
          Runda {view.round}
        </span>
        <span
          className={cn(
            "ml-auto flex items-center gap-1 font-ui text-[10.5px] font-bold uppercase tracking-[0.12em]",
            view.isPlayerTurn ? "text-ember-glow" : "text-danger-glow",
          )}
        >
          <CaretRightGlyph on={view.isPlayerTurn} /> {turnLabel}
        </span>
        <button
          type="button"
          aria-label={collapsed ? "Rozwiń baner" : "Zwiń baner"}
          onClick={() => setCollapsed((v) => !v)}
          className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-sm border border-line bg-bg text-text-3"
        >
          {collapsed ? <CaretDown size={13} /> : <CaretUp size={13} />}
        </button>
      </header>

      {/* body — zwijalne dla oszczędności miejsca na mobile */}
      {collapsed ? (
        <div className="flex items-center gap-2 px-3.5 py-1.5 font-ui text-[11.5px] text-text-2">
          <Sword weight="fill" size={13} className="text-danger" />
          {enemyCount} {enemyCount === 1 ? "wróg" : "wrogów"}
          {[...view.engaged, ...view.ranged].slice(0, 3).map((e) => (
            <span key={e.id} className="text-text-3">
              · {e.name} {e.hp_current}/{e.hp_max}
            </span>
          ))}
        </div>
      ) : (
        <div className="px-3 pb-2 pt-1">
          <Zone
            kind="melee"
            label="Zwarcie"
            list={view.engaged}
            view={view}
            selectedTargetId={selectedTargetId}
            onSelectTarget={onSelectTarget}
            player={view.player}
          />
          <Zone
            kind="ranged"
            label="Dystans"
            list={view.ranged}
            view={view}
            selectedTargetId={selectedTargetId}
            onSelectTarget={onSelectTarget}
            player={view.player}
          />
        </div>
      )}
    </div>
  );
}

function CaretRightGlyph({ on }: { on: boolean }) {
  return (
    <span className={cn("text-[9px]", on ? "text-ember" : "text-danger")}>▶</span>
  );
}

function Zone({
  kind,
  label,
  list,
  view,
  selectedTargetId,
  onSelectTarget,
  player,
}: {
  kind: "melee" | "ranged";
  label: string;
  list: Combatant[];
  view: CombatView;
  selectedTargetId: string | null;
  onSelectTarget: (id: string) => void;
  player?: Combatant | null;
}) {
  // Gracz jest stałym punktem odniesienia — renderuje się w swojej strefie (wg zone).
  const playerHere =
    player && String(player.zone || "engaged") === (kind === "melee" ? "engaged" : "ranged")
      ? player
      : null;
  const Icon = kind === "melee" ? Sword : CrosshairSimple;
  const count = list.length + (playerHere ? 1 : 0);

  return (
    <>
      <div
        className={cn(
          "mx-0.5 mb-1 mt-1.5 flex items-center gap-1.5 font-ui text-[8.5px] font-bold uppercase tracking-[0.18em] first:mt-0.5",
          kind === "melee" ? "text-[#d98a5a]" : "text-mana",
        )}
      >
        <Icon size={11} /> {label}
        <span className="ml-auto font-mono text-[8.5px] tracking-normal text-text-3">
          {count}
        </span>
      </div>
      {playerHere && (
        <CombatRow
          c={playerHere}
          isMe
          active={isCombatantActive(playerHere, view.currentTurn)}
        />
      )}
      {list.map((c) => (
        <CombatRow
          key={c.id}
          c={c}
          active={isCombatantActive(c, view.currentTurn)}
          isTarget={String(c.id) === selectedTargetId}
          onClick={
            Number(c.hp_current ?? 0) > 0 ? () => onSelectTarget(String(c.id)) : undefined
          }
        />
      ))}
      {count === 0 && (
        <div className="px-2 pb-1 pt-0.5 font-ui text-[10px] italic text-text-3">
          — pusto —
        </div>
      )}
    </>
  );
}

function CombatRow({
  c,
  isMe = false,
  active = false,
  isTarget = false,
  onClick,
}: {
  c: Combatant;
  isMe?: boolean;
  active?: boolean;
  isTarget?: boolean;
  onClick?: () => void;
}) {
  const cur = Math.max(0, Number(c.hp_current ?? 0));
  const max = Math.max(1, Number(c.hp_max ?? cur ?? 1));
  const dead = cur <= 0;
  const tier = hpTier(cur, max);
  const absorb = Math.max(0, Number(c.absorb_hp ?? 0));
  const conds = Array.isArray(c.conditions) ? c.conditions : [];

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={cn(
        "mb-1 flex w-full items-center gap-2 rounded-sm border px-2 py-1 text-left transition-shadow",
        "border-line-soft bg-bg",
        isMe && "border-[rgba(255,122,61,.28)] bg-player-card",
        dead && "opacity-45",
        active && "border-ember shadow-[0_0_0_1px_var(--ember),0_0_10px_rgba(255,122,61,.25)]",
        isTarget && !active && "border-line-danger",
        onClick && "cursor-pointer hover:border-line-ember",
      )}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px] border border-line-mech bg-mech-card font-mono text-[9.5px] font-semibold text-gold">
        {c.initiative_roll ?? "–"}
      </span>
      <span
        className={cn(
          "max-w-[86px] shrink-0 truncate font-ui text-[12px] font-semibold",
          isMe && "text-ember-glow",
          dead && "text-text-3 line-through",
        )}
      >
        {isMe ? `Ty · ${c.name ?? ""}` : c.name ?? c.enemy_key ?? "Wróg"}
      </span>
      {!dead && (
        <span className="h-[5px] min-w-[36px] flex-1 overflow-hidden rounded-[3px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
          <span
            className={cn("block h-full rounded-[3px]", HP_FILL[tier])}
            style={{ width: `${hpPct(cur, max)}%` }}
          />
        </span>
      )}
      <span className="w-[38px] shrink-0 text-right font-mono text-[9px] text-text-3">
        {dead ? "💀" : `${cur}/${max}`}
      </span>
      <span className="flex shrink-0 items-center gap-[3px]">
        {c.defense != null && (
          <Pin className="border-[rgba(130,167,199,.3)] text-mana">{c.defense}</Pin>
        )}
        {absorb > 0 && (
          <Pin className="border-[rgba(168,201,131,.3)] text-success">
            <ShieldCheck size={9} className="inline" /> {absorb}
          </Pin>
        )}
        {conds.map((cd, i) => (
          <Pin key={i} className="border-line-danger text-danger">
            {condLabel(cd)}
          </Pin>
        ))}
        {isTarget && !dead && (
          <Target weight="fill" size={11} className="text-danger" />
        )}
      </span>
    </button>
  );
}

function Pin({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "rounded-[4px] border border-line px-1 py-px font-mono text-[8px] text-text-3",
        className,
      )}
    >
      {children}
    </span>
  );
}

function condLabel(cd: CombatCondition): string {
  const lvl = cd.runtime?.level;
  const base = (cd.label || cd.key || "?").slice(0, 6);
  return lvl && lvl > 1 ? `${base}·${lvl}` : base;
}
