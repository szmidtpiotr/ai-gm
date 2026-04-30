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
 * @returns {{ cmd: string, value?: number|string, key?: string, stat?: string, kind?: string } | null}
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
    const key = rest ? rest.trim() : undefined;
    return { cmd: "add item", key, kind: "weapon" };
  }
  if (p0 === "add" && p1 === "consumable") {
    const key = rest ? rest.trim() : undefined;
    return { cmd: "add item", key, kind: "consumable" };
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

/** Cache katalogów (osobno items / weapons / consumables). */
const CATALOG_TTL_MS = 60_000;
/** @type {Record<string, { rows: Record<string, unknown>[] | null; at: number }>} */
const _catalogCache = {
  items: { rows: null, at: 0 },
  weapons: { rows: null, at: 0 },
  consumables: { rows: null, at: 0 },
};

/**
 * Czy po "/admin " jesteśmy w kontekście doboru przedmiotu z katalogu DB.
 * @param {string} afterAdmin
 */
export function shouldUseAdminCatalog(afterAdmin) {
  return /^\s*add\s+(item|weapon|consumable)\b/i.test(afterAdmin || "");
}

function _apiBase() {
  const raw =
    typeof window !== "undefined" && window.API_BASE_URL ? String(window.API_BASE_URL) : "/api";
  return raw.replace(/\/+$/, "");
}

/**
 * @param {'items'|'weapons'|'consumables'} listKey
 * @param {string} path
 */
async function _fetchCatalogList(listKey, path) {
  const now = Date.now();
  const slot = _catalogCache[listKey];
  if (slot && slot.rows && now - slot.at < CATALOG_TTL_MS) {
    return slot.rows;
  }
  const token =
    typeof localStorage !== "undefined" ? localStorage.getItem("aigm_admin_token") : null;
  if (!token) {
    return [];
  }
  const url = `${_apiBase()}${path}`;
  try {
    const r = await fetch(url, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
    if (!r.ok) {
      return [];
    }
    const data = await r.json();
    const rows = Array.isArray(data.items) ? data.items : [];
    if (slot) {
      slot.rows = rows;
      slot.at = now;
    }
    return rows;
  } catch (_e) {
    return [];
  }
}

/**
 * Podpowiedzi z bazy (label + key) dla "add item|weapon|consumable &lt;fragment&gt;".
 * Zwraca null jeśli nie jesteśmy w trybie katalogu — wtedy slash_commands używa getAdminSuggestions.
 *
 * @param {string} afterAdmin
 * @returns {Promise<{ command: string, description: string }[] | null>}
 */
export async function fetchAdminCatalogSuggestions(afterAdmin) {
  if (!shouldUseAdminCatalog(afterAdmin)) {
    return null;
  }
  const trimmed = afterAdmin.trimStart();
  const m = trimmed.match(/^add\s+(item|weapon|consumable)\s*(.*)$/i);
  if (!m) {
    return [];
  }
  const branch = m[1].toLowerCase();
  const rest = (m[2] || "").trim();
  const queryToken = (rest.split(/\s+/)[0] || "").trim();
  const q = queryToken.toLowerCase();

  const listKey = branch === "item" ? "items" : branch === "weapon" ? "weapons" : "consumables";
  const path =
    branch === "item" ? "/admin/items" : branch === "weapon" ? "/admin/weapons" : "/admin/consumables";
  const rows = await _fetchCatalogList(listKey, path);

  const filtered = rows.filter((row) => {
    const active = row.is_active !== false && row.is_active !== 0;
    const label = String(row.label ?? "").toLowerCase();
    const key = String(row.key ?? "").toLowerCase();
    if (!q) {
      return active;
    }
    return label.includes(q) || key.includes(q);
  });

  filtered.sort((a, b) =>
    String(a.label || a.key || "").localeCompare(String(b.label || b.key || ""), undefined, {
      sensitivity: "base",
    }),
  );

  const max = 40;
  const slice = filtered.slice(0, max);

  return slice.map((row) => {
    const key = String(row.key ?? "").trim();
    const label = String(row.label ?? key).trim();
    const cmdBranch = branch === "item" ? "item" : branch === "weapon" ? "weapon" : "consumable";
    return {
      command: `/admin add ${cmdBranch} ${key}`,
      description: `${label} (${key})`,
    };
  });
}
