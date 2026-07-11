// #1191 · Kolekcje — Bestiariusz + Atlas Kresów (kolekcjonerskie odkrycia,
// cross-kampanijne per bohater). Bestiariusz: siatka kart wrogów, zamknięte jako
// sylwetki „???"; klik → modal z opisem/lore. Atlas: kafle eksploracji (heksy,
// lokacje, plotki) + rozbicie na krainy. Progresja wiedzy łowcy: 1/5/15 zabójstw.
import { useState } from "react";
import { CircleNotch, Eye, Skull, Sword, MapPin, Scroll, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { SecHead, PanelScroll } from "./sheetUi";
import {
  useBestiary,
  useAtlas,
  type BestiaryEntry,
} from "@/hooks/useSheetData";

type SubTab = "bestiary" | "atlas";

// Badge tieru wiedzy łowcy — 📖 wpis / 👁 podgląd HP / ⚔ +1 do trafienia.
function tierBadge(tier: number) {
  if (tier >= 3) return { icon: Sword, label: "+1 do trafienia", cls: "text-ember" };
  if (tier >= 2) return { icon: Eye, label: "podgląd HP", cls: "text-gold" };
  return { icon: Skull, label: "wpis", cls: "text-label" };
}

export function PanelCollections({ characterId }: { characterId: number | undefined }) {
  const [sub, setSub] = useState<SubTab>("bestiary");
  return (
    <PanelScroll>
      <div className="mb-5 flex gap-1 rounded-lg border border-line-soft bg-surface p-1">
        {(
          [
            ["bestiary", "Bestiariusz"],
            ["atlas", "Atlas Kresów"],
          ] as [SubTab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setSub(key)}
            className={cn(
              "flex-1 rounded-md px-3 py-2 font-ui text-[11px] font-bold uppercase tracking-[0.15em] transition-colors",
              sub === key ? "bg-ember/15 text-ember" : "text-label hover:text-text",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {sub === "bestiary" ? (
        <Bestiary characterId={characterId} />
      ) : (
        <Atlas characterId={characterId} />
      )}
    </PanelScroll>
  );
}

// ─── Bestiariusz ──────────────────────────────────────────────────────────────

function Bestiary({ characterId }: { characterId: number | undefined }) {
  const { data, isLoading } = useBestiary(characterId);
  const [open, setOpen] = useState<BestiaryEntry | null>(null);

  if (isLoading) return <Loading />;
  const s = data?.summary;
  const entries = data?.entries ?? [];

  return (
    <>
      <SecHead>
        Bestiariusz {s && (
          <span className="ml-auto text-label">
            {s.unlocked}/{s.total} · {s.pct}%
            {s.bonus ? <span className="text-ember"> · +{s.bonus} kampanijne</span> : null}
          </span>
        )}
      </SecHead>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4">
        {entries.map((e, i) =>
          e.locked ? (
            <div
              key={i}
              className="flex aspect-[3/4] flex-col items-center justify-center rounded-lg border border-line-soft bg-bg/40 text-label"
            >
              <Skull size={26} weight="fill" className="opacity-25" />
              <span className="mt-2 font-ui text-[13px] font-bold tracking-widest opacity-40">???</span>
            </div>
          ) : (
            <BestiaryCard key={e.enemy_key ?? i} entry={e} onClick={() => setOpen(e)} />
          ),
        )}
      </div>
      {open && <BestiaryModal entry={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function BestiaryCard({ entry, onClick }: { entry: BestiaryEntry; onClick: () => void }) {
  const tier = entry.unlocked_tier ?? 1;
  const badge = tierBadge(tier);
  const kills = entry.kills ?? 0;
  const next = entry.next_threshold;
  const pct = next ? Math.min(100, Math.round((kills / next) * 100)) : 100;
  return (
    <button
      onClick={onClick}
      className="group flex aspect-[3/4] flex-col overflow-hidden rounded-lg border border-line-soft bg-surface text-left transition-colors hover:border-ember/50"
    >
      <div className="relative flex-1 overflow-hidden bg-bg/60">
        {entry.image_url ? (
          <img src={entry.image_url} alt={entry.name ?? ""} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Skull size={30} weight="fill" className="text-label opacity-30" />
          </div>
        )}
        <span
          className={cn(
            "absolute right-1 top-1 rounded bg-bg/80 px-1 py-0.5 backdrop-blur",
            badge.cls,
          )}
          title={badge.label}
        >
          <badge.icon size={13} weight="fill" />
        </span>
        {entry.campaign_unique && (
          <span className="absolute left-1 top-1 rounded bg-bg/80 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-ember backdrop-blur" title="Unikat kampanijny">
            kampania
          </span>
        )}
      </div>
      <div className="px-2 py-1.5">
        <div className="truncate font-ui text-[12px] font-bold text-text">{entry.name}</div>
        <div className="mt-0.5 flex items-center justify-between text-[10px] text-label">
          <span>{kills} ubitych</span>
          {next && <span>→ {next}</span>}
        </div>
        <div className="mt-1 h-0.5 w-full overflow-hidden rounded-full bg-line">
          <div className="h-full bg-ember/70" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </button>
  );
}

function BestiaryModal({ entry, onClose }: { entry: BestiaryEntry; onClose: () => void }) {
  const tier = entry.unlocked_tier ?? 1;
  const badge = tierBadge(tier);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-xl border border-line-mech bg-surface p-5"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <h3 className="font-display text-xl text-text">{entry.name}</h3>
          <button onClick={onClose} className="text-label hover:text-text">
            <X size={20} />
          </button>
        </div>
        {entry.image_url && (
          <img
            src={entry.image_url}
            alt={entry.name ?? ""}
            className="mb-3 aspect-square w-full rounded-lg object-cover"
          />
        )}
        <div className={cn("mb-3 inline-flex items-center gap-1.5 text-[12px]", badge.cls)}>
          <badge.icon size={15} weight="fill" /> Wiedza łowcy: {badge.label}
        </div>
        <p className="mb-3 whitespace-pre-line text-[14px] leading-relaxed text-prose">
          {entry.lore_text || entry.description}
        </p>
        <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-line-soft pt-3 text-[13px] text-label">
          <span>Pokonanych: <b className="text-text">{entry.kills}</b></span>
          {entry.hp_max != null && <span>HP: <b className="text-text">{entry.hp_max}</b></span>}
        </div>
      </div>
    </div>
  );
}

// ─── Atlas Kresów ─────────────────────────────────────────────────────────────

function Atlas({ characterId }: { characterId: number | undefined }) {
  const { data, isLoading } = useAtlas(characterId);
  if (isLoading) return <Loading />;
  if (!data) return null;
  const { hexes, locations, rumors } = data;
  return (
    <>
      <SecHead>Atlas Kresów</SecHead>
      <div className="mb-5 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <Tile icon={MapPin} label="Odkryte heksy" value={`${hexes.discovered}`} sub={`${hexes.pct}% świata`} />
        <Tile icon={MapPin} label="Lokacje" value={`${locations.discovered}`} />
        <Tile icon={Scroll} label="Plotki (potw.)" value={`${rumors.confirmed}`} sub={`${rumors.heard} niesprawdzonych`} />
        <Tile icon={MapPin} label="Krainy" value={`${hexes.regions.length}`} />
      </div>

      {hexes.regions.length > 0 && (
        <div className="mb-5">
          <SecHead>Krainy</SecHead>
          <div className="space-y-1.5">
            {hexes.regions.map((r) => (
              <div key={r.region} className="flex items-center justify-between rounded-md border border-line-soft bg-surface px-3 py-2 text-[13px]">
                <span className="capitalize text-text">{r.region.replace(/_/g, " ")}</span>
                <span className="text-label">{r.discovered} heksów</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <SecHead>Plotki</SecHead>
      {rumors.entries.length === 0 ? (
        <p className="text-[13px] text-label">Jeszcze nie zebrałeś żadnych plotek. Zaglądaj do karczm.</p>
      ) : (
        <div className="space-y-1.5">
          {rumors.entries.map((r, i) => (
            <div
              key={i}
              className={cn(
                "rounded-md border px-3 py-2 text-[13px]",
                r.status === "confirmed"
                  ? "border-ember/40 bg-ember/5 text-text"
                  : "border-line-soft bg-surface text-prose",
              )}
            >
              <span className="mr-2 align-middle">{r.status === "confirmed" ? "✓" : "•"}</span>
              {r.rumor_text}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Tile({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: typeof MapPin;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-line-soft bg-surface p-3">
      <div className="mb-1 flex items-center gap-1.5 text-label">
        <Icon size={14} weight="fill" />
        <span className="font-ui text-[10px] font-bold uppercase tracking-widest">{label}</span>
      </div>
      <div className="font-display text-2xl text-text">{value}</div>
      {sub && <div className="text-[10.5px] text-label">{sub}</div>}
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center py-16 text-label">
      <CircleNotch size={22} className="animate-spin" />
    </div>
  );
}
