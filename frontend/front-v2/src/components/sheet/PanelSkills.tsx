// F-54 · Umiejętności — pipsy rang (sufit 3) + bonus, ★ = biegłość (+2).
// Makieta: zar2-postac.html sekcja Umiejętności.
import { cn } from "@/lib/utils";
import { readSkills, PROFICIENCY_RANK } from "@/lib/sheet";
import type { HeroSheet } from "@/lib/types";
import { SecHead, PanelScroll } from "./sheetUi";

export function PanelSkills({ sheet }: { sheet: HeroSheet | undefined }) {
  const skills = readSkills(sheet);

  return (
    <PanelScroll>
      <SecHead>
        Umiejętności <span className="ml-1 font-normal normal-case tracking-normal text-text-3">★ = biegłość (+2)</span>
      </SecHead>
      {skills.length === 0 ? (
        <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
          Brak wyuczonych umiejętności.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2 lg:gap-x-4">
          {skills.map((s) => (
            <div
              key={s.key}
              className="flex items-center gap-2.5 rounded-md border border-line-soft bg-surface px-3.5 py-2.5"
            >
              <span className="flex-1 text-label font-medium text-text">
                {s.label}
                {s.proficient && <span className="ml-1.5 align-[2px] text-[10px] text-ember">★</span>}
              </span>
              <span className="font-mono text-[10px] tracking-wide text-text-3">{s.stat}</span>
              <div className="flex gap-1">
                {Array.from({ length: PROFICIENCY_RANK }).map((_, i) => (
                  <span
                    key={i}
                    className={cn(
                      "h-2 w-2 rounded-full",
                      i < s.rank
                        ? "bg-ember shadow-[0_0_6px_rgba(255,122,61,.6)]"
                        : "bg-inset shadow-[inset_0_0_0_1px_var(--line)]",
                    )}
                  />
                ))}
              </div>
              <span className="w-9 text-right font-mono text-label font-medium text-ember-glow">
                {(s.bonus >= 0 ? "+" : "") + s.bonus}
              </span>
            </div>
          ))}
        </div>
      )}
    </PanelScroll>
  );
}
