// WL-5 (#1504/#1505) — wskaźnik stanu pływu na wybrzeżu (Wybrzeże Łez).
// Pokazuje się TYLKO gdy bohater stoi na hexie wybrzeża (on_coast). Licznik godzin
// do zmiany widoczny wyłącznie z Tabliczką pływów (has_board); bez niej — zachęta do kupna.
import { Waves, Warning, Clock } from "@phosphor-icons/react";
import { useTide } from "@/hooks/useTides";

export function TideIndicator({
  campaignId,
  characterId,
}: {
  campaignId: number | undefined;
  characterId: number | undefined;
}) {
  const tide = useTide(campaignId, characterId);
  const t = tide.data;
  if (!t || !t.on_coast) return null;

  const flood = t.is_flood;
  // Kolor: przypływ = groźny (amber/czerwony), odpływ = spokojny (morski).
  const tone = flood
    ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
    : "border-cyan-500/40 bg-cyan-500/10 text-cyan-200";

  return (
    <div
      className={`mx-3 mb-2 flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${tone}`}
      role="status"
    >
      <Waves size={18} weight="bold" className="shrink-0" />
      <div className="flex flex-1 flex-wrap items-center gap-x-2 gap-y-0.5">
        <span className="font-semibold">{t.phase_label}</span>
        <span className="opacity-80">
          {flood ? "— płycizna zalana, nie wejdziesz" : "— płycizna przejezdna"}
        </span>
        {t.on_shallows && flood && (
          <span className="inline-flex items-center gap-1 font-semibold text-amber-300">
            <Warning size={14} weight="fill" /> Uciekaj z mielizny!
          </span>
        )}
        {t.has_board && t.hours_to_change != null ? (
          <span className="inline-flex items-center gap-1 opacity-90">
            <Clock size={14} weight="bold" />
            {t.next_phase_label} za {t.hours_to_change} h
          </span>
        ) : (
          <span className="opacity-60 italic">
            Bez Tabliczki pływów nie wiesz, ile do zmiany
          </span>
        )}
      </div>
    </div>
  );
}
