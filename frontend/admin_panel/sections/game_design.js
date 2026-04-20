import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";
import { renderTable, showConfirm } from "/admin_panel/shared/table.js?v=20";

const SUB_TABS = [
  { id: "stats", label: "Stats" },
  { id: "skills", label: "Skills" },
  { id: "dc", label: "DC" },
  { id: "weapons", label: "Weapons" },
  { id: "enemies", label: "Enemies" },
  { id: "conditions", label: "Conditions" },
  { id: "items", label: "Items" },
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

/** @param {string} listPath e.g. /api/admin/skills */
async function fetchExistingKeysFromAdminList(listPath) {
  const data = await adminFetch(listPath);
  return new Set((data.items || []).map((r) => String(r.key)));
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
    renderTable(
      tableHost,
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
    renderTable(
      tableHost,
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "linked_stat", label: "Stat", editable: true },
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
    renderTable(
      tableHost,
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
    renderTable(
      tableHost,
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
        { key: "linked_stat", label: "Stat", editable: true },
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
    renderTable(
      tableHost,
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

async function refreshConditions(host) {
  const tableHost = host.querySelector(".admin-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/conditions");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderTable(
      tableHost,
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
 *   buildPayload: (raw: object) => object,
 *   postPath: string,
 *   refresh: () => void | Promise<void>,
 *   confirmNoun?: string,
 *   existingKeys?: () => Promise<Set<string>>,
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
    if (opts.existingKeys && errors.length === 0) {
      try {
        const existing = await opts.existingKeys();
        parsed.forEach((row, i) => {
          if (row && typeof row === "object" && row.key != null) {
            const k = String(row.key).trim();
            if (k && existing.has(k)) {
              dupWarn.push(
                `Row ${i + 1} (${k}): klucz już jest w bazie — POST zwróci 409 (Conflict). Włącz „Pomiń 409” lub użyj innego klucza.`,
              );
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
      showToast(`Dry run: ${errors.length} issue(s).`, "info");
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
      showToast("Fix validation errors before commit.", "error");
      return;
    }
    const skip409 = bulk.querySelector("[data-bulk-skip-409]")?.checked ?? true;
    const ok = await showConfirm(`Utworzyć ${parsed.length} rekord(ów) z JSON?`, { dangerous: false });
    if (!ok) {
      return;
    }
    let okn = 0;
    let skip409n = 0;
    const fail = [];
    for (let i = 0; i < parsed.length; i += 1) {
      const r = parsed[i];
      const key = r && typeof r === "object" && r.key != null ? String(r.key) : `row ${i + 1}`;
      try {
        await adminFetch(opts.postPath, { method: "POST", body: JSON.stringify(opts.buildPayload(r)) });
        okn += 1;
      } catch (e) {
        if (skip409 && e instanceof APIError && e.status === 409) {
          skip409n += 1;
          continue;
        }
        fail.push(`${key}: ${parseApiError(e, "failed")}`);
      }
    }
    resultPre.textContent = [
      `Utworzono: ${okn}. Pominięto (409, klucz już istnieje): ${skip409n}. Inne błędy: ${fail.length}`,
      fail.length ? `\n${fail.join("\n")}` : "",
    ]
      .filter(Boolean)
      .join("");
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
    renderTable(
      tableHost,
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
        },
        { key: "description", label: "Description", editable: true },
        { key: "value_gp", label: "GP", type: "number", editable: true },
        { key: "weight", label: "Weight (legacy)", type: "number", editable: true },
        { key: "weight_kg", label: "Weight kg", type: "number", editable: true },
        { key: "_proficiency_json", label: "Proficiency classes (JSON)", type: "textarea", editable: true },
        { key: "note", label: "Note", editable: true },
        { key: "effect_json", label: "Effect JSON", type: "textarea", editable: true },
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
          if (key === "weight") {
            body.weight = Number(newValue);
          }
          if (key === "weight_kg") {
            body.weight_kg = Number(newValue);
          }
          if (key === "_proficiency_json") {
            let parsed;
            try {
              parsed = JSON.parse(String(newValue || "[]"));
            } catch (_e) {
              showToast("proficiency_classes must be valid JSON array.", "error");
              throw new Error("invalid_json");
            }
            if (!Array.isArray(parsed)) {
              showToast("proficiency_classes must be a JSON array.", "error");
              throw new Error("invalid_json");
            }
            body.proficiency_classes = parsed;
          }
          if (key === "note") {
            body.note = newValue;
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
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field"><span>Value (GP)</span><input data-field="value_gp" type="number" value="0" /></label>
      <label class="field"><span>Weight (legacy)</span><input data-field="weight" type="number" step="any" value="0" /></label>
      <label class="field"><span>Weight (kg)</span><input data-field="weight_kg" type="number" step="any" value="0" /></label>
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
    renderTable(
      tableHost,
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
        <label class="field"><span>Weight</span><input data-loot-weight type="number" value="10" min="1" /></label>
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
    const sum = entries.reduce((s, e) => s + Math.max(1, Number(e.weight) || 0), 0);
    entries.forEach((e) => {
      const w = Math.max(1, Number(e.weight) || 0);
      const pct = sum > 0 ? Math.round((w / sum) * 1000) / 10 : 0;
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
    ["Source (type · label · key)", "Weight", "Qty min", "Qty max", ""].forEach((h) => {
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
    renderWeightViz(entries);
    const descTa = right.querySelector("[data-loot-desc-edit]");
    try {
      const tables = await adminFetch("/api/admin/loot-tables");
      const meta = (tables.items || []).find((t) => t.key === selectedKey);
      descTa.value = meta ? meta.description || "" : "";
    } catch (_e) {
      descTa.value = "";
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
      renderTable(
        listMount,
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

  void refreshLootList();
  void refreshEntriesPanel();
}

function mountArchetypes(host) {
  const root = el("div", "admin-subpanel-inner");
  const banner = el("div", "admin-callout");
  banner.textContent =
    "⚠️ To add or remove archetypes, edit character_creation_config.py and redeploy.";
  root.appendChild(banner);
  const grid = el("div", "archetype-admin-grid");
  const w = el("div", "archetype-card-admin");
  w.innerHTML = `
    <h3>Warrior</h3>
    <p><strong>Skill weights (preferred at creation):</strong> athletics, melee_attack, endurance, intimidation, survival</p>
    <p><strong>Skill budget:</strong> 8 slots, 7 active skills at creation</p>
    <p><strong>Max skill level at creation:</strong> 2</p>
    <p class="muted">Defined in backend/app/character_creation_config.py</p>
  `;
  const s = el("div", "archetype-card-admin");
  s.innerHTML = `
    <h3>Scholar</h3>
    <p><strong>Skill weights (preferred at creation):</strong> arcana, lore, investigation, medicine, awareness</p>
    <p><strong>Skill budget:</strong> 10 slots, 8 active skills at creation</p>
    <p><strong>Max skill level at creation:</strong> 2</p>
    <p class="muted">Defined in backend/app/character_creation_config.py</p>
  `;
  grid.appendChild(w);
  grid.appendChild(s);
  root.appendChild(grid);
  host.appendChild(root);
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

  tabs.addEventListener("click", (e) => {
    const b = e.target.closest(".sub-tab-btn");
    if (!b) {
      return;
    }
    activate(b.dataset.subTab);
  });

  activate("stats");
}
