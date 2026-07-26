// F-24 pasek akcji walki (#1236). Makieta: zar7-walka.html (actrow).
// Atak (primary) / Czar / Zbliż↔Cofnij / Obrona / Uciekaj. Composer prozy renderuje CombatView obok.
import {
  Sword,
  Sparkle,
  ArrowsInLineHorizontal,
  Shield,
  PersonSimpleRun,
  Megaphone,
  HandGrabbing,
  Eye,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

export function CombatActionBar({
  playerZone,
  disabled,
  hasMana,
  onAttack,
  onSpell,
  onMove,
  onDefense,
  onFlee,
  // #1476 — kit Wojownika-Zabijaki (tylko rasa Wyspiarze + archetyp warrior).
  isZabijaka,
  onThreat,
  onGrip,
  onDirty,
}: {
  playerZone: "engaged" | "ranged";
  disabled?: boolean;
  hasMana: boolean;
  onAttack: () => void;
  onSpell: () => void;
  onMove: () => void;
  onDefense: () => void;
  onFlee: () => void;
  isZabijaka?: boolean;
  onThreat?: () => void;
  onGrip?: () => void;
  onDirty?: () => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto px-3.5 pb-1 pt-2.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <ABtn variant="primary" icon={<Sword weight="fill" size={16} />} label="Atak" disabled={disabled} onClick={onAttack} />
      {hasMana && (
        <ABtn icon={<Sparkle size={16} />} label="Czar" disabled={disabled} onClick={onSpell} />
      )}
      <ABtn
        variant="move"
        icon={<ArrowsInLineHorizontal size={16} />}
        label={playerZone === "engaged" ? "Cofnij się" : "Zbliż się"}
        disabled={disabled}
        onClick={onMove}
      />
      {isZabijaka && (
        <>
          <ABtn variant="zabijaka" icon={<Megaphone size={16} />} label="Groźba" disabled={disabled} onClick={onThreat} />
          <ABtn variant="zabijaka" icon={<HandGrabbing size={16} />} label="Chwyt" disabled={disabled} onClick={onGrip} />
          <ABtn variant="zabijaka" icon={<Eye size={16} />} label="Brudny cios" disabled={disabled} onClick={onDirty} />
        </>
      )}
      <ABtn icon={<Shield size={16} />} label="Obrona" disabled={disabled} onClick={onDefense} />
      <ABtn variant="flee" icon={<PersonSimpleRun size={16} />} label="Uciekaj" disabled={disabled} onClick={onFlee} />
    </div>
  );
}

function ABtn({
  variant,
  icon,
  label,
  disabled,
  onClick,
}: {
  variant?: "primary" | "move" | "flee" | "zabijaka";
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-md border border-line bg-bg px-3.5 py-2.5 font-ui text-[13.5px] font-semibold text-text transition-colors disabled:opacity-40",
        variant === "primary" &&
          "border-transparent bg-gradient-to-br from-[#d1602c] to-ember text-white shadow-[0_0_14px_rgba(255,122,61,.35)]",
        variant === "move" && "border-line-ember text-ember-glow",
        variant === "flee" && "border-line-danger text-danger-glow",
        // #1476 — Zabijaka: morski akcent (kontrola pola/morale), odróżnia od ataku.
        variant === "zabijaka" && "border-[#3c6e8f] text-[#7fb8d8]",
      )}
    >
      {icon}
      {label}
    </button>
  );
}
