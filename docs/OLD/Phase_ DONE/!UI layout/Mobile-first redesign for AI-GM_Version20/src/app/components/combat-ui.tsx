import { useState } from "react";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { Sword, Footprints, Shield as ShieldIcon, Check, X } from "lucide-react";

interface Character {
  name: string;
  hp: number;
  maxHp: number;
  level: number;
  dex: number;
}

interface Enemy {
  name: string;
  hp: number;
  maxHp: number;
  level: number;
  armor?: number;
}

interface CombatLog {
  id: string;
  content: string;
  type: string;
  rollResult?: {
    dice: string;
    result: number;
    modifier?: number;
    total: number;
  };
}

interface CombatUIProps {
  character: Character;
  enemy: Enemy;
  playerTurn: boolean;
  onAttack: () => void;
  onFlee: () => void;
  disabled?: boolean;
  combatLogs?: CombatLog[];
}

export function CombatUI({
  character,
  enemy,
  playerTurn,
  onAttack,
  onFlee,
  disabled = false,
  combatLogs = [],
}: CombatUIProps) {
  const [showLogs, setShowLogs] = useState(false);

  const enemyHpPercent = (enemy.hp / enemy.maxHp) * 100;
  const playerHpPercent = (character.hp / character.maxHp) * 100;

  const playerAc = 10 + Math.floor((character.dex - 10) / 2);
  const enemyAc = enemy.armor || 10 + Math.floor((enemy.level) / 2);

  return (
    <div
      id="combat-ui"
      className="rounded-xl border border-accent/20 bg-[var(--panel)]/60 text-foreground shadow-[0_0_20px_rgba(183,122,43,0.1)] overflow-hidden flex flex-col"
    >
      {/* Header */}
      <div
        className="flex justify-between items-center px-4 py-3 border-b border-accent/10 bg-[var(--panel-2)]/40 cursor-pointer hover:bg-[var(--panel-2)]/60 transition-colors"
        onClick={() => setShowLogs(!showLogs)}
      >
        <h3 className="font-semibold text-accent-light flex items-center gap-2">
          <Sword className="size-4" />
          Walka
          <span className="text-xs font-normal text-muted bg-[var(--panel)]/60 px-2 py-0.5 rounded-full border border-accent/20">
            {showLogs ? 'Ukryj logi' : 'Pokaż logi'}
          </span>
        </h3>
        <span className="text-xs text-muted">
          Tura: {playerTurn ? "Gracz" : "Przeciwnik"}
        </span>
      </div>

      {/* Engine Logs */}
      {showLogs && combatLogs.length > 0 && (
        <div className="px-4 py-3 border-b border-accent/10 bg-[var(--panel)]/30">
          <div className="text-xs font-semibold tracking-wider text-accent/80 uppercase mb-2">
            Historia Walki
          </div>
          <div className="space-y-2">
            {combatLogs.map((log, i) => {
              const isPlayerAction = log.type === "roll" || log.content.includes("Trafiłeś") || log.content.includes("Chybiłeś");
              const isHit = log.content.includes("rafia") || log.content.includes("Trafiłeś") || log.content.includes("obrażeń");
              const isMiss = log.content.includes("chybił") || log.content.includes("Chybiłeś");

              return (
                <div key={log.id || i} className="text-xs">
                  {log.type === "roll" ? (
                    <div className="bg-[var(--panel-2)]/40 rounded-md p-2 border border-accent/10">
                      <div className="font-semibold flex items-center gap-1 text-accent-light">
                        <Sword className="size-3" /> ATAK GRACZA → {enemy.name}
                      </div>
                      <div className="text-muted flex items-center gap-1 mt-1">
                        Rzut: {log.rollResult?.total} vs AC {enemyAc} → {log.rollResult?.total && log.rollResult.total >= enemyAc ? <><Check className="size-3 text-ok"/> <span className="text-ok">TRAFIENIE</span></> : <><X className="size-3 text-danger"/> <span className="text-danger">PUDŁO</span></>}
                      </div>
                    </div>
                  ) : (
                    <div className="bg-[var(--panel-2)]/40 rounded-md p-2 border border-accent/10">
                      {!isPlayerAction && (
                         <div className="font-semibold flex items-center gap-1 text-accent/80">
                           <Sword className="size-3" /> ATAK WROGA — {enemy.name}
                         </div>
                      )}
                      <div className={isHit ? "text-ok mt-0.5" : isMiss ? "text-danger mt-0.5" : "text-muted mt-0.5"}>
                        {log.content}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* HP Bars */}
      <div className="px-4 py-3 space-y-4 bg-[var(--panel)]/20">
        {/* Player */}
        <div className="space-y-1">
          <div className="flex justify-between items-end">
            <span className="font-semibold text-foreground">{character.name}</span>
            <span className="text-xs text-muted font-medium">INI 13</span>
          </div>
          <div className="flex justify-between items-center text-xs text-muted">
            <span>HP</span>
            <span>{character.hp} / {character.maxHp} · DEF {playerAc}</span>
          </div>
          <div className="h-2 w-full bg-[#1a1410] rounded-full overflow-hidden border border-accent/20">
            <div
              className="h-full bg-gradient-to-r from-[#15803d] to-[#22c55e] rounded-full transition-all duration-300"
              style={{ width: `${Math.max(0, Math.min(100, playerHpPercent))}%` }}
            />
          </div>
        </div>

        {/* Enemy */}
        <div className="space-y-1">
          <div className="flex justify-between items-end">
            <span className="font-semibold text-foreground">{enemy.name}</span>
            <span className="text-xs text-muted font-medium">INI 17</span>
          </div>
          <div className="flex justify-between items-center text-xs text-muted">
            <span>HP</span>
            <span>{enemy.hp} / {enemy.maxHp} · DEF {enemyAc}</span>
          </div>
          <div className="h-2 w-full bg-[#1a1410] rounded-full overflow-hidden border border-accent/20">
            <div
              className="h-full bg-gradient-to-r from-[#b45309] to-[#f59e0b] rounded-full transition-all duration-300"
              style={{ width: `${Math.max(0, Math.min(100, enemyHpPercent))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="px-4 py-3 bg-[var(--panel-2)]/40 border-t border-accent/10">
        <div id="combat-actions" className="grid grid-cols-2 gap-3">
          <Button
            id="combat-attack-button"
            onClick={onAttack}
            disabled={!playerTurn || disabled}
            className="w-full bg-accent hover:bg-accent-light text-[var(--bg)] font-semibold disabled:opacity-40"
          >
            <Sword className="size-4 mr-2" />
            Atak
          </Button>
          <Button
            id="combat-flee-button"
            onClick={onFlee}
            disabled={!playerTurn || disabled}
            variant="outline"
            className="w-full border-accent/30 text-muted hover:text-accent hover:bg-[var(--panel)]/40 font-semibold disabled:opacity-40"
          >
            <Footprints className="size-4 mr-2" />
            Ucieczka
          </Button>
        </div>
      </div>
    </div>
  );
}
