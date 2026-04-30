/**
 * Drzewo komend /admin — autocomplete i parser.
 * Importowany przez slash_commands.js i actions.js.
 */

/** @type {Record<string, Record<string, {}> | {}>} */
export const ADMIN_CMD_TREE = {
  add: { gold: {}, health: {}, item: {}, weapon: {}, consumable: {}, stat: {} },
  set: { gold: {}, health: {}, level: {}, location: {} },
  remove: { item: {} },
  clear: { inventory: {} },
  combat: { end: {} },
  quest: { add: {}, complete: {} },
  show: { state: {} },
};

/** Hinty i placeholdery dla leaf-komend */
export const ADMIN_CMD_HINTS = {
  "add gold": { hint: "Dodaj złoto", placeholder: "[ilość, np. 100]" },
  "add health": { hint: "Dodaj HP", placeholder: "[ilość lub max]" },
  "add item": { hint: "Dodaj przedmiot", placeholder: "[item_key]" },
  "add weapon": {
    hint: "Dodaj broń",
    placeholder: "[weapon_key lub sama nazwa, np. battleaxe]",
  },
  "add consumable": {
    hint: "Dodaj konsumable",
    placeholder: "[consumable_key lub sama nazwa, np. potion]",
  },
  "add stat": {
    hint: "Dodaj do statystyki",
    placeholder: "[STR|DEX|CON|INT|WIS|CHA] [wartość]",
  },
  "set gold": { hint: "Ustaw złoto", placeholder: "[ilość]" },
  "set health": { hint: "Ustaw HP", placeholder: "[ilość lub max]" },
  "set level": { hint: "Ustaw poziom", placeholder: "[1-20]" },
  "set location": { hint: "Teleportuj postać", placeholder: "[location_key]" },
  "remove item": { hint: "Usuń przedmiot", placeholder: "[item_key]" },
  "clear inventory": { hint: "Wyczyść cały plecak", placeholder: "" },
  "combat end": { hint: "Zakończ aktywną walkę", placeholder: "" },
  "quest add": { hint: "Dodaj questa do aktywnych", placeholder: "[quest_key]" },
  "quest complete": { hint: "Ukończ questa", placeholder: "[quest_key]" },
  "show state": { hint: "Pokaż stan postaci", placeholder: "" },
};

/**
 * Zwraca listę sugestii dla aktualnie wpisanego fragmentu po "/admin ".
 * @param {string} afterAdmin
 * @returns {{ command: string, description: string, placeholder?: string }[]}
 */
export function getAdminSuggestions(afterAdmin) {
  const parts = afterAdmin.trimStart().split(/\s+/);
  const token0 = (parts[0] || "").toLowerCase();
  const token1 = (parts[1] || "").toLowerCase();
  const hasSpace1 = afterAdmin.trimStart().includes(" ");

  if (hasSpace1 && ADMIN_CMD_TREE[token0]) {
    const subtree = ADMIN_CMD_TREE[token0];
    const subKeys = Object.keys(subtree);
    if (!subKeys.length) return [];
    return subKeys.filter((k) => k.startsWith(token1)).map((k) => {
      const fullCmd = `${token0} ${k}`;
      const meta = ADMIN_CMD_HINTS[fullCmd] || {};
      return {
        command: `/admin ${fullCmd}`,
        description: meta.hint || "",
        placeholder: meta.placeholder || "",
      };
    });
  }

  return Object.keys(ADMIN_CMD_TREE)
    .filter((k) => k.startsWith(token0))
    .map((k) => {
      const subtree = ADMIN_CMD_TREE[k];
      const hasChildren = Object.keys(subtree).length > 0;
      return {
        command: `/admin ${k}`,
        description: hasChildren
          ? Object.keys(subtree).join(" | ")
          : ADMIN_CMD_HINTS[k]?.hint || "",
        placeholder: "",
      };
    });
}

/**
 * Parsuje "/admin add gold 100" na body request dla POST /api/admin/cheat/{id}.
 * @param {string} raw
 * @returns {{ cmd: string, value?: number|string, key?: string, stat?: string } | null}
 */
export function parseAdminCommand(raw) {
  const t = (raw || "").trim().replace(/^\/admin\s*/i, "");
  const parts = t.split(/\s+/);
  if (!parts[0]) return null;

  const p0 = parts[0].toLowerCase();
  const p1 = (parts[1] || "").toLowerCase();
  const rest = parts.slice(2).join(" ");

  if (p0 === "add" && (p1 === "gold" || p1 === "health")) {
    const v = rest.toLowerCase() === "max" ? "max" : parseInt(rest, 10);
    return { cmd: `add ${p1}`, value: Number.isNaN(v) ? rest : v };
  }
  if (p0 === "add" && p1 === "weapon") {
    const key = rest ? (rest.startsWith("weapon_") ? rest : `weapon_${rest}`) : undefined;
    return { cmd: "add item", key };
  }
  if (p0 === "add" && p1 === "consumable") {
    const key = rest ? (rest.startsWith("consumable_") ? rest : `consumable_${rest}`) : undefined;
    return { cmd: "add item", key };
  }
  if (p0 === "add" && p1 === "item") {
    return { cmd: "add item", key: rest || undefined };
  }
  if (p0 === "add" && p1 === "stat") {
    const stat = (parts[2] || "").toUpperCase();
    const val = parseInt(parts[3] || "1", 10);
    return { cmd: "add stat", stat, value: Number.isNaN(val) ? 1 : val };
  }
  if (p0 === "set" && (p1 === "gold" || p1 === "health" || p1 === "level")) {
    const v = rest.toLowerCase() === "max" ? "max" : parseInt(rest, 10);
    return { cmd: `set ${p1}`, value: Number.isNaN(v) ? rest : v };
  }
  if (p0 === "set" && p1 === "location") {
    return { cmd: "set location", key: rest || undefined };
  }
  if (p0 === "remove" && p1 === "item") {
    return { cmd: "remove item", key: rest || undefined };
  }
  if (p0 === "clear" && p1 === "inventory") {
    return { cmd: "clear inventory" };
  }
  if (p0 === "combat" && p1 === "end") {
    return { cmd: "combat end" };
  }
  if (p0 === "quest" && (p1 === "add" || p1 === "complete")) {
    return { cmd: `quest ${p1}`, key: rest || undefined };
  }
  if (p0 === "show" && p1 === "state") {
    return { cmd: "show state" };
  }
  return null;
}
