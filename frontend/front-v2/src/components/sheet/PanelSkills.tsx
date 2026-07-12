// F-54 · Umiejętności — TYLKO wyuczone (ranga ≥ 1) + opisy (tap rozwija).
// Pipsy rang (sufit 3) + bonus, ★ = biegłość (+2). Makieta: zar2-postac.html.
import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { readSkills, PROFICIENCY_RANK } from "@/lib/sheet";
import { usePublicSkills } from "@/hooks/useSheetData";
import type { HeroSheet } from "@/lib/types";
import { SecHead, PanelScroll } from "./sheetUi";

export function PanelSkills({ sheet }: { sheet: HeroSheet | undefined }) {
  // Tylko umiejętności, które bohater faktycznie rozwinął (ranga ≥ 1) —
  // sheet.skills trzyma cały katalog z rangami 0, których nie pokazujemy.
  const skills = readSkills(sheet).filter((s) => s.rank >= 1);
  const catalog = usePublicSkills();
  const descOf = (key: string) =>
    catalog.data?.find((c) => c.key === key)?.description ?? null;
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

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
          {skills.map((s) => {
            const desc = descOf(s.key);
            const isOpen = open.has(s.key);
            return (
              <div
                key={s.key}
                className="overflow-hidden rounded-md border border-line-soft bg-surface"
              >
                <button
                  type="button"
                  onClick={() => desc && toggle(s.key)}
                  className={cn(
                    "flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left",
                    desc && "transition-colors hover:bg-inset",
                  )}
                  aria-expanded={desc ? isOpen : undefined}
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
                  {desc && (
                    <CaretDown
                      size={13}
                      className={cn(
                        "shrink-0 text-text-3 transition-transform",
                        isOpen && "rotate-180",
                      )}
                    />
                  )}
                </button>
                {desc && isOpen && (
                  <p className="border-t border-line-soft bg-bg px-3.5 py-2.5 font-serif text-micro leading-relaxed text-text-2">
                    {desc}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </PanelScroll>
  );
}
