// FE14 (#1263 / F-44) — paleta komend wg makiety zar9-komendy.html.
// Otwierana Ctrl+/ (lub Cmd+/) i ikoną w composerze. Szukajka + grupy
// (Kości i testy / Nawigacja / Odpoczynek) + skróty klawiszowe + nawigacja ↑/↓/Enter/Esc.
import { useEffect, useMemo, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Backpack,
  Campfire,
  Cube,
  DiceFive,
  Hourglass,
  MagnifyingGlass,
  MapTrifold,
  Shield,
  type Icon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore, type GameTab } from "@/store/appStore";

interface Command {
  id: string;
  group: string;
  icon: Icon;
  fillIcon?: boolean;
  title: string;
  subtitle?: string;
  keyLabel: string;
  /** litera skrótu (gdy paleta zamknięta, poza polem tekstowym). */
  hotkey?: string;
  /** tekst wstawiany do composera (komendy /…). */
  prefill?: string;
  /** przełączenie zakładki gry (nawigacja). */
  tab?: GameTab;
  /** strukturalna akcja chipu — wysyłana przez setComposerPrefill jako akcja (np. WAIT:open). */
  action?: string;
}

const COMMANDS: Command[] = [
  {
    id: "roll",
    group: "Kości i testy",
    icon: Cube,
    fillIcon: true,
    title: "Rzuć kością",
    subtitle: "/roll 1d20+5",
    keyLabel: "/roll",
    prefill: "/roll 1d20+5",
  },
  {
    id: "test",
    group: "Kości i testy",
    icon: DiceFive,
    title: "Test cechy",
    subtitle: "Rzut na wybraną cechę",
    keyLabel: "/test",
    prefill: "/test ",
  },
  {
    id: "character",
    group: "Nawigacja",
    icon: Shield,
    title: "Karta postaci",
    keyLabel: "C",
    hotkey: "c",
    tab: "character",
  },
  {
    id: "inventory",
    group: "Nawigacja",
    icon: Backpack,
    title: "Ekwipunek",
    keyLabel: "E",
    hotkey: "e",
    tab: "inventory",
  },
  {
    id: "map",
    group: "Nawigacja",
    icon: MapTrifold,
    title: "Mapa świata",
    keyLabel: "M",
    hotkey: "m",
    tab: "map",
  },
  {
    id: "rest",
    group: "Odpoczynek",
    icon: Campfire,
    title: "Krótki odpoczynek",
    subtitle: "Odzyskaj część HP",
    keyLabel: "/rest",
    prefill: "/rest",
  },
  {
    id: "wait",
    group: "Odpoczynek",
    icon: Hourglass,
    title: "Czekaj",
    subtitle: "Przesuń czas do wybranej pory",
    keyLabel: "/wait",
    action: "WAIT:open",
  },
];

function isEditableTarget(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || node.isContentEditable;
}

export function CommandPalette() {
  const open = useAppStore((s) => s.paletteOpen);
  const closePalette = useAppStore((s) => s.closePalette);
  const togglePalette = useAppStore((s) => s.togglePalette);
  const setGameTab = useAppStore((s) => s.setGameTab);
  const setComposerPrefill = useAppStore((s) => s.setComposerPrefill);
  const openWait = useAppStore((s) => s.openWait);

  const [query, setQuery] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filtruj po tytule / podtytule / skrócie.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COMMANDS;
    return COMMANDS.filter((c) =>
      `${c.title} ${c.subtitle ?? ""} ${c.keyLabel}`.toLowerCase().includes(q),
    );
  }, [query]);

  // Grupy w kolejności pierwszego wystąpienia.
  const groups = useMemo(() => {
    const out: { name: string; items: Command[] }[] = [];
    for (const c of filtered) {
      let g = out.find((x) => x.name === c.group);
      if (!g) {
        g = { name: c.group, items: [] };
        out.push(g);
      }
      g.items.push(c);
    }
    return out;
  }, [filtered]);

  // Reset przy otwarciu; auto-focus pola.
  useEffect(() => {
    if (open) {
      setQuery("");
      setSel(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  function run(cmd: Command) {
    closePalette();
    if (cmd.tab) {
      setGameTab(cmd.tab);
    } else if (cmd.action === "WAIT:open") {
      openWait();
    } else if (cmd.prefill) {
      setComposerPrefill(cmd.prefill);
    }
  }

  // Globalne skróty: Ctrl/Cmd+/ toggle; pojedyncze litery gdy paleta zamknięta i
  // fokus poza polem tekstowym (skróty nawigacyjne C/E/M).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        togglePalette();
        return;
      }
      if (open || e.ctrlKey || e.metaKey || e.altKey) return;
      if (isEditableTarget(e.target)) return;
      const hit = COMMANDS.find((c) => c.hotkey && c.hotkey === e.key.toLowerCase());
      if (hit) {
        e.preventDefault();
        run(hit);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onInputKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSel((s) => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSel((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[sel];
      if (cmd) run(cmd);
    }
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && closePalette()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[60] bg-black/[.66] animate-fade-in" />
        <DialogPrimitive.Content
          aria-label="Paleta komend"
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="fixed left-1/2 top-[60px] z-[60] flex max-h-[78vh] w-[calc(100%-2.25rem)] max-w-[440px] -translate-x-1/2 flex-col overflow-hidden rounded-xl border border-line-ember bg-gradient-to-b from-[#211811] to-[#171009] shadow-modal animate-fade-in"
        >
          <DialogPrimitive.Title className="sr-only">Paleta komend</DialogPrimitive.Title>

          {/* Szukajka */}
          <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
            <MagnifyingGlass size={19} className="text-text-3" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onInputKey}
              placeholder="Szukaj komendy lub akcji…"
              className="flex-1 bg-transparent font-ui text-body text-text outline-none placeholder:text-text-3"
            />
            <span className="rounded-md border border-line px-1.5 py-[3px] font-mono text-[10px] text-text-3">
              ESC
            </span>
          </div>

          {/* Lista pogrupowana */}
          <div className="overflow-y-auto p-2 [scrollbar-width:thin]">
            {groups.length === 0 && (
              <p className="px-3 py-6 text-center font-serif text-body text-text-3">
                Brak pasujących komend.
              </p>
            )}
            {groups.map((g) => (
              <div key={g.name}>
                <div className="px-2.5 pb-1.5 pt-2.5 text-[9.5px] font-bold uppercase tracking-[0.16em] text-text-3">
                  {g.name}
                </div>
                {g.items.map((c) => {
                  const idx = filtered.indexOf(c);
                  const on = idx === sel;
                  const Ico = c.icon;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onMouseEnter={() => setSel(idx)}
                      onClick={() => run(c)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                        on && "bg-[rgba(255,122,61,0.1)]",
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-8 w-8 flex-none items-center justify-center rounded-lg border",
                          on
                            ? "border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow"
                            : "border-line bg-bg text-text-2",
                        )}
                      >
                        <Ico size={16} weight={c.fillIcon ? "fill" : "regular"} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-label font-semibold text-text">
                          {c.title}
                        </span>
                        {c.subtitle && (
                          <span className="mt-px block text-micro text-text-3">
                            {c.subtitle}
                          </span>
                        )}
                      </span>
                      <span className="flex-none rounded-md border border-line px-1.5 py-[3px] font-mono text-[10px] text-text-3">
                        {c.keyLabel}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
