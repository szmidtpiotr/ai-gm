import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CircleNotch, Warning, BookOpen } from "@phosphor-icons/react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { TurnHistoryEntry, TurnHistoryPage } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE = 50;

// #1095 — czytnik zakończonej/zarchiwizowanej kampanii. Tylko do odczytu:
// nigdy nie wchodzi do gry, renderuje tury chronologicznie (najstarsze → najnowsze).
export default function CampaignHistory() {
  const { campaignId } = useParams();
  const cid = Number(campaignId);
  const navigate = useNavigate();

  const [turns, setTurns] = useState<TurnHistoryEntry[]>([]);
  const [title, setTitle] = useState("Historia");
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadPage = useCallback(
    async (off: number) => {
      setLoading(true);
      try {
        const data = await apiFetch<TurnHistoryPage>(
          `/campaigns/${cid}/turns-history?limit=${PAGE}&offset=${off}`,
        );
        setTitle(data.title || "Historia");
        setTotal(data.total_count || 0);
        setTurns((prev) => (off === 0 ? data.turns : [...prev, ...data.turns]));
        setOffset(off + (data.turns?.length ?? 0));
        setError(false);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    },
    [cid],
  );

  useEffect(() => {
    void loadPage(0);
  }, [loadPage]);

  const hasMore = offset < total;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5 border-b border-line-mech/30 pb-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line text-text-3">
          <BookOpen weight="fill" size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-serif text-title font-semibold text-text">
            {title}
          </div>
          <div className="font-ui text-micro text-text-3">Historia — tylko do odczytu</div>
        </div>
      </div>

      {loading && turns.length === 0 && (
        <div className="flex items-center justify-center gap-2 py-16 text-text-3">
          <CircleNotch className="animate-spin" size={22} />
          <span className="font-ui text-body">Ładowanie historii…</span>
        </div>
      )}

      {error && turns.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-line-danger bg-danger/10 px-4 py-3 text-danger-glow">
          <Warning size={20} />
          <span className="font-ui text-body">Nie udało się wczytać historii.</span>
        </div>
      )}

      {!loading && !error && turns.length === 0 && (
        <p className="py-10 text-center font-ui text-label text-text-3">
          Brak zapisanych tur w tej kampanii.
        </p>
      )}

      {turns.map((t, i) => (
        <TurnEntry key={`${t.turn_number}-${i}`} turn={t} />
      ))}

      {hasMore && (
        <div className="flex justify-center py-2">
          <Button variant="secondary" size="sm" onClick={() => loadPage(offset)} disabled={loading}>
            {loading ? <CircleNotch className="animate-spin" size={15} /> : null}
            Wczytaj starsze ({turns.length}/{total})
          </Button>
        </div>
      )}

      <div className="sticky bottom-2 mt-2 flex justify-center">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          ← Wróć do kampanii
        </Button>
      </div>
    </div>
  );
}

function cleanNarrative(raw: string): string {
  let narr = raw;
  try {
    const parsed = JSON.parse(raw);
    narr = parsed.narrative || parsed.text || raw;
  } catch {
    /* plain text */
  }
  return narr.replace(/【[^】]*】/g, "").trim();
}

function TurnEntry({ turn }: { turn: TurnHistoryEntry }) {
  return (
    <div className="flex flex-col gap-2">
      {turn.user_text && (
        <div className="flex justify-end">
          <div className="max-w-[82%] rounded-lg border-r-2 border-line-ember bg-player-card px-3.5 py-2.5 font-serif italic text-prose text-text">
            {turn.user_text}
          </div>
        </div>
      )}
      {turn.assistant_text && (
        <div className="flex justify-start">
          <div className="max-w-[88%] whitespace-pre-wrap rounded-lg border-l-2 border-line-ember bg-gm-bubble px-3.5 py-2.5 font-serif text-prose text-text">
            {cleanNarrative(turn.assistant_text)}
          </div>
        </div>
      )}
      <div className={cn("text-center font-mono text-[10px] text-text-3/70")}>
        — tura {turn.turn_number} —
      </div>
    </div>
  );
}
