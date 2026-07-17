// #1191 · Kolekcje — Bestiariusz + Atlas Kresów (kolekcjonerskie odkrycia,
// cross-kampanijne per bohater). Bestiariusz: siatka kart wrogów, zamknięte jako
// sylwetki „???"; klik → modal z opisem/lore. Atlas: kafle eksploracji (heksy,
// lokacje, plotki) + rozbicie na krainy. Progresja wiedzy łowcy: 1/5/15 zabójstw.
import { useEffect, useState } from "react";
import { markRumorsSeen } from "@/hooks/useUnreadRumors";
import { CircleNotch, Eye, Skull, Sword, MapPin, Scroll, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { SecHead, PanelScroll } from "./sheetUi";
import {
  useBestiary,
  useAtlas,
  type BestiaryEntry,
  type BestiaryKnowledge,
} from "@/hooks/useSheetData";

// Etykiety strefy walki + typu obrażeń — lustro showcase (bestiariusz.js).
const ZONE_LABEL: Record<string, string> = { engaged: "⚔ Zwarcie", ranged: "🏹 Dystans" };
const DMG_LABEL: Record<string, string> = {
  physical: "fizyczny",
  fire: "ognisty",
  cold: "mrozem",
  poison: "trucizną",
  arcane: "magiczny",
  holy: "święty",
  necrotic: "nekrotyczny",
  lightning: "błyskawicą",
};

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
  const knowledge = data?.knowledge;
  // #1384 — odkryci wrogowie na górę: wg tieru wiedzy malejąco, potem liczby
  // zabójstw; sylwetki „???" spadają na koniec.
  const entries = [...(data?.entries ?? [])].sort((a, b) => {
    if (a.locked !== b.locked) return a.locked ? 1 : -1;
    const t = (b.unlocked_tier ?? 0) - (a.unlocked_tier ?? 0);
    return t || (b.kills ?? 0) - (a.kills ?? 0);
  });

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
      {open && <BestiaryModal entry={open} knowledge={knowledge} onClose={() => setOpen(null)} />}
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
          <img src={entry.image_url} alt={entry.name ?? ""} className="h-full w-full object-cover object-top" />
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

// Kafel statystyki bojowej — etykieta u góry, wartość pod spodem (jak showcase).
function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-line-soft bg-bg/40 px-3 py-2">
      <div className="font-ui text-[9.5px] font-bold uppercase tracking-widest text-label">{label}</div>
      <div className="mt-0.5 font-display text-lg text-text">{value}</div>
    </div>
  );
}

// 3-stopniowy tor wiedzy łowcy: 📖 Wpis(1) → 👁 Podgląd HP(5) → ⚔ +1 trafienie(15).
// Pokazuje osiągnięte progi i ile zabójstw do następnego (#1384).
function HunterTrack({
  tier,
  kills,
  next,
  knowledge,
}: {
  tier: number;
  kills: number;
  next?: number | null;
  knowledge?: BestiaryKnowledge;
}) {
  const hpT = knowledge?.hp_tier ?? 2;
  const bonT = knowledge?.bonus_tier ?? 3;
  const bonus = knowledge?.bonus ?? 1;
  const steps = [
    { t: 1, icon: Skull, label: "Wpis" },
    { t: hpT, icon: Eye, label: "Podgląd HP" },
    { t: bonT, icon: Sword, label: `+${bonus} do trafienia` },
  ];
  const nextLabel = steps.find((st) => st.t > tier)?.label;
  return (
    <div className="mb-3">
      <div className="flex gap-1.5">
        {steps.map((st) => {
          const on = tier >= st.t;
          return (
            <div
              key={st.t}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 rounded-lg border px-1.5 py-2 text-center transition-colors",
                on ? "border-ember/40 bg-ember/10 text-ember" : "border-line-soft bg-bg/30 text-label opacity-50",
              )}
            >
              <st.icon size={16} weight="fill" />
              <span className="font-ui text-[9px] font-bold uppercase leading-tight tracking-wide">{st.label}</span>
            </div>
          );
        })}
      </div>
      {next != null && nextLabel && (
        <div className="mt-1.5 text-center text-[11px] text-label">
          Jeszcze <b className="text-ember">{Math.max(0, next - kills)}</b> do: {nextLabel}
        </div>
      )}
    </div>
  );
}

function BestiaryModal({
  entry,
  knowledge,
  onClose,
}: {
  entry: BestiaryEntry;
  knowledge?: BestiaryKnowledge;
  onClose: () => void;
}) {
  const tier = entry.unlocked_tier ?? 1;
  const hpT = knowledge?.hp_tier ?? 2;
  const bonT = knowledge?.bonus_tier ?? 3;
  const showStats = tier >= hpT;
  const showAbilities = tier >= bonT;
  const zoneTxt = entry.zone ? ZONE_LABEL[entry.zone] : null;
  const dmgTxt = entry.damage_type ? (DMG_LABEL[entry.damage_type] ?? entry.damage_type) : null;
  const armour = entry.ac_base != null ? Math.max(0, entry.ac_base - 10) : null;
  const dmg = entry.damage_die
    ? `${entry.damage_die}${entry.damage_bonus ? `+${entry.damage_bonus}` : ""}`
    : null;
  const statOrder = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-md overflow-y-auto rounded-xl border border-line-mech bg-surface p-5"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <h3 className="font-display text-xl text-text">{entry.name}</h3>
          <button onClick={onClose} className="text-label hover:text-text">
            <X size={20} />
          </button>
        </div>
        {entry.image_url && (
          // object-contain + max-h — cały portret bez przycinania (fix #1384).
          <img
            src={entry.image_url}
            alt={entry.name ?? ""}
            className="mb-3 max-h-[55vh] w-full rounded-lg bg-bg/60 object-contain"
          />
        )}
        {/* Chipy: strefa · typ ataku · liczba pokonań · unikat kampanijny */}
        <div className="mb-3 flex flex-wrap gap-1.5 text-[11px]">
          {zoneTxt && <span className="rounded border border-line-soft bg-bg/40 px-2 py-0.5 text-label">{zoneTxt}</span>}
          {dmgTxt && <span className="rounded border border-line-soft bg-bg/40 px-2 py-0.5 text-label">Atak: {dmgTxt}</span>}
          <span className="rounded border border-line-soft bg-bg/40 px-2 py-0.5 text-label">✦ pokonany {entry.kills}×</span>
          {entry.campaign_unique && (
            <span className="rounded border border-ember/40 bg-ember/10 px-2 py-0.5 font-bold uppercase tracking-wide text-ember">kampania</span>
          )}
        </div>

        <HunterTrack tier={tier} kills={entry.kills ?? 0} next={entry.next_threshold} knowledge={knowledge} />

        {/* Statblok bojowy — od tieru „podgląd HP" (#1384). */}
        {showStats && (
          <div className="mb-3 grid grid-cols-3 gap-1.5">
            {entry.hp_max != null && <StatBox label="HP" value={entry.hp_max} />}
            {armour != null && <StatBox label="Pancerz" value={armour} />}
            {entry.attack_bonus != null && <StatBox label="Atak" value={`+${entry.attack_bonus}`} />}
            {dmg && <StatBox label="Obrażenia" value={dmg} />}
            {entry.attacks_per_turn != null && <StatBox label="Ataki/turę" value={entry.attacks_per_turn} />}
            {entry.min_level != null && <StatBox label="Poziom" value={entry.min_level} />}
            {entry.xp_award != null && <StatBox label="XP" value={entry.xp_award} />}
          </div>
        )}

        {/* Rząd cech — od najwyższego tieru wiedzy. */}
        {showAbilities && entry.stats && (
          <div className="mb-3 grid grid-cols-7 gap-1">
            {statOrder.map((k) => (
              <div key={k} className="rounded border border-line-soft bg-bg/40 py-1 text-center">
                <div className="font-ui text-[8.5px] font-bold uppercase tracking-wide text-label">{k}</div>
                <div className="text-[13px] font-bold text-text">{entry.stats?.[k] ?? "–"}</div>
              </div>
            ))}
          </div>
        )}

        <p className="whitespace-pre-line text-[14px] leading-relaxed text-prose">
          {entry.lore_text || entry.description}
        </p>
      </div>
    </div>
  );
}

// ─── Atlas Kresów ─────────────────────────────────────────────────────────────

function Atlas({ characterId }: { characterId: number | undefined }) {
  const { data, isLoading } = useAtlas(characterId);
  // #1190 — otwarcie Atlasu = „przeczytane": zgaś kropkę powiadomienia na Kolekcjach.
  const rumorCount = data?.rumors.entries.length ?? 0;
  useEffect(() => {
    if (characterId && data) markRumorsSeen(characterId, rumorCount);
  }, [characterId, data, rumorCount]);
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
      {/* #1190 — legenda statusów: bez niej gracz nie wie, co znaczą ikony/kolory. */}
      <div className="mb-2.5 flex flex-wrap gap-x-3 gap-y-1 rounded-md border border-line-soft bg-bg/30 px-3 py-2 text-[11px] text-label">
        <span><span className="text-ember">✓</span> potwierdzona</span>
        <span className="line-through decoration-label/50">✗ fałszywa</span>
        <span>• niepewna</span>
        <span><span className="rounded bg-gold/15 px-1 py-0.5 font-bold uppercase tracking-wide text-gold">podejrzana</span> — coś śmierdzi</span>
      </div>
      <p className="mb-2.5 text-[11.5px] italic text-label">
        Plotki zbierasz w karczmach: napisz „nadstawiam ucha" (za darmo) lub „stawiam kolejkę" (kilka złotych, pewniejsza wieść).
      </p>
      {rumors.entries.length === 0 ? (
        <p className="text-[13px] text-label">Jeszcze nie zebrałeś żadnych plotek. Zaglądaj do karczm.</p>
      ) : (
        <div className="space-y-1.5">
          {rumors.entries.map((r, i) => {
            // #1190 — 3 statusy + znacznik „podejrzana". debunked = fałszywka
            // zdemaskowana wizytą (przekreślona); suspected = wyczułeś, że coś śmierdzi.
            const debunked = r.status === "debunked";
            const confirmed = r.status === "confirmed";
            const glyph = debunked ? "✗" : confirmed ? "✓" : "•";
            return (
              <div
                key={i}
                className={cn(
                  "rounded-md border px-3 py-2 text-[13px]",
                  debunked
                    ? "border-line-soft bg-bg/30 text-label line-through decoration-label/50"
                    : confirmed
                      ? "border-ember/40 bg-ember/5 text-text"
                      : "border-line-soft bg-surface text-prose",
                )}
              >
                <span className="mr-2 align-middle">{glyph}</span>
                {r.rumor_text}
                {!debunked && r.suspected ? (
                  <span className="ml-2 rounded bg-gold/15 px-1.5 py-0.5 align-middle text-[10px] font-bold uppercase tracking-wide text-gold">
                    podejrzana
                  </span>
                ) : null}
                {debunked ? (
                  <span className="ml-2 align-middle text-[10.5px] italic text-label">— okazała się bujdą</span>
                ) : null}
              </div>
            );
          })}
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
