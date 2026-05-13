import { Progress } from "./ui/progress";
import { Heart, Shield, Zap } from "lucide-react";

interface CharacterStatsProps {
  hp: number;
  maxHp: number;
  str: number;
  dex: number;
  con: number;
  int: number;
  wis: number;
  cha: number;
  lck: number;
  level: number;
  compact?: boolean;
}

export function CharacterStats({
  hp,
  maxHp,
  str,
  dex,
  con,
  int: intelligence,
  wis,
  cha,
  lck,
  level,
  compact = false,
}: CharacterStatsProps) {
  const hpPercent = (hp / maxHp) * 100;
  const hpColor =
    hpPercent > 60
      ? "var(--hp-high)"
      : hpPercent > 30
        ? "var(--hp-mid)"
        : "var(--hp-low)";

  if (compact) {
    return (
      <div id="character-stats-compact" className="space-y-2">
        <div className="flex items-center gap-2">
          <Heart className="size-4 text-primary" />
          <div className="flex-1">
            <Progress value={hpPercent} className="h-2" />
          </div>
          <span className="text-sm tabular-nums">
            {hp}/{maxHp}
          </span>
        </div>
        <div className="flex gap-1 text-xs">
          <StatPill label="STR" value={str} />
          <StatPill label="DEX" value={dex} />
          <StatPill label="CON" value={con} />
          <StatPill label="INT" value={intelligence} />
          <StatPill label="WIS" value={wis} />
          <StatPill label="CHA" value={cha} />
          <StatPill label="LCK" value={lck} />
        </div>
      </div>
    );
  }

  return (
    <div id="character-stats" className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="size-5 text-primary" />
          <span className="text-sm text-muted-foreground">Poziom {level}</span>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <Heart className="size-4" style={{ color: hpColor }} />
            <span>Punkty Życia</span>
          </div>
          <span className="tabular-nums" style={{ color: hpColor }}>
            {hp}/{maxHp}
          </span>
        </div>
        <Progress value={hpPercent} className="h-3" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <StatBlock label="STR" value={str} />
        <StatBlock label="DEX" value={dex} />
        <StatBlock label="CON" value={con} />
        <StatBlock label="INT" value={intelligence} />
        <StatBlock label="WIS" value={wis} />
        <StatBlock label="CHA" value={cha} />
        <StatBlock label="LCK" value={lck} />
      </div>
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1 rounded bg-muted px-1.5 py-0.5 text-center tabular-nums">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="text-xs">{value}</div>
    </div>
  );
}

function StatBlock({ label, value }: { label: string; value: number }) {
  const modifier = Math.floor((value - 10) / 2);
  const modifierStr = modifier >= 0 ? `+${modifier}` : modifier.toString();

  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="flex items-baseline justify-between">
        <span className="text-2xl tabular-nums">{value}</span>
        <span className="text-sm text-primary">{modifierStr}</span>
      </div>
    </div>
  );
}
