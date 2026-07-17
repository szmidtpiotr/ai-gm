import { Heart, Drop, Warning } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { Vitals } from "@/lib/game";
import type { ConditionRow } from "@/lib/sheet";

function pct(v: number, max: number): number {
  return max > 0 ? Math.max(0, Math.min(100, (v / max) * 100)) : 0;
}

// #1414 — pigułki aktywnych stanów z konsekwencją w tooltipie (native title=).
// `compact` = wariant mobilny (bez opisu inline, tylko tap/hover). Zawsze widoczne
// w HUD, żeby gracz wiedział jakie efekty ma nałożone i co robią.
function ConditionsPills({ conditions, compact }: { conditions: ConditionRow[]; compact?: boolean }) {
  if (!conditions.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-1.5", compact && "px-0.5")}>
      {conditions.map((c) => (
        <span
          key={c.key}
          title={c.desc}
          className="inline-flex cursor-help items-center gap-1 rounded-pill border border-danger/40 bg-danger/10 px-2 py-0.5 text-micro text-danger"
        >
          <Warning weight="fill" size={11} className="shrink-0" />
          <span className="font-ui">
            {c.label}
            {c.level > 1 && <span className="opacity-70"> ·{c.level}</span>}
          </span>
        </span>
      ))}
    </div>
  );
}

// 2 cienkie paski HP/Mana nad dolnym tabbarem (sekcja 5, zamrożone reguły mobilne).
// Mana pokazywana tylko dla klas z pulą (mag).
export function VitalBars({ v, conditions = [] }: { v: Vitals; conditions?: ConditionRow[] }) {
  return (
    <div className="flex flex-col gap-1 bg-surface px-3.5 pb-1.5 pt-1.5 lg:hidden">
      <Bar
        kind="hp"
        icon={<Heart weight="fill" size={12} />}
        pct={pct(v.hp, v.maxHp)}
        label={`${v.hp}/${v.maxHp}`}
      />
      {v.hasMana && (
        <Bar
          kind="mana"
          icon={<Drop weight="fill" size={12} />}
          pct={pct(v.mana, v.maxMana)}
          label={`${v.mana}/${v.maxMana}`}
        />
      )}
      {conditions.length > 0 && (
        <div className="pt-1">
          <ConditionsPills conditions={conditions} compact />
        </div>
      )}
    </div>
  );
}

function Bar({
  kind,
  icon,
  pct,
  label,
}: {
  kind: "hp" | "mana";
  icon: React.ReactNode;
  pct: number;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className={cn("w-3.5 shrink-0 text-center", kind === "hp" ? "text-ember" : "text-mana")}>
        {icon}
      </span>
      <div className="h-[5px] flex-1 overflow-hidden rounded-[3px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
        <div
          className={cn(
            "h-full rounded-[3px] transition-[width] duration-500",
            kind === "hp"
              ? "bg-gradient-to-r from-[#c14a2b] to-ember shadow-[0_0_6px_rgba(255,122,61,.55)]"
              : "bg-gradient-to-r from-[#5f74e8] to-mana",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-[42px] shrink-0 text-right font-mono text-[10px] text-text-3">
        {label}
      </span>
    </div>
  );
}

// Desktop: prawy rail z pełnymi paskami + atrybutami (sekcja 5).
export function VitalsRail({
  v,
  stats,
  locationLabel,
  conditions,
}: {
  v: Vitals;
  stats: Array<{ k: string; v: number }>;
  locationLabel?: string | null;
  conditions?: ConditionRow[];
}) {
  return (
    <aside className="hidden w-[310px] shrink-0 overflow-y-auto border-l border-line bg-surface p-6 lg:block">
      <RailHead>Żywotność</RailHead>
      <BigBar label="Zdrowie" value={`${v.hp} / ${v.maxHp}`} pct={pct(v.hp, v.maxHp)} kind="hp" />
      {v.hasMana && (
        <BigBar label="Mana" value={`${v.mana} / ${v.maxMana}`} pct={pct(v.mana, v.maxMana)} kind="mana" />
      )}
      {v.maxXp > 0 && (
        <BigBar label="Doświadczenie" value={`${v.xp} / ${v.maxXp}`} pct={pct(v.xp, v.maxXp)} kind="xp" />
      )}

      {/* #1414 — stany zawsze widoczne w HUD (wcześniej tylko w panelu Bohater).
          Najeżdżając/dotykając pigułkę gracz widzi konsekwencję efektu. Sekcja tylko
          gdy widok przekaże `conditions` (undefined → pomiń, brak fałszywego „pełnia sił"). */}
      {conditions !== undefined && (
        <>
          <RailHead>Stany</RailHead>
          {conditions.length > 0 ? (
            <ConditionsPills conditions={conditions} />
          ) : (
            <p className="rounded-md border border-line bg-bg px-3.5 py-2 text-label text-text-3">
              Pełnia sił — brak aktywnych efektów.
            </p>
          )}
        </>
      )}

      <RailHead>Atrybuty</RailHead>
      <div className="grid grid-cols-4 gap-1.5">
        {stats.map((s) => (
          <div key={s.k} className="rounded-md border border-line bg-bg px-0.5 py-2 text-center">
            <div className="text-[9px] font-semibold uppercase tracking-wide text-text-3">{s.k}</div>
            <div className="mt-0.5 font-mono text-body text-text">{s.v}</div>
          </div>
        ))}
      </div>

      <RailHead>Sakiewka</RailHead>
      <div className="flex items-center justify-between rounded-md border border-line bg-bg px-3.5 py-2.5 text-label text-text-2">
        <span>Złoto</span>
        <b className="font-mono text-body font-semibold text-ember-glow">{v.gold} gp</b>
      </div>

      {locationLabel && (
        <>
          <RailHead>Miejsce</RailHead>
          <div className="rounded-md border border-line bg-bg px-3.5 py-2.5 font-serif text-label text-text-2">
            {locationLabel}
          </div>
        </>
      )}
    </aside>
  );
}

function RailHead({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 mt-5 flex items-center gap-2.5 font-ui text-[10.5px] font-bold uppercase tracking-[0.22em] text-ember first:mt-0 after:h-px after:flex-1 after:bg-line-soft after:content-['']">
      {children}
    </h3>
  );
}

function BigBar({
  label,
  value,
  pct,
  kind,
}: {
  label: string;
  value: string;
  pct: number;
  kind: "hp" | "mana" | "xp";
}) {
  return (
    <div className="mb-3">
      <div className="mb-1.5 flex justify-between text-label text-text-2">
        <span>{label}</span>
        <b className="font-mono font-medium text-text">{value}</b>
      </div>
      <div className="h-[7px] overflow-hidden rounded-[4px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
        <div
          className={cn(
            "h-full rounded-[4px] transition-[width] duration-500",
            kind === "hp" && "bg-gradient-to-r from-[#c14a2b] to-ember shadow-[0_0_9px_rgba(255,122,61,.55)]",
            kind === "mana" && "bg-mana",
            kind === "xp" && "bg-text-3",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
