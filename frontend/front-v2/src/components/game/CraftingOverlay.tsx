// #1338 BL-C3 — modal Rzemiosła u rzemieślnika NPC (obok sklepu). Otwierany
// deterministycznie chipem „Rzemiosło" (OPEN_CRAFTING:<locationKey>) — jak Usługi,
// bez narratora. Lista przepisów z podświetleniem „starczy komponentów", licznikiem
// have/need na każdym składniku, opłatą usługi i przyciskiem Wytwórz. Po craftcie
// unieważniamy postać+ekwipunek → liczniki i złoto odświeżają się na żywo.
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  CheckCircle,
  CircleNotch,
  Coins,
  Cube,
  Flask,
  Hammer,
  Leaf,
  Sword,
  Wrench,
  X,
  type Icon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useCharacter } from "@/hooks/useGameData";
import { useInventory } from "@/hooks/useSheetData";
import { useLocationCrafting, useCraft } from "@/hooks/useCrafting";
import {
  hasAllComponents,
  outputTypeLabel,
  ownedQty,
  type CraftRecipe,
} from "@/lib/crafting";
import { useToast } from "@/components/ui/toast";

export function CraftingOverlay() {
  const locationKey = useAppStore((s) => s.crafting);
  const closeCrafting = useAppStore((s) => s.closeCrafting);
  const characterId = useAppStore((s) => s.currentHeroId) ?? undefined;

  const open = !!locationKey;
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && closeCrafting()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100%-1.5rem)] max-w-[720px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-modal animate-fade-in"
          aria-describedby={undefined}
        >
          {locationKey && characterId ? (
            <CraftingBody locationKey={locationKey} characterId={characterId} onClose={closeCrafting} />
          ) : (
            <div className="flex items-center justify-center gap-2 p-10 text-text-3">
              <CircleNotch className="animate-spin" size={20} />
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function CraftingBody({
  locationKey,
  characterId,
  onClose,
}: {
  locationKey: string;
  characterId: number;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const crafting = useLocationCrafting(locationKey, characterId);
  const inventory = useInventory(characterId);
  const character = useCharacter(characterId);
  const craft = useCraft(locationKey, characterId);

  const data = crafting.data;
  const inv = inventory.data;
  const sheet = character.data?.sheet_json;
  const gold = Number(sheet?.gold_gp ?? sheet?.gold ?? 0);

  function onCraft(r: CraftRecipe) {
    craft.mutate(
      { characterId, recipeKey: r.key },
      {
        onSuccess: (res) => {
          const suffix = res.dwarf_discount ? " (zniżka krasnoluda)" : "";
          toast(`Wytworzono: ${res.recipe_label} — ${res.service_cost_gold} zł${suffix}`, "success");
        },
        onError: (e) => toast(e instanceof Error ? e.message : "Nie udało się wytworzyć", "danger"),
      },
    );
  }

  return (
    <>
      {/* ── Nagłówek rzemieślnika ── */}
      <header className="flex items-center gap-3 border-b border-line bg-gradient-to-r from-[rgba(255,122,61,0.08)] to-surface px-4 py-3.5">
        <div className="flex h-12 w-12 flex-none items-center justify-center rounded-xl border border-line-ember bg-[radial-gradient(circle_at_40%_35%,rgba(255,122,61,0.25),#241c13)] text-ember-glow">
          <Hammer weight="fill" size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <DialogPrimitive.Title className="truncate font-serif text-title font-semibold text-text">
            Rzemiosło
          </DialogPrimitive.Title>
          {data?.location_label && (
            <div className="mt-0.5 truncate font-serif text-micro italic text-text-2">
              {data.location_label}
            </div>
          )}
        </div>
        <div className="flex flex-none items-center gap-1.5 rounded-pill border border-line bg-bg px-3 py-1.5 font-mono text-label font-semibold text-gold">
          <Coins weight="fill" size={14} /> {gold}
        </div>
        <button
          onClick={onClose}
          aria-label="Zamknij"
          className="flex h-9 w-9 flex-none items-center justify-center rounded-md border border-line bg-bg text-text-2 hover:border-line-ember hover:text-ember-glow"
        >
          <X size={16} />
        </button>
      </header>

      {/* ── Lista przepisów ── */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3.5 [scrollbar-width:thin]">
        {crafting.isLoading ? (
          <Loading />
        ) : crafting.isError || !data ? (
          <Empty>Rzemieślnik nie ma dziś nic do zaproponowania.</Empty>
        ) : !data.recipes.length ? (
          <Empty>Brak dostępnych przepisów w tej lokacji.</Empty>
        ) : (
          <div className="flex flex-col gap-2.5">
            {data.recipes.map((r) => (
              <RecipeCard
                key={r.key}
                recipe={r}
                inv={inv}
                gold={gold}
                busy={craft.isPending}
                onCraft={() => onCraft(r)}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

// ── Karta pojedynczego przepisu ──────────────────────────────────────────────
function RecipeCard({
  recipe,
  inv,
  gold,
  busy,
  onCraft,
}: {
  recipe: CraftRecipe;
  inv: { key: string; quantity: number; label?: string }[] | undefined;
  gold: number;
  busy: boolean;
  onCraft: () => void;
}) {
  const enoughComponents = hasAllComponents(recipe, inv);
  const enoughGold = gold >= recipe.service_cost_gold;
  const craftable = enoughComponents && enoughGold;
  const Ico = crafterIcon(recipe.crafter_type, recipe.output_type);

  // Mapa klucz→nazwa z ekwipunku (dla składników, które gracz posiada).
  const labelFor = (key: string) => inv?.find((i) => i.key === key)?.label ?? prettify(key);

  return (
    <div
      className={cn(
        "flex flex-col rounded-xl border p-3 transition-colors",
        enoughComponents
          ? "border-[rgba(168,201,131,0.45)] bg-[rgba(168,201,131,0.06)]"
          : "border-line bg-mech-card",
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex h-10 w-10 flex-none items-center justify-center rounded-lg border",
            enoughComponents
              ? "border-[rgba(168,201,131,0.4)] bg-[rgba(168,201,131,0.12)] text-success"
              : "border-line bg-[rgba(255,122,61,0.08)] text-ember-glow",
          )}
        >
          <Ico weight="fill" size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-label font-semibold leading-tight text-text">{recipe.label}</div>
          <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] text-text-3">
            <span className="rounded-sm border border-line-soft px-1 py-px">{outputTypeLabel(recipe.output_type)}</span>
            {recipe.output_type === "consumable" && (recipe.output_qty ?? 1) > 1 && (
              <span>×{recipe.output_qty}</span>
            )}
          </div>
        </div>
        {enoughComponents && (
          <span className="flex flex-none items-center gap-1 rounded-pill border border-[rgba(168,201,131,0.4)] bg-[rgba(168,201,131,0.12)] px-2 py-0.5 font-ui text-[10px] font-semibold text-success">
            <CheckCircle weight="fill" size={11} /> Starczy
          </span>
        )}
      </div>

      {/* Składniki — badge 🧩 + licznik have/need */}
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {recipe.inputs.map((inp) => {
          const have = ownedQty(inv, inp.item_key);
          const ok = have >= inp.qty;
          return (
            <span
              key={inp.item_key}
              className={cn(
                "flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[11px]",
                ok
                  ? "border-[rgba(168,201,131,0.35)] bg-[rgba(168,201,131,0.1)] text-success"
                  : "border-line-danger bg-[rgba(232,96,79,0.1)] text-danger",
              )}
            >
              <Cube weight="fill" size={11} />
              {labelFor(inp.item_key)}
              <span className="font-semibold">
                {have}/{inp.qty}
              </span>
            </span>
          );
        })}
      </div>

      {/* Opłata + przycisk Wytwórz */}
      <div className="mt-3 flex items-center gap-2">
        <div className="flex flex-1 items-center gap-1.5 font-mono text-label font-semibold text-gold">
          <Coins weight="fill" size={14} />
          {recipe.service_cost_gold > 0 ? `${recipe.service_cost_gold} zł` : "za darmo"}
        </div>
        <button
          type="button"
          disabled={!craftable || busy}
          onClick={onCraft}
          className={cn(
            "rounded-md px-4 py-2 font-ui text-micro font-semibold transition-colors",
            craftable
              ? "bg-gradient-to-br from-[#d1602c] to-ember text-white hover:brightness-110"
              : "cursor-not-allowed border border-line bg-bg text-text-3",
            busy && "opacity-60",
          )}
        >
          {!enoughComponents ? "Brak komponentów" : !enoughGold ? "Za mało złota" : "Wytwórz"}
        </button>
      </div>
    </div>
  );
}

// ── prymitywy ────────────────────────────────────────────────────────────────
function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-14 text-text-3">
      <CircleNotch className="animate-spin" size={20} />
      <span className="font-ui text-body">Rzemieślnik rozkłada narzędzia…</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-line-soft bg-surface px-4 py-8 text-center font-serif text-body text-text-3">
      {children}
    </p>
  );
}

function prettify(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

// Ikona przepisu z typu rzemieślnika / wyniku.
function crafterIcon(crafterType: string, outputType: string): Icon {
  if (outputType === "weapon_upgrade") return Sword;
  if (outputType === "armor_repair") return Wrench;
  if (crafterType === "herbalist") return Leaf;
  if (outputType === "consumable") return Flask;
  return Hammer;
}
