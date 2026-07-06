import { useEffect, useState } from "react";
import { formatCountdown } from "@/lib/multiplayer";
import { useMpStore } from "@/store/mpStore";

// FE15 (#1264) — pasek statusu rundy (F-71): odliczanie deadline'u + licznik zgłoszeń
// + tekst stanu. Czyta mpStore (poller). Zegar tyka lokalnie z deadline'u.
export function MpStatusBar() {
  const status = useMpStore((s) => s.status);
  const [, tick] = useState(0);

  // Odliczanie: przerysuj co sekundę gdy jest deadline.
  useEffect(() => {
    if (!status?.deadline) return;
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [status?.deadline]);

  const submitted = status?.submitted_count ?? 0;
  const total = status?.total_players ?? 0;
  const countdown = formatCountdown(status?.deadline ?? null);

  let state = "";
  if (status) {
    if (status.status === "narrating") state = "GM pisze…";
    else if (status.my_submitted && total > 0)
      state = `czekasz na ${total - submitted} z ${total}`;
    else if (submitted > 0) state = `${submitted} z ${total} oddało`;
  }

  return (
    <div className="flex items-center gap-2 border-b border-line-ember bg-[rgba(255,122,61,.06)] px-3.5 py-1.5">
      <span className="min-w-[58px] font-mono text-body font-semibold text-ember-glow">
        {countdown}
      </span>
      {total > 0 && (
        <span className="rounded-pill bg-[rgba(255,255,255,.06)] px-2 py-0.5 font-mono text-micro text-text-2">
          {submitted}/{total}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate font-ui text-micro text-text-3">
        {state}
      </span>
    </div>
  );
}
