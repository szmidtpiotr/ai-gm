import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=18";
import { renderTable, showConfirm } from "/admin_panel/shared/table.js?v=24";

const SUB_TABS = [
  { id: "stats", label: "Stats" },
  { id: "skills", label: "Skills" },
  { id: "dc", label: "DC" },
  { id: "weapons", label: "Weapons" },
  { id: "enemies", label: "Enemies" },
  { id: "npcs", label: "NPC" },
  { id: "locations", label: "Locations" },
  { id: "conditions", label: "Conditions" },
  { id: "items", label: "Przedmioty" },
  { id: "consumables", label: "Consumables" },
  { id: "loot-tables", label: "Loot Tables" },
  { id: "archetypes", label: "Archetypes" },
  { id: "prompts", label: "Prompts" },
];

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) {
    n.className = cls;
  }
  if (text !== undefined && text !== null) {
    n.textContent = text;
  }
  return n;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail != null) {
    const d = err.body.detail;
    if (Array.isArray(d)) {
      return d.map((x) => (typeof x === "object" && x.msg ? x.msg : String(x))).join("; ");
    }
    return String(d);
  }
  return fallback;
}

function downloadJsonFile(data, filenameBase) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  a.download = `${filenameBase}_${y}${m}${day}.json`;
  a.click();
  URL.revokeObjectURL(blobUrl);
}

function normalizeDiffValue(value) {
  if (Array.isArray(value)) {
    return [...value].map((v) => normalizeDiffValue(v)).sort();
  }
  if (value && typeof value === "object") {
    const out = {};
    Object.keys(value)
      .sort()
      .forEach((k) => {
        out[k] = normalizeDiffValue(value[k]);
      });
    return out;
  }
  return value == null ? null : value;
}

function valuesDiffer(a, b) {
  return JSON.stringify(normalizeDiffValue(a)) !== JSON.stringify(normalizeDiffValue(b));
}

function buildPatchFromExplicitFields(raw, existing, spec) {
  const patch = {};
  spec.forEach(({ rawKey, patchKey, getValue, getExistingValue }) => {
    if (!Object.prototype.hasOwnProperty.call(raw, rawKey)) {
      return;
    }
    const nextValue = getValue(raw);
    const prevValue = typeof getExistingValue === "function" ? getExistingValue(existing) : existing?.[patchKey];
    if (valuesDiffer(prevValue, nextValue)) {
      patch[patchKey] = nextValue;
    }
  });
  return patch;
}

function renderGameDesignTable(tableHost, tableName, columns, rows, options = {}) {
  return renderTable(tableHost, columns, rows, {
    selectable: true,
    tableName,
    exportFilename: tableName,
    rowKey: "key",
    showTextSearch: true,
    searchPlaceholder: `Search ${tableName}…`,
    ...options,
  });
}

/** @param {string} listPath e.g. /api/admin/skills */
async function fetchExistingKeysFromAdminList(listPath) {
  const data = await adminFetch(listPath);
  return new Set((data.items || []).map((r) => String(r.key)));
}

async function fetchExistingRowsByKeyFromAdminList(listPath) {
  const data = await adminFetch(listPath);
  const out = new Map();
  (data.items || []).forEach((r) => {
    if (r && r.key != null) {
      out.set(String(r.key), r);
    }
  });
  return out;
}

async function populateEnemyLootTableSelect(fieldsRoot) {
  const sel = fieldsRoot.querySelector("[data-enemy-loot-table]");
  if (!sel) {
    return;
  }
  try {
    const lootData = await adminFetch("/api/admin/loot-tables");
    const activeLoot = (lootData.items || []).filter((t) => t.is_active !== 0 && t.is_active !== false);
    const cur = sel.value;
    sel.innerHTML = "";
    const o0 = document.createElement("option");
    o0.value = "";
    o0.textContent = "— none —";
    sel.appendChild(o0);
    activeLoot.forEach((t) => {
      const o = document.createElement("option");
      o.value = t.key;
      o.textContent = `${t.label || t.key} [${t.key}]`;
      sel.appendChild(o);
    });
    if (cur && [...sel.options].some((opt) => opt.value === cur)) {
      sel.value = cur;
    }
  } catch (_e) {
    /* leave — none — */
  }
}

function formatAllowedClasses(raw) {
  if (raw == null) {
    return "";
  }
  if (Array.isArray(raw)) {
    return raw.join(", ");
  }
  try {
    const arr = JSON.parse(String(raw));
    return Array.isArray(arr) ? arr.join(", ") : String(raw);
  } catch (_e) {
    return String(raw);
  }
}

function weaponTypeBadgeClass(row) {
  const t = String(row.weapon_type || "melee").toLowerCase();
  if (t === "ranged") {
    return "weapon-type-ranged";
  }
  if (t === "spell") {
    return "weapon-type-spell";
  }
  return "weapon-type-melee";
}

function tierBadgeClass(row) {
  const t = String(row.tier || "standard").toLowerCase();
  const m = { weak: "tier-weak", standard: "tier-standard", elite: "tier-elite", boss: "tier-boss" };
  return m[t] || "tier-standard";
}

function damageTypeBadgeClass(row) {
  const t = String(row.damage_type || "physical").toLowerCase();
  const m = {
    physical: "dmg-physical",
    magic: "dmg-magic",
    fire: "dmg-fire",
    poison: "dmg-poison",
    misc: "dmg-misc",
  };
  return m[t] || "dmg-physical";
}

function effectTypeBadgeClass(row) {
  const t = String(row.effect_type || "misc").toLowerCase();
  const m = {
    heal_hp: "effect-heal_hp",
    restore_mana: "effect-restore_mana",
    remove_condition: "effect-remove_condition",
    add_condition: "effect-add_condition",
    stat_buff: "effect-stat_buff",
    misc: "effect-misc",
  };
  return m[t] || "effect-misc";
}

async function refreshStats(host) {
  const tableHost = host.querySelector(".admin-subpanel-body");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/stats");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "stats",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "description") {
            body.description = newValue;
          }
          await adminFetch(`/api/admin/stats/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, { [key]: newValue });
          showToast("Stat updated.", "success");
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load stats."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountStats(host) {
  const root = el("div", "admin-subpanel-inner");
  const note = el("p", "admin-note muted");
  note.textContent = "Stats are seeded at install. Edit labels/descriptions only.";
  const body = el("div", "", "");
  body.dataset.subpanel = "stats";
  body.className = "admin-subpanel-body";
  root.appendChild(note);
  root.appendChild(body);
  host.appendChild(root);
  void refreshStats(host);
}

async function refreshSkills(host, statKeys) {
  const tableHost = host.querySelector(".admin-table-mount");
  const addHost = host.querySelector(".admin-add-form-fields");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/skills");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "skills",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "linked_stat", label: "Stat", editable: true, filterable: true, filterOptions: statKeys },
        { key: "rank_ceiling", label: "Ceiling", type: "number", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "linked_stat") {
            body.linked_stat = String(newValue).trim().toUpperCase();
          }
          if (key === "rank_ceiling") {
            body.rank_ceiling = Number(newValue);
          }
          if (key === "description") {
            body.description = newValue;
          }
          await adminFetch(`/api/admin/skills/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, { [key]: newValue });
          showToast("Skill updated.", "success");
        },
        onDelete: async (row, meta = {}) => {
          try {
            await adminFetch(`/api/admin/skills/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!meta.force }),
            });
            showToast("Skill deleted.", "success");
            await refreshSkills(host, statKeys);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
      },
    );

    const sel = addHost.querySelector('[data-field="linked_stat"]');
    if (sel) {
      sel.innerHTML = "";
      statKeys.forEach((k) => {
        const o = document.createElement("option");
        o.value = k;
        o.textContent = k;
        sel.appendChild(o);
      });
    }
  } catch (e) {
    showToast(parseApiError(e, "Failed to load skills."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountSkills(host, statKeys) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add skill ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" placeholder="e.g. sleight_of_hand" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field"><span>Linked stat</span><select data-field="linked_stat"></select></label>
      <label class="field"><span>Rank ceiling</span><input data-field="rank_ceiling" type="number" value="5" /></label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-skill">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add skill ▾" : "Add skill ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);
  wireBulkJsonImport(root, {
    hint: "Wklej tablicę JSON (jak w Import Templates). Klucze z przykładu (athletics, arcana) są zwykle już w bazie — dostaniesz 409, chyba że włączysz „Pomiń 409” albo zmienisz key.",
    templatesHref: "/admin_panel/templates.html#sec-skills",
    templatesAnchor: "Szablony JSON — Skills",
    placeholder: '[{ "key": "athletics", "label": "Athletics", "linked_stat": "STR", ... }]',
    validateRow: (row, i) => validateSkillImportRow(row, i, statKeys),
    buildPayload: (row) => skillImportRowToPayload(row),
    postPath: "/api/admin/skills",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/skills"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/admin/skills"),
    patchPath: (key) => `/api/admin/skills/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "linked_stat", patchKey: "linked_stat", getValue: (r) => String(r.linked_stat).trim().toUpperCase() },
        { rawKey: "rank_ceiling", patchKey: "rank_ceiling", getValue: (r) => Number(r.rank_ceiling) },
        { rawKey: "sort_order", patchKey: "sort_order", getValue: (r) => Number(r.sort_order) },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? null : String(r.description)) },
      ]),
    refresh: () => refreshSkills(host, statKeys),
    confirmNoun: "wierszy",
  });
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);

  fields.querySelector('[data-action="create-skill"]').addEventListener("click", async () => {
    const key = fields.querySelector('[data-field="key"]').value.trim();
    const label = fields.querySelector('[data-field="label"]').value.trim();
    const linked_stat = fields.querySelector('[data-field="linked_stat"]').value.trim();
    const rank_ceiling = Number(fields.querySelector('[data-field="rank_ceiling"]').value || 5);
    const description = fields.querySelector('[data-field="description"]').value.trim();
    if (!key || !label || !linked_stat) {
      showToast("Key, label, and linked stat are required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/skills", {
        method: "POST",
        body: JSON.stringify({
          key,
          label,
          linked_stat,
          rank_ceiling,
          description,
        }),
      });
      showToast("Skill created.", "success");
      await refreshSkills(host, statKeys);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });

  host.appendChild(root);
  void refreshSkills(host, statKeys);
}

async function refreshDc(host) {
  const tableHost = host.querySelector(".admin-subpanel-body");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/dc");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "dc",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "value", label: "Value", type: "number", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "value") {
            body.value = Number(newValue);
          }
          if (key === "description") {
            body.description = newValue;
          }
          await adminFetch(`/api/admin/dc/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, { [key]: newValue });
          showToast("DC tier updated.", "success");
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load DC."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountDc(host) {
  const root = el("div", "admin-subpanel-inner");
  const note = el("p", "admin-note muted");
  note.textContent = "DC tiers are fixed (easy/medium/hard/extreme/legendary). Edit values only.";
  const body = el("div", "", "");
  body.className = "admin-subpanel-body";
  root.appendChild(note);
  root.appendChild(body);
  host.appendChild(root);
  void refreshDc(host);
}

async function refreshWeapons(host, statKeys) {
  const tableHost = host.querySelector(".admin-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/weapons");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "weapons",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        {
          key: "weapon_type",
          label: "Type",
          type: "badge",
          badgeClass: weaponTypeBadgeClass,
          editable: true,
          editType: "select",
          editOptions: ["melee", "ranged", "spell"],
        },
        { key: "damage_die", label: "Die", editable: true },
        { key: "linked_stat", label: "Stat", editable: true, filterable: true, filterOptions: statKeys },
        {
          key: "allowed_classes",
          label: "Classes",
          type: "checkbox-set",
          editable: true,
          editOptions: ["warrior", "ranger", "scholar"],
          formatDisplay: (row) => formatAllowedClasses(row.allowed_classes),
        },
        { key: "two_handed", label: "2H", type: "boolean", editable: true },
        { key: "finesse", label: "Finesse", type: "boolean", editable: true },
        {
          key: "range_m",
          label: "Range m",
          editable: true,
          formatDisplay: (row) => (row.range_m != null && row.range_m !== "" ? String(row.range_m) : "—"),
        },
        { key: "weight_kg", label: "Weight kg", type: "number", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "note", label: "Note", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "weapon_type") {
            const wt = String(newValue).trim().toLowerCase();
            if (!["melee", "ranged", "spell"].includes(wt)) {
              showToast("weapon_type must be: melee, ranged, or spell", "error");
              throw new Error("invalid_weapon_type");
            }
            body.weapon_type = wt;
          }
          if (key === "damage_die") {
            body.damage_die = String(newValue).trim().toLowerCase();
          }
          if (key === "linked_stat") {
            body.linked_stat = String(newValue).trim().toUpperCase();
          }
          if (key === "allowed_classes") {
            if (!Array.isArray(newValue) || !newValue.length) {
              showToast("Select at least one class (warrior, ranger, or scholar).", "error");
              throw new Error("invalid_allowed_classes");
            }
            body.allowed_classes = newValue;
          }
          if (key === "two_handed") {
            body.two_handed = !!newValue;
          }
          if (key === "finesse") {
            body.finesse = !!newValue;
          }
          if (key === "range_m") {
            const s = String(newValue ?? "").trim();
            if (s === "") {
              body.range_m = null;
            } else {
              const n = Number(s);
              if (!Number.isFinite(n)) {
                showToast("range_m must be a number or empty.", "error");
                throw new Error("invalid_range_m");
              }
              body.range_m = n;
            }
          }
          if (key === "weight_kg") {
            body.weight_kg = Number(newValue);
          }
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "note") {
            body.note = String(newValue || "").trim() ? String(newValue) : null;
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/weapons/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {});
          showToast("Weapon updated.", "success");
        },
        onDelete: async (row, meta = {}) => {
          try {
            await adminFetch(`/api/admin/weapons/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!meta.force }),
            });
            showToast("Weapon deleted.", "success");
            await refreshWeapons(host, statKeys);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load weapons."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountWeapons(host, statKeys) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add weapon ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field"><span>Weapon type</span>
        <select data-field="weapon_type">
          <option value="melee" selected>melee</option>
          <option value="ranged">ranged</option>
          <option value="spell">spell</option>
        </select>
      </label>
      <label class="field"><span>Damage die</span><input data-field="damage_die" type="text" placeholder="d6" /></label>
      <label class="field"><span>Linked stat</span><select data-field="linked_stat"></select></label>
      <label class="field add-form-span-2"><span>Allowed classes</span>
        <span class="checkbox-inline"><label><input type="checkbox" data-class="warrior" checked /> warrior</label>
        <label><input type="checkbox" data-class="scholar" checked /> scholar</label>
        <label><input type="checkbox" data-class="ranger" /> ranger</label></span>
      </label>
      <label class="field"><span>Two-handed</span><input data-field="two_handed" type="checkbox" /></label>
      <label class="field"><span>Finesse</span><input data-field="finesse" type="checkbox" /></label>
      <label class="field"><span>Range (m)</span><input data-field="range_m" type="number" placeholder="optional" /></label>
      <label class="field"><span>Weight (kg)</span><input data-field="weight_kg" type="number" step="any" value="0" /></label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field add-form-span-2"><span>Note</span><input data-field="note" type="text" /></label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-weapon">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add weapon ▾" : "Add weapon ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);
  wireBulkJsonImport(root, {
    hint: "Wklej tablicę broni. Wymagane m.in. allowed_classes (niepusta tablica).",
    templatesHref: "/admin_panel/templates.html#sec-weapons",
    templatesAnchor: "Szablony JSON — Weapons",
    placeholder: '[{ "key": "shortsword", "damage_die": "d6", "allowed_classes": ["warrior"], ... }]',
    validateRow: (row, i) => validateWeaponImportRow(row, i, statKeys),
    buildPayload: (row) => weaponImportRowToPayload(row),
    postPath: "/api/admin/weapons",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/weapons"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/admin/weapons"),
    patchPath: (key) => `/api/admin/weapons/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "damage_die", patchKey: "damage_die", getValue: (r) => String(r.damage_die).trim() },
        { rawKey: "linked_stat", patchKey: "linked_stat", getValue: (r) => String(r.linked_stat).trim().toUpperCase() },
        { rawKey: "allowed_classes", patchKey: "allowed_classes", getValue: (r) => (Array.isArray(r.allowed_classes) ? r.allowed_classes : []) },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? null : String(r.description)) },
        { rawKey: "weapon_type", patchKey: "weapon_type", getValue: (r) => String(r.weapon_type).trim().toLowerCase() },
        { rawKey: "two_handed", patchKey: "two_handed", getValue: (r) => !!r.two_handed },
        { rawKey: "finesse", patchKey: "finesse", getValue: (r) => !!r.finesse },
        { rawKey: "range_m", patchKey: "range_m", getValue: (r) => (r.range_m == null || r.range_m === "" ? null : Number(r.range_m)) },
        { rawKey: "weight_kg", patchKey: "weight_kg", getValue: (r) => Number(r.weight_kg) },
        { rawKey: "note", patchKey: "note", getValue: (r) => (r.note == null || String(r.note).trim() === "" ? null : String(r.note)) },
        { rawKey: "is_active", patchKey: "is_active", getValue: (r) => r.is_active !== false && r.is_active !== 0 },
      ]),
    refresh: () => refreshWeapons(host, statKeys),
    confirmNoun: "wierszy",
  });
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  const sel = fields.querySelector('[data-field="linked_stat"]');
  statKeys.forEach((k) => {
    const o = document.createElement("option");
    o.value = k;
    o.textContent = k;
    sel.appendChild(o);
  });
  fields.querySelector('[data-action="create-weapon"]').addEventListener("click", async () => {
    const allowed = [];
    fields.querySelectorAll("[data-class]").forEach((c) => {
      if (c.checked) {
        allowed.push(c.getAttribute("data-class"));
      }
    });
    const rangeEl = fields.querySelector('[data-field="range_m"]');
    const rangeRaw = rangeEl.value.trim();
    let range_m = null;
    if (rangeRaw) {
      range_m = Number(rangeRaw);
      if (!Number.isFinite(range_m)) {
        showToast("Range (m) must be a number.", "info");
        return;
      }
    }
    const noteRaw = fields.querySelector('[data-field="note"]').value.trim();
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      damage_die: fields.querySelector('[data-field="damage_die"]').value.trim(),
      linked_stat: fields.querySelector('[data-field="linked_stat"]').value.trim(),
      allowed_classes: allowed,
      description: fields.querySelector('[data-field="description"]').value.trim(),
      weapon_type: fields.querySelector('[data-field="weapon_type"]').value.trim(),
      two_handed: fields.querySelector('[data-field="two_handed"]').checked,
      finesse: fields.querySelector('[data-field="finesse"]').checked,
      range_m,
      weight_kg: Number(fields.querySelector('[data-field="weight_kg"]').value || 0),
      note: noteRaw || null,
      is_active: fields.querySelector('[data-field="is_active"]').checked,
    };
    if (!payload.key || !payload.label || !payload.damage_die) {
      showToast("Key, label, and damage die are required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/weapons", { method: "POST", body: JSON.stringify(payload) });
      showToast("Weapon created.", "success");
      await refreshWeapons(host, statKeys);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });
  host.appendChild(root);
  void refreshWeapons(host, statKeys);
}

async function refreshEnemies(host) {
  const tableHost = host.querySelector(".admin-table-mount");
  renderTable(tableHost, [], null, {});
  let lootSelectOptions = [{ value: "", label: "— none —" }];
  try {
    const lootData = await adminFetch("/api/admin/loot-tables");
    const activeLoot = (lootData.items || []).filter((t) => t.is_active !== 0 && t.is_active !== false);
    lootSelectOptions = [{ value: "", label: "— none —" }].concat(
      activeLoot.map((t) => ({
        value: t.key,
        label: `${t.label || t.key} [${t.key}]`,
      })),
    );
  } catch (_e) {
    /* optional */
  }
  try {
    const data = await adminFetch("/api/admin/enemies");
    const rows = (data.items || []).map((r) => ({
      ...r,
      _ci: Array.isArray(r.conditions_immune) ? JSON.stringify(r.conditions_immune) : "[]",
      _drop_pct: Math.round((r.drop_chance != null ? Number(r.drop_chance) : 1) * 100),
    }));
    renderGameDesignTable(
      tableHost,
      "enemies",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        {
          key: "tier",
          label: "Tier",
          type: "badge",
          badgeClass: tierBadgeClass,
          editable: true,
          editType: "select",
          editOptions: ["weak", "standard", "elite", "boss"],
        },
        { key: "hp_base", label: "HP", type: "number", editable: true },
        { key: "ac_base", label: "AC", type: "number", editable: true },
        { key: "attack_bonus", label: "Atk+", type: "number", editable: true },
        { key: "damage_die", label: "Die", editable: true },
        { key: "attacks_per_turn", label: "Attacks/Turn", type: "number", editable: true },
        { key: "damage_bonus", label: "Dmg Bonus", type: "number", editable: true },
        {
          key: "damage_type",
          label: "Type",
          type: "badge",
          badgeClass: damageTypeBadgeClass,
          editable: true,
          editType: "select",
          editOptions: ["physical", "magic", "fire", "poison", "misc"],
        },
        { key: "xp_award", label: "XP", type: "number", editable: true },
        {
          key: "loot_table_key",
          label: "Loot Table",
          type: "select-dropdown",
          editable: true,
          editOptions: lootSelectOptions,
        },
        {
          key: "_drop_pct",
          label: "Drop %",
          type: "number",
          editable: true,
          min: 0,
          max: 100,
          formatDisplay: (row) =>
            row.drop_chance != null ? `${Math.round(Number(row.drop_chance) * 100)}%` : "—",
        },
        { key: "_ci", label: "Immune JSON", type: "textarea", editable: true },
        { key: "note", label: "Note", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        exportRow: (row) => {
          const copy = { ...row };
          delete copy._ci;
          delete copy._drop_pct;
          return copy;
        },
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "tier") {
            const t = String(newValue).trim().toLowerCase();
            if (!["weak", "standard", "elite", "boss"].includes(t)) {
              showToast("tier must be: weak, standard, elite, or boss", "error");
              throw new Error("invalid_tier");
            }
            body.tier = t;
          }
          if (key === "hp_base") {
            body.hp_base = Number(newValue);
          }
          if (key === "ac_base") {
            body.ac_base = Number(newValue);
          }
          if (key === "attack_bonus") {
            body.attack_bonus = Number(newValue);
          }
          if (key === "damage_die") {
            body.damage_die = String(newValue).trim().toLowerCase();
          }
          if (key === "attacks_per_turn") {
            body.attacks_per_turn = Number(newValue);
          }
          if (key === "damage_bonus") {
            body.damage_bonus = Number(newValue);
          }
          if (key === "damage_type") {
            const dt = String(newValue).trim().toLowerCase();
            if (!["physical", "magic", "fire", "poison", "misc"].includes(dt)) {
              showToast("damage_type must be: physical, magic, fire, poison, or misc", "error");
              throw new Error("invalid_damage_type");
            }
            body.damage_type = dt;
          }
          if (key === "xp_award") {
            body.xp_award = Number(newValue);
          }
          if (key === "loot_table_key") {
            body.loot_table_key = newValue === "" ? "" : String(newValue);
          }
          if (key === "_drop_pct") {
            const p = Number(newValue);
            if (!Number.isFinite(p) || p < 0 || p > 100) {
              showToast("Drop % must be between 0 and 100.", "error");
              throw new Error("invalid_drop_chance");
            }
            body.drop_chance = p / 100;
          }
          if (key === "_ci") {
            let parsed;
            try {
              parsed = JSON.parse(String(newValue || "[]"));
            } catch (_e) {
              showToast("conditions_immune must be valid JSON array.", "error");
              throw new Error("invalid_json");
            }
            if (!Array.isArray(parsed)) {
              showToast("conditions_immune must be a JSON array.", "error");
              throw new Error("invalid_json");
            }
            body.conditions_immune = parsed;
          }
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "note") {
            body.note = String(newValue || "").trim() ? String(newValue) : null;
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/enemies/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {}, {
            _ci: JSON.stringify((res.item && res.item.conditions_immune) || []),
            _drop_pct: Math.round(
              (res.item && res.item.drop_chance != null ? Number(res.item.drop_chance) : 1) * 100,
            ),
          });
          showToast("Enemy updated.", "success");
        },
        onDelete: async (row, meta = {}) => {
          try {
            await adminFetch(`/api/admin/enemies/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!meta.force }),
            });
            showToast("Enemy deleted.", "success");
            await refreshEnemies(host);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load enemies."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountEnemies(host) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add enemy ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field"><span>Tier</span>
        <select data-field="tier">
          <option value="weak">weak</option>
          <option value="standard" selected>standard</option>
          <option value="elite">elite</option>
          <option value="boss">boss</option>
        </select>
      </label>
      <label class="field"><span>HP base</span><input data-field="hp_base" type="number" value="8" /></label>
      <label class="field"><span>AC base</span><input data-field="ac_base" type="number" value="10" /></label>
      <label class="field"><span>Attack bonus</span><input data-field="attack_bonus" type="number" value="0" /></label>
      <label class="field"><span>Damage die</span><input data-field="damage_die" type="text" placeholder="d6" /></label>
      <label class="field"><span>Attacks / turn</span><input data-field="attacks_per_turn" type="number" value="1" min="1" /></label>
      <label class="field"><span>Damage bonus</span><input data-field="damage_bonus" type="number" value="0" /></label>
      <label class="field"><span>Damage type</span>
        <select data-field="damage_type">
          <option value="physical" selected>physical</option>
          <option value="magic">magic</option>
          <option value="fire">fire</option>
          <option value="poison">poison</option>
          <option value="misc">misc</option>
        </select>
      </label>
      <label class="field"><span>XP award</span><input data-field="xp_award" type="number" value="0" min="0" /></label>
      <label class="field add-form-span-2"><span>conditions_immune (JSON array)</span>
        <input data-field="conditions_immune" type="text" placeholder='["poisoned"]' /></label>
      <label class="field add-form-span-2"><span>Loot table</span>
        <select data-enemy-loot-table><option value="">— none —</option></select></label>
      <label class="field"><span>Drop chance (0–100%)</span>
        <input data-enemy-drop-chance type="number" min="0" max="100" step="1" value="100" /></label>
      <label class="field add-form-span-2"><span>Note</span><input data-field="note" type="text" /></label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-enemy">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add enemy ▾" : "Add enemy ▴";
    if (!details.classList.contains("admin-add-form-collapsed")) {
      void populateEnemyLootTableSelect(fields);
    }
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);
  wireBulkJsonImport(root, {
    hint: "Wklej tablicę wrogów. loot_table_key musi istnieć w Loot Tables (inaczej POST zwróci błąd). drop_chance: 0–1.",
    templatesHref: "/admin_panel/templates.html#sec-enemies",
    templatesAnchor: "Szablony JSON — Enemies",
    placeholder: '[{ "key": "goblin", "hp_base": 8, "ac_base": 11, ... }]',
    validateRow: (row, i) => validateEnemyImportRow(row, i),
    buildPayload: (row) => enemyImportRowToPayload(row),
    postPath: "/api/admin/enemies",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/enemies"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/admin/enemies"),
    patchPath: (key) => `/api/admin/enemies/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "hp_base", patchKey: "hp_base", getValue: (r) => Number(r.hp_base) },
        { rawKey: "ac_base", patchKey: "ac_base", getValue: (r) => Number(r.ac_base) },
        { rawKey: "attack_bonus", patchKey: "attack_bonus", getValue: (r) => Number(r.attack_bonus) },
        { rawKey: "dex_modifier", patchKey: "dex_modifier", getValue: (r) => Number(r.dex_modifier) },
        { rawKey: "damage_die", patchKey: "damage_die", getValue: (r) => String(r.damage_die).trim() },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? null : String(r.description)) },
        { rawKey: "tier", patchKey: "tier", getValue: (r) => String(r.tier).trim().toLowerCase() },
        { rawKey: "attacks_per_turn", patchKey: "attacks_per_turn", getValue: (r) => Number(r.attacks_per_turn) },
        { rawKey: "damage_bonus", patchKey: "damage_bonus", getValue: (r) => Number(r.damage_bonus) },
        { rawKey: "damage_type", patchKey: "damage_type", getValue: (r) => String(r.damage_type).trim().toLowerCase() },
        { rawKey: "xp_award", patchKey: "xp_award", getValue: (r) => Number(r.xp_award) },
        { rawKey: "conditions_immune", patchKey: "conditions_immune", getValue: (r) => (Array.isArray(r.conditions_immune) ? r.conditions_immune : []) },
        { rawKey: "loot_table_key", patchKey: "loot_table_key", getValue: (r) => (r.loot_table_key == null || String(r.loot_table_key).trim() === "" ? null : String(r.loot_table_key).trim()) },
        { rawKey: "drop_chance", patchKey: "drop_chance", getValue: (r) => Number(r.drop_chance) },
        { rawKey: "note", patchKey: "note", getValue: (r) => (r.note == null || String(r.note).trim() === "" ? null : String(r.note)) },
        { rawKey: "is_active", patchKey: "is_active", getValue: (r) => r.is_active !== false && r.is_active !== 0 },
      ]),
    refresh: () => refreshEnemies(host),
    confirmNoun: "wierszy",
  });
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  fields.querySelector('[data-action="create-enemy"]').addEventListener("click", async () => {
    let conditions_immune = [];
    const ciRaw = fields.querySelector('[data-field="conditions_immune"]').value.trim();
    if (ciRaw) {
      try {
        const parsed = JSON.parse(ciRaw);
        if (!Array.isArray(parsed)) {
          showToast("conditions_immune must be a JSON array.", "info");
          return;
        }
        conditions_immune = parsed;
      } catch (_e) {
        showToast("conditions_immune must be valid JSON.", "info");
        return;
      }
    }
    const ltRaw = fields.querySelector("[data-enemy-loot-table]").value.trim();
    const dropPctRaw = Number.parseInt(String(fields.querySelector("[data-enemy-drop-chance]").value || "100"), 10);
    const dropPct = Number.isFinite(dropPctRaw) ? Math.min(100, Math.max(0, dropPctRaw)) : 100;
    const noteRaw = fields.querySelector('[data-field="note"]').value.trim();
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      hp_base: Number(fields.querySelector('[data-field="hp_base"]').value || 0),
      ac_base: Number(fields.querySelector('[data-field="ac_base"]').value || 0),
      attack_bonus: Number(fields.querySelector('[data-field="attack_bonus"]').value || 0),
      damage_die: fields.querySelector('[data-field="damage_die"]').value.trim(),
      tier: fields.querySelector('[data-field="tier"]').value.trim(),
      attacks_per_turn: Number(fields.querySelector('[data-field="attacks_per_turn"]').value || 1),
      damage_bonus: Number(fields.querySelector('[data-field="damage_bonus"]').value || 0),
      damage_type: fields.querySelector('[data-field="damage_type"]').value.trim(),
      xp_award: Number(fields.querySelector('[data-field="xp_award"]').value || 0),
      conditions_immune,
      loot_table_key: ltRaw || null,
      drop_chance: dropPct / 100,
      note: noteRaw || null,
      description: fields.querySelector('[data-field="description"]').value.trim() || null,
      is_active: fields.querySelector('[data-field="is_active"]').checked,
    };
    if (!payload.key || !payload.label || !payload.damage_die) {
      showToast("Key, label, and damage die are required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/enemies", { method: "POST", body: JSON.stringify(payload) });
      showToast("Enemy created.", "success");
      await refreshEnemies(host);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });
  host.appendChild(root);
  void refreshEnemies(host);
}

function npcTypeBadgeClass(row) {
  const t = String(row.npc_type || "neutral").toLowerCase();
  const map = {
    neutral: "tier-standard",
    merchant: "tier-elite",
    quest_giver: "tier-boss",
    ally: "tier-weak",
  };
  return map[t] || "tier-standard";
}

function normalizeLocationKeysInput(newValue) {
  if (Array.isArray(newValue)) {
    return newValue.map((v) => String(v).trim()).filter(Boolean);
  }
  return String(newValue || "")
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

async function refreshNpcs(host) {
  const tableHost = host.querySelector(".admin-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/npcs");
    const rows = (data.data || []).map((r) => ({
      ...r,
      _location_keys_text: Array.isArray(r.location_keys) ? r.location_keys.join(", ") : "",
    }));
    renderGameDesignTable(
      tableHost,
      "npcs",
      [
        { key: "id", label: "ID", type: "number" },
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        {
          key: "npc_type",
          label: "Type",
          type: "badge",
          badgeClass: npcTypeBadgeClass,
          editable: true,
          editType: "select",
          editOptions: ["neutral", "merchant", "quest_giver", "ally"],
        },
        { key: "_location_keys_text", label: "Locations", type: "textarea", editable: true },
        { key: "is_shop", label: "Shop", type: "boolean", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "personality_json", label: "Personality JSON", type: "textarea", editable: true },
        { key: "shop_inventory_json", label: "Shop JSON", type: "textarea", editable: true },
      ],
      rows,
      {
        exportRow: (row) => {
          const copy = { ...row };
          delete copy._location_keys_text;
          return copy;
        },
        onEdit: async (row, key, newValue) => {
          const body = {};
          if (key === "label") body.label = String(newValue || "").trim();
          if (key === "npc_type") body.npc_type = String(newValue || "").trim();
          if (key === "description") body.description = String(newValue || "").trim() || null;
          if (key === "is_shop") body.is_shop = newValue ? 1 : 0;
          if (key === "is_active") body.is_active = newValue ? 1 : 0;
          if (key === "_location_keys_text") body.location_keys = normalizeLocationKeysInput(newValue);
          if (key === "personality_json") {
            try {
              JSON.parse(String(newValue || "{}"));
            } catch (_e) {
              showToast("personality_json must be valid JSON.", "error");
              throw new Error("invalid_json");
            }
            body.personality_json = String(newValue || "{}");
          }
          if (key === "shop_inventory_json") {
            try {
              JSON.parse(String(newValue || "[]"));
            } catch (_e) {
              showToast("shop_inventory_json must be valid JSON.", "error");
              throw new Error("invalid_json");
            }
            body.shop_inventory_json = String(newValue || "[]");
          }
          const res = await adminFetch(`/api/admin/npcs/${encodeURIComponent(String(row.id))}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          if (!res || !res.ok) {
            throw new Error("patch_failed");
          }
          if (key === "_location_keys_text") {
            row.location_keys = body.location_keys || [];
            row._location_keys_text = (body.location_keys || []).join(", ");
          }
          Object.assign(row, body);
          showToast("NPC updated.", "success");
        },
        onDelete: async (row) => {
          await adminFetch(`/api/admin/npcs/${encodeURIComponent(String(row.id))}`, { method: "DELETE" });
          showToast("NPC deleted.", "success");
          await refreshNpcs(host);
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load NPCs."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function validateNpcImportRow(raw, index) {
  const prefix = `Row ${index + 1}:`;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return `${prefix} must be an object`;
  }
  if (!raw.key || typeof raw.key !== "string") {
    return `${prefix} key (string) is required`;
  }
  if (!raw.label || typeof raw.label !== "string") {
    return `${prefix} label (string) is required`;
  }
  if (raw.personality_json !== undefined) {
    if (typeof raw.personality_json === "string") {
      try {
        JSON.parse(String(raw.personality_json || "{}"));
      } catch (_e) {
        return `${prefix} personality_json must be valid JSON`;
      }
    } else if (
      raw.personality_json !== null &&
      typeof raw.personality_json !== "object"
    ) {
      return `${prefix} personality_json must be JSON string or object`;
    }
  }
  if (raw.shop_inventory_json !== undefined) {
    if (typeof raw.shop_inventory_json === "string") {
      try {
        JSON.parse(String(raw.shop_inventory_json || "[]"));
      } catch (_e) {
        return `${prefix} shop_inventory_json must be valid JSON`;
      }
    } else if (
      raw.shop_inventory_json !== null &&
      typeof raw.shop_inventory_json !== "object"
    ) {
      return `${prefix} shop_inventory_json must be JSON string or array/object`;
    }
  }
  return null;
}

function npcImportRowToPayload(raw) {
  return {
    key: String(raw.key).trim(),
    label: String(raw.label).trim(),
    npc_type: String(raw.npc_type || "neutral").trim(),
    description: raw.description == null ? null : String(raw.description),
    personality_json:
      raw.personality_json == null
        ? "{}"
        : typeof raw.personality_json === "string"
          ? raw.personality_json
          : JSON.stringify(raw.personality_json),
    is_shop: raw.is_shop ? 1 : 0,
    shop_inventory_json:
      raw.shop_inventory_json == null
        ? "[]"
        : typeof raw.shop_inventory_json === "string"
          ? raw.shop_inventory_json
          : JSON.stringify(raw.shop_inventory_json),
    is_active: raw.is_active === false || raw.is_active === 0 ? 0 : 1,
    location_keys: Array.isArray(raw.location_keys) ? raw.location_keys.map((x) => String(x).trim()).filter(Boolean) : [],
  };
}

function mountNpcs(host) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add NPC ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field"><span>Type</span>
        <select data-field="npc_type">
          <option value="neutral" selected>neutral</option>
          <option value="merchant">merchant</option>
          <option value="quest_giver">quest_giver</option>
          <option value="ally">ally</option>
        </select>
      </label>
      <label class="field"><span>Shop</span><input data-field="is_shop" type="checkbox" /></label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field add-form-span-2"><span>Personality JSON</span><textarea data-field="personality_json" rows="4">{}</textarea></label>
      <label class="field add-form-span-2"><span>Shop inventory JSON</span><textarea data-field="shop_inventory_json" rows="4">[]</textarea></label>
      <label class="field add-form-span-2"><span>Location keys (one per line)</span><textarea data-field="location_keys" rows="4"></textarea></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-npc">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add NPC ▾" : "Add NPC ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);

  wireBulkJsonImport(root, {
    hint: "Wklej tablicę NPC. location_keys: tablica stringów. personality_json/shop_inventory_json: JSON string lub obiekt/tablica.",
    templatesHref: "/admin_panel/templates.html#sec-npcs",
    templatesAnchor: "Szablony JSON — NPC",
    placeholder: '[{ "key":"merchant_aldric","label":"Aldric","npc_type":"merchant","is_shop":1 }]',
    validateRow: (row, i) => validateNpcImportRow(row, i),
    buildPayload: (row) => npcImportRowToPayload(row),
    postPath: "/api/admin/npcs",
    existingKeys: async () => {
      const data = await adminFetch("/api/admin/npcs");
      return new Set((data.data || []).map((r) => String(r.key)));
    },
    refresh: () => refreshNpcs(host),
    confirmNoun: "NPC",
  });

  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  fields.querySelector('[data-action="create-npc"]').addEventListener("click", async () => {
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      npc_type: fields.querySelector('[data-field="npc_type"]').value.trim(),
      description: fields.querySelector('[data-field="description"]').value.trim() || null,
      personality_json: fields.querySelector('[data-field="personality_json"]').value || "{}",
      shop_inventory_json: fields.querySelector('[data-field="shop_inventory_json"]').value || "[]",
      is_shop: fields.querySelector('[data-field="is_shop"]').checked ? 1 : 0,
      is_active: fields.querySelector('[data-field="is_active"]').checked ? 1 : 0,
      location_keys: normalizeLocationKeysInput(fields.querySelector('[data-field="location_keys"]').value),
    };
    if (!payload.key || !payload.label) {
      showToast("Key i label są wymagane.", "info");
      return;
    }
    try {
      JSON.parse(payload.personality_json);
      JSON.parse(payload.shop_inventory_json);
    } catch (_e) {
      showToast("Personality/Shop JSON must be valid.", "error");
      return;
    }
    try {
      await adminFetch("/api/admin/npcs", { method: "POST", body: JSON.stringify(payload) });
      showToast("NPC created.", "success");
      await refreshNpcs(host);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });
  host.appendChild(root);
  void refreshNpcs(host);
}

async function refreshConditions(host) {
  const tableHost = host.querySelector(".admin-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/conditions");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "conditions",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "effect_json", label: "Effect JSON", type: "textarea", editable: true },
        { key: "description", label: "Description", editable: true },
        { key: "stackable", label: "Stack", type: "boolean", editable: true },
        { key: "auto_remove", label: "Auto remove", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "effect_json") {
            body.effect_json = newValue;
          }
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "stackable") {
            body.stackable = !!newValue;
          }
          if (key === "auto_remove") {
            body.auto_remove = String(newValue ?? "").trim();
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/conditions/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {});
          showToast("Condition updated.", "success");
        },
        onDelete: async (row, meta = {}) => {
          try {
            await adminFetch(`/api/admin/conditions/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!meta.force }),
            });
            showToast("Condition deleted.", "success");
            await refreshConditions(host);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load conditions."), "error");
    renderTable(tableHost, [], [], {});
  }
}

// ============ LOCATIONS ============
const LOCATION_RULES_DEFINITION = [
  { key: "no_combat", label: "No Combat", type: "boolean", description: "Combat is forbidden (e.g., temples, safe zones)" },
  { key: "no_loot", label: "No Loot", type: "boolean", description: "Enemies don't drop loot" },
  { key: "teleport_blocked", label: "Teleport Blocked", type: "boolean", description: "Teleportation spells don't work" },
  { key: "stealth_check", label: "Stealth Check", type: "boolean", description: "Entry requires successful stealth roll" },
  { key: "rest_bonus", label: "Rest Bonus", type: "number", default: 2, description: "HP regen multiplier (e.g., 2 = 2x HP)" },
  { key: "mana_regen", label: "Mana Regen", type: "number", default: 0, description: "Natural mana regen (0 = none, 1 = normal)" },
  { key: "required_item", label: "Required Item", type: "text", default: "torch", description: "Item required in inventory to enter" },
  { key: "reason", label: "Reason", type: "text", default: "Sacred ground", description: "Explanation shown to player (e.g., why combat is blocked)" },
];

function locationTypeBadgeClass(type) {
  if (type === "macro") return "badge-blue";
  if (type === "sub") return "badge-green";
  return "badge";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function slugifyLocationKey(label) {
  return String(label || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 100);
}

async function fetchLocationParentLabel(parentId, allLocations) {
  const parent = allLocations.find(l => l.id === parentId);
  return parent ? `${parent.label} (${parent.key})` : `ID:${parentId}`;
}

function validateLocationImportRow(row, i) {
  const errs = [];
  if (!row.label || String(row.label).trim() === "") errs.push(`[${i}] label is required`);
  if (row.key != null && String(row.key).trim() === "") errs.push(`[${i}] key must be non-empty when provided`);
  const resolvedKey = row.key != null && String(row.key).trim() !== "" ? String(row.key).trim() : slugifyLocationKey(row.label);
  if (!resolvedKey) errs.push(`[${i}] key could not be generated from label`);
  const t = String(row.location_type || "macro").toLowerCase();
  if (!["macro", "sub"].includes(t)) errs.push(`[${i}] location_type must be macro or sub`);
  if (t === "sub" && !((row.parent_id != null && Number(row.parent_id) > 0) || (row.parent_key != null && String(row.parent_key).trim() !== ""))) {
    errs.push(`[${i}] parent_id or parent_key is required for sub locations`);
  }
  return errs.length ? errs.join("; ") : null;
}

function locationImportRowToPayload(row) {
  const label = String(row.label || "").trim();
  const key = row.key != null && String(row.key).trim() !== "" ? String(row.key).trim() : slugifyLocationKey(label);
  return {
    key,
    label,
    location_type: String(row.location_type || "macro").toLowerCase(),
    parent_id: row.parent_id != null ? Number(row.parent_id) || null : null,
    parent_key: row.parent_key != null && String(row.parent_key).trim() ? String(row.parent_key).trim() : null,
    description: row.description == null ? null : String(row.description),
    rules: (() => {
      if (row.rules == null) return {};
      if (typeof row.rules === "object") return row.rules;
      try { return JSON.parse(String(row.rules)); } catch { return { text: String(row.rules) }; }
    })(),
    enemy_keys: Array.isArray(row.enemy_keys) ? row.enemy_keys : [],
    npc_keys: Array.isArray(row.npc_keys) ? row.npc_keys : [],
    is_active: row.is_active !== false && row.is_active !== 0,
  };
}

// Rules builder helper - converts rules object to/from UI
function buildRulesFromCheckboxes(container) {
  const rules = {};
  container.querySelectorAll("[data-rule-key]").forEach(el => {
    const key = el.dataset.ruleKey;
    const def = LOCATION_RULES_DEFINITION.find(r => r.key === key);
    if (!def) return;
    if (def.type === "boolean") {
      if (el.checked) rules[key] = true;
    } else if (def.type === "number") {
      const val = parseFloat(el.value);
      if (!isNaN(val)) rules[key] = val;
    } else {
      if (el.value.trim()) rules[key] = el.value.trim();
    }
  });
  return rules;
}

function setRulesCheckboxes(container, rules) {
  container.querySelectorAll("[data-rule-key]").forEach(el => {
    const key = el.dataset.ruleKey;
    const def = LOCATION_RULES_DEFINITION.find(r => r.key === key);
    if (!def) return;
    const val = rules?.[key];
    if (def.type === "boolean") {
      el.checked = !!val;
    } else {
      el.value = val != null ? String(val) : (def.default || "");
    }
  });
}

async function refreshLocations(host, statKeys) {
  const mount = host.querySelector(".admin-table-mount");
  if (!mount) return;
  try {
    const data = await adminFetch("/api/locations/admin/locations?active_only=1");
    const allLocations = data || [];
    const rows = await Promise.all(
      allLocations.map(async (r) => ({
        ...r,
        _parent_label: r.parent_id ? await fetchLocationParentLabel(r.parent_id, allLocations) : "—",
        _enemy_count: Array.isArray(r.enemy_keys) ? r.enemy_keys.length : 0,
        _rules_preview: r.rules ? (typeof r.rules === "object" ? JSON.stringify(r.rules).slice(0, 40) : String(r.rules).slice(0, 40)) : "",
        _rules: r.rules || {}, // keep full rules object for editing
      })),
    );
    renderGameDesignTable(
      mount,
      "locations",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "location_type", label: "Type", type: "badge", badgeClass: locationTypeBadgeClass, editable: true, editType: "select", editOptions: ["macro", "sub"] },
        { key: "_parent_label", label: "Parent" },
        { key: "_enemy_count", label: "Enemies", type: "number" },
        { key: "_rules_preview", label: "Rules" },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") body.label = newValue;
          if (key === "is_active") body.is_active = !!newValue;
          if (key === "location_type") body.location_type = String(newValue).trim().toLowerCase();
          const pathKey = row.key;
          const res = await adminFetch(`/api/locations/admin/locations/${encodeURIComponent(pathKey)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          return res;
        },
        onDelete: async (row, meta = {}) => {
          const doDelete = async (force) => {
            await adminFetch(`/api/locations/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!force }),
            });
          };
          try {
            await doDelete(!!meta.force);
          } catch (err) {
            // If 204 No Content or 404, treat as success for soft-delete
            if (err.status === 204 || err.status === 404) {
              return;
            }
            const detail = String(err?.body?.detail || "");
            // Location has active children and backend asks for force=true
            if (err.status === 422 && detail.toLowerCase().includes("force=true")) {
              if (meta && meta.bulk) {
                await doDelete(true);
                return;
              }
              const okForce = await showConfirm(
                "This location has active child locations. Delete location with children?",
                { dangerous: true, showForceCheckbox: true, forceCheckboxLabel: "Force delete with children" },
              );
              if (!okForce || !okForce.ok || !okForce.force) {
                return;
              }
              await doDelete(true);
              return;
            }
            throw err;
          }
        },
        extraActions: (row) => [
          { label: "Edit", class: "secondary-btn", onClick: () => openLocationEditModal(host, row, allLocations) },
        ],
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load locations."), "error");
    renderTable(mount, [], [], {});
  }
}

// Full edit modal for locations
function openLocationEditModal(host, row, allLocations) {
  const existing = document.getElementById("location-edit-modal");
  if (existing) existing.remove();

  const modal = el("div", "admin-modal");
  modal.id = "location-edit-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;";

  const content = el("div", "admin-modal-content");
  content.style.cssText = "background:var(--panel);padding:20px;border-radius:var(--radius);max-width:700px;width:90%;max-height:80vh;overflow:auto;";

  const enemiesList = window._cachedEnemiesList || [];
  const selectedEnemies = new Set(Array.isArray(row.enemy_keys) ? row.enemy_keys : []);

  // Build selected rules for multi-select
  const currentRules = row._rules || {};
  const selectedRules = Object.keys(currentRules).filter(k => {
    const def = LOCATION_RULES_DEFINITION.find(d => d.key === k);
    if (def) return true;
    return false; // custom rules handled separately
  });
  const customRules = Object.entries(currentRules).filter(([k]) => !LOCATION_RULES_DEFINITION.find(d => d.key === k));

  content.innerHTML = `
    <h3>Edit Location: ${row.label}</h3>
    <div class="edit-form-grid" style="display:grid;gap:12px;margin:16px 0;">
      <label class="field"><span>Key</span><input id="edit-key" type="text" value="${row.key}" disabled /></label>
      <label class="field"><span>Label</span><input id="edit-label" type="text" value="${row.label || ""}" /></label>
      <label class="field"><span>Type</span>
        <select id="edit-type">
          <option value="macro" ${row.location_type === "macro" ? "selected" : ""}>Macro</option>
          <option value="sub" ${row.location_type === "sub" ? "selected" : ""}>Sub</option>
        </select>
      </label>
      <label class="field"><span>Parent</span>
        <select id="edit-parent">
          <option value="">— None —</option>
          ${allLocations.filter(l => l.id !== row.id && l.location_type === "macro").map(p => 
            `<option value="${p.id}" ${p.id === row.parent_id ? "selected" : ""}>${p.label} (${p.key})</option>`
          ).join("")}
        </select>
      </label>
      <label class="field" style="grid-column:1/-1;"><span>Description</span><textarea id="edit-desc" rows="2">${row.description || ""}</textarea></label>
      
      <div class="field" style="grid-column:1/-1;">
        <span>Rules</span>
        <div class="multi-select-help" style="font-size:0.85em;color:var(--muted);margin-bottom:4px;">
          💡 <strong>Ctrl+Click</strong> (Win) or <strong>Cmd+Click</strong> (Mac) to select multiple
        </div>
        <select id="edit-rules" multiple size="6" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--panel);">
          ${LOCATION_RULES_DEFINITION.map(def => `
            <option value="${def.key}" ${currentRules[def.key] !== undefined ? "selected" : ""}>
              ${def.label} ${def.type !== "boolean" && currentRules[def.key] !== undefined ? `(${currentRules[def.key]})` : ""}
            </option>
          `).join("")}
        </select>
        <div id="edit-rules-values" style="margin-top:8px;">
          ${LOCATION_RULES_DEFINITION.filter(def => def.type !== "boolean" && currentRules[def.key] !== undefined).map(def => `
            <label style="display:flex;align-items:center;gap:8px;margin:4px 0;">
              <span>${def.label}:</span>
              <input type="text" data-rule-value="${def.key}" value="${currentRules[def.key] || def.default || ""}" style="width:120px;padding:4px 8px;" />
            </label>
          `).join("")}
        </div>
      </div>

      <div class="field" style="grid-column:1/-1;">
        <span>Custom Rules <em class="muted">(JSON key:value pairs)</em></span>
        <div id="edit-custom-rules" style="background:var(--panel-2);padding:12px;border-radius:6px;margin-top:4px;">
          ${customRules.length === 0 ? '<div class="custom-rule-row" style="display:flex;gap:8px;margin:4px 0;"><input type="text" placeholder="key" class="custom-rule-key" style="width:150px;padding:4px 8px;" /><input type="text" placeholder="value" class="custom-rule-value" style="flex:1;padding:4px 8px;" /><button type="button" class="remove-custom-rule secondary-btn" style="padding:4px 12px;">×</button></div>' : 
            customRules.map(([k, v]) => `
              <div class="custom-rule-row" style="display:flex;gap:8px;margin:4px 0;">
                <input type="text" value="${k}" class="custom-rule-key" style="width:150px;padding:4px 8px;" />
                <input type="text" value="${typeof v === 'object' ? JSON.stringify(v) : v}" class="custom-rule-value" style="flex:1;padding:4px 8px;" />
                <button type="button" class="remove-custom-rule secondary-btn" style="padding:4px 12px;">×</button>
              </div>
            `).join("")}
        </div>
        <button type="button" id="edit-add-custom-rule" class="secondary-btn" style="margin-top:8px;">+ Add Custom Rule</button>
      </div>

      <div class="field" style="grid-column:1/-1;">
        <span>Enemies</span>
        <div class="multi-select-help" style="font-size:0.85em;color:var(--muted);margin-bottom:4px;">
          💡 <strong>Ctrl+Click</strong> (Win) or <strong>Cmd+Click</strong> (Mac) to select multiple
        </div>
        <select id="edit-enemies" multiple size="6" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--panel);">
          ${enemiesList.length === 0 ? '<option disabled>No enemies available</option>' : 
            enemiesList.slice().sort((a, b) => a.label.localeCompare(b.label)).map(e => `<option value="${e.key}" ${selectedEnemies.has(e.key) ? "selected" : ""}>${e.label} (${e.key})</option>`).join("")}
        </select>
      </div>

      <label class="field"><span>Active</span><input id="edit-active" type="checkbox" ${row.is_active !== 0 ? "checked" : ""} /></label>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end;">
      <button type="button" class="secondary-btn" id="edit-cancel">Cancel</button>
      <button type="button" class="danger-btn" id="edit-delete">Delete</button>
      <button type="button" class="primary-btn" id="edit-save">Save</button>
    </div>
  `;

  // Add event listeners for rules select
  const rulesSelect = content.querySelector("#edit-rules");
  const rulesValuesContainer = content.querySelector("#edit-rules-values");
  
  rulesSelect.addEventListener("change", () => {
    const selected = Array.from(rulesSelect.selectedOptions).map(o => o.value);
    // Show value inputs for selected non-boolean rules
    let valuesHtml = "";
    selected.forEach(key => {
      const def = LOCATION_RULES_DEFINITION.find(d => d.key === key);
      if (def && def.type !== "boolean") {
        const currentVal = currentRules[key] || def.default || "";
        valuesHtml += `
          <label style="display:flex;align-items:center;gap:8px;margin:4px 0;">
            <span>${def.label}:</span>
            <input type="text" data-rule-value="${def.key}" value="${currentVal}" style="width:120px;padding:4px 8px;" />
          </label>
        `;
      }
    });
    rulesValuesContainer.innerHTML = valuesHtml;
  });

  // Add custom rule
  content.querySelector("#edit-add-custom-rule").addEventListener("click", () => {
    const container = content.querySelector("#edit-custom-rules");
    const row = document.createElement("div");
    row.className = "custom-rule-row";
    row.style.cssText = "display:flex;gap:8px;margin:4px 0;";
    row.innerHTML = `
      <input type="text" placeholder="key" class="custom-rule-key" style="width:150px;padding:4px 8px;" />
      <input type="text" placeholder="value" class="custom-rule-value" style="flex:1;padding:4px 8px;" />
      <button type="button" class="remove-custom-rule secondary-btn" style="padding:4px 12px;">×</button>
    `;
    container.appendChild(row);
  });

  // Remove custom rule
  content.querySelector("#edit-custom-rules").addEventListener("click", (e) => {
    if (e.target.classList.contains("remove-custom-rule")) {
      e.target.closest(".custom-rule-row").remove();
    }
  });

  modal.appendChild(content);
  document.body.appendChild(modal);

  // Events
  content.querySelector("#edit-cancel").addEventListener("click", () => modal.remove());
  content.querySelector("#edit-delete").addEventListener("click", async () => {
    if (!confirm(`Delete location "${row.label}" (${row.key})?`)) return;
    const doDelete = async (force) => {
      await adminFetch(`/api/locations/${encodeURIComponent(row.key)}`, {
        method: "DELETE",
        body: JSON.stringify({ force: !!force }),
      });
    };
    try {
      await doDelete(false);
      showToast("Location deleted", "success");
      modal.remove();
      refreshLocations(host);
    } catch (e) {
      const detail = String(e?.body?.detail || "");
      if (e?.status === 422 && detail.toLowerCase().includes("force=true")) {
        const okForce = confirm(
          `Location "${row.label}" has active child locations. Delete with children?`,
        );
        if (!okForce) return;
        try {
          await doDelete(true);
          showToast("Location and child locations deleted", "success");
          modal.remove();
          refreshLocations(host);
          return;
        } catch (e2) {
          showToast(parseApiError(e2, "Delete failed"), "error");
          return;
        }
      }
      showToast(parseApiError(e, "Delete failed"), "error");
    }
  });
  content.querySelector("#edit-save").addEventListener("click", async () => {
    // Build rules from multi-select
    const rules = {};
    const selectedRules = Array.from(content.querySelector("#edit-rules").selectedOptions).map(o => o.value);
    selectedRules.forEach(key => {
      const def = LOCATION_RULES_DEFINITION.find(d => d.key === key);
      if (def) {
        if (def.type === "boolean") {
          rules[key] = true;
        } else {
          // Get value from input
          const valueInput = content.querySelector(`[data-rule-value="${key}"]`);
          if (valueInput) {
            if (def.type === "number") {
              const numVal = parseFloat(valueInput.value);
              if (!isNaN(numVal)) rules[key] = numVal;
            } else {
              rules[key] = valueInput.value.trim();
            }
          }
        }
      }
    });
    
    // Add custom rules
    content.querySelectorAll("#edit-custom-rules .custom-rule-row").forEach(rowEl => {
      const keyInput = rowEl.querySelector(".custom-rule-key");
      const valueInput = rowEl.querySelector(".custom-rule-value");
      if (keyInput && valueInput && keyInput.value.trim()) {
        const key = keyInput.value.trim();
        const val = valueInput.value.trim();
        // Try to parse as number or JSON, otherwise store as string
        if (!isNaN(parseFloat(val)) && val !== "") {
          rules[key] = parseFloat(val);
        } else if (val === "true") {
          rules[key] = true;
        } else if (val === "false") {
          rules[key] = false;
        } else if (val.startsWith("{") || val.startsWith("[")) {
          try { rules[key] = JSON.parse(val); } catch { rules[key] = val; }
        } else {
          rules[key] = val;
        }
      }
    });
    
    const enemyKeys = Array.from(content.querySelector("#edit-enemies").selectedOptions).map(o => o.value);
    const body = {
      label: content.querySelector("#edit-label").value.trim(),
      location_type: content.querySelector("#edit-type").value,
      parent_id: content.querySelector("#edit-parent").value ? Number(content.querySelector("#edit-parent").value) : null,
      description: content.querySelector("#edit-desc").value.trim(),
      rules,
      enemy_keys: enemyKeys,
      is_active: content.querySelector("#edit-active").checked ? 1 : 0,
    };
    try {
      await adminFetch(`/api/locations/${encodeURIComponent(row.key)}`, { method: "PUT", body: JSON.stringify(body) });
      showToast("Location updated", "success");
      modal.remove();
      refreshLocations(host);
    } catch (e) { showToast(parseApiError(e, "Save failed"), "error"); }
  });

  // Close on backdrop click
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
}

function mountLocations(host) {
  const root = el("div", "admin-subpanel-inner");
  const versionInfo = el("div", "muted", "Locations UI version: 8D-fix-2026-04-28-1740");
  versionInfo.style.cssText = "font-size:12px;margin:0 0 8px 0;";
  root.appendChild(versionInfo);
  
  // Cache enemies for dropdowns
  let enemiesListCache = [];
  async function loadEnemiesCache() {
    try {
      const d = await adminFetch("/api/admin/enemies");
      enemiesListCache = (d.items || []).filter(e => e.is_active);
      window._cachedEnemiesList = enemiesListCache;
    } catch (e) { /* ignore */ }
  }
  loadEnemiesCache();

  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add location ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");

  // Formularz dodawania z rules dropdown i enemies dropdown (multi-select)
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" placeholder="auto-from-label" /></label>
      <label class="field"><span>Label *</span><input data-field="label" type="text" /></label>
      <label class="field"><span>Type</span>
        <select data-field="location_type" id="add-type">
          <option value="macro" selected>Macro (top-level)</option>
          <option value="sub">Sub (under macro)</option>
        </select>
      </label>
      <label class="field"><span>Parent (for sub)</span>
        <select data-field="parent_key" id="add-parent-key">
          <option value="">— Select parent macro —</option>
        </select>
      </label>
      <label class="field"><span>Parent Key (for sub)</span><input data-field="parent_key" type="text" placeholder="slug of parent macro" /></label>
      <label class="field" style="grid-column:1/-1;"><span>Description</span><textarea data-field="description" rows="2"></textarea></label>
      
      <div class="field" style="grid-column:1/-1;">
        <span>Rules</span>
        <div class="multi-select-help" style="font-size:0.85em;color:var(--muted);margin-bottom:4px;">
          💡 <strong>Ctrl+Click</strong> (Win) or <strong>Cmd+Click</strong> (Mac) to select multiple. Click again to deselect.
        </div>
        <select id="add-rules" multiple size="6" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--panel);">
          ${LOCATION_RULES_DEFINITION.map(def => `<option value="${def.key}">${def.label} ${def.type !== "boolean" ? `(default: ${def.default})` : ""} — ${def.description}</option>`).join("")}
        </select>
        <div id="add-rules-values" style="margin-top:8px;"></div>
      </div>

      <div class="field" style="grid-column:1/-1;">
        <span>Custom Rules <em class="muted">(create your own)</em></span>
        <div id="add-custom-rules" style="background:var(--panel-2);padding:12px;border-radius:6px;margin-top:4px;">
          <div class="custom-rule-row" style="display:flex;gap:8px;margin:4px 0;">
            <input type="text" placeholder="rule_key" class="custom-rule-key" style="width:150px;padding:4px 8px;" />
            <input type="text" placeholder="value (text/number/true/false/JSON)" class="custom-rule-value" style="flex:1;padding:4px 8px;" />
            <button type="button" class="remove-custom-rule secondary-btn" style="padding:4px 12px;">×</button>
          </div>
        </div>
        <button type="button" id="add-custom-rule-btn" class="secondary-btn" style="margin-top:8px;">+ Add Custom Rule</button>
      </div>

      <div class="field" style="grid-column:1/-1;">
        <span>Enemies</span>
        <div class="multi-select-help" style="font-size:0.85em;color:var(--muted);margin-bottom:4px;">
          💡 <strong>Ctrl+Click</strong> (Win) or <strong>Cmd+Click</strong> (Mac) to select multiple enemies
        </div>
        <select id="add-enemies" multiple size="6" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--panel);">
          <option disabled>Loading enemies...</option>
        </select>
      </div>

      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-location">Create</button>
  `;

  // Rules select change handler
  const rulesSelect = fields.querySelector("#add-rules");
  const rulesValuesContainer = fields.querySelector("#add-rules-values");
  rulesSelect.addEventListener("change", () => {
    const selected = Array.from(rulesSelect.selectedOptions).map(o => o.value);
    let valuesHtml = "";
    selected.forEach(key => {
      const def = LOCATION_RULES_DEFINITION.find(d => d.key === key);
      if (def && def.type !== "boolean") {
        valuesHtml += `
          <label style="display:flex;align-items:center;gap:8px;margin:4px 0;">
            <span>${def.label}:</span>
            <input type="text" data-rule-value="${def.key}" placeholder="${def.default || "value"}" style="width:120px;padding:4px 8px;" />
          </label>
        `;
      }
    });
    rulesValuesContainer.innerHTML = valuesHtml;
  });

  // Add custom rule
  fields.querySelector("#add-custom-rule-btn").addEventListener("click", () => {
    const container = fields.querySelector("#add-custom-rules");
    const row = document.createElement("div");
    row.className = "custom-rule-row";
    row.style.cssText = "display:flex;gap:8px;margin:4px 0;";
    row.innerHTML = `
      <input type="text" placeholder="rule_key" class="custom-rule-key" style="width:150px;padding:4px 8px;" />
      <input type="text" placeholder="value" class="custom-rule-value" style="flex:1;padding:4px 8px;" />
      <button type="button" class="remove-custom-rule secondary-btn" style="padding:4px 12px;">×</button>
    `;
    container.appendChild(row);
  });

  // Remove custom rule
  fields.querySelector("#add-custom-rules").addEventListener("click", (e) => {
    if (e.target.classList.contains("remove-custom-rule")) {
      e.target.closest(".custom-rule-row").remove();
    }
  });

  // Populate enemies dropdown
  setTimeout(async () => {
    await loadEnemiesCache();
    const enemiesSelect = fields.querySelector("#add-enemies");
    if (enemiesListCache.length === 0) {
      enemiesSelect.innerHTML = "<option disabled>No active enemies. Create enemies in Enemies tab first.</option>";
    } else {
      enemiesSelect.innerHTML = enemiesListCache.slice().sort((a, b) => a.label.localeCompare(b.label)).map(e => `<option value="${e.key}">${e.label} (${e.key})</option>`).join("");
    }
    try {
      const locations = await adminFetch("/api/locations/admin/locations?active_only=1");
      const parentSelect = fields.querySelector("#add-parent-key");
      const macroLocations = (locations || []).filter((loc) => loc.location_type === "macro");
      parentSelect.innerHTML = [
        '<option value="">— Select parent macro —</option>',
        ...macroLocations
          .slice()
          .sort((a, b) => String(a.label || a.key).localeCompare(String(b.label || b.key), undefined, { sensitivity: "base" }))
          .map((loc) => `<option value="${loc.key}">${loc.label || loc.key} (${loc.key})</option>`),
      ].join("");
    } catch (_e) {
      // Parent dropdown is a helper only; backend validation still catches invalid parents.
    }
  }, 100);

  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add location ▾" : "Add location ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);

  // Rules panel section with custom rule creation
  const rulesPanel = el("div", "rules-panel-section");
  rulesPanel.style.cssText = "background:var(--panel-2);padding:12px;border-radius:6px;margin:12px 0;";
  rulesPanel.innerHTML = `
    <h4 style="margin:0 0 8px 0;">📋 Rules System</h4>
    
    <details style="margin-bottom:12px;">
      <summary style="cursor:pointer;font-weight:600;color:var(--accent);">Available Rules (click to expand)</summary>
      <div class="rules-list" style="display:grid;gap:4px;margin-top:8px;">
        ${LOCATION_RULES_DEFINITION.map(def => `
          <div class="rule-item" style="display:flex;align-items:center;gap:8px;padding:6px;background:var(--panel);border-radius:4px;">
            <code style="background:#e2e8f0;padding:2px 6px;border-radius:3px;">${def.key}</code>
            <strong>${def.label}</strong>
            <span class="muted">${def.description}</span>
            <span class="muted" style="margin-left:auto;font-size:0.85em;">${def.type}${def.default ? ` (default: ${def.default})` : ""}</span>
          </div>
        `).join("")}
      </div>
    </details>
    
    <details>
      <summary style="cursor:pointer;font-weight:600;color:var(--accent);">➕ Create Custom Rule</summary>
      <div style="margin-top:8px;padding:12px;background:var(--panel);border-radius:6px;">
        <p class="muted" style="margin:0 0 8px 0;">Add your own rule that will be available in the dropdown above.</p>
        <div style="display:grid;gap:8px;">
          <label class="field">
            <span>Rule Key <em class="muted">(lowercase_snake_case)</em></span>
            <input id="new-rule-key" type="text" placeholder="e.g., poison_immunity" style="width:100%;padding:6px 8px;" />
          </label>
          <label class="field">
            <span>Label <em class="muted">(display name)</em></span>
            <input id="new-rule-label" type="text" placeholder="e.g., Poison Immunity" style="width:100%;padding:6px 8px;" />
          </label>
          <label class="field">
            <span>Type</span>
            <select id="new-rule-type" style="width:100%;padding:6px 8px;">
              <option value="boolean">Boolean (on/off)</option>
              <option value="number">Number (e.g., 2, 0.5)</option>
              <option value="text">Text (e.g., "torch", "magic_key")</option>
            </select>
          </label>
          <label class="field">
            <span>Default Value <em class="muted">(optional)</em></span>
            <input id="new-rule-default" type="text" placeholder="e.g., true, 2, torch" style="width:100%;padding:6px 8px;" />
          </label>
          <label class="field">
            <span>Description</span>
            <input id="new-rule-desc" type="text" placeholder="What this rule does..." style="width:100%;padding:6px 8px;" />
          </label>
        </div>
        <button type="button" id="create-rule-btn" class="primary-btn" style="margin-top:12px;">Add Rule to System</button>
        <div id="custom-rules-list" style="margin-top:12px;"></div>
      </div>
    </details>
  `;
  
  // Create custom rule handler
  rulesPanel.querySelector("#create-rule-btn").addEventListener("click", () => {
    const key = rulesPanel.querySelector("#new-rule-key").value.trim();
    const label = rulesPanel.querySelector("#new-rule-label").value.trim();
    const type = rulesPanel.querySelector("#new-rule-type").value;
    const defaultVal = rulesPanel.querySelector("#new-rule-default").value.trim();
    const desc = rulesPanel.querySelector("#new-rule-desc").value.trim();
    
    if (!key || !label) {
      showToast("Key and Label are required", "error");
      return;
    }
    
    // Add to definitions
    const newRule = { key, label, type, default: defaultVal || undefined, description: desc || `Custom rule: ${key}` };
    LOCATION_RULES_DEFINITION.push(newRule);
    
    // Add to dropdowns
    const rulesSelects = [fields.querySelector("#add-rules"), document.querySelector("#edit-rules")].filter(Boolean);
    rulesSelects.forEach(select => {
      if (select) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = `${label} ${type !== "boolean" && defaultVal ? `(default: ${defaultVal})` : ""} — ${desc || "Custom rule"}`;
        select.appendChild(option);
      }
    });
    
    // Clear inputs
    rulesPanel.querySelector("#new-rule-key").value = "";
    rulesPanel.querySelector("#new-rule-label").value = "";
    rulesPanel.querySelector("#new-rule-default").value = "";
    rulesPanel.querySelector("#new-rule-desc").value = "";
    
    // Show in list
    const list = rulesPanel.querySelector("#custom-rules-list");
    const item = document.createElement("div");
    item.style.cssText = "display:flex;align-items:center;gap:8px;padding:6px;background:#f0ebe0;border-radius:4px;margin:4px 0;";
    item.innerHTML = `
      <code style="background:#e2e8f0;padding:2px 6px;border-radius:3px;">${key}</code>
      <strong>${label}</strong>
      <span class="muted">${type}${defaultVal ? ` (default: ${defaultVal})` : ""}</span>
      <span class="muted" style="margin-left:auto;font-size:0.85em;">✓ Added</span>
    `;
    list.appendChild(item);
    
    showToast(`Rule "${key}" added to system`, "success");
  });
  
  root.appendChild(rulesPanel);

  // Bulk Import
  wireBulkJsonImport(root, {
    hint: "Wklej tablicę lokalizacji. Macro locations nie wymagają parent_id. Sub locations wymagają istniejącego parent_id.",
    templatesHref: "/admin_panel/templates.html#sec-locations",
    templatesAnchor: "Szablony JSON — Locations",
    placeholder: '[{ "key": "dark_forest", "label": "Dark Forest", "location_type": "macro", ... }]',
    validateRow: (row, i) => validateLocationImportRow(row, i),
    buildPayload: (row) => locationImportRowToPayload(row),
    postPath: "/api/locations",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/locations/admin/locations?active_only=0"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/locations/admin/locations?active_only=0"),
    patchPath: (key) => `/api/locations/admin/locations/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? null : String(r.description)) },
        { rawKey: "rules", patchKey: "rules", getValue: (r) => {
          if (r.rules == null) return {};
          if (typeof r.rules === "object") return r.rules;
          try { return JSON.parse(String(r.rules)); } catch { return { text: String(r.rules) }; }
        }},
        { rawKey: "enemy_keys", patchKey: "enemy_keys", getValue: (r) => (Array.isArray(r.enemy_keys) ? r.enemy_keys : []) },
        { rawKey: "is_active", patchKey: "is_active", getValue: (r) => r.is_active !== false && r.is_active !== 0 },
      ]),
    refresh: () => refreshLocations(host),
    confirmNoun: "lokalizacji",
  });

  // Pending AI locations approval
  const pendingSection = el("div", "locations-pending-section");
  pendingSection.style.cssText = "background:#f8fafc;padding:12px;border-radius:6px;margin:16px 0;";
  pendingSection.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;">
      <h4 style="margin:0;">Lokalizacje do zatwierdzenia <span id="pending-locations-badge" class="badge">0</span></h4>
      <button type="button" class="secondary-btn" id="pending-locations-refresh">Refresh</button>
    </div>
    <div id="pending-locations-table" class="table-wrap"><p class="muted">Loading pending locations...</p></div>
  `;
  root.appendChild(pendingSection);

  const pendingBadge = pendingSection.querySelector("#pending-locations-badge");
  const pendingTable = pendingSection.querySelector("#pending-locations-table");

  async function loadPendingLocations() {
    try {
      const data = await adminFetch("/api/admin/locations/pending");
      const rows = data.locations || [];
      pendingBadge.textContent = String(data.count ?? rows.length);
      if (!rows.length) {
        pendingTable.innerHTML = "<p class='muted'>No AI-generated locations waiting for approval.</p>";
        return;
      }

      const table = document.createElement("table");
      table.className = "admin-table";
      table.innerHTML = `
        <thead>
          <tr>
            <th>Label</th>
            <th>Type</th>
            <th>Parent</th>
            <th>Created</th>
            <th>Akcja</th>
          </tr>
        </thead>
        <tbody></tbody>
      `;
      const tbody = table.querySelector("tbody");
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        const parent = row.parent_label ? `${row.parent_label} (${row.parent_key || "?"})` : "—";
        tr.innerHTML = `
          <td><strong>${escapeHtml(row.label || row.key || String(row.id))}</strong><br><code>${escapeHtml(row.key || "")}</code></td>
          <td><span class="${locationTypeBadgeClass(row.location_type)}">${escapeHtml(row.location_type || "macro")}</span></td>
          <td>${escapeHtml(parent)}</td>
          <td>${escapeHtml(row.created_at || "")}</td>
          <td style="white-space:nowrap;">
            <button type="button" class="primary-btn" data-approve="${row.id}">Zatwierdź</button>
            <button type="button" class="danger-btn" data-reject="${row.id}">Odrzuć</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
      pendingTable.innerHTML = "";
      pendingTable.appendChild(table);
    } catch (e) {
      pendingTable.innerHTML = "<p class='muted'>Error loading pending locations.</p>";
      showToast(parseApiError(e, "Load pending locations failed"), "error");
    }
  }

  pendingSection.querySelector("#pending-locations-refresh").addEventListener("click", loadPendingLocations);
  pendingTable.addEventListener("click", async (event) => {
    const approveId = event.target?.dataset?.approve;
    const rejectId = event.target?.dataset?.reject;
    const id = approveId || rejectId;
    if (!id) return;
    try {
      await adminFetch(`/api/admin/locations/${encodeURIComponent(id)}/${approveId ? "approve" : "reject"}`, {
        method: "POST",
      });
      showToast(approveId ? "Location approved" : "Location rejected", "success");
      await loadPendingLocations();
      await refreshLocations(host);
    } catch (e) {
      showToast(parseApiError(e, "Location approval action failed"), "error");
    }
  });

  // Table mount
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);

  // Create button
  fields.querySelector('[data-action="create-location"]').addEventListener("click", async () => {
    const get = (k) => {
      const el = fields.querySelector(`[data-field="${k}"]`);
      if (!el) return null;
      if (el.type === "checkbox") return el.checked;
      return el.value;
    };
    
    // Build rules from multi-select
    const rules = {};
    const selectedRules = Array.from(fields.querySelector("#add-rules").selectedOptions).map(o => o.value);
    selectedRules.forEach(key => {
      const def = LOCATION_RULES_DEFINITION.find(d => d.key === key);
      if (def) {
        if (def.type === "boolean") {
          rules[key] = true;
        } else {
          const valueInput = fields.querySelector(`[data-rule-value="${key}"]`);
          if (valueInput && valueInput.value.trim()) {
            if (def.type === "number") {
              const numVal = parseFloat(valueInput.value);
              if (!isNaN(numVal)) rules[key] = numVal;
            } else {
              rules[key] = valueInput.value.trim();
            }
          }
        }
      }
    });
    
    // Add custom rules
    fields.querySelectorAll("#add-custom-rules .custom-rule-row").forEach(rowEl => {
      const keyInput = rowEl.querySelector(".custom-rule-key");
      const valueInput = rowEl.querySelector(".custom-rule-value");
      if (keyInput && valueInput && keyInput.value.trim()) {
        const key = keyInput.value.trim();
        const val = valueInput.value.trim();
        if (!isNaN(parseFloat(val)) && val !== "") {
          rules[key] = parseFloat(val);
        } else if (val === "true") {
          rules[key] = true;
        } else if (val === "false") {
          rules[key] = false;
        } else if (val.startsWith("{") || val.startsWith("[")) {
          try { rules[key] = JSON.parse(val); } catch { rules[key] = val; }
        } else {
          rules[key] = val;
        }
      }
    });
    
    const enemyKeys = Array.from(fields.querySelector("#add-enemies").selectedOptions).map(o => o.value);
    
    const label = get("label");
    const generatedKey = slugifyLocationKey(label);
    const key = get("key").trim() || generatedKey;
    const parentKey = get("parent_key").trim();
    const payload = {
      key,
      label,
      location_type: get("location_type"),
      parent_id: null,
      parent_key: parentKey || null,
      description: get("description"),
      rules,
      enemy_keys: enemyKeys,
      is_active: get("is_active") ? 1 : 0,
    };
    if (!payload.label) {
      showToast("Label is required", "error");
      return;
    }
    if (!payload.key) {
      showToast("Could not auto-generate key from label", "error");
      return;
    }
    if (payload.location_type === "sub" && !payload.parent_id && !payload.parent_key) {
      showToast("Sub location needs parent_id or parent_key", "error");
      return;
    }
    try {
      await adminFetch("/api/locations", { method: "POST", body: JSON.stringify(payload) });
      showToast("Location created", "success");
      // Clear form
      fields.querySelectorAll("[data-field]").forEach((el) => {
        if (el.type === "checkbox") el.checked = el.dataset.field === "is_active";
        else el.value = "";
      });
      fields.querySelector("#add-rules").selectedIndex = -1;
      fields.querySelector("#add-rules-values").innerHTML = "";
      fields.querySelector("#add-enemies").selectedIndex = -1;
      // Clear custom rules except one empty row
      const customContainer = fields.querySelector("#add-custom-rules");
      customContainer.innerHTML = `
        <div class="custom-rule-row" style="display:flex;gap:8px;margin:4px 0;">
          <input type="text" placeholder="rule_key" class="custom-rule-key" style="width:150px;padding:4px 8px;" />
          <input type="text" placeholder="value (text/number/true/false/JSON)" class="custom-rule-value" style="flex:1;padding:4px 8px;" />
          <button type="button" class="remove-custom-rule secondary-btn" style="padding:4px 12px;">×</button>
        </div>
      `;
      await refreshLocations(host);
    } catch (e) {
      showToast(parseApiError(e, "Create failed"), "error");
    }
  });

  // Location Integrity System section
  const flagsSection = el("div", "locations-flags-section");
  flagsSection.style.cssText = "background:#f8fafc;padding:12px;border-radius:6px;margin:16px 0;";
  flagsSection.innerHTML = `
    <h4>Location Integrity System</h4>
    <div style="display:grid;gap:8px;margin:8px 0;">
      <label style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;">
        <span>Location Integrity enabled</span><input type="checkbox" id="flag-integrity" checked />
      </label>
      <label style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;">
        <span>Auto-create unknown locations</span><input type="checkbox" id="flag-auto-create" checked />
      </label>
      <label style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;">
        <span>Parser JSON (Option A)</span><input type="checkbox" id="flag-parser-json" checked />
      </label>
    </div>
    <div id="flags-info" class="muted" style="font-size:0.85em;margin:8px 0;">Global defaults: integrity ON / auto-create ON / parser JSON ON</div>
    <div style="display:flex;gap:8px;">
      <button type="button" class="primary-btn" id="flags-save">Save</button>
    </div>
  `;
  root.appendChild(flagsSection);

  // Log section
  const logSection = el("div", "locations-log-section");
  logSection.innerHTML = `
    <h4>Location Integrity Log</h4>
    <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center;">
      <input type="date" id="log-since" /><input type="date" id="log-until" />
      <button type="button" class="secondary-btn" id="log-refresh">Refresh</button>
    </div>
    <div id="loc-log-table" class="table-wrap"><p class="muted">Select date range and click Refresh to view logs.</p></div>
  `;
  root.appendChild(logSection);

  host.appendChild(root);

  // Flags events
  const flagsInfo = flagsSection.querySelector("#flags-info");
  flagsSection.querySelector("#flags-save").addEventListener("click", async () => {
    const flags = {
      location_integrity_enabled: flagsSection.querySelector("#flag-integrity").checked ? 1 : 0,
      location_auto_create_enabled: flagsSection.querySelector("#flag-auto-create").checked ? 1 : 0,
      location_parser_json_enabled: flagsSection.querySelector("#flag-parser-json").checked ? 1 : 0,
    };
    try {
      await adminFetch("/api/admin/config/location-flags", { method: "PUT", body: JSON.stringify(flags) });
      showToast("Flags saved", "success");
      loadFlags();
    } catch (e) { showToast(parseApiError(e, "Save failed"), "error"); }
  });

  // Log events
  const logTable = logSection.querySelector("#loc-log-table");
  logSection.querySelector("#log-refresh").addEventListener("click", async () => {
    const since = logSection.querySelector("#log-since").value;
    const until = logSection.querySelector("#log-until").value;
    const params = new URLSearchParams();
    if (since) params.append("since", since);
    if (until) params.append("until", until);
    params.append("limit", "50");
    try {
      const data = await adminFetch(`/api/admin/location-log?${params.toString()}`);
      const logs = data.entries || [];
      if (!logs.length) { logTable.innerHTML = "<p class='muted'>No log entries for selected range.</p>"; return; }
      let html = "";
      for (const log of logs) {
        const time = new Date(log.created_at).toLocaleString("pl-PL");
        const blocked = log.reason_blocked && log.reason_blocked !== "allowed";
        const cls = blocked ? "blocked" : "allowed";
        const icon = blocked ? "🚫" : "✅";
        html += `<div class="log-entry ${cls}"><span class="log-time">${time}</span> ${icon} ${log.attempted_move || "move"} <span class="log-loc">${log.current_location_key || "?"}</span>${blocked ? ` <span class="log-reason">(${log.reason_blocked})</span>` : ""}</div>`;
      }
      logTable.innerHTML = html;
    } catch (e) { showToast(parseApiError(e, "Load log failed"), "error"); logTable.innerHTML = "<p class='muted'>Error loading logs.</p>"; }
  });

  // Load flags
  async function loadFlags() {
    try {
      const flags = await adminFetch("/api/admin/config/location-flags");
      flagsSection.querySelector("#flag-integrity").checked = flags.location_integrity_enabled;
      flagsSection.querySelector("#flag-auto-create").checked = flags.location_auto_create_enabled;
      flagsSection.querySelector("#flag-parser-json").checked = flags.location_parser_json_enabled;
      const gi = flags.location_integrity_enabled ? "ON" : "OFF";
      const ga = flags.location_auto_create_enabled ? "ON" : "OFF";
      const gj = flags.location_parser_json_enabled ? "ON" : "OFF";
      flagsInfo.textContent = `Global defaults: integrity ${gi} / auto-create ${ga} / parser JSON ${gj}`;
    } catch (e) { flagsInfo.textContent = "Global defaults: integrity ON / auto-create ON / parser JSON ON (error loading)"; }
  }

  // Init
  refreshLocations(host);
  loadPendingLocations();
  loadFlags();
}

function mountConditions(host) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add condition ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field add-form-span-2"><span>Effect JSON</span>
        <textarea data-field="effect_json" rows="3" placeholder='{"stat_mods":{"STR":-2},"duration":"3 turns"}'></textarea>
      </label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field"><span>Stackable</span><input data-field="stackable" type="checkbox" /></label>
      <label class="field add-form-span-2"><span>Auto remove</span><input data-field="auto_remove" type="text" placeholder="e.g. end_of_encounter" /></label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-condition">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add condition ▾" : "Add condition ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);
  wireBulkJsonImport(root, {
    hint: "Wklej tablicę stanów. effect_json może być stringiem JSON lub obiektem.",
    templatesHref: "/admin_panel/templates.html#sec-conditions",
    templatesAnchor: "Szablony JSON — Conditions",
    placeholder: '[{ "key": "poisoned", "effect_json": "{...}", ... }]',
    validateRow: (row, i) => validateConditionImportRow(row, i),
    buildPayload: (row) => conditionImportRowToPayload(row),
    postPath: "/api/admin/conditions",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/conditions"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/admin/conditions"),
    patchPath: (key) => `/api/admin/conditions/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "effect_json", patchKey: "effect_json", getValue: (r) => (typeof r.effect_json === "string" ? r.effect_json : JSON.stringify(r.effect_json)) },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? null : String(r.description)) },
        { rawKey: "stackable", patchKey: "stackable", getValue: (r) => !!r.stackable },
        { rawKey: "auto_remove", patchKey: "auto_remove", getValue: (r) => (r.auto_remove == null || String(r.auto_remove).trim() === "" ? null : String(r.auto_remove).trim()) },
        { rawKey: "is_active", patchKey: "is_active", getValue: (r) => r.is_active !== false && r.is_active !== 0 },
      ]),
    refresh: () => refreshConditions(host),
    confirmNoun: "wierszy",
  });
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  fields.querySelector('[data-action="create-condition"]').addEventListener("click", async () => {
    const ar = fields.querySelector('[data-field="auto_remove"]').value.trim();
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      effect_json: fields.querySelector('[data-field="effect_json"]').value.trim(),
      description: fields.querySelector('[data-field="description"]').value.trim() || null,
      stackable: fields.querySelector('[data-field="stackable"]').checked,
      auto_remove: ar || null,
      is_active: fields.querySelector('[data-field="is_active"]').checked,
    };
    if (!payload.key || !payload.label || !payload.effect_json) {
      showToast("Key, label, and effect JSON are required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/conditions", { method: "POST", body: JSON.stringify(payload) });
      showToast("Condition created.", "success");
      await refreshConditions(host);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });
  host.appendChild(root);
  void refreshConditions(host);
}

function itemTypeBadgeClass(row) {
  const t = String(row.item_type || "misc").toLowerCase();
  const ok = ["weapon", "armor", "consumable", "misc", "quest"];
  return `item-type-${ok.includes(t) ? t : "misc"}`;
}

const IMPORT_KEY_RE = /^[a-z0-9_]{1,40}$/;
const IMPORT_DAMAGE_DIE_RE = /^\d*d\d+$/i;

/**
 * @param {HTMLElement} root
 * @param {{
 *   hint: string,
 *   templatesHref?: string,
 *   templatesAnchor?: string,
 *   placeholder?: string,
 *   validateRow: (raw: unknown, index: number) => string | null,
 *   buildPayload?: (raw: object) => object,
 *   postPath?: string,
 *   refresh: () => void | Promise<void>,
 *   confirmNoun?: string,
 *   existingKeys?: () => Promise<Set<string>>,
 *   existingRows?: () => Promise<Map<string, object>>,
 *   patchPath?: (key: string, raw: object) => string,
 *   buildDuplicatePatch?: (raw: object, existing: object) => object,
 *   commitRows?: (
 *     parsed: object[],
 *     ctx: { skip409: boolean },
 *   ) => Promise<{ okn: number; skip409n: number; fail: string[]; footer?: string }>,
 * }} opts
 */
function wireBulkJsonImport(root, opts) {
  const templatesHref = opts.templatesHref || "/admin_panel/templates.html";
  const templatesAnchor = opts.templatesAnchor || "Import Templates — przykłady JSON";
  const noun = opts.confirmNoun || "wierszy";
  const bulk = el("details", "admin-bulk-import");
  bulk.innerHTML = `
    <summary>Bulk import (JSON array)</summary>
    <p class="muted">${opts.hint}</p>
    <p class="muted"><a href="${templatesHref}" target="_blank" rel="noopener noreferrer">${templatesAnchor}</a></p>
    <label class="admin-bulk-skip muted"><input type="checkbox" data-bulk-skip-409 checked /> Pomiń wiersze przy 409 (klucz już istnieje)</label>
    <textarea class="admin-bulk-textarea" data-bulk-json rows="8"></textarea>
    <div class="admin-bulk-actions">
      <button type="button" class="secondary-btn" data-bulk-dry>Dry run</button>
      <button type="button" class="primary-btn" data-bulk-commit>Commit</button>
    </div>
    <pre class="admin-bulk-result muted" data-bulk-result></pre>
  `;
  root.appendChild(bulk);
  const ta = bulk.querySelector("[data-bulk-json]");
  ta.placeholder = opts.placeholder || "[...]";
  const resultPre = bulk.querySelector("[data-bulk-result]");
  bulk.querySelector("[data-bulk-dry]").addEventListener("click", async () => {
    resultPre.textContent = "";
    let parsed;
    try {
      parsed = JSON.parse(ta.value || "[]");
    } catch (e) {
      resultPre.textContent = `Invalid JSON: ${e.message || e}`;
      showToast("Invalid JSON.", "error");
      return;
    }
    if (!Array.isArray(parsed)) {
      resultPre.textContent = "Top-level value must be a JSON array.";
      showToast("Expected array.", "error");
      return;
    }
    const errors = [];
    parsed.forEach((row, i) => {
      const err = opts.validateRow(row, i);
      if (err) {
        errors.push(err);
      }
    });
    const dupWarn = [];
    if ((opts.existingKeys || opts.existingRows) && errors.length === 0) {
      try {
        const existingKeys = opts.existingKeys ? await opts.existingKeys() : null;
        const existingRows = opts.existingRows ? await opts.existingRows() : null;
        parsed.forEach((row, i) => {
          if (row && typeof row === "object" && row.key != null) {
            const k = String(row.key).trim();
            if (k && ((existingKeys && existingKeys.has(k)) || (existingRows && existingRows.has(k)))) {
              const existing = existingRows ? existingRows.get(k) : null;
              const patch =
                existing && typeof opts.buildDuplicatePatch === "function" ? opts.buildDuplicatePatch(row, existing) : {};
              if (patch && Object.keys(patch).length) {
                dupWarn.push(`Row ${i + 1} (${k}): duplicate key with changed fields -> will PATCH changed values only.`);
              } else {
                dupWarn.push(`Row ${i + 1} (${k}): duplicate key with no new field values -> will be skipped.`);
              }
            }
          }
        });
      } catch (e) {
        resultPre.textContent = `Nie można wczytać istniejących kluczy: ${parseApiError(e, "błąd")}`;
        showToast("Dry run: nie udało się pobrać listy z API.", "error");
        return;
      }
    }
    if (errors.length) {
      resultPre.textContent = errors.join("\n");
      showToast(`Dry run: ${errors.length} issue(s): ${errors.slice(0, 3).join(" | ")}`, "info");
      return;
    }
    let msg = `OK — ${parsed.length} ${noun} gotowych do importu.`;
    if (dupWarn.length) {
      msg += `\n\nUwaga — duplikaty kluczy:\n${dupWarn.join("\n")}`;
      showToast(`Dry run OK. ${dupWarn.length} klucz(y) już w bazie.`, "info");
    } else {
      showToast("Dry run OK.", "success");
    }
    resultPre.textContent = msg;
  });
  bulk.querySelector("[data-bulk-commit]").addEventListener("click", async () => {
    let parsed;
    try {
      parsed = JSON.parse(ta.value || "[]");
    } catch (e) {
      showToast(`Invalid JSON: ${e.message || e}`, "error");
      return;
    }
    if (!Array.isArray(parsed)) {
      showToast("Expected array.", "error");
      return;
    }
    const errors = [];
    parsed.forEach((row, i) => {
      const err = opts.validateRow(row, i);
      if (err) {
        errors.push(err);
      }
    });
    if (errors.length) {
      resultPre.textContent = errors.join("\n");
      showToast(`Fix validation errors before commit: ${errors.slice(0, 3).join(" | ")}`, "error");
      return;
    }
    const skip409 = bulk.querySelector("[data-bulk-skip-409]")?.checked ?? true;
    const confirmMsg = opts.commitRows
      ? `Zaimportować ${parsed.length} tabel loot (tworzenie tabel + wpisy entries)?`
      : `Utworzyć ${parsed.length} rekord(ów) z JSON?`;
    const ok = await showConfirm(confirmMsg, { dangerous: false });
    if (!ok) {
      return;
    }
    let okn = 0;
    let skip409n = 0;
    const fail = [];
    let footer = "";
    if (opts.commitRows) {
      const res = await opts.commitRows(parsed, { skip409 });
      okn = res.okn;
      skip409n = res.skip409n;
      fail.push(...res.fail);
      footer = res.footer || "";
    } else {
      const postPath = opts.postPath;
      const buildPayload = opts.buildPayload;
      if (!postPath || !buildPayload) {
        showToast("Bulk import: brak postPath/buildPayload.", "error");
        return;
      }
      let existingRows = null;
      if (opts.existingRows) {
        existingRows = await opts.existingRows();
      }
      const updates = [];
      if (existingRows && typeof opts.buildDuplicatePatch === "function") {
        parsed.forEach((r) => {
          const key = r && typeof r === "object" && r.key != null ? String(r.key).trim() : "";
          if (!key || !existingRows.has(key)) {
            return;
          }
          const patch = opts.buildDuplicatePatch(r, existingRows.get(key));
          if (patch && Object.keys(patch).length) {
            updates.push({ key, patch, raw: r });
          }
        });
      }
      if (updates.length) {
        const ack = await showConfirm(
          `Found ${updates.length} duplicate key(s) with new field values. Check the box to apply PATCH only for changed fields.`,
          {
            showForceCheckbox: true,
            forceCheckboxLabel: "I agree to update duplicate rows with changed fields only",
          },
        );
        if (!ack || !ack.ok) {
          showToast("Import cancelled.", "info");
          return;
        }
      }
      for (let i = 0; i < parsed.length; i += 1) {
        const r = parsed[i];
        const key = r && typeof r === "object" && r.key != null ? String(r.key) : `row ${i + 1}`;
        const existing = existingRows && existingRows.get(String(key).trim());
        const patch =
          existing && typeof opts.buildDuplicatePatch === "function" ? opts.buildDuplicatePatch(r, existing) : null;
        try {
          if (existing && patch && Object.keys(patch).length && typeof opts.patchPath === "function") {
            await adminFetch(opts.patchPath(String(key).trim(), r), {
              method: "PATCH",
              body: JSON.stringify({ ...patch, force: false }),
            });
            okn += 1;
            existingRows.set(String(key).trim(), { ...existing, ...patch });
          } else if (existing) {
            skip409n += 1;
          } else {
            await adminFetch(postPath, { method: "POST", body: JSON.stringify(buildPayload(r)) });
            okn += 1;
          }
        } catch (e) {
          if (skip409 && e instanceof APIError && e.status === 409) {
            skip409n += 1;
            continue;
          }
          fail.push(`${key}: ${parseApiError(e, "failed")}`);
        }
      }
    }
    resultPre.textContent = [
      `Utworzono: ${okn}. Pominięto (409, klucz już istnieje): ${skip409n}. Inne błędy: ${fail.length}`,
      footer,
      fail.length ? `\n${fail.join("\n")}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    const bad = fail.length;
    showToast(`Import: ${okn} nowych, ${skip409n} pominiętych (409), ${bad} błędów.`, bad ? "info" : "success");
    await opts.refresh();
  });
}

function validateItemImportRow(raw, index) {
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  const key = String(raw.key || "").trim();
  const lbl = String(raw.label || "").trim();
  if (!key) {
    return `${label}: key is required`;
  }
  if (!/^[a-z0-9_]{1,40}$/.test(key)) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!lbl) {
    return `${label}: label is required`;
  }
  const it = String(raw.item_type || "misc").toLowerCase();
  if (!["weapon", "armor", "consumable", "misc", "quest"].includes(it)) {
    return `${label}: item_type must be weapon|armor|consumable|misc|quest`;
  }
  const gp = raw.value_gp != null ? Number(raw.value_gp) : 0;
  const w = raw.weight != null ? Number(raw.weight) : 0;
  if (!Number.isFinite(gp) || gp < 0) {
    return `${label}: value_gp must be a number >= 0`;
  }
  if (!Number.isFinite(w) || w < 0) {
    return `${label}: weight must be a number >= 0`;
  }
  if (raw.weight_kg != null) {
    const wkg = Number(raw.weight_kg);
    if (!Number.isFinite(wkg) || wkg < 0) {
      return `${label}: weight_kg must be a number >= 0`;
    }
  }
  if (raw.proficiency_classes != null) {
    if (!Array.isArray(raw.proficiency_classes)) {
      return `${label}: proficiency_classes must be an array of strings`;
    }
    for (const pc of raw.proficiency_classes) {
      const p = String(pc || "").toLowerCase();
      if (!["warrior", "ranger", "scholar"].includes(p)) {
        return `${label}: invalid proficiency class "${pc}"`;
      }
    }
  }
  if (raw.effect_json != null && String(raw.effect_json).trim()) {
    try {
      JSON.parse(String(raw.effect_json));
    } catch (_e) {
      return `${label}: effect_json must be valid JSON`;
    }
  }
  return null;
}

function itemImportRowToPayload(r) {
  return {
    key: String(r.key).trim(),
    label: String(r.label).trim(),
    item_type: String(r.item_type || "misc").toLowerCase(),
    description: r.description != null ? String(r.description) : "",
    value_gp: r.value_gp != null ? Number(r.value_gp) : 0,
    weight: r.weight != null ? Number(r.weight) : 0,
    weight_kg: r.weight_kg != null ? Number(r.weight_kg) : 0,
    proficiency_classes: Array.isArray(r.proficiency_classes) ? r.proficiency_classes : [],
    note: r.note != null && String(r.note).trim() ? String(r.note) : null,
    effect_json: r.effect_json != null && String(r.effect_json).trim() ? String(r.effect_json) : null,
    is_active: r.is_active !== false && r.is_active !== 0,
  };
}

/**
 * @param {unknown} en
 * @param {string} label e.g. "Row 1 entry 2"
 * @returns {string | null}
 */
function validateLootEntryImportSpec(en, label) {
  if (!en || typeof en !== "object") {
    return `${label}: must be an object`;
  }
  const ik = en.item_key != null && String(en.item_key).trim() ? String(en.item_key).trim() : "";
  const wk = en.weapon_key != null && String(en.weapon_key).trim() ? String(en.weapon_key).trim() : "";
  const ck = en.consumable_key != null && String(en.consumable_key).trim() ? String(en.consumable_key).trim() : "";
  const nSet = (ik ? 1 : 0) + (wk ? 1 : 0) + (ck ? 1 : 0);
  if (nSet !== 1) {
    return `${label}: exactly one of item_key, weapon_key, consumable_key (non-empty)`;
  }
  const weight = en.weight != null ? Number(en.weight) : 10;
  const qty_min = en.qty_min != null ? Number(en.qty_min) : 1;
  const qty_max = en.qty_max != null ? Number(en.qty_max) : 1;
  if (!Number.isFinite(weight) || weight < 1 || weight > 100) {
    return `${label}: weight must be a number in range 1..100`;
  }
  if (!Number.isFinite(qty_min) || qty_min < 1) {
    return `${label}: qty_min must be a number >= 1`;
  }
  if (!Number.isFinite(qty_max) || qty_max < 1) {
    return `${label}: qty_max must be a number >= 1`;
  }
  if (qty_min > qty_max) {
    return `${label}: qty_min must be <= qty_max`;
  }
  return null;
}

/**
 * @param {unknown} raw
 * @param {number} index
 * @returns {string | null}
 */
function validateLootTableBulkRow(raw, index) {
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  const key = String(raw.key || "").trim();
  if (!key) {
    return `${label}: key is required`;
  }
  if (!IMPORT_KEY_RE.test(key)) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!String(raw.label || "").trim()) {
    return `${label}: label is required`;
  }
  const entries = raw.entries;
  if (entries == null) {
    return null;
  }
  if (!Array.isArray(entries)) {
    return `${label}: entries must be an array or omitted`;
  }
  for (let j = 0; j < entries.length; j += 1) {
    const err = validateLootEntryImportSpec(entries[j], `${label} entry ${j + 1}`);
    if (err) {
      return err;
    }
  }
  return null;
}

/** @param {object} en */
function lootEntryImportToPayload(en) {
  const weight = en.weight != null ? Number(en.weight) : 10;
  const qty_min = en.qty_min != null ? Number(en.qty_min) : 1;
  const qty_max = en.qty_max != null ? Number(en.qty_max) : 1;
  const payload = { weight, qty_min, qty_max };
  const ik = en.item_key != null && String(en.item_key).trim() ? String(en.item_key).trim() : "";
  const wk = en.weapon_key != null && String(en.weapon_key).trim() ? String(en.weapon_key).trim() : "";
  const ck = en.consumable_key != null && String(en.consumable_key).trim() ? String(en.consumable_key).trim() : "";
  if (ik) {
    payload.item_key = ik;
  } else if (wk) {
    payload.weapon_key = wk;
  } else {
    payload.consumable_key = ck;
  }
  return payload;
}

/**
 * @param {object[]} parsed
 * @param {{ skip409: boolean }} ctx
 */
async function commitLootTablesBulkImport(parsed, ctx) {
  const { skip409 } = ctx;
  let okn = 0;
  let skip409n = 0;
  const fail = [];
  let entriesOk = 0;
  let entriesFail = 0;
  let existingRows = new Map();
  try {
    existingRows = await fetchExistingRowsByKeyFromAdminList("/api/admin/loot-tables");
  } catch (_e) {
    existingRows = new Map();
  }
  const duplicateUpdates = [];
  parsed.forEach((r) => {
    const tableKey = String(r?.key || "").trim();
    if (!tableKey || !existingRows.has(tableKey)) {
      return;
    }
    const patch = buildPatchFromExplicitFields(r, existingRows.get(tableKey), [
      { rawKey: "label", patchKey: "label", getValue: (x) => String(x.label).trim() },
      { rawKey: "description", patchKey: "description", getValue: (x) => (x.description == null ? "" : String(x.description)) },
      { rawKey: "is_active", patchKey: "is_active", getValue: (x) => x.is_active !== false && x.is_active !== 0 },
    ]);
    if (Object.keys(patch).length) {
      duplicateUpdates.push({ key: tableKey, patch });
    }
  });
  if (duplicateUpdates.length) {
    const ack = await showConfirm(
      `Found ${duplicateUpdates.length} duplicate loot table key(s) with changed metadata. Check the box to PATCH changed table fields before entries sync.`,
      {
        showForceCheckbox: true,
        forceCheckboxLabel: "I agree to update changed loot table fields on duplicate keys",
      },
    );
    if (!ack || !ack.ok) {
      return { okn: 0, skip409n: 0, fail: ["Import cancelled before duplicate loot-table updates."], footer: "" };
    }
  }
  for (let i = 0; i < parsed.length; i += 1) {
    const r = parsed[i];
    const tableKey = String(r.key).trim();
    const tableBody = {
      key: tableKey,
      label: String(r.label).trim(),
      description: r.description != null ? String(r.description) : "",
      is_active: r.is_active !== false && r.is_active !== 0,
    };
    let canPostEntries = false;
    const duplicatePatch = existingRows.has(tableKey)
      ? buildPatchFromExplicitFields(r, existingRows.get(tableKey), [
          { rawKey: "label", patchKey: "label", getValue: (x) => String(x.label).trim() },
          { rawKey: "description", patchKey: "description", getValue: (x) => (x.description == null ? "" : String(x.description)) },
          { rawKey: "is_active", patchKey: "is_active", getValue: (x) => x.is_active !== false && x.is_active !== 0 },
        ])
      : {};
    try {
      if (existingRows.has(tableKey)) {
        if (Object.keys(duplicatePatch).length) {
          await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(tableKey)}`, {
            method: "PATCH",
            body: JSON.stringify({ ...duplicatePatch, force: false }),
          });
          okn += 1;
          existingRows.set(tableKey, { ...existingRows.get(tableKey), ...duplicatePatch });
        } else {
          skip409n += 1;
        }
        canPostEntries = true;
      } else {
        await adminFetch("/api/admin/loot-tables", { method: "POST", body: JSON.stringify(tableBody) });
        okn += 1;
        canPostEntries = true;
        existingRows.set(tableKey, { ...tableBody });
      }
    } catch (e) {
      fail.push(`${tableKey}: ${parseApiError(e, "create/update table failed")}`);
      continue;
    }
    const entries = Array.isArray(r.entries) ? r.entries : [];
    for (let j = 0; j < entries.length; j += 1) {
      const en = entries[j];
      try {
        await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(tableKey)}/entries`, {
          method: "POST",
          body: JSON.stringify(lootEntryImportToPayload(en)),
        });
        entriesOk += 1;
      } catch (err) {
        entriesFail += 1;
        fail.push(`${tableKey} entry ${j + 1}: ${parseApiError(err, "entry failed")}`);
      }
    }
  }
  const footer = `Wpisy loot (POST /entries): ${entriesOk} OK, ${entriesFail} błędów.`;
  return { okn, skip409n, fail, footer };
}

function validateSkillImportRow(raw, index, statKeys) {
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  const key = String(raw.key || "").trim();
  if (!IMPORT_KEY_RE.test(key)) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!String(raw.label || "").trim()) {
    return `${label}: label is required`;
  }
  const ls = String(raw.linked_stat || "").trim();
  if (!statKeys.includes(ls)) {
    return `${label}: linked_stat must be one of configured stats (${statKeys.join(", ")})`;
  }
  const rc = raw.rank_ceiling != null ? Number(raw.rank_ceiling) : 5;
  if (!Number.isFinite(rc) || rc < 1) {
    return `${label}: rank_ceiling must be >= 1`;
  }
  return null;
}

function skillImportRowToPayload(raw) {
  const payload = {
    key: String(raw.key).trim(),
    label: String(raw.label).trim(),
    linked_stat: String(raw.linked_stat).trim(),
    rank_ceiling: raw.rank_ceiling != null ? Number(raw.rank_ceiling) : 5,
    description: raw.description != null ? String(raw.description) : "",
  };
  if (Object.prototype.hasOwnProperty.call(raw, "sort_order") && raw.sort_order != null && raw.sort_order !== "") {
    const n = Number(raw.sort_order);
    if (Number.isFinite(n)) {
      payload.sort_order = n;
    }
  }
  return payload;
}

function validateWeaponImportRow(raw, index, statKeys) {
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  const key = String(raw.key || "").trim();
  if (!IMPORT_KEY_RE.test(key)) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!String(raw.label || "").trim()) {
    return `${label}: label is required`;
  }
  const dd = String(raw.damage_die || "").trim().toLowerCase();
  if (!IMPORT_DAMAGE_DIE_RE.test(dd)) {
    return `${label}: damage_die must match pattern like d6 or 2d8`;
  }
  const lst = String(raw.linked_stat || "").trim();
  if (!statKeys.includes(lst)) {
    return `${label}: linked_stat must be one of configured stats`;
  }
  const ac = raw.allowed_classes;
  if (!Array.isArray(ac) || ac.length === 0) {
    return `${label}: allowed_classes must be a non-empty array`;
  }
  for (const c of ac) {
    const cl = String(c || "").toLowerCase();
    if (!["warrior", "ranger", "scholar"].includes(cl)) {
      return `${label}: invalid allowed_class "${c}"`;
    }
  }
  const wt = String(raw.weapon_type || "melee").toLowerCase();
  if (!["melee", "ranged", "spell"].includes(wt)) {
    return `${label}: weapon_type must be melee, ranged, or spell`;
  }
  const wkg = raw.weight_kg != null ? Number(raw.weight_kg) : 0;
  if (!Number.isFinite(wkg) || wkg < 0) {
    return `${label}: weight_kg must be >= 0`;
  }
  if (raw.range_m != null && String(raw.range_m).trim() !== "") {
    const rm = Number(raw.range_m);
    if (!Number.isFinite(rm)) {
      return `${label}: range_m must be a number or null`;
    }
  }
  return null;
}

function weaponImportRowToPayload(raw) {
  let range_m = null;
  if (raw.range_m != null && String(raw.range_m).trim() !== "") {
    range_m = Number(raw.range_m);
  }
  const noteRaw = raw.note != null ? String(raw.note).trim() : "";
  return {
    key: String(raw.key).trim(),
    label: String(raw.label).trim(),
    damage_die: String(raw.damage_die).trim().toLowerCase(),
    linked_stat: String(raw.linked_stat).trim(),
    allowed_classes: Array.isArray(raw.allowed_classes)
      ? raw.allowed_classes.map((c) => String(c).toLowerCase())
      : [],
    description: raw.description != null ? String(raw.description) : "",
    weapon_type: String(raw.weapon_type || "melee").toLowerCase(),
    two_handed: !!(raw.two_handed === true || raw.two_handed === 1),
    finesse: !!(raw.finesse === true || raw.finesse === 1),
    range_m,
    weight_kg: raw.weight_kg != null ? Number(raw.weight_kg) : 0,
    note: noteRaw ? noteRaw : null,
    is_active: raw.is_active !== false && raw.is_active !== 0,
  };
}

/** Accept legacy field names: hp → hp_base, ac → ac_base, atk_bonus → attack_bonus. */
function normalizeEnemyImportRaw(raw) {
  if (!raw || typeof raw !== "object") {
    return raw;
  }
  const o = { ...raw };
  if (o.hp_base == null && o.hp != null) {
    o.hp_base = o.hp;
  }
  if (o.ac_base == null && o.ac != null) {
    o.ac_base = o.ac;
  }
  if (o.attack_bonus == null && o.atk_bonus != null) {
    o.attack_bonus = o.atk_bonus;
  }
  return o;
}

function validateEnemyImportRow(raw, index) {
  raw = normalizeEnemyImportRaw(raw);
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  const key = String(raw.key || "").trim();
  if (!IMPORT_KEY_RE.test(key)) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!String(raw.label || "").trim()) {
    return `${label}: label is required`;
  }
  const hp = Number(raw.hp_base);
  const ac = Number(raw.ac_base);
  if (!Number.isFinite(hp) || hp < 1) {
    return `${label}: hp_base must be >= 1`;
  }
  if (!Number.isFinite(ac) || ac < 1) {
    return `${label}: ac_base must be >= 1`;
  }
  const ab = Number(raw.attack_bonus);
  if (!Number.isFinite(ab) || ab < 0) {
    return `${label}: attack_bonus must be >= 0`;
  }
  const dd = String(raw.damage_die || "").trim().toLowerCase();
  if (!IMPORT_DAMAGE_DIE_RE.test(dd)) {
    return `${label}: damage_die must match pattern like d6 or 2d8`;
  }
  const tier = String(raw.tier || "standard").toLowerCase();
  if (!["weak", "standard", "elite", "boss"].includes(tier)) {
    return `${label}: tier must be weak|standard|elite|boss`;
  }
  const apt = raw.attacks_per_turn != null ? Number(raw.attacks_per_turn) : 1;
  if (!Number.isFinite(apt) || apt < 1) {
    return `${label}: attacks_per_turn must be >= 1`;
  }
  const dt = String(raw.damage_type || "physical").toLowerCase();
  if (!["physical", "magic", "fire", "poison", "misc"].includes(dt)) {
    return `${label}: damage_type invalid`;
  }
  const xp = raw.xp_award != null ? Number(raw.xp_award) : 0;
  if (!Number.isFinite(xp) || xp < 0) {
    return `${label}: xp_award must be >= 0`;
  }
  if (raw.conditions_immune != null && !Array.isArray(raw.conditions_immune)) {
    return `${label}: conditions_immune must be an array`;
  }
  if (raw.drop_chance != null) {
    const dc = Number(raw.drop_chance);
    if (!Number.isFinite(dc) || dc < 0 || dc > 1) {
      return `${label}: drop_chance must be between 0 and 1`;
    }
  }
  if (raw.loot_table_key != null && String(raw.loot_table_key).trim()) {
    const lk = String(raw.loot_table_key).trim();
    if (!IMPORT_KEY_RE.test(lk)) {
      return `${label}: loot_table_key must be a valid key or null`;
    }
  }
  return null;
}

function enemyImportRowToPayload(raw) {
  raw = normalizeEnemyImportRaw(raw);
  const lt = raw.loot_table_key != null && String(raw.loot_table_key).trim() ? String(raw.loot_table_key).trim() : null;
  const noteRaw = raw.note != null ? String(raw.note).trim() : "";
  return {
    key: String(raw.key).trim(),
    label: String(raw.label).trim(),
    hp_base: Number(raw.hp_base),
    ac_base: Number(raw.ac_base),
    attack_bonus: Number(raw.attack_bonus),
    damage_die: String(raw.damage_die).trim().toLowerCase(),
    description: raw.description != null && String(raw.description).trim() ? String(raw.description) : null,
    tier: String(raw.tier || "standard").toLowerCase(),
    attacks_per_turn: raw.attacks_per_turn != null ? Number(raw.attacks_per_turn) : 1,
    damage_bonus: raw.damage_bonus != null ? Number(raw.damage_bonus) : 0,
    damage_type: String(raw.damage_type || "physical").toLowerCase(),
    xp_award: raw.xp_award != null ? Number(raw.xp_award) : 0,
    conditions_immune: Array.isArray(raw.conditions_immune) ? raw.conditions_immune : [],
    loot_table_key: lt,
    drop_chance: raw.drop_chance != null ? Number(raw.drop_chance) : 1,
    note: noteRaw ? noteRaw : null,
    is_active: raw.is_active !== false && raw.is_active !== 0,
  };
}

function validateConditionImportRow(raw, index) {
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  if (!IMPORT_KEY_RE.test(String(raw.key || "").trim())) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!String(raw.label || "").trim()) {
    return `${label}: label is required`;
  }
  let ej = raw.effect_json;
  if (ej != null && typeof ej === "object") {
    try {
      ej = JSON.stringify(ej);
    } catch (_e) {
      return `${label}: effect_json object not serializable`;
    }
  }
  if (ej == null || !String(ej).trim()) {
    return `${label}: effect_json is required`;
  }
  try {
    JSON.parse(String(ej));
  } catch (_e) {
    return `${label}: effect_json must be valid JSON`;
  }
  return null;
}

function conditionImportRowToPayload(raw) {
  let ej = raw.effect_json;
  if (ej != null && typeof ej === "object") {
    ej = JSON.stringify(ej);
  }
  const ar = raw.auto_remove != null ? String(raw.auto_remove).trim() : "";
  return {
    key: String(raw.key).trim(),
    label: String(raw.label).trim(),
    effect_json: String(ej),
    description: raw.description != null && String(raw.description).trim() ? String(raw.description) : null,
    stackable: !!(raw.stackable === true || raw.stackable === 1),
    auto_remove: ar || null,
    is_active: raw.is_active !== false && raw.is_active !== 0,
  };
}

function validateConsumableImportRow(raw, index) {
  const label = `Row ${index + 1}`;
  if (!raw || typeof raw !== "object") {
    return `${label}: must be an object`;
  }
  if (!IMPORT_KEY_RE.test(String(raw.key || "").trim())) {
    return `${label}: key must be lowercase_snake_case, 1–40 chars`;
  }
  if (!String(raw.label || "").trim()) {
    return `${label}: label is required`;
  }
  const et = String(raw.effect_type || "misc").toLowerCase();
  if (!["heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff", "misc"].includes(et)) {
    return `${label}: effect_type invalid`;
  }
  const tgt = String(raw.effect_target || "self").toLowerCase();
  if (!["self", "ally", "any"].includes(tgt)) {
    return `${label}: effect_target must be self, ally, or any`;
  }
  if (raw.effect_dice != null && String(raw.effect_dice).trim()) {
    const d = String(raw.effect_dice).trim().toLowerCase();
    if (!IMPORT_DAMAGE_DIE_RE.test(d)) {
      return `${label}: effect_dice must match dice pattern (e.g. 2d4) or be null/empty`;
    }
  }
  const ch = raw.charges != null ? Number(raw.charges) : 1;
  if (!Number.isFinite(ch) || ch < 1) {
    return `${label}: charges must be >= 1`;
  }
  const bp = raw.base_price != null ? Number(raw.base_price) : 0;
  if (!Number.isFinite(bp) || bp < 0) {
    return `${label}: base_price must be >= 0`;
  }
  const wkg = raw.weight_kg != null ? Number(raw.weight_kg) : 0;
  if (!Number.isFinite(wkg) || wkg < 0) {
    return `${label}: weight_kg must be >= 0`;
  }
  return null;
}

function consumableImportRowToPayload(raw) {
  let effect_dice = null;
  if (raw.effect_dice != null && String(raw.effect_dice).trim()) {
    effect_dice = String(raw.effect_dice).trim();
  }
  const noteRaw = raw.note != null ? String(raw.note).trim() : "";
  return {
    key: String(raw.key).trim(),
    label: String(raw.label).trim(),
    description: raw.description != null ? String(raw.description) : "",
    effect_type: String(raw.effect_type || "misc").toLowerCase(),
    effect_dice,
    effect_bonus: raw.effect_bonus != null ? Number(raw.effect_bonus) : 0,
    effect_target: String(raw.effect_target || "self").toLowerCase(),
    weight_kg: raw.weight_kg != null ? Number(raw.weight_kg) : 0,
    charges: raw.charges != null ? Number(raw.charges) : 1,
    base_price: raw.base_price != null ? Number(raw.base_price) : 0,
    note: noteRaw ? noteRaw : null,
    is_active: raw.is_active !== false && raw.is_active !== 0,
  };
}

async function refreshItems(host) {
  const tableHost = host.querySelector(".items-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/items");
    const rows = (data.items || []).map((r) => ({
      ...r,
      _proficiency_json: JSON.stringify(Array.isArray(r.proficiency_classes) ? r.proficiency_classes : []),
    }));
    renderGameDesignTable(
      tableHost,
      "items",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        {
          key: "item_type",
          label: "Type",
          type: "badge",
          badgeClass: itemTypeBadgeClass,
          editable: true,
          editType: "select",
          editOptions: ["weapon", "armor", "consumable", "misc", "quest"],
          filterable: true,
          filterOptions: ["weapon", "armor", "consumable", "misc", "quest"],
        },
        { key: "weight_kg", label: "Weight kg", type: "number", editable: true },
        { key: "value_gp", label: "GP", type: "number", editable: true },
        { key: "description", label: "Description", type: "textarea", editable: true },
        { key: "effect_json", label: "Effect JSON", type: "textarea", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        searchPlaceholder: "Search items (key, label, type)…",
        exportRow: (row) => {
          const copy = { ...row };
          delete copy._proficiency_json;
          return copy;
        },
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "item_type") {
            const v = String(newValue || "").trim().toLowerCase();
            if (!["weapon", "armor", "consumable", "misc", "quest"].includes(v)) {
              showToast("item_type must be weapon, armor, consumable, misc, or quest.", "error");
              throw new Error("invalid_item_type");
            }
            body.item_type = v;
          }
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "value_gp") {
            body.value_gp = Number(newValue);
          }
          if (key === "weight_kg") {
            body.weight_kg = Number(newValue);
          }
          if (key === "effect_json") {
            body.effect_json = newValue;
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/items/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {}, {
            _proficiency_json: JSON.stringify((res.item && res.item.proficiency_classes) || []),
          });
          showToast("Item updated.", "success");
        },
        onDelete: async (row, meta = {}) => {
          try {
            await adminFetch(`/api/admin/items/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!meta.force }),
            });
            showToast("Item deleted.", "success");
            await refreshItems(host);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load items."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountItems(host) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add item ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field"><span>Item type</span>
        <select data-field="item_type">
          <option value="weapon">weapon</option>
          <option value="armor">armor</option>
          <option value="consumable">consumable</option>
          <option value="misc" selected>misc</option>
          <option value="quest">quest</option>
        </select>
      </label>
      <label class="field add-form-span-2"><span>Description</span>
        <textarea data-field="description" rows="3" placeholder="Short player-facing description"></textarea>
      </label>
      <label class="field"><span>Value (GP)</span><input data-field="value_gp" type="number" value="0" /></label>
      <label class="field"><span>Weight (kg)</span><input data-field="weight_kg" type="number" step="any" value="0" /></label>
      <input type="hidden" data-field="weight" value="0" />
      <label class="field add-form-span-2"><span>Proficiency classes</span>
        <span class="checkbox-inline"><label><input type="checkbox" data-pclass="warrior" /> warrior</label>
        <label><input type="checkbox" data-pclass="scholar" /> scholar</label>
        <label><input type="checkbox" data-pclass="ranger" /> ranger</label></span>
      </label>
      <label class="field add-form-span-2"><span>Note</span><input data-field="note" type="text" /></label>
      <label class="field add-form-span-2"><span>Effect JSON (optional)</span>
        <textarea data-field="effect_json" rows="2" placeholder='{"stat_mods":{"AC":2}}'></textarea>
      </label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-item">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add item ▾" : "Add item ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);

  wireBulkJsonImport(root, {
    hint: "Wklej tablicę przedmiotów (katalog). Dry run = walidacja; Commit = POST /api/admin/items.",
    templatesHref: "/admin_panel/templates.html#sec-items",
    templatesAnchor: "Szablony JSON — Items",
    placeholder: '[{ "key": "health_potion", "item_type": "consumable", ... }]',
    validateRow: (row, i) => validateItemImportRow(row, i),
    buildPayload: (row) => itemImportRowToPayload(row),
    postPath: "/api/admin/items",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/items"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/admin/items"),
    patchPath: (key) => `/api/admin/items/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "item_type", patchKey: "item_type", getValue: (r) => String(r.item_type || "misc").toLowerCase() },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? "" : String(r.description)) },
        { rawKey: "value_gp", patchKey: "value_gp", getValue: (r) => Number(r.value_gp) },
        { rawKey: "weight", patchKey: "weight", getValue: (r) => Number(r.weight) },
        { rawKey: "weight_kg", patchKey: "weight_kg", getValue: (r) => Number(r.weight_kg) },
        { rawKey: "proficiency_classes", patchKey: "proficiency_classes", getValue: (r) => (Array.isArray(r.proficiency_classes) ? r.proficiency_classes : []) },
        { rawKey: "note", patchKey: "note", getValue: (r) => (r.note == null || String(r.note).trim() === "" ? null : String(r.note)) },
        { rawKey: "effect_json", patchKey: "effect_json", getValue: (r) => (r.effect_json == null || String(r.effect_json).trim() === "" ? null : String(r.effect_json)) },
        { rawKey: "is_active", patchKey: "is_active", getValue: (r) => r.is_active !== false && r.is_active !== 0 },
      ]),
    refresh: () => refreshItems(host),
    confirmNoun: "przedmiotów",
  });

  const mount = el("div", "admin-table-mount items-table-mount");
  root.appendChild(mount);

  fields.querySelector('[data-action="create-item"]').addEventListener("click", async () => {
    const eff = fields.querySelector('[data-field="effect_json"]').value.trim();
    const pclasses = [];
    fields.querySelectorAll("[data-pclass]").forEach((c) => {
      if (c.checked) {
        pclasses.push(c.getAttribute("data-pclass"));
      }
    });
    const noteRaw = fields.querySelector('[data-field="note"]').value.trim();
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      item_type: fields.querySelector('[data-field="item_type"]').value.trim(),
      description: fields.querySelector('[data-field="description"]').value.trim(),
      value_gp: Number(fields.querySelector('[data-field="value_gp"]').value || 0),
      weight: Number(fields.querySelector('[data-field="weight"]').value || 0),
      weight_kg: Number(fields.querySelector('[data-field="weight_kg"]').value || 0),
      proficiency_classes: pclasses,
      note: noteRaw || null,
      effect_json: eff || null,
      is_active: fields.querySelector('[data-field="is_active"]').checked,
    };
    if (!payload.key || !payload.label) {
      showToast("Key and label are required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/items", { method: "POST", body: JSON.stringify(payload) });
      showToast("Item created.", "success");
      await refreshItems(host);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });

  host.appendChild(root);
  void refreshItems(host);
}

async function refreshConsumables(host) {
  const tableHost = host.querySelector(".admin-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/consumables");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "consumables",
      [
        { key: "key", label: "Key", editable: true },
        { key: "label", label: "Label", editable: true },
        { key: "description", label: "Description", editable: true },
        {
          key: "effect_type",
          label: "Effect",
          type: "badge",
          badgeClass: effectTypeBadgeClass,
          editable: true,
          editType: "select",
          editOptions: [
            "heal_hp",
            "restore_mana",
            "remove_condition",
            "add_condition",
            "stat_buff",
            "misc",
          ],
        },
        { key: "effect_dice", label: "Dice", editable: true },
        { key: "effect_bonus", label: "Bonus", type: "number", editable: true },
        { key: "effect_target", label: "Target", editable: true },
        { key: "weight_kg", label: "Weight kg", type: "number", editable: true },
        { key: "charges", label: "Charges", type: "number", editable: true },
        { key: "base_price", label: "Price", type: "number", editable: true },
        { key: "note", label: "Note", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "key") {
            const nk = String(newValue || "").trim();
            if (!nk) {
              showToast("Key is required.", "info");
              throw new Error("invalid_key");
            }
            if (nk === row.key) {
              return;
            }
            body.new_key = nk;
          }
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "effect_type") {
            const et = String(newValue).trim().toLowerCase();
            if (
              !["heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff", "misc"].includes(et)
            ) {
              showToast(
                "effect_type must be: heal_hp, restore_mana, remove_condition, add_condition, stat_buff, or misc",
                "error",
              );
              throw new Error("invalid_effect_type");
            }
            body.effect_type = et;
          }
          if (key === "effect_dice") {
            body.effect_dice = String(newValue || "").trim() || null;
          }
          if (key === "effect_bonus") {
            body.effect_bonus = Number(newValue);
          }
          if (key === "effect_target") {
            body.effect_target = String(newValue || "").trim();
          }
          if (key === "weight_kg") {
            body.weight_kg = Number(newValue);
          }
          if (key === "charges") {
            body.charges = Number(newValue);
          }
          if (key === "base_price") {
            body.base_price = Number(newValue);
          }
          if (key === "note") {
            body.note = String(newValue || "").trim() ? String(newValue) : null;
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/consumables/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {});
          showToast("Consumable updated.", "success");
        },
        onDelete: async (row, meta = {}) => {
          try {
            await adminFetch(`/api/admin/consumables/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: !!meta.force }),
            });
            showToast("Consumable deleted.", "success");
            await refreshConsumables(host);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Failed to load consumables."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountConsumables(host) {
  const root = el("div", "admin-subpanel-inner");
  const toggleRow = el("div", "admin-add-form-toggle");
  const toggle = el("button", "secondary-btn", "Add consumable ▾");
  toggle.type = "button";
  const details = el("div", "add-form admin-add-form-collapsed");
  const fields = el("div", "admin-add-form-fields");
  fields.innerHTML = `
    <div class="add-form-grid">
      <label class="field"><span>Key</span><input data-field="key" type="text" /></label>
      <label class="field"><span>Label</span><input data-field="label" type="text" /></label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field"><span>Effect type</span>
        <select data-field="effect_type">
          <option value="heal_hp">heal_hp</option>
          <option value="restore_mana">restore_mana</option>
          <option value="remove_condition">remove_condition</option>
          <option value="add_condition">add_condition</option>
          <option value="stat_buff">stat_buff</option>
          <option value="misc" selected>misc</option>
        </select>
      </label>
      <label class="field"><span>Effect dice</span><input data-field="effect_dice" type="text" placeholder="2d4 or empty" /></label>
      <label class="field"><span>Effect bonus</span><input data-field="effect_bonus" type="number" value="0" /></label>
      <label class="field"><span>Effect target</span>
        <select data-field="effect_target">
          <option value="self" selected>self</option>
          <option value="ally">ally</option>
          <option value="any">any</option>
        </select>
      </label>
      <label class="field"><span>Weight (kg)</span><input data-field="weight_kg" type="number" step="any" value="0" /></label>
      <label class="field"><span>Charges</span><input data-field="charges" type="number" value="1" min="1" /></label>
      <label class="field"><span>Base price</span><input data-field="base_price" type="number" value="0" min="0" /></label>
      <label class="field add-form-span-2"><span>Note</span><input data-field="note" type="text" /></label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-consumable">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed")
      ? "Add consumable ▾"
      : "Add consumable ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);
  wireBulkJsonImport(root, {
    hint: "Wklej tablicę consumables (game_config_consumables). effect_dice w formacie kości (np. 2d4) lub null.",
    templatesHref: "/admin_panel/templates.html#sec-consumables",
    templatesAnchor: "Szablony JSON — Consumables",
    placeholder: '[{ "key": "potion_healing_minor", "effect_type": "heal_hp", ... }]',
    validateRow: (row, i) => validateConsumableImportRow(row, i),
    buildPayload: (row) => consumableImportRowToPayload(row),
    postPath: "/api/admin/consumables",
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/consumables"),
    existingRows: () => fetchExistingRowsByKeyFromAdminList("/api/admin/consumables"),
    patchPath: (key) => `/api/admin/consumables/${encodeURIComponent(key)}`,
    buildDuplicatePatch: (raw, existing) =>
      buildPatchFromExplicitFields(raw, existing, [
        { rawKey: "label", patchKey: "label", getValue: (r) => String(r.label).trim() },
        { rawKey: "description", patchKey: "description", getValue: (r) => (r.description == null ? "" : String(r.description)) },
        { rawKey: "effect_type", patchKey: "effect_type", getValue: (r) => String(r.effect_type || "misc").toLowerCase() },
        { rawKey: "effect_dice", patchKey: "effect_dice", getValue: (r) => (r.effect_dice == null || String(r.effect_dice).trim() === "" ? null : String(r.effect_dice).trim()) },
        { rawKey: "effect_bonus", patchKey: "effect_bonus", getValue: (r) => Number(r.effect_bonus) },
        { rawKey: "effect_target", patchKey: "effect_target", getValue: (r) => String(r.effect_target || "self").toLowerCase() },
        { rawKey: "weight_kg", patchKey: "weight_kg", getValue: (r) => Number(r.weight_kg) },
        { rawKey: "charges", patchKey: "charges", getValue: (r) => Number(r.charges) },
        { rawKey: "base_price", patchKey: "base_price", getValue: (r) => Number(r.base_price) },
        { rawKey: "note", patchKey: "note", getValue: (r) => (r.note == null || String(r.note).trim() === "" ? null : String(r.note)) },
        { rawKey: "is_active", patchKey: "is_active", getValue: (r) => r.is_active !== false && r.is_active !== 0 },
      ]),
    refresh: () => refreshConsumables(host),
    confirmNoun: "wierszy",
  });
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  fields.querySelector('[data-action="create-consumable"]').addEventListener("click", async () => {
    const diceRaw = fields.querySelector('[data-field="effect_dice"]').value.trim();
    const noteRaw = fields.querySelector('[data-field="note"]').value.trim();
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      description: fields.querySelector('[data-field="description"]').value.trim(),
      effect_type: fields.querySelector('[data-field="effect_type"]').value.trim(),
      effect_dice: diceRaw || null,
      effect_bonus: Number(fields.querySelector('[data-field="effect_bonus"]').value || 0),
      effect_target: fields.querySelector('[data-field="effect_target"]').value.trim(),
      weight_kg: Number(fields.querySelector('[data-field="weight_kg"]').value || 0),
      charges: Number(fields.querySelector('[data-field="charges"]').value || 1),
      base_price: Number(fields.querySelector('[data-field="base_price"]').value || 0),
      note: noteRaw || null,
      is_active: fields.querySelector('[data-field="is_active"]').checked,
    };
    if (!payload.key || !payload.label) {
      showToast("Key and label are required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/consumables", { method: "POST", body: JSON.stringify(payload) });
      showToast("Consumable created.", "success");
      await refreshConsumables(host);
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });
  host.appendChild(root);
  void refreshConsumables(host);
}

function mountLootTables(host) {
  const root = el("div", "admin-subpanel-inner loot-editor-layout");
  const left = el("div", "loot-sidebar-panel");
  const right = el("div", "loot-editor-panel");
  left.innerHTML = `<h3 class="loot-sidebar-title">Loot tables</h3>
    <div class="admin-add-form-toggle"><button type="button" class="secondary-btn" data-loot-add-toggle>Add table ▾</button></div>
    <div class="add-form admin-add-form-collapsed" data-loot-add-form>
      <div class="admin-add-form-fields">
        <div class="add-form-grid">
          <label class="field"><span>Key</span><input data-loot-key type="text" /></label>
          <label class="field"><span>Label</span><input data-loot-label type="text" /></label>
          <label class="field add-form-span-2"><span>Description</span><input data-loot-desc type="text" /></label>
          <label class="field"><span>Active</span><input data-loot-active type="checkbox" checked /></label>
        </div>
        <button type="button" class="primary-btn" data-loot-create>Create</button>
      </div>
    </div>
    <div class="loot-table-list-mount"></div>`;
  right.innerHTML = `<div class="loot-editor-empty muted" data-loot-placeholder>Select a loot table on the left, or create one.</div>
    <div class="loot-editor-active" data-loot-active-panel hidden>
      <h3 class="loot-editor-heading"><span data-loot-h-label></span> <span class="muted" data-loot-h-key></span></h3>
      <div class="loot-table-key-rename add-form-grid" data-loot-key-rename-wrap>
        <label class="field add-form-span-2"><span>Rename table key</span>
          <input type="text" data-loot-rename-key-input placeholder="new_snake_case_key" autocomplete="off" />
        </label>
        <button type="button" class="secondary-btn" data-loot-rename-key-save>Save new key</button>
      </div>
      <label class="field loot-desc-field"><span>Description</span><textarea data-loot-desc-edit rows="2"></textarea></label>
      <div class="add-form-grid">
        <label class="field"><span>Gold min (GP)</span><input data-loot-gold-min type="number" min="0" step="1" value="0" /></label>
        <label class="field"><span>Gold max (GP)</span><input data-loot-gold-max type="number" min="0" step="1" value="0" /></label>
      </div>
      <h4 class="loot-entries-title">Entries</h4>
      <div class="loot-entries-table-wrap" data-loot-entries-wrap></div>
      <div class="loot-add-entry add-form-grid">
        <label class="field"><span>Source type</span>
          <select data-loot-source-type>
            <option value="item" selected>Item</option>
            <option value="weapon">Weapon</option>
            <option value="consumable">Consumable</option>
          </select>
        </label>
        <label class="field add-form-span-2"><span>Source</span><select data-loot-source-select></select></label>
        <label class="field"><span>Drop chance (%)</span><input data-loot-weight type="number" value="10" min="1" max="100" /></label>
        <label class="field"><span>Qty min</span><input data-loot-qty-min type="number" value="1" min="1" /></label>
        <label class="field"><span>Qty max</span><input data-loot-qty-max type="number" value="1" min="1" /></label>
        <button type="button" class="primary-btn" data-loot-add-entry>+ Add</button>
      </div>
      <div class="loot-weight-viz" data-loot-viz></div>
    </div>`;
  root.appendChild(left);
  root.appendChild(right);
  host.appendChild(root);

  const lootCatalogues = { items: [], weapons: [], consumables: [] };

  let selectedKey = null;
  let selectedLabel = "";
  const listMount = left.querySelector(".loot-table-list-mount");
  const addForm = left.querySelector("[data-loot-add-form]");
  const addToggle = left.querySelector("[data-loot-add-toggle]");
  addToggle.addEventListener("click", () => {
    addForm.classList.toggle("admin-add-form-collapsed");
    addToggle.textContent = addForm.classList.contains("admin-add-form-collapsed") ? "Add table ▾" : "Add table ▴";
  });

  const renameKeyBtn = right.querySelector("[data-loot-rename-key-save]");
  if (renameKeyBtn && !renameKeyBtn.dataset.wired) {
    renameKeyBtn.dataset.wired = "1";
    renameKeyBtn.addEventListener("click", async () => {
      if (!selectedKey) {
        return;
      }
      const inp = right.querySelector("[data-loot-rename-key-input]");
      const nk = String(inp?.value || "").trim();
      if (!nk) {
        showToast("Enter a new table key.", "info");
        return;
      }
      if (nk === selectedKey) {
        showToast("Key unchanged.", "info");
        return;
      }
      try {
        await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}`, {
          method: "PATCH",
          body: JSON.stringify({ new_key: nk, force: false }),
        });
        showToast("Loot table key updated.", "success");
        selectedKey = nk;
        if (inp) {
          inp.value = nk;
        }
        right.querySelector("[data-loot-h-key]").textContent = nk;
        await refreshEntriesPanel();
        await refreshLootList();
      } catch (e) {
        showToast(parseApiError(e, "Rename failed."), "error");
      }
    });
  }

  function renderWeightViz(entries) {
    const viz = right.querySelector("[data-loot-viz]");
    viz.innerHTML = "";
    if (!entries || !entries.length) {
      viz.appendChild(el("p", "muted", "No entries yet."));
      return;
    }
    entries.forEach((e) => {
      const pct = Math.max(1, Math.min(100, Number(e.weight) || 0));
      const row = el("div", "loot-weight-row");
      const lab = el(
        "span",
        "loot-weight-label",
        `${e.source_label || e.item_label || e.weapon_label || e.item_key || e.consumable_key || e.weapon_key || ""}`,
      );
      const barWrap = el("div", "loot-weight-bar");
      const bar = el("span", "");
      bar.style.width = `${pct}%`;
      barWrap.appendChild(bar);
      const pctEl = el("span", "loot-weight-pct", `${pct}%`);
      row.appendChild(lab);
      row.appendChild(barWrap);
      row.appendChild(pctEl);
      viz.appendChild(row);
    });
  }

  function populateLootSourceSelect() {
    const typeSel = right.querySelector("[data-loot-source-type]");
    const keySel = right.querySelector("[data-loot-source-select]");
    if (!typeSel || !keySel) {
      return;
    }
    const type = typeSel.value;
    keySel.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "— pick —";
    keySel.appendChild(placeholder);
    let catalogue = [];
    if (type === "item") {
      catalogue = lootCatalogues.items;
    } else if (type === "weapon") {
      catalogue = lootCatalogues.weapons;
    } else if (type === "consumable") {
      catalogue = lootCatalogues.consumables;
    }
    catalogue
      .filter((r) => r.is_active !== 0 && r.is_active !== false)
      .slice()
      .sort((a, b) => String(a.label || a.key).localeCompare(String(b.label || b.key), undefined, { sensitivity: "base" }))
      .forEach((r) => {
        const o = document.createElement("option");
        o.value = r.key;
        o.textContent = `${r.label || r.key}  [${r.key}]`;
        keySel.appendChild(o);
      });
  }

  async function refreshEntriesPanel() {
    const wrap = right.querySelector("[data-loot-entries-wrap]");
    const ph = right.querySelector("[data-loot-placeholder]");
    const panel = right.querySelector("[data-loot-active-panel]");
    if (!selectedKey) {
      ph.hidden = false;
      panel.hidden = true;
      return;
    }
    ph.hidden = true;
    panel.hidden = false;
    right.querySelector("[data-loot-h-label]").textContent = selectedLabel || selectedKey;
    right.querySelector("[data-loot-h-key]").textContent = selectedKey;
    const rkInp = right.querySelector("[data-loot-rename-key-input]");
    if (rkInp) {
      rkInp.value = selectedKey || "";
    }
    wrap.innerHTML = "";
    const entriesSearch = el("input");
    entriesSearch.type = "search";
    entriesSearch.className = "admin-table-search-input";
    entriesSearch.placeholder = "Search loot entries…";
    entriesSearch.setAttribute("aria-label", "Search loot entries");
    wrap.appendChild(entriesSearch);
    try {
      const [itemsData, weaponsData, consumablesData] = await Promise.all([
        adminFetch("/api/admin/items"),
        adminFetch("/api/admin/weapons"),
        adminFetch("/api/admin/consumables"),
      ]);
      lootCatalogues.items = itemsData.items || [];
      lootCatalogues.weapons = weaponsData.items || [];
      lootCatalogues.consumables = consumablesData.items || [];
    } catch (e) {
      showToast(parseApiError(e, "Failed to load catalogues for loot."), "error");
    }
    const typeSel = right.querySelector("[data-loot-source-type]");
    if (typeSel && !typeSel.dataset.lootSourceWired) {
      typeSel.dataset.lootSourceWired = "1";
      typeSel.addEventListener("change", () => {
        populateLootSourceSelect();
      });
    }
    // Must run after catalogues are loaded so the key dropdown is filled on first open (no manual type change).
    populateLootSourceSelect();
    let entries = [];
    try {
      const d = await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries`);
      entries = d.items || [];
    } catch (e) {
      showToast(parseApiError(e, "Failed to load entries."), "error");
    }
    const tbl = el("table", "admin-table");
    const thead = el("thead");
    const hr = el("tr");
    ["Source (type · label · key)", "Drop chance %", "Qty min", "Qty max", ""].forEach((h) => {
      const th = el("th", "", h);
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    tbl.appendChild(thead);
    const tb = el("tbody");
    const recalcViz = () => {
      const live = [];
      tb.querySelectorAll("tr").forEach((tr) => {
        const sk = tr.dataset.sourceKey;
        if (!sk) {
          return;
        }
        const ins = tr.querySelectorAll("input[type='number']");
        if (ins.length < 3) {
          return;
        }
        live.push({
          source_label: tr.cells[0]?.innerText?.replace(/\s+/g, " ").trim() || sk,
          weight: Number(ins[0].value) || 0,
          qty_min: Number(ins[1].value) || 0,
          qty_max: Number(ins[2].value) || 0,
        });
      });
      renderWeightViz(live);
    };
    entries.forEach((en) => {
      const st =
        en.source_type ||
        (en.item_key ? "item" : en.consumable_key ? "consumable" : en.weapon_key ? "weapon" : "item");
      const tr = el("tr");
      tr.dataset.sourceType = st;
      tr.dataset.sourceKey = en.item_key || en.consumable_key || en.weapon_key || "";
      const td1 = el("td", "");
      const stLabel = st === "item" ? "Item" : st === "weapon" ? "Weapon" : st === "consumable" ? "Consumable" : st;
      const badge = el("span", `admin-badge loot-src-${st}`, stLabel);
      const srcName = en.source_label || en.item_label || en.consumable_label || en.weapon_label || "";
      const srcKey = en.item_key || en.consumable_key || en.weapon_key || "";
      td1.appendChild(badge);
      td1.appendChild(document.createTextNode(" "));
      td1.appendChild(el("span", "loot-entry-label", srcName || srcKey));
      if (srcKey) {
        td1.appendChild(el("span", "muted loot-entry-key", ` [${srcKey}]`));
      }
      const td2 = el("td");
      const inW = el("input", "");
      inW.type = "number";
      inW.min = "1";
      inW.max = "100";
      inW.value = String(en.weight);
      inW.dataset.field = "weight";
      const td3 = el("td");
      const inMin = el("input", "");
      inMin.type = "number";
      inMin.min = "1";
      inMin.value = String(en.qty_min);
      inMin.dataset.field = "qty_min";
      const td4 = el("td");
      const inMax = el("input", "");
      inMax.type = "number";
      inMax.min = "1";
      inMax.value = String(en.qty_max);
      inMax.dataset.field = "qty_max";
      const td5 = el("td");
      const rm = el("button", "secondary-btn", "Remove");
      rm.type = "button";
      rm.addEventListener("click", async () => {
        try {
          const delPath =
            st === "item"
              ? `/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries/${encodeURIComponent(en.item_key)}`
              : st === "consumable"
                ? `/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries/consumable/${encodeURIComponent(en.consumable_key)}`
                : `/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries/weapon/${encodeURIComponent(en.weapon_key)}`;
          await adminFetch(delPath, { method: "DELETE" });
          showToast("Entry removed.", "success");
          await refreshEntriesPanel();
          await refreshLootList();
        } catch (e) {
          showToast(parseApiError(e, "Remove failed."), "error");
        }
      });
      const saveRow = async () => {
        const weight = Number(inW.value || 0);
        const qty_min = Number(inMin.value || 0);
        const qty_max = Number(inMax.value || 0);
        const payload = { weight, qty_min, qty_max };
        if (st === "item") {
          payload.item_key = en.item_key;
        } else if (st === "consumable") {
          payload.consumable_key = en.consumable_key;
        } else {
          payload.weapon_key = en.weapon_key;
        }
        try {
          await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
        } catch (e) {
          showToast(parseApiError(e, "Save failed."), "error");
        }
      };
      [inW, inMin, inMax].forEach((inp) => {
        inp.addEventListener("blur", () => {
          void saveRow();
        });
        inp.addEventListener("input", recalcViz);
      });
      td2.appendChild(inW);
      td3.appendChild(inMin);
      td4.appendChild(inMax);
      td5.appendChild(rm);
      tr.appendChild(td1);
      tr.appendChild(td2);
      tr.appendChild(td3);
      tr.appendChild(td4);
      tr.appendChild(td5);
      tb.appendChild(tr);
    });
    tbl.appendChild(tb);
    wrap.appendChild(tbl);
    entriesSearch.addEventListener("input", () => {
      const q = (entriesSearch.value || "").trim().toLowerCase();
      tb.querySelectorAll("tr").forEach((tr) => {
        if (!tr.dataset.sourceKey) {
          return;
        }
        const t = (tr.textContent || "").toLowerCase().replace(/\s+/g, " ");
        tr.style.display = !q || t.includes(q) ? "" : "none";
      });
      recalcViz();
    });
    renderWeightViz(entries);
    const descTa = right.querySelector("[data-loot-desc-edit]");
    const goldMinInp = right.querySelector("[data-loot-gold-min]");
    const goldMaxInp = right.querySelector("[data-loot-gold-max]");
    const saveGoldRange = async () => {
      if (!selectedKey || !goldMinInp || !goldMaxInp) return;
      const gmin = Number.parseInt(String(goldMinInp.value || "0"), 10);
      const gmax = Number.parseInt(String(goldMaxInp.value || "0"), 10);
      if (!Number.isFinite(gmin) || !Number.isFinite(gmax) || gmin < 0 || gmax < 0 || gmin > gmax) {
        showToast("Gold min/max: wymagane liczby >= 0 i min <= max.", "error");
        return;
      }
      try {
        await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}`, {
          method: "PATCH",
          body: JSON.stringify({ gold_min: gmin, gold_max: gmax, force: false }),
        });
        showToast("Loot table gold range saved.", "success");
        await refreshLootList();
      } catch (e) {
        showToast(parseApiError(e, "Save gold range failed."), "error");
      }
    };
    try {
      const tables = await adminFetch("/api/admin/loot-tables");
      const meta = (tables.items || []).find((t) => t.key === selectedKey);
      descTa.value = meta ? meta.description || "" : "";
      if (goldMinInp) goldMinInp.value = String(Math.max(0, Number(meta?.gold_min || 0)));
      if (goldMaxInp) goldMaxInp.value = String(Math.max(0, Number(meta?.gold_max || 0)));
    } catch (_e) {
      descTa.value = "";
      if (goldMinInp) goldMinInp.value = "0";
      if (goldMaxInp) goldMaxInp.value = "0";
    }
    descTa.onblur = async () => {
      try {
        await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}`, {
          method: "PATCH",
          body: JSON.stringify({ description: descTa.value, force: false }),
        });
        showToast("Loot table description saved.", "success");
        await refreshLootList();
      } catch (e) {
        showToast(parseApiError(e, "Save failed."), "error");
      }
    };
    if (goldMinInp) goldMinInp.onblur = () => {
      void saveGoldRange();
    };
    if (goldMaxInp) goldMaxInp.onblur = () => {
      void saveGoldRange();
    };
  }

  right.querySelector("[data-loot-add-entry]").addEventListener("click", async () => {
    if (!selectedKey) {
      return;
    }
    const sourceType = right.querySelector("[data-loot-source-type]").value;
    const sourceKey = right.querySelector("[data-loot-source-select]").value;
    const weight = Number.parseInt(String(right.querySelector("[data-loot-weight]").value || "10"), 10) || 10;
    const qty_min = Number.parseInt(String(right.querySelector("[data-loot-qty-min]").value || "1"), 10) || 1;
    const qty_max = Number.parseInt(String(right.querySelector("[data-loot-qty-max]").value || "1"), 10) || 1;
    if (!sourceKey) {
      showToast("Select an item, weapon, or consumable first.", "info");
      return;
    }
    const payload = { weight, qty_min, qty_max };
    if (sourceType === "consumable") {
      payload.consumable_key = sourceKey;
    } else if (sourceType === "weapon") {
      payload.weapon_key = sourceKey;
    } else {
      payload.item_key = sourceKey;
    }
    try {
      await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Entry added.", "success");
      await refreshEntriesPanel();
      await refreshLootList();
    } catch (e) {
      showToast(parseApiError(e, "Add failed."), "error");
    }
  });

  async function refreshLootList() {
    renderTable(listMount, [], null, {});
    try {
      const data = await adminFetch("/api/admin/loot-tables");
      const rows = (data.items || []).map((r) => ({ ...r }));
      renderGameDesignTable(
        listMount,
        "loot_tables",
        [
          { key: "key", label: "Key" },
          { key: "label", label: "Label", editable: true },
          { key: "is_active", label: "Active", type: "boolean", editable: true },
          { key: "locked_at", label: "Lock", type: "locked" },
        ],
        rows,
        {
          onEdit: async (row, key, newValue, meta) => {
            const body = { force: !!(meta && meta.force) };
            if (key === "label") {
              body.label = newValue;
            }
            if (key === "is_active") {
              body.is_active = !!newValue;
            }
            const pathKey = row.key;
            const res = await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(pathKey)}`, {
              method: "PATCH",
              body: JSON.stringify(body),
            });
            const wasSelected = selectedKey === pathKey;
            Object.assign(row, res.item || {});
            if (wasSelected && res.item && res.item.key) {
              selectedKey = res.item.key;
              selectedLabel = res.item.label || selectedLabel;
              await refreshEntriesPanel();
            } else if (selectedKey === pathKey) {
              selectedLabel = row.label || selectedLabel;
            }
            showToast("Loot table updated.", "success");
            await refreshLootList();
          },
          onDelete: async (row, meta = {}) => {
            try {
              await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(row.key)}`, {
                method: "DELETE",
                body: JSON.stringify({ force: !!meta.force }),
              });
              showToast("Loot table deleted.", "success");
              if (selectedKey === row.key) {
                selectedKey = null;
                selectedLabel = "";
                await refreshEntriesPanel();
              }
              await refreshLootList();
            } catch (e) {
              showToast(parseApiError(e, "Delete failed."), "error");
              throw e;
            }
          },
          extraActions: (row) => [
            {
              label: selectedKey === row.key ? "● Open" : "Open →",
              class: selectedKey === row.key ? "primary-btn" : "secondary-btn",
              onClick: async () => {
                selectedKey = row.key;
                selectedLabel = row.label;
                await refreshEntriesPanel();
                await refreshLootList();
              },
            },
          ],
        },
      );
      const tableEl = listMount.querySelector("table.admin-table");
      if (tableEl) {
        tableEl.querySelectorAll("tbody tr").forEach((tr) => {
          const keyTd = tr.querySelector('td[data-col="key"]');
          const keyText = keyTd?.textContent?.trim() ?? "";
          const row = rows.find((r) => r.key === keyText);
          if (!row || !row.key) {
            return;
          }
          if (selectedKey === row.key) {
            tr.classList.add("loot-row-selected");
          }
          keyTd.classList.add("loot-row-select-cell");
          keyTd.title = "Open this loot table";
          keyTd.addEventListener("click", async () => {
            selectedKey = row.key;
            selectedLabel = row.label;
            await refreshEntriesPanel();
            await refreshLootList();
          });
        });
      }
    } catch (e) {
      showToast(parseApiError(e, "Failed to load loot tables."), "error");
      renderTable(listMount, [], [], {});
    }
  }

  left.querySelector("[data-loot-create]").addEventListener("click", async () => {
    const payload = {
      key: left.querySelector("[data-loot-key]").value.trim(),
      label: left.querySelector("[data-loot-label]").value.trim(),
      description: left.querySelector("[data-loot-desc]").value.trim(),
      is_active: left.querySelector("[data-loot-active]").checked,
    };
    if (!payload.key || !payload.label) {
      showToast("Key and label required.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/loot-tables", { method: "POST", body: JSON.stringify(payload) });
      showToast("Loot table created.", "success");
      await refreshLootList();
    } catch (e) {
      showToast(parseApiError(e, "Create failed."), "error");
    }
  });

  wireBulkJsonImport(left, {
    hint:
      "Każdy element: key, label, opcjonalnie description i is_active, opcjonalnie entries. W entries: dokładnie jedno z item_key | weapon_key | consumable_key (musi istnieć w katalogu), weight (drop chance %) w zakresie 1..100, qty_min / qty_max ≥ 1 i min ≤ max. Pusta lub brak entries = tabela bez wierszy. Przy 409 na tabeli z „Pomiń 409” wpisy i tak są wysyłane (upsert na istniejącą tabelę).",
    templatesHref: "/admin_panel/templates.html#sec-loot-tables",
    templatesAnchor: "Szablony JSON — Loot tables",
    placeholder:
      '[{"key":"example_loot","label":"Example","description":"","is_active":true,"entries":[{"item_key":"rope","weight":35,"qty_min":1,"qty_max":1}]}]',
    validateRow: validateLootTableBulkRow,
    existingKeys: () => fetchExistingKeysFromAdminList("/api/admin/loot-tables"),
    refresh: async () => {
      await refreshLootList();
      if (selectedKey) {
        await refreshEntriesPanel();
      }
    },
    confirmNoun: "tabel loot",
    commitRows: (parsed, ctx) => commitLootTablesBulkImport(parsed, ctx),
  });

  void refreshLootList();
  void refreshEntriesPanel();
}

async function refreshArchetypes(host) {
  const tableHost = host.querySelector(".admin-subpanel-body");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/archetypes");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderGameDesignTable(
      tableHost,
      "archetypes",
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        {
          key: "starter_gold_gp",
          label: "Złoto startowe (GP)",
          type: "number",
          editable: true,
        },
        {
          key: "starter_items_json",
          label: "Starter items (JSON)",
          type: "textarea",
          editable: true,
        },
        { key: "description", label: "Description", type: "textarea", editable: true },
        { key: "is_active", label: "Active", type: "boolean", editable: true },
        { key: "locked_at", label: "Lock", type: "locked" },
      ],
      rows,
      {
        searchPlaceholder: "Search archetypes…",
        onEdit: async (row, key, newValue, meta) => {
          const body = { force: !!(meta && meta.force) };
          if (key === "label") {
            body.label = newValue;
          }
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "starter_gold_gp") {
            const n = Number(newValue);
            if (!Number.isFinite(n) || n < 0) {
              showToast("starter_gold_gp musi być liczbą ≥ 0.", "error");
              throw new Error("invalid_starter_gold");
            }
            body.starter_gold_gp = Math.floor(n);
          }
          if (key === "starter_items_json") {
            const raw = String(newValue ?? "").trim();
            try {
              JSON.parse(raw || "[]");
            } catch (_e) {
              showToast("Niepoprawny JSON tablicy starter_items.", "error");
              throw new Error("invalid_starter_json");
            }
            body.starter_items_json = raw;
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          await adminFetch(`/api/admin/archetypes/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, { [key]: newValue });
          showToast("Archetyp zaktualizowany.", "success");
          await refreshArchetypes(host);
        },
      },
    );
  } catch (e) {
    showToast(parseApiError(e, "Nie udało się wczytać archetypów."), "error");
    renderTable(tableHost, [], [], {});
  }
}

function mountArchetypes(host) {
  const root = el("div", "admin-subpanel-inner");
  const note = el("p", "admin-note muted");
  note.innerHTML =
    "Pakiet startowy i <strong>gold_gp</strong> przy tworzeniu postaci: tylko gdy w kreatorze wybrano <code>warrior</code> lub <code>scholar</code>. " +
    "JSON to tablica obiektów; każdy element musi mieć dokładnie jedno z pól: <code>weapon_key</code>, <code>item_key</code>, <code>consumable_key</code> " +
    "(klucze muszą istnieć w katalogu). Preferencje skilli przy kreacji nadal w <code>character_creation_config.py</code>.";
  const body = el("div", "");
  body.dataset.subpanel = "archetypes";
  body.className = "admin-subpanel-body";
  root.appendChild(note);
  root.appendChild(body);
  host.appendChild(root);
  void refreshArchetypes(host);
}

function mountPrompts(host) {
  const root = el("div", "admin-subpanel-inner prompts-layout");
  const list = el("div", "prompts-list");
  const editor = el("div", "prompts-editor");
  editor.innerHTML = `
    <h3 class="prompts-heading">—</h3>
    <div class="prompts-meta muted">—</div>
    <textarea class="prompts-textarea" rows="24" disabled></textarea>
    <div class="prompts-actions">
      <button type="button" class="primary-btn" data-prompt-save disabled>Save</button>
      <button type="button" class="secondary-btn" data-prompt-reset disabled>Reset to backup</button>
    </div>
    <div class="prompts-count muted" data-prompt-count></div>
  `;
  root.appendChild(list);
  root.appendChild(editor);
  host.appendChild(root);

  const ta = editor.querySelector(".prompts-textarea");
  const metaEl = editor.querySelector(".prompts-meta");
  const headEl = editor.querySelector(".prompts-heading");
  const saveBtn = editor.querySelector("[data-prompt-save]");
  const resetBtn = editor.querySelector("[data-prompt-reset]");
  const countEl = editor.querySelector("[data-prompt-count]");

  let activeName = null;
  let hasBackup = false;

  const syncCount = () => {
    countEl.textContent = `${ta.value.length} characters`;
  };
  ta.addEventListener("input", syncCount);

  async function loadDetail(name) {
    activeName = name;
    const data = await adminFetch(`/api/admin/prompts/${encodeURIComponent(name)}`);
    headEl.textContent = data.name;
    metaEl.textContent = `Last modified: ${data.last_modified || "—"}`;
    ta.disabled = false;
    ta.value = data.content || "";
    hasBackup = !!data.has_backup;
    resetBtn.disabled = !hasBackup;
    saveBtn.disabled = false;
    syncCount();
  }

  async function initList() {
    list.innerHTML = "";
    const data = await adminFetch("/api/admin/prompts");
    const items = data.items || [];
    if (!items.length) {
      list.textContent = "No prompt files found.";
      return;
    }
    items.forEach((it) => {
      const b = el("button", "prompts-list-btn", it.name);
      b.type = "button";
      b.addEventListener("click", async () => {
        list.querySelectorAll(".prompts-list-btn").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        try {
          await loadDetail(it.name);
        } catch (e) {
          showToast(parseApiError(e, "Failed to load prompt."), "error");
        }
      });
      list.appendChild(b);
    });
    const firstBtn = list.querySelector(".prompts-list-btn");
    if (firstBtn) {
      firstBtn.click();
    }
  }

  saveBtn.addEventListener("click", async () => {
    if (!activeName) {
      return;
    }
    try {
      await adminFetch(`/api/admin/prompts/${encodeURIComponent(activeName)}`, {
        method: "PUT",
        body: JSON.stringify({ content: ta.value }),
      });
      showToast("Prompt saved.", "success");
      await loadDetail(activeName);
    } catch (e) {
      showToast(parseApiError(e, "Save failed."), "error");
    }
  });

  resetBtn.addEventListener("click", async () => {
    if (!activeName || !hasBackup) {
      return;
    }
    try {
      await adminFetch(`/api/admin/prompts/${encodeURIComponent(activeName)}`, {
        method: "PUT",
        body: JSON.stringify({ restore_from_backup: true }),
      });
      showToast("Restored from backup.", "success");
      await loadDetail(activeName);
    } catch (e) {
      showToast(parseApiError(e, "Restore failed."), "error");
    }
  });

  void initList().catch((e) => showToast(parseApiError(e, "Failed to list prompts."), "error"));
}

/**
 * @param {HTMLElement} container — .section-panel[data-section="game-design"]
 */
export async function init(container) {
  container.innerHTML = "";
  const title = el("h2", "", "Game Design");
  const tabs = el("div", "sub-tabs");
  const body = el("div", "game-design-body");
  container.appendChild(title);
  container.appendChild(tabs);
  container.appendChild(body);

  const panels = new Map();
  SUB_TABS.forEach((t) => {
    const btn = el("button", "sub-tab-btn", t.label);
    btn.type = "button";
    btn.dataset.subTab = t.id;
    tabs.appendChild(btn);
    const panel = el("div", "sub-tab-panel");
    panel.dataset.subTab = t.id;
    panel.hidden = true;
    body.appendChild(panel);
    panels.set(t.id, panel);
  });

  const statKeys = [];
  try {
    const d = await adminFetch("/api/admin/stats");
    statKeys.push(...(d.items || []).map((x) => x.key));
  } catch (_e) {
    statKeys.push("STR", "DEX", "CON", "INT", "WIS", "CHA");
  }

  const mountFns = {
    stats: () => mountStats(panels.get("stats")),
    skills: () => mountSkills(panels.get("skills"), statKeys),
    dc: () => mountDc(panels.get("dc")),
    weapons: () => mountWeapons(panels.get("weapons"), statKeys),
    enemies: () => mountEnemies(panels.get("enemies")),
    npcs: () => mountNpcs(panels.get("npcs")),
    locations: () => mountLocations(panels.get("locations")),
    conditions: () => mountConditions(panels.get("conditions")),
    items: () => mountItems(panels.get("items")),
    consumables: () => mountConsumables(panels.get("consumables")),
    "loot-tables": () => mountLootTables(panels.get("loot-tables")),
    archetypes: () => mountArchetypes(panels.get("archetypes")),
    prompts: () => mountPrompts(panels.get("prompts")),
  };

  const activated = new Set();
  function activate(id) {
    tabs.querySelectorAll(".sub-tab-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.subTab === id);
    });
    panels.forEach((p, pid) => {
      p.hidden = pid !== id;
    });
    if (!activated.has(id)) {
      mountFns[id]?.();
      activated.add(id);
    }
  }

  function remountActiveGameDesignTab() {
    const activeBtn = tabs.querySelector(".sub-tab-btn.active");
    const id = activeBtn?.dataset?.subTab || "stats";
    const p = panels.get(id);
    if (p) {
      p.innerHTML = "";
    }
    activated.delete(id);
    activate(id);
  }

  const snapshotBtn = el("button", "sub-tab-btn sub-tab-btn-action", "⬇ Export catalog snapshot (LLM)");
  snapshotBtn.type = "button";
  snapshotBtn.addEventListener("click", async () => {
    try {
      const data = await adminFetch("/api/admin/config/catalog-snapshot");
      downloadJsonFile(data, "aigm_catalog_snapshot");
      showToast("Catalog snapshot exported.", "success");
    } catch (e) {
      showToast(parseApiError(e, "Snapshot export failed."), "error");
    }
  });
  tabs.appendChild(snapshotBtn);

  const importInput = el("input");
  importInput.type = "file";
  importInput.accept = "application/json,.json";
  importInput.hidden = true;
  importInput.addEventListener("change", async () => {
    const f = importInput.files?.[0];
    if (!f) {
      return;
    }
    try {
      const text = await f.text();
      const payload = JSON.parse(text);
      const ok = await showConfirm(
        "Replace ALL Game Design catalogue tables from this file (stats, skills, DC, weapons, enemies, conditions, items, consumables, loot tables + entries)? " +
          "game_config_meta in the file is ignored (slash commands / Loki URLs are not overwritten). This cannot be undone.",
        { dangerous: true },
      );
      if (!ok) {
        importInput.value = "";
        return;
      }
      await adminFetch("/api/admin/config/catalog-snapshot/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Catalog snapshot imported.", "success");
      try {
        const d2 = await adminFetch("/api/admin/stats");
        statKeys.length = 0;
        statKeys.push(...(d2.items || []).map((x) => x.key));
      } catch (_e) {
        /* keep previous statKeys */
      }
      remountActiveGameDesignTab();
    } catch (e) {
      showToast(parseApiError(e, "Import failed (invalid JSON or server rejected payload)."), "error");
    } finally {
      importInput.value = "";
    }
  });

  const importBtn = el("button", "sub-tab-btn sub-tab-btn-action", "⬆ Import catalog snapshot (LLM)");
  importBtn.type = "button";
  importBtn.addEventListener("click", () => importInput.click());
  tabs.appendChild(importBtn);
  tabs.appendChild(importInput);

  tabs.addEventListener("click", (e) => {
    const b = e.target.closest(".sub-tab-btn");
    if (!b || !b.dataset.subTab) {
      return;
    }
    activate(b.dataset.subTab);
  });

  activate("stats");
}
