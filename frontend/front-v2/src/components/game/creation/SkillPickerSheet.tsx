// F-11b (#1523) — wybór umiejętności do zamiany w kreatorze.
// Zastępuje natywny <select>, który był jedynym niestylowanym elementem ŻAR-a
// (jasne menu systemowe na ciemnym UI) i nie mieścił opisu — gracz wybierał
// „Dochodzenie" nie wiedząc, co ono robi.
//
// Bottom-sheet na mobile / panel z prawej na desktopie (ten sam `Sheet` co reszta
// gry), z wyszukiwarką i grupowaniem po cesze wiodącej. Opis z katalogu
// (`game_config_skills.description`) widoczny przy każdej pozycji.
import { useMemo, useState } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { STAT_META, type StatKey, type SkillRow } from "@/lib/creation";
import { cn } from "@/lib/utils";

/** Kolejność sekcji = kolejność cech w karcie postaci. Nieznana cecha → „Inne". */
const STAT_ORDER: StatKey[] = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];

function normalize(s: string): string {
  // Gracze mobilni piszą bez ogonków — „skradanie" musi znaleźć „Skradanie",
  // a „przetrwanie" → „Przetrwanie" niezależnie od diakrytyków w obie strony.
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ł/g, "l");
}

export function SkillPickerSheet({
  open,
  onOpenChange,
  currentLabel,
  candidates,
  onPick,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** Nazwa umiejętności, którą zamieniamy — tytuł arkusza. */
  currentLabel: string;
  candidates: SkillRow[];
  onPick: (skillKey: string) => void;
}) {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = normalize(query.trim());
    const matched = q
      ? candidates.filter(
          (c) => normalize(c.label).includes(q) || normalize(c.hint || "").includes(q),
        )
      : candidates;
    const byStat = new Map<string, SkillRow[]>();
    for (const row of matched) {
      const stat = STAT_ORDER.includes(row.stat as StatKey) ? row.stat : "—";
      const list = byStat.get(stat) ?? [];
      list.push(row);
      byStat.set(stat, list);
    }
    const ordered: Array<[string, SkillRow[]]> = [];
    for (const stat of STAT_ORDER) {
      const list = byStat.get(stat);
      if (list?.length) ordered.push([stat, list]);
    }
    const rest = byStat.get("—");
    if (rest?.length) ordered.push(["—", rest]);
    return ordered;
  }, [candidates, query]);

  const total = groups.reduce((n, [, list]) => n + list.length, 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title={`Zamień: ${currentLabel}`}>
        <div className="sticky top-0 z-10 -mx-4 mb-3 border-b border-line-soft bg-surface px-4 pb-3">
          <div className="flex items-center gap-2 rounded-md border border-line bg-inset px-3 py-2 focus-within:border-line-ember">
            <MagnifyingGlass size={16} className="shrink-0 text-text-3" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Szukaj umiejętności…"
              aria-label="Szukaj umiejętności"
              className="min-w-0 flex-1 bg-transparent font-ui text-label text-text placeholder:text-text-3 focus:outline-none"
            />
          </div>
          <p className="mt-1.5 font-ui text-micro text-text-3">
            {total === 0
              ? "Nic nie pasuje do wyszukiwania."
              : `${total} do wyboru · pogrupowane wedle cechy`}
          </p>
        </div>

        <div className="flex flex-col gap-4 pb-2">
          {groups.map(([stat, list]) => (
            <section key={stat}>
              <h3 className="mb-1.5 flex items-center gap-2 font-ui text-[10px] font-bold uppercase tracking-[0.18em] text-ember after:h-px after:flex-1 after:bg-line-soft after:content-['']">
                {stat}
                {STAT_META[stat as StatKey] && (
                  <span className="font-medium normal-case tracking-normal text-text-3">
                    · {STAT_META[stat as StatKey].name}
                  </span>
                )}
              </h3>
              <div className="flex flex-col gap-1.5">
                {list.map((row) => (
                  <button
                    key={row.key}
                    type="button"
                    onClick={() => {
                      onPick(row.key);
                      setQuery("");
                    }}
                    className={cn(
                      "w-full rounded-md border border-line bg-bg px-3.5 py-2.5 text-left",
                      "transition-colors hover:border-line-ember hover:bg-ember/[0.04]",
                      "focus:border-line-ember focus:outline-none",
                    )}
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="font-ui text-label font-semibold text-text">
                        {row.label}
                      </span>
                      <span className="font-mono text-micro text-text-3">{row.stat}</span>
                    </span>
                    {row.hint && (
                      <span className="mt-0.5 block font-serif text-micro leading-relaxed text-text-2">
                        {row.hint}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
