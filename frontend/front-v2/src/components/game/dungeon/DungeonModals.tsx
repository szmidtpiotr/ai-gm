// FE16 loch (#1265) — rodzina modali lochu (L13 #682): porzucenie, wznowienie,
// śmierć-punkt kontrolny, ukończenie. Parytet z showDungeon{Abandon,Resume,Death}Modal
// + _showDungeonComplete. ŻAR: krew dla śmierci, żar/złoto dla ukończenia.
import {
  Skull,
  DoorOpen,
  ArrowUUpLeft,
  Crown,
  Package,
  HourglassMedium,
  Warning,
} from "@phosphor-icons/react";
import type { DungeonRun, LootLine } from "@/lib/dungeon";

function Backdrop({ children, testid }: { children: React.ReactNode; testid: string }) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-bg/88 p-6 backdrop-blur-sm"
      data-testid={testid}
    >
      <div className="w-full max-w-sm rounded-xl border border-line bg-surface p-5 shadow-modal">
        {children}
      </div>
    </div>
  );
}

// ── Porzucenie (mid-segment) ──────────────────────────────────────────────────

export function AbandonModal({
  run,
  busy,
  onCancel,
  onConfirm,
}: {
  run: DungeonRun | undefined;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dungeon = run?.dungeon_label || run?.dungeon_key || "lochu";
  return (
    <Backdrop testid="dungeon-abandon-modal">
      <div className="mb-2 flex items-center gap-2 font-serif text-body font-semibold text-text">
        <Warning weight="fill" size={18} className="text-danger" />
        Porzucić wyprawę?
      </div>
      <p className="mb-1 font-ui text-label text-text-2">
        Opuszczasz {dungeon} w połowie segmentu.
      </p>
      <p className="mb-4 font-ui text-micro text-text-3">
        Stan wróci do ostatniego punktu kontrolnego, a loch dostanie 50% odnowy.
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="flex-1 rounded-lg border border-line px-3 py-2 font-ui text-label text-text-2 hover:text-text disabled:opacity-50"
        >
          Zostań
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-line-danger bg-danger/[0.1] px-3 py-2 font-ui text-label font-semibold text-danger-glow hover:bg-danger/[0.18] disabled:opacity-50"
        >
          <DoorOpen weight="fill" size={16} /> Porzuć
        </button>
      </div>
    </Backdrop>
  );
}

// ── Wznowienie (z pickera, E22) ───────────────────────────────────────────────

export function ResumeModal({
  run,
  busy,
  onContinue,
  onAbandon,
}: {
  run: DungeonRun;
  busy: boolean;
  onContinue: () => void;
  onAbandon: () => void;
}) {
  const total = Object.keys(run.graph?.nodes || {}).length || "?";
  const room = run.current_room || 1;
  return (
    <Backdrop testid="dungeon-resume-modal">
      <div className="mb-2 flex items-center gap-2 font-serif text-body font-semibold text-text">
        <ArrowUUpLeft weight="fill" size={18} className="text-ember-glow" />
        Niedokończona wyprawa
      </div>
      <p className="mb-1 font-ui text-label text-text">
        {run.dungeon_label || run.dungeon_key || "Loch"}
      </p>
      <p className="mb-4 font-ui text-micro text-text-3">
        Komnata {room} z {total} — masz otwartą ekspedycję.
      </p>
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={onContinue}
          disabled={busy}
          className="flex items-center justify-center gap-1.5 rounded-lg border border-line-ember bg-ember/[0.1] px-3 py-2.5 font-ui text-label font-semibold text-ember-glow hover:bg-ember/[0.18] disabled:opacity-50"
        >
          <ArrowUUpLeft weight="fill" size={16} /> Kontynuuj
        </button>
        <button
          type="button"
          onClick={onAbandon}
          disabled={busy}
          className="flex items-center justify-center gap-1.5 rounded-lg border border-line px-3 py-2 font-ui text-label text-text-2 hover:text-danger-glow disabled:opacity-50"
        >
          <DoorOpen size={15} /> Porzuć
        </button>
      </div>
    </Backdrop>
  );
}

// ── Śmierć w lochu — punkt kontrolny (L13) ────────────────────────────────────

export function DeathCheckpointModal({
  run,
  cooldownUntil,
  busy,
  onExit,
}: {
  run: DungeonRun | undefined;
  cooldownUntil: string | null | undefined;
  busy: boolean;
  onExit: () => void;
}) {
  const hasCheckpoint =
    Array.isArray(run?.checkpoints) && (run?.checkpoints?.length ?? 0) > 1;
  const cooldownTxt = cooldownUntil
    ? cooldownHours(cooldownUntil)
    : "";
  return (
    <Backdrop testid="dungeon-death-modal">
      <div className="mb-2 flex items-center gap-2 font-serif text-title-sm font-semibold text-danger-glow">
        <Skull weight="fill" size={22} className="text-danger" />
        Poległeś w lochu
      </div>
      <p className="mb-1.5 font-ui text-label text-text-2">
        {hasCheckpoint
          ? "Stan przywrócony do ostatniego bossa (punkt kontrolny)."
          : "Stan przywrócony do momentu wejścia do lochu."}
      </p>
      <p className="mb-1.5 font-ui text-micro text-text-3">
        XP i złoto zdobyte po punkcie kontrolnym utracone.
      </p>
      {cooldownTxt && (
        <p className="mb-4 flex items-center gap-1.5 font-ui text-micro text-text-3">
          <HourglassMedium size={13} /> Cooldown lochu: {cooldownTxt}
        </p>
      )}
      <button
        type="button"
        onClick={onExit}
        disabled={busy}
        autoFocus
        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-line-danger bg-danger/[0.1] px-3 py-2.5 font-ui text-label font-semibold text-danger-glow hover:bg-danger/[0.18] disabled:opacity-50"
      >
        <DoorOpen weight="fill" size={16} /> Opuść loch
      </button>
    </Backdrop>
  );
}

// ── Ukończenie lochu (parytet _showDungeonComplete) ──────────────────────────

export function DungeonCompleteModal({
  run,
  loot,
  busy,
  onExit,
}: {
  run: DungeonRun | undefined;
  loot: LootLine[];
  busy: boolean;
  onExit: () => void;
}) {
  return (
    <Backdrop testid="dungeon-complete-modal">
      <Crown weight="fill" size={56} className="mx-auto mb-2 text-gold drop-shadow-[0_0_20px_rgba(232,193,90,.5)]" />
      <div className="mb-3 text-center font-serif text-title-sm font-semibold text-text">
        Loch ukończony!
      </div>
      {loot.length ? (
        <ul className="mb-3 flex flex-col gap-1">
          {loot.map((l, i) => (
            <li key={i} className="flex items-center gap-2 font-ui text-label text-text">
              <Package weight="fill" size={15} className="text-gold" />
              {l.label || l.key || "?"} ×{l.quantity || 1}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-3 text-center font-ui text-label text-text-3">
          Brak łupów z bossa.
        </p>
      )}
      {run?.cooldown_hours ? (
        <p className="mb-3 flex items-center justify-center gap-1.5 font-ui text-micro text-text-3">
          <HourglassMedium size={13} /> Następna ekspedycja za {run.cooldown_hours}h
        </p>
      ) : null}
      <button
        type="button"
        onClick={onExit}
        disabled={busy}
        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-line-mech bg-gold/[0.1] px-3 py-2.5 font-ui text-label font-semibold text-gold hover:bg-gold/[0.18] disabled:opacity-50"
      >
        <DoorOpen weight="fill" size={16} /> Wyjdź z łupem
      </button>
    </Backdrop>
  );
}

function cooldownHours(until: string): string {
  const t = new Date(until).getTime();
  const hours = Math.round((t - Date.now()) / 3_600_000);
  return hours > 0 ? `${hours}h` : "zakończony";
}
