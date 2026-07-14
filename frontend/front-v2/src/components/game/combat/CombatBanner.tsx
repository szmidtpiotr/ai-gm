// F-53 baner walki (#1236 / #967) — kompaktowy, jednokolumnowy. Makieta: zar7-walka.html.
// Strefy ZWARCIE/DYSTANS = lekkie nagłówki; każdy uczestnik = jedna ciasna linia z
// inline HP + pinami DEF/tarcza/warunek; aktywny aktor = amber glow; zwijanie (mobile).
// #1385: klik na pasek = rozwija panel inline z pełnymi parametrami (HP/obrona/stany/
// zamiar wroga; gracz dodatkowo mana+staty). Wybór celu przeniesiony na ikonę 🎯 —
// tap na pasek NIE zmienia celu (podgląd ≠ celowanie).
import { useState } from "react";
import {
  Sword,
  CrosshairSimple,
  Target,
  CaretUp,
  CaretDown,
  CaretRight,
  ShieldCheck,
  Heart,
  Sparkle,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { Combatant, CombatCondition } from "@/lib/types";
import {
  hpPct,
  hpTier,
  isCombatantActive,
  armorReduction,
  conditionTtl,
  conditionLevel,
  enemyIntent,
  type CombatView,
} from "@/lib/combat";

const HP_FILL: Record<string, string> = {
  hi: "bg-gradient-to-r from-[#6b9a4a] to-success",
  mid: "bg-gradient-to-r from-[#c9a24a] to-gold",
  lo: "bg-gradient-to-r from-[#b33] to-danger",
};

// #1385 — dodatkowe parametry gracza (mana/staty/poziom) niedostępne w combatant.
export interface PlayerExtra {
  mana: number;
  maxMana: number;
  hasMana: boolean;
  level: number;
  statMods: Array<{ k: string; mod: number }>;
}

export function CombatBanner({
  view,
  selectedTargetId,
  onSelectTarget,
  playerExtra,
}: {
  view: CombatView;
  selectedTargetId: string | null;
  onSelectTarget: (id: string) => void;
  playerExtra?: PlayerExtra | null;
}) {
  const [collapsed, setCollapsed] = useState(false);
  // #1385 — jednocześnie rozwinięty max 1 panel (inline expand).
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const toggleExpand = (id: string) =>
    setExpandedId((cur) => (cur === id ? null : id));
  const enemyCount = view.engaged.length + view.ranged.length;
  const turnLabel = view.isPlayerTurn ? "Twoja tura" : "Tura wroga";
  const playerZone: "engaged" | "ranged" =
    view.player?.zone === "ranged" ? "ranged" : "engaged";

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
        {/* BL-A7 (#1344): mały wskaźnik zagrożenia na czas walki — refresher do decyzji o ucieczce */}
        {view.relativeThreat && (
          <span
            className="flex items-center gap-1 rounded-pill border border-line-danger bg-bg px-2 py-0.5 font-ui text-[10px] font-bold uppercase tracking-[0.06em] text-text-2"
            title={`Zagrożenie: ${view.relativeThreat.label}`}
            data-testid="banner-threat"
          >
            <span className="text-[12px] leading-none">{view.relativeThreat.glyph}</span>
            {view.relativeThreat.label}
          </span>
        )}
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
            playerZone={playerZone}
            playerExtra={playerExtra}
            expandedId={expandedId}
            onToggleExpand={toggleExpand}
          />
          <Zone
            kind="ranged"
            label="Dystans"
            list={view.ranged}
            view={view}
            selectedTargetId={selectedTargetId}
            onSelectTarget={onSelectTarget}
            player={view.player}
            playerZone={playerZone}
            playerExtra={playerExtra}
            expandedId={expandedId}
            onToggleExpand={toggleExpand}
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
  playerZone,
  playerExtra,
  expandedId,
  onToggleExpand,
}: {
  kind: "melee" | "ranged";
  label: string;
  list: Combatant[];
  view: CombatView;
  selectedTargetId: string | null;
  onSelectTarget: (id: string) => void;
  player?: Combatant | null;
  playerZone: "engaged" | "ranged";
  playerExtra?: PlayerExtra | null;
  expandedId: string | null;
  onToggleExpand: (id: string) => void;
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
          expanded={expandedId === "player"}
          onToggleExpand={() => onToggleExpand("player")}
          playerExtra={playerExtra}
          playerZone={playerZone}
          groupThreat={view.relativeThreat}
        />
      )}
      {list.map((c) => (
        <CombatRow
          key={c.id}
          c={c}
          active={isCombatantActive(c, view.currentTurn)}
          isTarget={String(c.id) === selectedTargetId}
          expanded={expandedId === String(c.id)}
          onToggleExpand={() => onToggleExpand(String(c.id))}
          onSelectTarget={
            Number(c.hp_current ?? 0) > 0 ? () => onSelectTarget(String(c.id)) : undefined
          }
          playerZone={playerZone}
          groupThreat={view.relativeThreat}
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
  expanded = false,
  onToggleExpand,
  onSelectTarget,
  playerExtra,
  playerZone,
  groupThreat,
}: {
  c: Combatant;
  isMe?: boolean;
  active?: boolean;
  isTarget?: boolean;
  expanded?: boolean;
  onToggleExpand: () => void;
  onSelectTarget?: () => void;
  playerExtra?: PlayerExtra | null;
  playerZone: "engaged" | "ranged";
  groupThreat?: CombatView["relativeThreat"];
}) {
  const cur = Math.max(0, Number(c.hp_current ?? 0));
  const max = Math.max(1, Number(c.hp_max ?? cur ?? 1));
  const dead = cur <= 0;
  const tier = hpTier(cur, max);
  const absorb = Math.max(0, Number(c.absorb_hp ?? 0));
  const conds = Array.isArray(c.conditions) ? c.conditions : [];

  return (
    <div className="mb-1">
      {/* pasek (klik = rozwiń/zwiń podgląd — NIE zmienia celu, #1385) */}
      <div
        role="button"
        tabIndex={0}
        onClick={onToggleExpand}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggleExpand();
          }
        }}
        aria-expanded={expanded}
        className={cn(
          "flex w-full cursor-pointer items-center gap-2 rounded-sm border px-2 py-1 text-left transition-shadow",
          "border-line-soft bg-bg hover:border-line-ember",
          isMe && "border-[rgba(255,122,61,.28)] bg-player-card",
          dead && "opacity-45",
          active && "border-ember shadow-[0_0_0_1px_var(--ember),0_0_10px_rgba(255,122,61,.25)]",
          isTarget && !active && "border-line-danger",
          expanded && "rounded-b-none",
        )}
      >
        <CaretRight
          size={11}
          className={cn(
            "shrink-0 text-text-3 transition-transform",
            expanded && "rotate-90",
          )}
        />
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
          {/* 🎯 wybór celu — osobna kontrolka, tap tu NIE rozwija panelu */}
          {onSelectTarget && !dead && (
            <button
              type="button"
              aria-label={isTarget ? "Aktualny cel" : "Ustaw jako cel"}
              title={isTarget ? "Aktualny cel" : "Ustaw jako cel"}
              onClick={(e) => {
                e.stopPropagation();
                onSelectTarget();
              }}
              className={cn(
                "flex h-[18px] w-[18px] items-center justify-center rounded-[4px] border",
                isTarget
                  ? "border-line-danger text-danger"
                  : "border-line text-text-3 hover:text-danger",
              )}
            >
              <Target weight={isTarget ? "fill" : "regular"} size={11} />
            </button>
          )}
        </span>
      </div>

      {/* #1385 rozwinięty panel — pełne parametry, pcha listę w dół */}
      {expanded && (
        <ExpandedPanel
          c={c}
          isMe={isMe}
          cur={cur}
          max={max}
          conds={conds}
          absorb={absorb}
          playerExtra={playerExtra}
          playerZone={playerZone}
          groupThreat={groupThreat}
        />
      )}
    </div>
  );
}

function ExpandedPanel({
  c,
  isMe,
  cur,
  max,
  conds,
  absorb,
  playerExtra,
  playerZone,
  groupThreat,
}: {
  c: Combatant;
  isMe: boolean;
  cur: number;
  max: number;
  conds: CombatCondition[];
  absorb: number;
  playerExtra?: PlayerExtra | null;
  playerZone: "engaged" | "ranged";
  groupThreat?: CombatView["relativeThreat"];
}) {
  const dead = cur <= 0;
  const pct = hpPct(cur, max);
  const reduction = armorReduction(c.defense);
  const zoneLabel =
    String(c.zone || "engaged") === "ranged" ? "🏹 dystans" : "⚔ zwarcie";
  const intent = !isMe ? enemyIntent(c, playerZone) : null;

  return (
    <div
      className={cn(
        "rounded-b-sm border border-t-0 px-2.5 py-2 font-ui text-[10.5px] text-text-2",
        isMe
          ? "border-[rgba(255,122,61,.28)] bg-[rgba(255,122,61,.05)]"
          : "border-line-soft bg-[rgba(255,255,255,.02)]",
      )}
      data-testid="combatant-detail"
    >
      {/* nagłówek panelu — strefa + (grupowe) zagrożenie */}
      <div className="mb-1.5 flex items-center gap-2 text-[9px] uppercase tracking-[0.1em] text-text-3">
        <span>{zoneLabel}</span>
        {!isMe && groupThreat && (
          <span title={`Zagrożenie grupy: ${groupThreat.label}`}>
            {groupThreat.glyph} {groupThreat.label}
          </span>
        )}
      </div>

      {/* HP */}
      <DetailBar
        icon={<Heart weight="fill" size={11} className="text-danger" />}
        label="Życie"
        value={dead ? "💀 pokonany" : `${cur}/${max} (${pct}%)`}
        pct={pct}
        fill={HP_FILL[hpTier(cur, max)]}
      />

      {/* Mana (tylko gracz z maną) */}
      {isMe && playerExtra?.hasMana && (
        <DetailBar
          icon={<Sparkle weight="fill" size={11} className="text-mana" />}
          label="Mana"
          value={`${playerExtra.mana}/${playerExtra.maxMana}`}
          pct={hpPct(playerExtra.mana, Math.max(1, playerExtra.maxMana))}
          fill="bg-gradient-to-r from-[#4a6a9a] to-mana"
        />
      )}

      {/* Obrona → redukcja (#826) */}
      <DetailRow label="Obrona">
        {c.defense != null ? (
          <>
            AC {c.defense} → <span className="text-mana">redukcja {reduction}</span>{" "}
            <span className="text-text-3">dmg/trafienie</span>
          </>
        ) : (
          <span className="text-text-3">—</span>
        )}
        {absorb > 0 && (
          <span className="ml-1 text-success">· tarcza {absorb}</span>
        )}
      </DetailRow>

      {/* Statystyki (tylko gracz) */}
      {isMe && playerExtra?.statMods?.length ? (
        <DetailRow label="Statystyki">
          <span className="flex flex-wrap gap-x-2 gap-y-0.5 font-mono">
            {playerExtra.statMods.map((s) => (
              <span key={s.k}>
                <span className="text-text-3">{s.k}</span>
                <span className={s.mod >= 0 ? "text-success" : "text-danger"}>
                  {s.mod >= 0 ? "+" : ""}
                  {s.mod}
                </span>
              </span>
            ))}
          </span>
        </DetailRow>
      ) : null}

      {/* Stany z TTL / poziomem */}
      <DetailRow label="Stany">
        {conds.length ? (
          <span className="flex flex-wrap gap-1">
            {conds.map((cd, i) => {
              const ttl = conditionTtl(cd);
              const lvl = conditionLevel(cd);
              return (
                <span
                  key={i}
                  className="rounded-[4px] border border-line-danger px-1 py-px text-danger"
                >
                  {cd.label || cd.key || "?"}
                  {lvl > 1 && <span className="text-text-3"> ·lvl {lvl}</span>}
                  {ttl != null && (
                    <span className="text-text-3"> ·{ttl}t</span>
                  )}
                </span>
              );
            })}
          </span>
        ) : (
          <span className="text-text-3">brak</span>
        )}
      </DetailRow>

      {/* Zamiar wroga — telegraf (v1 heurystyka strefowa, #1385) */}
      {intent && (
        <DetailRow label="Zamiar">
          <span className="text-gold">
            {intent.glyph} {intent.label}
          </span>
          <span className="ml-1 text-[8.5px] text-text-3">(przewidywanie)</span>
        </DetailRow>
      )}

      {/* Death-save ladder gdy gracz na 0 HP */}
      {isMe && dead && (
        <DetailRow label="Rzut na śmierć">
          <span className="font-mono text-danger">DC 10 → 13 → 16 → 19</span>
        </DetailRow>
      )}
    </div>
  );
}

function DetailBar({
  icon,
  label,
  value,
  pct,
  fill,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  pct: number;
  fill: string;
}) {
  return (
    <div className="mb-1.5">
      <div className="mb-0.5 flex items-center gap-1.5">
        {icon}
        <span className="text-[9px] uppercase tracking-[0.08em] text-text-3">
          {label}
        </span>
        <span className="ml-auto font-mono text-[10px] text-text-2">{value}</span>
      </div>
      <span className="block h-[6px] overflow-hidden rounded-[3px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
        <span
          className={cn("block h-full rounded-[3px]", fill)}
          style={{ width: `${pct}%` }}
        />
      </span>
    </div>
  );
}

function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-2 py-0.5">
      <span className="w-[74px] shrink-0 text-[9px] uppercase tracking-[0.06em] text-text-3">
        {label}
      </span>
      <span className="flex-1">{children}</span>
    </div>
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
