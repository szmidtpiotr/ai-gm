import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  X,
  Check,
  ArrowLeft,
  ArrowRight,
  Minus,
  Plus,
  Coins,
  Heart,
  Drop,
  Lightning,
  CircleNotch,
  ArrowsLeftRight,
  ArrowUUpLeft,
  CaretDown,
} from "@phosphor-icons/react";
import {
  useCreateCharacter,
  useGenerateIdentity,
  useFinalizeSheet,
  useCampaigns,
} from "@/hooks/useGameData";
import { apiFetch } from "@/lib/api";
import {
  usePublicSkills,
  useCreationRaces,
  type PublicSkill,
  type CreationRace,
} from "@/hooks/useSheetData";
import { useAppStore } from "@/store/appStore";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ARCHETYPE_BONUS,
  RACE_BLOCKED_ARCHETYPES,
  RACE_STAT_MODS,
  skillAllowed,
  RANK_LABEL,
  STAT_KEYS,
  STAT_META,
  WIZARD_MAX_SWAPS,
  WIZARD_STAT_MAX,
  WIZARD_STAT_MIN,
  calcHp,
  calcMana,
  canAdjSkill,
  skillBudgetUsed,
  skillMeta,
  statMod,
  type Archetype,
  type SkillRow,
  type Race,
  type StatKey,
} from "@/lib/creation";
import type { Hero, IdentityPreview } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SkillPickerSheet } from "@/components/game/creation/SkillPickerSheet";

const STEPS = ["Rasa", "Tożsamość", "Cechy", "Umiej.", "Finał"];

const RACES: Array<{ key: Race; icon: string; title: string; desc: string; bonus: string }> = [
  {
    key: "human",
    icon: "🧑",
    title: "Człowiek",
    desc: "Wszechstronny i elastyczny. Brak rasowych modyfikatorów.",
    bonus: "Brak modyfikatorów · Magia arkanów",
  },
  {
    key: "dwarf",
    icon: "⛏️",
    title: "Krasnolud",
    desc: "Twardy jak kamień. Odporny na trucizny i mroczną magię, widzi w ciemności.",
    bonus: "+2 KON · +1 SIŁ · −1 CHA · −1 ZRĘ · Rdzeń-magia",
  },
  {
    key: "elf",
    icon: "🏹",
    title: "Elf leśny",
    desc: "Cichy strażnik starych granic. Celny łuk, zmierzchowy wzrok, odskok ze zwarcia. Kruchy w bezpośrednim starciu.",
    bonus: "+2 ZRĘ · +1 MĄD · −1 KON · Magia strojenia",
  },
  {
    key: "pietnowani",
    icon: "🔥",
    title: "Piętnowany",
    desc: "Naznaczony przez Rdzeń potomek tych, którzy nie uciekli. Krew oswojona z magią — łagodniejszy miscast i więcej many, lecz obcy się go boją. Droga: Uczony albo Wojownik-Mag.",
    bonus: "+2 INT · +1 MĄD · −1 KON · Magia krwi oswojonej",
  },
];

const ARCHETYPES: Array<{ key: Archetype; icon: string; title: string; desc: string; bonus: string }> = [
  { key: "warrior", icon: "⚔️", title: "Wojownik", desc: "Frontowy wojownik w ciężkiej zbroi. Wysoki HP, silne ciosy.", bonus: "+2 SIŁ · +1 KON · HP 10" },
  { key: "rogue", icon: "🏹", title: "Łotrzyk", desc: "Zwinny cień: skradanie, łuk, inteligentna walka.", bonus: "+2 ZRĘ · +1 SZC · HP 8" },
  { key: "scholar", icon: "📜", title: "Uczony", desc: "Tkacz arkanów: kruchy, ale niszczycielski dzięki zaklęciom i manie.", bonus: "+2 INT · +1 MĄD · HP 6 · Mana" },
];

// #1474 — ta sama mechanika archetypu, inna nazwa i klimat wedle rasy. Elf nie ma
// "Łotrzyka" (nazwa nie pasuje do strażnika granic) ani zwykłego "Uczonego" —
// jego magia to strojenie, nie nauka z ksiąg. Klucze archetypów bez zmian.
const RACE_ARCHETYPE_OVERRIDE: Partial<
  Record<Race, Partial<Record<Archetype, { title: string; desc: string; bonus?: string }>>>
> = {
  elf: {
    rogue: {
      title: "Zwiadowca",
      desc: "Łucznik i tropiciel: cichy w kniei, celny z dystansu, odskakuje ze zwarcia.",
    },
    scholar: {
      title: "Uczony-Stroiciel",
      desc: "Stroi pęknięcia Rdzenia zamiast je rwać: kontrola, ochrona i iluzje zamiast czystego ognia.",
    },
  },
  // #1475 — Piętnowany-Uczony to pełny mag krwi oswojonej. Wojownik-Mag (gish)
  // to osobny archetyp dodany w PN-2 (klucz `wojownik_mag`), nie override.
  pietnowani: {
    scholar: {
      title: "Uczony",
      desc: "Pełny mag krwi oswojonej: łagodniejszy miscast, więcej many, cały arsenał zaklęć. Kruchy w zwarciu.",
    },
  },
};

const BOND_TYPES = { person: "Osoba", place: "Miejsce", object: "Przedmiot", ideal: "Ideał" };
const WEAK_TYPES = { fear: "Strach", flaw: "Wada", addiction: "Nałóg", trauma: "Trauma" };

interface IdentityDraft {
  appearance: string;
  personality: string;
  bonds: Array<{ description: string; type: string }>;
  weaknesses: Array<{ description: string; type: string }>;
}

export default function CreateCharacter() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const user = useAppStore((s) => s.currentUser);
  const currentCampaignId = useAppStore((s) => s.currentCampaignId);
  const setHero = useAppStore((s) => s.setHero);
  const { data: campaigns } = useCampaigns();

  const createChar = useCreateCharacter();
  const genIdentity = useGenerateIdentity();
  const finalize = useFinalizeSheet();
  // Pełny żywy katalog skilli — pula zamiany (↔) w kroku Umiejętności musi
  // oferować cały game_config_skills, nie tylko rolowaną legacy-pulę arkusza.
  const { data: skillCatalog } = usePublicSkills();
  // #1479 — dostępność ras zależy od tego, czy ich kraina ojczysta jest otwarta.
  const { data: raceOptions } = useCreationRaces();

  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);

  // Step 1 — Rasa
  const [race, setRace] = useState<Race>("human");
  // Step 2 — Tożsamość
  const [name, setName] = useState("");
  const [archetype, setArchetype] = useState<Archetype>("warrior");
  const [backstory, setBackstory] = useState("");
  // Utworzona postać
  const [hero, setHeroState] = useState<Hero | null>(null);
  // Step 3 — Cechy (bazy pre-bonus)
  const [statBases, setStatBases] = useState<Record<StatKey, number>>(zeroStats());
  const [statOriginal, setStatOriginal] = useState<Record<StatKey, number>>(zeroStats());
  const [pool, setPool] = useState(0);
  // Step 4 — Umiejętności
  const [snapshot, setSnapshot] = useState<Record<string, number>>({});
  const [levels, setLevels] = useState<Record<string, number>>({});
  const [swapMap, setSwapMap] = useState<Record<string, string>>({});
  const [swapSlot, setSwapSlot] = useState<string | null>(null);
  // Step 5 — Finał
  const [identity, setIdentity] = useState<IdentityDraft | null>(null);

  // #1477 — archetypy zamknięte dla wybranej rasy. Serwer jest źródłem prawdy;
  // stała lokalna ratuje kreator, zanim odpowiedź /creation/races dojdzie.
  const blockedArchetypes = ((): Archetype[] => {
    const fromServer = raceOptions?.find((o) => o.key === race)?.blocked_archetypes;
    return (fromServer ?? RACE_BLOCKED_ARCHETYPES[race] ?? []) as Archetype[];
  })();

  // Zmiana rasy nie może zostawić zablokowanego archetypu w stanie kroku 2
  // (gracz wybrał Łotrzyka jako człowiek, cofnął się, wziął krasnoluda).
  function pickRace(r: Race) {
    setRace(r);
    const blocked = (raceOptions?.find((o) => o.key === r)?.blocked_archetypes ??
      RACE_BLOCKED_ARCHETYPES[r] ?? []) as Archetype[];
    // #1474: fallbackiem nie może być na sztywno Wojownik — dla elfa to właśnie
    // archetyp zamknięty. Bierzemy pierwszy dozwolony z listy kart.
    if (blocked.includes(archetype)) {
      const firstAllowed = ARCHETYPES.find((a) => !blocked.includes(a.key))?.key ?? "rogue";
      setArchetype(firstAllowed);
    }
  }

  const bonus = ARCHETYPE_BONUS[archetype];
  // #1520 — staty z serwera = rzuty + bonus klasy + modyfikatory rasy.
  // Bazy trzymamy czyste (same rzuty), a klasa i rasa wracają przy wyświetlaniu.
  const raceMod = RACE_STAT_MODS[race] ?? {};
  const eff = (k: StatKey) => statBases[k] + (bonus[k] || 0) + (raceMod[k] || 0);

  function effStats(): Record<StatKey, number> {
    return Object.fromEntries(STAT_KEYS.map((k) => [k, eff(k)])) as Record<StatKey, number>;
  }

  // ── Nawigacja ──────────────────────────────────────────────────────────
  async function next() {
    setBusy(true);
    try {
      if (step === 0) {
        setStep(1);
      } else if (step === 1) {
        await submitIdentityStep();
      } else if (step === 2) {
        setStep(3);
      } else if (step === 3) {
        await generateIdentityStep();
      } else {
        await finalizeStep();
      }
    } catch (e) {
      toast((e as Error).message || "Błąd kreatora", "danger");
    } finally {
      setBusy(false);
    }
  }

  function back() {
    if (step > 0) setStep((s) => s - 1);
  }

  // Step 2 → utwórz postać, wczytaj bazy statów + snapshot skilli
  async function submitIdentityStep() {
    if (!name.trim()) {
      toast("Podaj imię postaci", "danger");
      return;
    }
    if (!user?.id) return;

    let created = hero;
    const needCreate =
      !created ||
      created.name !== name.trim() ||
      created.sheet_json?.archetype !== archetype ||
      created.race !== race;

    if (needCreate) {
      created = await createChar.mutateAsync({
        userId: user.id,
        name: name.trim(),
        race,
        archetype,
        backstory: backstory.trim(),
      });
      setHeroState(created);
    }

    const sheet = created!.sheet_json ?? {};
    const stored = (sheet.stats ?? {}) as Record<string, number>;
    const bases = {} as Record<StatKey, number>;
    for (const k of STAT_KEYS) {
      const def = k === "LCK" ? 8 : 10;
      const b = (bonus[k] || 0) + (raceMod[k] || 0);
      bases[k] = Math.max(WIZARD_STAT_MIN, (Number(stored[k] ?? def)) - b);
    }
    setStatBases(bases);
    setStatOriginal({ ...bases });
    setPool(0);

    // Pula umiejętności = klucze z arkusza serwera (skills_at_creation), nie
    // statyczna lista — inaczej finalize odrzuci rolowane skille spoza listy.
    const skillsOrig = ((sheet.skills_at_creation ?? sheet.skills) ?? {}) as Record<string, number>;
    const snap: Record<string, number> = {};
    const lvl: Record<string, number> = {};
    for (const key of Object.keys(skillsOrig)) {
      const v = Math.max(0, Math.min(2, Number(skillsOrig[key] || 0)));
      snap[key] = v;
      if (v > 0) lvl[key] = v;
    }
    setSnapshot(snap);
    setLevels(lvl);
    setSwapMap({});
    setSwapSlot(null);
    setStep(2);
  }

  // Step 4 → wygeneruj tożsamość (LLM)
  async function generateIdentityStep() {
    if (!hero) return;
    setStep(4);
    const preview: IdentityPreview = await genIdentity.mutateAsync(hero.id);
    setIdentity({
      appearance: preview.appearance || "",
      personality: preview.personality || "",
      bonds: (preview.bonds?.length ? preview.bonds : [{ description: "", type: "ideal" }, { description: "", type: "ideal" }]).slice(0, 2),
      weaknesses: (preview.weaknesses?.length ? preview.weaknesses : [{ description: "", type: "flaw" }, { description: "", type: "flaw" }]).slice(0, 2),
    });
  }

  // Step 5 → finalizacja + wejście
  async function finalizeStep() {
    if (!hero) return;
    const statOverrides = Object.fromEntries(STAT_KEYS.map((k) => [k, statBases[k]]));

    const finalSkills: Record<string, number> = {};
    const skillSlot: Record<string, string> = {};
    for (const key of Object.keys(snapshot)) finalSkills[key] = 0;
    for (const orig of Object.keys(snapshot)) {
      const snap = Number(snapshot[orig] || 0);
      if (!snap) continue;
      const tgt = swapMap[orig] || orig;
      finalSkills[tgt] = Math.max(0, Math.min(2, levels[orig] ?? snap));
      skillSlot[orig] = tgt;
    }

    const bonds = (identity?.bonds ?? []).filter((b) => b.description.trim());
    const weaknesses = (identity?.weaknesses ?? []).filter((w) => w.description.trim());

    await finalize.mutateAsync({
      characterId: hero.id,
      statOverrides,
      skills: finalSkills,
      skillSlotCurrent: Object.keys(skillSlot).length ? skillSlot : null,
      identityOverrides: {
        appearance: identity?.appearance ?? "",
        personality: identity?.personality ?? "",
        bonds: bonds.length ? bonds : null,
        weaknesses: weaknesses.length ? weaknesses : null,
      },
    });

    setHero(hero.id);
    toast(`Bohater ${hero.name} gotowy!`, "success");

    // #1080 — brand-new player (no pre-selected campaign, owns zero campaigns) →
    // auto-launch the hidden onboarding tutorial and drop straight into it.
    // Any failure falls through to normal navigation — never block hero creation.
    if (!currentCampaignId && user?.id) {
      const mine = (campaigns ?? []).filter((c) => c.owner_user_id === user.id);
      if (mine.length === 0) {
        try {
          const res = await apiFetch<{ ok: boolean; campaign_id: number }>(
            "/onboarding/start",
            { method: "POST", body: { character_id: hero.id, user_id: user.id } },
          );
          navigate(`/gra/${res.campaign_id}`);
          return;
        } catch {
          // fall through to standard navigation below
        }
      }
    }

    if (currentCampaignId) navigate(`/gra/${currentCampaignId}`);
    else navigate(`/bohaterowie/${hero.id}/kampanie`);
  }

  const nextLabel = ["Dalej: Tożsamość", "Dalej: Cechy", "Dalej: Umiejętności", "Dalej: Finał", "Rozpocznij przygodę"][step];

  return (
    <div className="-mx-4 -my-4 flex min-h-[calc(100dvh-3.5rem)] flex-col lg:-my-4">
      {/* Topbar kreatora */}
      <header className="flex items-center gap-2.5 border-b border-line bg-surface px-4 py-3">
        <button
          onClick={() => navigate(-1)}
          aria-label="Zamknij"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-line text-text-2 hover:text-text"
        >
          <X size={17} />
        </button>
        <span className="font-serif text-title font-semibold text-text">Nowy bohater</span>
      </header>

      <Stepper step={step} />

      <div className="mx-auto w-full max-w-xl flex-1 px-4 py-5">
        {step === 0 && (
          <StepRace race={race} onPick={pickRace} options={raceOptions} />
        )}
        {step === 1 && (
          <StepIdentity
            name={name}
            setName={setName}
            archetype={archetype}
            setArchetype={setArchetype}
            blockedArchetypes={blockedArchetypes}
            race={race}
            backstory={backstory}
            setBackstory={setBackstory}
          />
        )}
        {step === 2 && (
          <StepStats
            archetype={archetype}
            statBases={statBases}
            bonus={bonus}
            raceMod={raceMod}
            pool={pool}
            eff={effStats()}
            onAdjust={(k, dir) => {
              setStatBases((prev) => {
                const v = prev[k];
                if (dir < 0) {
                  if (v <= WIZARD_STAT_MIN) return prev;
                  setPool((p) => p + 1);
                  return { ...prev, [k]: v - 1 };
                }
                if (v >= WIZARD_STAT_MAX || pool <= 0) return prev;
                setPool((p) => p - 1);
                return { ...prev, [k]: v + 1 };
              });
            }}
            onReset={() => {
              setStatBases({ ...statOriginal });
              setPool(0);
            }}
          />
        )}
        {step === 3 && (
          <StepSkills
            catalog={(skillCatalog ?? []).filter((sk) => skillAllowed(sk.key, archetype, race))}
            allow={(k) => skillAllowed(k, archetype, race)}
            snapshot={snapshot}
            levels={levels}
            swapMap={swapMap}
            swapSlot={swapSlot}
            setSwapSlot={setSwapSlot}
            onLevel={(orig, delta) => {
              if (!canAdjSkill(orig, delta, snapshot, levels)) return;
              const cur = levels[orig] ?? Number(snapshot[orig] || 0);
              setLevels({ ...levels, [orig]: cur + delta });
            }}
            onSwap={(orig, target) => {
              setSwapMap({ ...swapMap, [orig]: target });
              setSwapSlot(null);
            }}
            onRevert={(orig) => {
              const m = { ...swapMap };
              delete m[orig];
              setSwapMap(m);
              setSwapSlot(null);
            }}
            onReset={() => {
              setLevels(Object.fromEntries(Object.entries(snapshot).filter(([, v]) => v > 0)));
              setSwapMap({});
              setSwapSlot(null);
            }}
          />
        )}
        {step === 4 && (
          <StepFinal identity={identity} loading={genIdentity.isPending} onChange={setIdentity} />
        )}
      </div>

      {/* Sticky footer */}
      <div
        className="sticky bottom-0 z-10 flex gap-2.5 border-t border-line bg-surface px-4 py-3"
        style={{ paddingBottom: "calc(0.75rem + var(--sa-bottom))" }}
      >
        {step > 0 && (
          <Button variant="secondary" onClick={back} disabled={busy}>
            <ArrowLeft size={16} /> Wstecz
          </Button>
        )}
        <Button className="flex-1" onClick={next} disabled={busy}>
          {busy ? (
            <CircleNotch className="animate-spin" size={18} />
          ) : (
            <>
              {nextLabel}
              <ArrowRight size={16} />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

function zeroStats(): Record<StatKey, number> {
  return Object.fromEntries(STAT_KEYS.map((k) => [k, 10])) as Record<StatKey, number>;
}

// ── Stepper ──────────────────────────────────────────────────────────────
function Stepper({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto border-b border-line bg-surface px-3 py-3.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {STEPS.map((label, i) => {
        const done = i < step;
        const on = i === step;
        return (
          <div key={label} className="flex items-center">
            <div className="flex min-w-[62px] flex-col items-center gap-1.5">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border-[1.5px] font-mono text-label font-semibold",
                  on && "border-ember bg-ember text-[#1a0f08] shadow-float",
                  done && "border-line-ember bg-ember/[0.12] text-ember-glow",
                  !on && !done && "border-line bg-bg text-text-3",
                )}
              >
                {done ? <Check weight="bold" size={13} /> : i + 1}
              </span>
              <span
                className={cn(
                  "font-ui text-[9.5px] font-semibold uppercase tracking-wide",
                  on ? "text-ember-glow" : "text-text-3",
                )}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span className={cn("h-px min-w-[14px] flex-1", done ? "bg-line-ember" : "bg-line")} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Krok 1: Rasa ───────────────────────────────────────────────────────────
function StepRace({
  race,
  onPick,
  options,
}: {
  race: Race;
  onPick: (r: Race) => void;
  /** #1479 — dostępność z backendu; brak danych = wszystko dostępne (nie blokuj kreatora). */
  options?: CreationRace[];
}) {
  const byKey = new Map((options ?? []).map((o) => [o.key, o]));
  return (
    <div>
      <h1 className="text-center font-serif text-title-lg font-semibold text-text">Wybierz rasę</h1>
      <p className="mx-auto mt-1.5 max-w-md text-center font-ui text-label text-text-3">
        Rasa kształtuje cechy fizyczne i zdolności twojego bohatera.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {RACES.map(({ key, ...rest }) => {
          const opt = byKey.get(key);
          const locked = opt ? !opt.available : false;
          return (
            <PickCard
              key={key}
              selected={race === key}
              disabled={locked}
              lockReason={locked ? opt?.reason ?? null : null}
              onClick={() => !locked && onPick(key)}
              {...rest}
            />
          );
        })}
      </div>
    </div>
  );
}

// ── Krok 2: Tożsamość ───────────────────────────────────────────────────────
function StepIdentity({
  name,
  setName,
  archetype,
  setArchetype,
  backstory,
  setBackstory,
  blockedArchetypes = [],
  race,
}: {
  name: string;
  setName: (v: string) => void;
  archetype: Archetype;
  setArchetype: (a: Archetype) => void;
  backstory: string;
  setBackstory: (v: string) => void;
  /** #1477 — archetypy zamknięte dla wybranej rasy; karty w ogóle nie wchodzą. */
  blockedArchetypes?: Archetype[];
  /** #1474 — rasa nadaje archetypom własne nazwy (elf: Zwiadowca / Uczony-Stroiciel). */
  race?: Race;
}) {
  const options = ARCHETYPES.filter(({ key }) => !blockedArchetypes.includes(key)).map((a) => ({
    ...a,
    ...(RACE_ARCHETYPE_OVERRIDE[race as Race]?.[a.key] ?? {}),
  }));
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-center font-serif text-title-lg font-semibold text-text">Twój bohater</h1>
      <div>
        <label className="mb-1.5 block font-ui text-label text-text-2">Imię postaci</label>
        <Input
          value={name}
          maxLength={40}
          placeholder="np. Aldric z Północy"
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <div>
        <label className="mb-1.5 block font-ui text-label text-text-2">Historia / tło (opcjonalne)</label>
        <textarea
          rows={3}
          value={backstory}
          placeholder="Kim był twój bohater przed początkiem przygody?"
          onChange={(e) => setBackstory(e.target.value)}
          className="w-full resize-none rounded-sm border border-line bg-inset px-3 py-2.5 font-ui text-body text-text placeholder:text-text-3 focus:border-line-ember focus:outline-none focus:ring-1 focus:ring-line-ember"
        />
      </div>
      <div>
        <label className="mb-1.5 block font-ui text-label text-text-2">Archetyp</label>
        <div className="grid gap-3 sm:grid-cols-3">
          {options.map(({ key, ...rest }) => (
            <PickCard
              key={key}
              selected={archetype === key}
              onClick={() => setArchetype(key)}
              {...rest}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function PickCard({
  selected,
  onClick,
  icon,
  title,
  desc,
  bonus,
  disabled = false,
  lockReason = null,
}: {
  selected: boolean;
  onClick: () => void;
  icon: string;
  title: string;
  desc: string;
  bonus: string;
  /** #1479 — karta widoczna, ale nieklikalna (kraina rasy zamknięta). */
  disabled?: boolean;
  lockReason?: string | null;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled}
      data-testid={disabled ? "pick-card-locked" : undefined}
      title={lockReason ?? undefined}
      className={cn(
        "flex flex-col gap-1.5 rounded-lg border p-3.5 text-left transition-colors",
        disabled
          ? "cursor-not-allowed border-line bg-surface opacity-45"
          : selected
            ? "border-line-ember bg-ember/[0.06]"
            : "border-line bg-surface hover:border-line-ember",
      )}
    >
      <span className="text-2xl">{icon}</span>
      <span className="font-serif text-body font-semibold text-text">
        {title}
        {disabled && <span className="ml-1.5 align-middle text-micro">🔒</span>}
      </span>
      <span className="font-ui text-micro leading-snug text-text-3">{desc}</span>
      <span className="mt-1 font-ui text-[10.5px] font-semibold text-ember-glow">{bonus}</span>
      {disabled && lockReason && (
        <span className="mt-1 font-ui text-[10.5px] font-semibold text-text-3">{lockReason}</span>
      )}
    </button>
  );
}

// ── Krok 3: Cechy ───────────────────────────────────────────────────────────
function StepStats({
  archetype,
  statBases,
  bonus,
  raceMod,
  pool,
  eff,
  onAdjust,
  onReset,
}: {
  archetype: Archetype;
  statBases: Record<StatKey, number>;
  bonus: Partial<Record<StatKey, number>>;
  raceMod: Partial<Record<StatKey, number>>;
  pool: number;
  eff: Record<StatKey, number>;
  onAdjust: (k: StatKey, dir: number) => void;
  onReset: () => void;
}) {
  const hp = calcHp(archetype, eff.CON);
  const mana = calcMana(archetype, eff.INT);
  const init = statMod(eff.DEX);
  const fmtMod = (v: number) => `${v > 0 ? "+" : ""}${v}`;
  const bonusStr = Object.entries(bonus)
    .map(([k, v]) => `+${v} ${k}`)
    .join(" · ");
  const raceStr = Object.entries(raceMod)
    .filter(([, v]) => v)
    .map(([k, v]) => `${fmtMod(v as number)} ${k}`)
    .join(" · ");

  return (
    <div>
      <h1 className="text-center font-serif text-title-lg font-semibold text-text">Rozdziel cechy</h1>
      <p className="mt-1.5 text-center font-ui text-label text-text-3">
        Zmniejsz cechę (−), aby uwolnić punkt, i wydaj go (+) gdzie indziej.
      </p>
      <div className="my-4 flex items-center justify-center gap-2 font-ui text-label text-text-2">
        <Coins weight="fill" className="text-ember" size={16} /> Pozostałe punkty:{" "}
        <b className="font-mono text-title text-ember-glow">{pool}</b>
      </div>
      {bonusStr && (
        <p className="-mt-2 mb-3 text-center font-ui text-micro text-text-3">
          Bonus klasy {bonusStr}
          {raceStr ? <> · rasa {raceStr}</> : null} doliczony automatycznie
        </p>
      )}

      <div className="flex flex-col gap-2.5">
        {STAT_KEYS.map((k) => {
          const v = eff[k];
          const mod = statMod(v);
          const hi = (bonus[k] || 0) > 0;
          const canMinus = statBases[k] > WIZARD_STAT_MIN;
          const canPlus = statBases[k] < WIZARD_STAT_MAX && pool > 0;
          return (
            <div
              key={k}
              className={cn(
                "flex items-center gap-3 rounded-md border px-3.5 py-2.5",
                hi ? "border-line-ember bg-gradient-to-b from-ember/[0.06] to-surface" : "border-line bg-surface",
              )}
            >
              <span className={cn("w-10 shrink-0 font-mono text-label font-semibold tracking-wide", hi ? "text-ember-glow" : "text-text-2")}>
                {k}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-ui text-label font-semibold text-text">{STAT_META[k].name}</div>
                <div className="font-ui text-micro text-text-3">{STAT_META[k].desc}</div>
              </div>
              <button
                onClick={() => onAdjust(k, -1)}
                disabled={!canMinus}
                aria-label={`Zmniejsz ${k}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-text-2 hover:border-line-ember hover:text-ember-glow disabled:opacity-30"
              >
                <Minus size={15} />
              </button>
              <span className="w-8 text-center font-mono text-title font-semibold text-text">{v}</span>
              <button
                onClick={() => onAdjust(k, 1)}
                disabled={!canPlus}
                aria-label={`Zwiększ ${k}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-text-2 hover:border-line-ember hover:text-ember-glow disabled:opacity-30"
              >
                <Plus size={15} />
              </button>
              <span
                className={cn(
                  "w-8 text-center font-mono text-label",
                  mod > 0 ? "text-success" : mod < 0 ? "text-danger" : "text-text-3",
                )}
              >
                {mod >= 0 ? `+${mod}` : mod}
              </span>
            </div>
          );
        })}
      </div>

      {/* Podgląd pochodnych */}
      <div className="mt-4 flex gap-2">
        <Derived icon={<Heart weight="fill" className="text-ember" />} value={hp} label="Zdrowie" />
        <Derived
          icon={<Drop weight="fill" className="text-mana" />}
          value={archetype === "scholar" ? mana : "—"}
          label="Mana"
          muted={archetype !== "scholar"}
        />
        <Derived
          icon={<Lightning weight="fill" className="text-gold" />}
          value={init >= 0 ? `+${init}` : init}
          label="Inicjatywa"
        />
      </div>

      <div className="mt-4 flex justify-center">
        <Button variant="ghost" size="sm" onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}

function Derived({
  icon,
  value,
  label,
  muted,
}: {
  icon: React.ReactNode;
  value: React.ReactNode;
  label: string;
  muted?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col items-center gap-1 rounded-md border border-line-soft bg-mech-card px-2 py-3">
      <span className="text-[17px]">{icon}</span>
      <span className={cn("font-mono text-title font-semibold", muted ? "text-text-3" : "text-text")}>{value}</span>
      <span className="font-ui text-[9.5px] uppercase tracking-widest text-text-3">{label}</span>
    </div>
  );
}

// ── Krok 4: Umiejętności ────────────────────────────────────────────────────
function StepSkills({
  catalog,
  allow,
  snapshot,
  levels,
  swapMap,
  swapSlot,
  setSwapSlot,
  onLevel,
  onSwap,
  onRevert,
  onReset,
}: {
  catalog: PublicSkill[];
  allow: (skillKey: string) => boolean;
  snapshot: Record<string, number>;
  levels: Record<string, number>;
  swapMap: Record<string, string>;
  swapSlot: string | null;
  setSwapSlot: (s: string | null) => void;
  onLevel: (orig: string, delta: number) => void;
  onSwap: (orig: string, target: string) => void;
  onRevert: (orig: string) => void;
  onReset: () => void;
}) {
  const [openDesc, setOpenDesc] = useState<string | null>(null);
  const used = Math.max(0, skillBudgetUsed(snapshot, levels));
  const slots = Object.keys(snapshot)
    .filter((k) => Number(snapshot[k] || 0) > 0)
    .map(skillMeta)
    .sort(
      (a, b) =>
        Number(snapshot[b.key] || 0) - Number(snapshot[a.key] || 0) ||
        a.key.localeCompare(b.key),
    );
  const visible = new Set(slots.map((r) => swapMap[r.key] || r.key));
  // Pula zamiany = cały żywy katalog (game_config_skills) + statyczne etykiety +
  // klucze arkusza, nie tylko rolowana legacy-pula. Bez tego czarodziej (i każdy
  // archetyp) widział ~10 legacy-skilli zamiast pełnego katalogu silnika.
  const catMeta = new Map<string, SkillRow>(
    catalog.map((s) => [
      s.key,
      { key: s.key, label: s.label || s.key, stat: s.linked_stat || "?", hint: s.description || "" },
    ]),
  );
  const meta = (k: string): SkillRow => catMeta.get(k) ?? skillMeta(k);
  // #1523 — źródłem listy jest ŻYWY katalog (`game_config_skills`) + klucze już
  // trzymane w arkuszu. Statyczne ALL_SKILL_ROWS służą wyłącznie za etykiety
  // (skillMeta): siedzą w nich martwe klucze sprzed #1052 (melee_attack,
  // spell_attack, sleight_of_hand), których backend nie zna — wybranie takiego
  // kończyło się odmową dopiero przy finalizacji kreatora.
  const universe = new Set<string>([
    ...catalog.map((s) => s.key),
    ...Object.keys(snapshot),
  ]);
  const candidates = [...universe]
    .filter((k) => !Number(snapshot[k] || 0) && !visible.has(k) && allow(k))
    .map(meta)
    .sort((a, b) => a.label.localeCompare(b.label));

  return (
    <div>
      <h1 className="text-center font-serif text-title-lg font-semibold text-text">Umiejętności</h1>
      <p className="mt-1.5 text-center font-ui text-label text-text-3">
        Wylosowane umiejętności bohatera. Dotknij nazwy, żeby zobaczyć, co robi
        i zamienić ją na inną — zamiana nic nie kosztuje.
      </p>
      <p className="mt-1 text-center font-ui text-micro text-text-3">
        Podniesienie rangi kosztuje punkt, obniżenie go zwraca. Netto max {WIZARD_MAX_SWAPS}.
      </p>
      <div className="my-4 text-center font-ui text-label text-text-2">
        Zmieniono: <b className="font-mono text-ember-glow">{used} / {WIZARD_MAX_SWAPS}</b>
      </div>

      <div className="flex flex-col gap-2.5">
        {slots.map((slot) => {
          const orig = slot.key;
          const swapped = orig in swapMap;
          const curKey = swapped ? swapMap[orig] : orig;
          const cur = meta(curKey);
          const rank = levels[orig] ?? Number(snapshot[orig] || 0);

          const changed = swapped || rank !== Number(snapshot[orig] || 0);
          const expanded = openDesc === orig;
          return (
            <div
              key={orig}
              className={cn(
                "overflow-hidden rounded-md border transition-colors",
                changed ? "border-line-ember bg-ember/[0.04]" : "border-line bg-surface",
              )}
            >
              <div className="flex items-center gap-2 px-3.5 py-2.5">
                {/* Nazwa + cecha + rozwijanie opisu — cały blok jest przyciskiem,
                    żeby na telefonie nie trzeba było trafiać w ikonkę. */}
                <button
                  type="button"
                  onClick={() => setOpenDesc(expanded ? null : orig)}
                  aria-expanded={expanded}
                  className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                >
                  <span className="truncate font-ui text-label font-semibold text-text">
                    {cur.label}
                  </span>
                  <span className="shrink-0 font-mono text-micro text-text-3">{cur.stat}</span>
                  <CaretDown
                    size={12}
                    className={cn(
                      "shrink-0 text-text-3 transition-transform",
                      expanded && "rotate-180",
                    )}
                  />
                </button>
                <button
                  onClick={() => onLevel(orig, -1)}
                  disabled={!canAdjSkill(orig, -1, snapshot, levels)}
                  aria-label={`Obniż: ${cur.label}`}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-text-2 hover:border-line-ember disabled:opacity-30"
                >
                  <Minus size={14} />
                </button>
                <span className="w-24 shrink-0 text-center font-ui text-micro text-text-2">
                  <b className="font-mono text-label text-text">{rank}</b>{" "}
                  <span className="text-text-3">{RANK_LABEL[rank] || rank}</span>
                </span>
                <button
                  onClick={() => onLevel(orig, 1)}
                  disabled={!canAdjSkill(orig, 1, snapshot, levels)}
                  aria-label={`Podnieś: ${cur.label}`}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-text-2 hover:border-line-ember disabled:opacity-30"
                >
                  <Plus size={14} />
                </button>
              </div>

              {expanded && (
                <div className="border-t border-line-soft bg-bg px-3.5 py-2.5">
                  <p className="font-serif text-micro leading-relaxed text-text-2">
                    {cur.hint || "Brak opisu w katalogu."}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSwapSlot(orig)}
                      className="gap-1.5"
                    >
                      <ArrowsLeftRight size={13} /> Zamień na inną
                    </Button>
                    {swapped && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onRevert(orig)}
                        className="gap-1.5 text-text-3"
                      >
                        <ArrowUUpLeft size={13} /> Cofnij ({skillMeta(orig).label})
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <SkillPickerSheet
        open={!!swapSlot}
        onOpenChange={(v) => !v && setSwapSlot(null)}
        currentLabel={swapSlot ? meta(swapMap[swapSlot] ?? swapSlot).label : ""}
        candidates={candidates}
        onPick={(target) => swapSlot && onSwap(swapSlot, target)}
      />

      <div className="mt-4 flex justify-center">
        <Button variant="ghost" size="sm" onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}

// ── Krok 5: Finał ───────────────────────────────────────────────────────────
function StepFinal({
  identity,
  loading,
  onChange,
}: {
  identity: IdentityDraft | null;
  loading: boolean;
  onChange: (d: IdentityDraft) => void;
}) {
  if (loading || !identity) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-text-3">
        <CircleNotch className="animate-spin" size={24} />
        <p className="font-serif text-body italic">GM konsultuje starsze, mroczniejsze księgi…</p>
      </div>
    );
  }

  const set = (patch: Partial<IdentityDraft>) => onChange({ ...identity, ...patch });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-center font-serif text-title-lg font-semibold text-text">Tożsamość</h1>
      <IdField
        label="Wygląd"
        value={identity.appearance}
        onChange={(v) => set({ appearance: v })}
        placeholder="Jak wygląda twój bohater?"
      />
      <IdField
        label="Osobowość"
        value={identity.personality}
        onChange={(v) => set({ personality: v })}
        placeholder="Jak się zachowuje?"
      />
      <PairBlock
        label="Więzi"
        types={BOND_TYPES}
        pairs={identity.bonds}
        onChange={(bonds) => set({ bonds })}
      />
      <PairBlock
        label="Słabości"
        types={WEAK_TYPES}
        pairs={identity.weaknesses}
        onChange={(weaknesses) => set({ weaknesses })}
      />
      <p className="text-center font-ui text-micro italic text-text-3">
        GM zna też to, o czym sam nie wiesz. Objawi się w swoim czasie.
      </p>
    </div>
  );
}

function IdField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="mb-1.5 font-ui text-micro font-semibold uppercase tracking-wide text-ember-glow">{label}</div>
      <textarea
        rows={2}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full resize-none bg-transparent font-ui text-body text-text placeholder:text-text-3 focus:outline-none"
      />
    </div>
  );
}

function PairBlock({
  label,
  types,
  pairs,
  onChange,
}: {
  label: string;
  types: Record<string, string>;
  pairs: Array<{ description: string; type: string }>;
  onChange: (p: Array<{ description: string; type: string }>) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="mb-2 font-ui text-micro font-semibold uppercase tracking-wide text-ember-glow">{label}</div>
      <div className="flex flex-col gap-2.5">
        {pairs.map((p, i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <select
              value={p.type}
              onChange={(e) => {
                const nx = [...pairs];
                nx[i] = { ...p, type: e.target.value };
                onChange(nx);
              }}
              className="h-9 w-full rounded-sm border border-line bg-inset px-2 font-ui text-label text-text focus:border-line-ember focus:outline-none"
            >
              {Object.entries(types).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <textarea
              rows={2}
              value={p.description}
              placeholder="Opisz…"
              onChange={(e) => {
                const nx = [...pairs];
                nx[i] = { ...p, description: e.target.value };
                onChange(nx);
              }}
              className="w-full resize-none rounded-sm border border-line bg-inset px-2.5 py-2 font-ui text-body text-text placeholder:text-text-3 focus:border-line-ember focus:outline-none"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
