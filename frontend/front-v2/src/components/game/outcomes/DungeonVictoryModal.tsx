// FE10 (#1237) — F-29 Ekran zwycięstwa (loch) (makieta zar7-zwyciestwo). Laur +
// tytuł + statystyki + akcje: zejdź głębiej / wyjdź z łupem. Wywoływany
// zdarzeniem: dungeon_run.boss_choice_pending po pokonaniu bossa.
import { Crown, Star, Coins, Sword, Timer, Stairs, TreasureChest } from "@phosphor-icons/react";

export function DungeonVictoryModal({
  title,
  subtitle,
  xpGain,
  goldGain,
  defeated,
  rooms,
  busy,
  onDeeper,
  onExit,
}: {
  title: string;
  subtitle: string;
  xpGain: number;
  goldGain: number;
  defeated: number;
  rooms: number;
  busy: boolean;
  onDeeper: () => void;
  onExit: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center p-6 text-center"
      style={{
        background:
          "radial-gradient(75% 55% at 50% 26%, rgba(232,193,90,.18), transparent 62%), #0c0906",
      }}
      data-testid="modal-dungeon-victory"
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "conic-gradient(from 0deg at 50% 30%, transparent, rgba(232,193,90,.06) 8%, transparent 16%, rgba(232,193,90,.05) 24%, transparent 32%, rgba(232,193,90,.06) 40%, transparent 48%)",
        }}
      />
      <div className="relative z-[2] w-full max-w-[420px]">
        <Crown weight="fill" size={80} className="mx-auto text-gold drop-shadow-[0_0_28px_rgba(232,193,90,.6)]" />
        <div className="mt-3 font-ui text-[11px] font-bold uppercase tracking-[0.32em] text-gold-glow">
          Boss pokonany
        </div>
        <div className="mt-1.5 font-serif text-title-lg font-semibold text-text">{title}</div>
        <div className="mt-2 font-serif text-[15px] italic text-text-2">{subtitle}</div>

        <div className="my-[22px] flex overflow-hidden rounded-lg border border-line-mech bg-[#1e1811] font-mono">
          <St icon={<Star weight="fill" size={17} />} v={`+${xpGain}`} k="Doświadczenie" tone="success" />
          <St icon={<Coins weight="fill" size={17} />} v={`+${goldGain}`} k="Złoto" tone="gold" />
          <St icon={<Sword weight="fill" size={17} />} v={String(defeated)} k="Pokonanych" />
          <St icon={<Timer weight="fill" size={17} />} v={String(rooms)} k="Pokoi" />
        </div>

        <div className="mt-[22px] flex flex-col gap-[9px]">
          <button
            type="button"
            disabled={busy}
            onClick={onDeeper}
            data-testid="dungeon-deeper"
            className="flex items-center gap-3 rounded-[13px] border border-line-mech bg-gradient-to-br from-[rgba(232,193,90,.12)] to-[#1e1811] px-4 py-3.5 text-left font-ui text-[14.5px] font-semibold text-text transition-colors hover:border-gold disabled:opacity-60"
          >
            <Stairs weight="fill" size={20} className="flex-none text-gold-glow" />
            <span>
              <span className="block text-gold-glow">Zejdź głębiej</span>
              <span className="mt-px block font-ui text-[11.5px] font-normal text-text-3">
                Kolejne piętro · silniejsi wrogowie, lepszy łup
              </span>
            </span>
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onExit}
            data-testid="dungeon-exit"
            className="flex items-center gap-3 rounded-[13px] border border-line bg-[#1e1811] px-4 py-3.5 text-left font-ui text-[14.5px] font-semibold text-text transition-colors hover:border-gold disabled:opacity-60"
          >
            <TreasureChest weight="fill" size={20} className="flex-none text-ember-glow" />
            <span>
              <span className="block">Wyjdź z łupem</span>
              <span className="mt-px block font-ui text-[11.5px] font-normal text-text-3">
                Zabierz zdobycz i wróć na powierzchnię
              </span>
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}

function St({
  icon,
  v,
  k,
  tone,
}: {
  icon: React.ReactNode;
  v: string;
  k: string;
  tone?: "success" | "gold";
}) {
  return (
    <div className="flex-1 border-r border-line-soft px-1.5 py-[13px] last:border-r-0">
      <span className="text-gold">{icon}</span>
      <div
        className={
          "mt-1 text-[17px] font-semibold " +
          (tone === "success" ? "text-success" : tone === "gold" ? "text-gold" : "text-text")
        }
      >
        {v}
      </div>
      <div className="mt-0.5 font-ui text-[8.5px] uppercase tracking-[0.1em] text-text-3">{k}</div>
    </div>
  );
}
