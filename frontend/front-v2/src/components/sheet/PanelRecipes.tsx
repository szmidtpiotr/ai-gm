// #1375 BL-E1 — zakładka Receptury. Trwale znane receptury bohatera pogrupowane
// po secie (licznik „jeszcze X nieodkrytych" — bez nazw), z licznikami posiadanych
// komponentów. Dwie drogi wykonania: „Wykonaj sam" (Rzemiosło ≥1) lub „Zleć
// rzemieślnikowi" (koszt ×1.5, bez skilla). Pojawia się dopiero po nauczeniu 1.
// receptury (gating zakładki w tabs.ts/CharacterSheet).
import { useState } from "react";
import { CircleNotch, Hammer, Lock, Scroll, Storefront } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { SecHead, PanelScroll } from "./sheetUi";
import { useCharacterRecipes, useCraft } from "@/hooks/useCrafting";
import type { CraftMode, RecipeCard as RecipeCardT, RecipeSetGroup } from "@/lib/crafting";
import { outputTypeLabel } from "@/lib/crafting";

export function PanelRecipes({ characterId }: { characterId: number | undefined }) {
  const { data, isLoading } = useCharacterRecipes(characterId);
  const craft = useCraft(undefined, characterId);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ ok: boolean; text: string } | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-label">
        <CircleNotch size={22} className="animate-spin" />
      </div>
    );
  }

  const sets = data?.sets ?? [];
  const loose = data?.loose ?? [];

  const doCraft = (recipe: RecipeCardT, mode: CraftMode) => {
    if (!characterId) return;
    setBusyKey(recipe.recipe_key + mode);
    setFlash(null);
    craft.mutate(
      { characterId, recipeKey: recipe.recipe_key, mode },
      {
        onSuccess: (res) =>
          setFlash({
            ok: true,
            text: `Wykonano: ${res.recipe_label}${
              res.service_cost_gold ? ` — koszt ${res.service_cost_gold} gp` : ""
            }.`,
          }),
        onError: (e: unknown) =>
          setFlash({ ok: false, text: e instanceof Error ? e.message : "Nie udało się wykonać." }),
        onSettled: () => setBusyKey(null),
      },
    );
  };

  return (
    <PanelScroll>
      {flash && (
        <div
          className={cn(
            "mb-4 rounded-md border px-3 py-2 text-[13px]",
            flash.ok
              ? "border-ember/40 bg-ember/5 text-text"
              : "border-danger/40 bg-danger/5 text-danger-glow",
          )}
        >
          {flash.text}
        </div>
      )}

      {sets.map((s) => (
        <SetSection
          key={s.set_key}
          group={s}
          busyKey={busyKey}
          onCraft={doCraft}
        />
      ))}

      {loose.length > 0 && (
        <div className="mb-5">
          <SecHead>Luźne receptury</SecHead>
          <div className="space-y-2.5">
            {loose.map((r) => (
              <RecipeCard key={r.recipe_key} recipe={r} busyKey={busyKey} onCraft={doCraft} />
            ))}
          </div>
        </div>
      )}

      {sets.length === 0 && loose.length === 0 && (
        <p className="py-10 text-center text-[13px] text-label">
          Nie znasz jeszcze żadnej receptury. Znajdź je jako łup lub odkryj przy tyglu.
        </p>
      )}
    </PanelScroll>
  );
}

function SetSection({
  group,
  busyKey,
  onCraft,
}: {
  group: RecipeSetGroup;
  busyKey: string | null;
  onCraft: (r: RecipeCardT, mode: CraftMode) => void;
}) {
  const pct = group.total ? Math.round((group.discovered_count / group.total) * 100) : 0;
  return (
    <div className="mb-5">
      <SecHead>
        {group.set_label}
        <span className="ml-auto text-label">
          {group.discovered_count}/{group.total}
          {group.complete ? (
            <span className="text-ember"> · komplet!</span>
          ) : (
            <span> · jeszcze {group.undiscovered} nieodkrytych</span>
          )}
        </span>
      </SecHead>
      <div className="mb-3 h-1 w-full overflow-hidden rounded-full bg-line">
        <div className="h-full bg-ember/70" style={{ width: `${pct}%` }} />
      </div>
      <div className="space-y-2.5">
        {group.discovered.map((r) => (
          <RecipeCard key={r.recipe_key} recipe={r} busyKey={busyKey} onCraft={onCraft} />
        ))}
        {/* Nieodkryte części — sylwetki bez nazw (pętla domykania kolekcji). */}
        {Array.from({ length: group.undiscovered }).map((_, i) => (
          <div
            key={`ghost-${i}`}
            className="flex items-center gap-2 rounded-lg border border-dashed border-line-soft bg-bg/30 px-3 py-2.5 text-label"
          >
            <Lock size={15} weight="fill" className="opacity-40" />
            <span className="font-ui text-[12px] tracking-wide opacity-60">Nieodkryta część setu</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecipeCard({
  recipe,
  busyKey,
  onCraft,
}: {
  recipe: RecipeCardT;
  busyKey: string | null;
  onCraft: (r: RecipeCardT, mode: CraftMode) => void;
}) {
  const canNow = recipe.can_craft_now;
  const selfBusy = busyKey === recipe.recipe_key + "self";
  const svcBusy = busyKey === recipe.recipe_key + "service";
  const anyBusy = busyKey !== null;
  const selfBlocked = recipe.requires_skill_self && !recipe.can_self_craft;

  return (
    <div className="rounded-lg border border-line-soft bg-surface p-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 truncate font-ui text-[13px] font-bold text-text">
            <Scroll size={14} weight="fill" className="shrink-0 text-gold" />
            {recipe.label}
          </div>
          <div className="mt-0.5 text-[11px] text-label">
            {outputTypeLabel(recipe.output_type)}
            {recipe.output_qty > 1 ? ` ×${recipe.output_qty}` : ""}
            {recipe.craft_tier ? ` · ${recipe.craft_tier}` : ""}
          </div>
        </div>
      </div>

      {/* Liczniki posiadanych komponentów */}
      <div className="mb-2.5 flex flex-wrap gap-1.5">
        {recipe.inputs.map((inp) => (
          <span
            key={inp.item_key}
            className={cn(
              "rounded px-1.5 py-0.5 text-[11px]",
              inp.enough ? "bg-ember/10 text-ember-glow" : "bg-bg/60 text-label",
            )}
            title={inp.item_key}
          >
            {inp.label} {inp.owned}/{inp.qty}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          disabled={!canNow || selfBlocked || anyBusy}
          onClick={() => onCraft(recipe, "self")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-ui text-[12px] font-bold transition-colors",
            !canNow || selfBlocked || anyBusy
              ? "cursor-not-allowed bg-bg/50 text-label"
              : "bg-ember/15 text-ember hover:bg-ember/25",
          )}
          title={selfBlocked ? "Wymaga Rzemiosła (trade_craft) rangi ≥1" : undefined}
        >
          {selfBusy ? <CircleNotch size={13} className="animate-spin" /> : <Hammer size={13} weight="fill" />}
          Wykonaj sam
        </button>

        <button
          disabled={!canNow || anyBusy}
          onClick={() => onCraft(recipe, "service")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-ui text-[12px] font-bold transition-colors",
            !canNow || anyBusy
              ? "cursor-not-allowed bg-bg/50 text-label"
              : "bg-gold/15 text-gold hover:bg-gold/25",
          )}
          title="Rzemieślnik wykona bez wymogu skilla (koszt +50%)"
        >
          {svcBusy ? <CircleNotch size={13} className="animate-spin" /> : <Storefront size={13} weight="fill" />}
          Zleć ({recipe.service_cost_gold_hire} gp)
        </button>

        {selfBlocked && (
          <span className="text-[10.5px] text-label">
            <Lock size={11} weight="fill" className="mr-0.5 inline align-[-1px]" />
            Rzemiosło ≥1 do samodzielnego wykonania
          </span>
        )}
      </div>
    </div>
  );
}
