import { adminFetch, APIError } from "/admin_panel/shared/api.js";
import { showToast } from "/admin_panel/shared/toast.js";
import { renderTable, showConfirm } from "/admin_panel/shared/table.js";

const SUB_TABS = [
  { id: "stats", label: "Stats" },
  { id: "skills", label: "Skills" },
  { id: "dc", label: "DC" },
  { id: "weapons", label: "Weapons" },
  { id: "enemies", label: "Enemies" },
  { id: "conditions", label: "Conditions" },
  { id: "items", label: "Items" },
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
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail) {
    return String(err.body.detail);
  }
  return fallback;
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
        { key: "sort_order", label: "Sort", type: "number", editable: true },
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
          if (key === "sort_order") {
            body.sort_order = Number(newValue);
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
        { key: "sort_order", label: "Sort", type: "number", editable: true },
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
          if (key === "sort_order") {
            body.sort_order = Number(newValue);
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
        onDelete: async (row) => {
          try {
            await adminFetch(`/api/admin/skills/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: false }),
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
      <label class="field"><span>Sort order</span><input data-field="sort_order" type="number" value="0" /></label>
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
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);

  fields.querySelector('[data-action="create-skill"]').addEventListener("click", async () => {
    const key = fields.querySelector('[data-field="key"]').value.trim();
    const label = fields.querySelector('[data-field="label"]').value.trim();
    const linked_stat = fields.querySelector('[data-field="linked_stat"]').value.trim();
    const rank_ceiling = Number(fields.querySelector('[data-field="rank_ceiling"]').value || 5);
    const sort_order = Number(fields.querySelector('[data-field="sort_order"]').value || 0);
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
          sort_order,
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
        { key: "sort_order", label: "Sort", type: "number", editable: true },
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
          if (key === "sort_order") {
            body.sort_order = Number(newValue);
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
    const rows = (data.items || []).map((r) => ({
      ...r,
      _classes: formatAllowedClasses(r.allowed_classes),
    }));
    renderTable(
      tableHost,
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "damage_die", label: "Die", editable: true },
        { key: "linked_stat", label: "Stat", editable: true },
        { key: "_classes", label: "Classes" },
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
          if (key === "damage_die") {
            body.damage_die = String(newValue).trim().toLowerCase();
          }
          if (key === "linked_stat") {
            body.linked_stat = String(newValue).trim().toUpperCase();
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/weapons/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {}, {
            _classes: formatAllowedClasses((res.item && res.item.allowed_classes) || row.allowed_classes),
          });
          showToast("Weapon updated.", "success");
        },
        onDelete: async (row) => {
          try {
            await adminFetch(`/api/admin/weapons/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: false }),
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
      <label class="field"><span>Damage die</span><input data-field="damage_die" type="text" placeholder="d6" /></label>
      <label class="field"><span>Linked stat</span><select data-field="linked_stat"></select></label>
      <label class="field add-form-span-2"><span>Allowed classes</span>
        <span class="checkbox-inline"><label><input type="checkbox" data-class="warrior" checked /> warrior</label>
        <label><input type="checkbox" data-class="scholar" checked /> scholar</label>
        <label><input type="checkbox" data-class="ranger" /> ranger</label></span>
      </label>
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
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      damage_die: fields.querySelector('[data-field="damage_die"]').value.trim(),
      linked_stat: fields.querySelector('[data-field="linked_stat"]').value.trim(),
      allowed_classes: allowed,
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
  try {
    const data = await adminFetch("/api/admin/enemies");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderTable(
      tableHost,
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "hp_base", label: "HP", type: "number", editable: true },
        { key: "ac_base", label: "AC", type: "number", editable: true },
        { key: "attack_bonus", label: "Atk+", type: "number", editable: true },
        { key: "damage_die", label: "Die", editable: true },
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
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "is_active") {
            body.is_active = !!newValue;
          }
          const res = await adminFetch(`/api/admin/enemies/${encodeURIComponent(row.key)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          Object.assign(row, res.item || {});
          showToast("Enemy updated.", "success");
        },
        onDelete: async (row) => {
          try {
            await adminFetch(`/api/admin/enemies/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: false }),
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
      <label class="field"><span>HP base</span><input data-field="hp_base" type="number" value="8" /></label>
      <label class="field"><span>AC base</span><input data-field="ac_base" type="number" value="10" /></label>
      <label class="field"><span>Attack bonus</span><input data-field="attack_bonus" type="number" value="0" /></label>
      <label class="field"><span>Damage die</span><input data-field="damage_die" type="text" placeholder="d6" /></label>
      <label class="field add-form-span-2"><span>Description</span><input data-field="description" type="text" /></label>
      <label class="field"><span>Active</span><input data-field="is_active" type="checkbox" checked /></label>
    </div>
    <button type="button" class="primary-btn admin-add-form-submit" data-action="create-enemy">Create</button>
  `;
  details.appendChild(fields);
  toggle.addEventListener("click", () => {
    details.classList.toggle("admin-add-form-collapsed");
    toggle.textContent = details.classList.contains("admin-add-form-collapsed") ? "Add enemy ▾" : "Add enemy ▴";
  });
  toggleRow.appendChild(toggle);
  root.appendChild(toggleRow);
  root.appendChild(details);
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  fields.querySelector('[data-action="create-enemy"]').addEventListener("click", async () => {
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      hp_base: Number(fields.querySelector('[data-field="hp_base"]').value || 0),
      ac_base: Number(fields.querySelector('[data-field="ac_base"]').value || 0),
      attack_bonus: Number(fields.querySelector('[data-field="attack_bonus"]').value || 0),
      damage_die: fields.querySelector('[data-field="damage_die"]').value.trim(),
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
        onDelete: async (row) => {
          try {
            await adminFetch(`/api/admin/conditions/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: false }),
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
  const mount = el("div", "admin-table-mount");
  root.appendChild(mount);
  fields.querySelector('[data-action="create-condition"]').addEventListener("click", async () => {
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      effect_json: fields.querySelector('[data-field="effect_json"]').value.trim(),
      description: fields.querySelector('[data-field="description"]').value.trim() || null,
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
  if (raw.effect_json != null && String(raw.effect_json).trim()) {
    try {
      JSON.parse(String(raw.effect_json));
    } catch (_e) {
      return `${label}: effect_json must be valid JSON`;
    }
  }
  return null;
}

async function refreshItems(host) {
  const tableHost = host.querySelector(".items-table-mount");
  renderTable(tableHost, [], null, {});
  try {
    const data = await adminFetch("/api/admin/items");
    const rows = (data.items || []).map((r) => ({ ...r }));
    renderTable(
      tableHost,
      [
        { key: "key", label: "Key" },
        { key: "label", label: "Label", editable: true },
        { key: "item_type", label: "Type", type: "badge", badgeClass: itemTypeBadgeClass },
        { key: "description", label: "Description", editable: true },
        { key: "value_gp", label: "GP", type: "number", editable: true },
        { key: "weight", label: "Weight", type: "number", editable: true },
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
          if (key === "description") {
            body.description = newValue;
          }
          if (key === "value_gp") {
            body.value_gp = Number(newValue);
          }
          if (key === "weight") {
            body.weight = Number(newValue);
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
          Object.assign(row, res.item || {});
          showToast("Item updated.", "success");
        },
        onDelete: async (row) => {
          try {
            await adminFetch(`/api/admin/items/${encodeURIComponent(row.key)}`, {
              method: "DELETE",
              body: JSON.stringify({ force: false }),
            });
            showToast("Item deleted.", "success");
            await refreshItems(host);
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
            throw e;
          }
        },
        extraActions: (row) => [
          {
            label: "Set type",
            class: "secondary-btn",
            onClick: async () => {
              const cur = String(row.item_type || "misc");
              const n = window.prompt("item_type (weapon|armor|consumable|misc|quest)", cur);
              if (n == null) {
                return;
              }
              const v = String(n).trim().toLowerCase();
              if (!["weapon", "armor", "consumable", "misc", "quest"].includes(v)) {
                showToast("Invalid item_type.", "error");
                return;
              }
              try {
                const res = await adminFetch(`/api/admin/items/${encodeURIComponent(row.key)}`, {
                  method: "PATCH",
                  body: JSON.stringify({ item_type: v, force: false }),
                });
                Object.assign(row, res.item || {});
                await refreshItems(host);
                showToast("Type updated.", "success");
              } catch (e) {
                showToast(parseApiError(e, "Update failed."), "error");
              }
            },
          },
        ],
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
      <label class="field"><span>Weight</span><input data-field="weight" type="number" step="any" value="0" /></label>
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

  const bulk = el("details", "admin-bulk-import");
  bulk.innerHTML = `
    <summary>Bulk import (JSON array)</summary>
    <p class="muted">Paste a JSON array of items. Dry run validates all rows; commit POSTs each row.</p>
    <textarea class="admin-bulk-textarea" data-bulk-items rows="8" placeholder='[{ "key": "health_potion", ... }]'></textarea>
    <div class="admin-bulk-actions">
      <button type="button" class="secondary-btn" data-bulk-dry>Dry run</button>
      <button type="button" class="primary-btn" data-bulk-commit>Commit</button>
    </div>
    <pre class="admin-bulk-result muted" data-bulk-result></pre>
  `;
  root.appendChild(bulk);

  const mount = el("div", "admin-table-mount items-table-mount");
  root.appendChild(mount);

  fields.querySelector('[data-action="create-item"]').addEventListener("click", async () => {
    const eff = fields.querySelector('[data-field="effect_json"]').value.trim();
    const payload = {
      key: fields.querySelector('[data-field="key"]').value.trim(),
      label: fields.querySelector('[data-field="label"]').value.trim(),
      item_type: fields.querySelector('[data-field="item_type"]').value.trim(),
      description: fields.querySelector('[data-field="description"]').value.trim(),
      value_gp: Number(fields.querySelector('[data-field="value_gp"]').value || 0),
      weight: Number(fields.querySelector('[data-field="weight"]').value || 0),
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

  const ta = bulk.querySelector("[data-bulk-items]");
  const resultPre = bulk.querySelector("[data-bulk-result]");
  bulk.querySelector("[data-bulk-dry]").addEventListener("click", () => {
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
      const err = validateItemImportRow(row, i);
      if (err) {
        errors.push(err);
      }
    });
    if (errors.length) {
      resultPre.textContent = errors.join("\n");
      showToast(`Dry run: ${errors.length} issue(s).`, "info");
    } else {
      resultPre.textContent = `OK — ${parsed.length} row(s) would be imported.`;
      showToast("Dry run OK.", "success");
    }
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
      const err = validateItemImportRow(row, i);
      if (err) {
        errors.push(err);
      }
    });
    if (errors.length) {
      resultPre.textContent = errors.join("\n");
      showToast("Fix validation errors before commit.", "error");
      return;
    }
    const ok = await showConfirm(`Create ${parsed.length} item(s) from JSON?`, { dangerous: false });
    if (!ok) {
      return;
    }
    let okn = 0;
    const fail = [];
    for (let i = 0; i < parsed.length; i += 1) {
      const r = parsed[i];
      const body = {
        key: String(r.key).trim(),
        label: String(r.label).trim(),
        item_type: String(r.item_type || "misc").toLowerCase(),
        description: r.description != null ? String(r.description) : "",
        value_gp: r.value_gp != null ? Number(r.value_gp) : 0,
        weight: r.weight != null ? Number(r.weight) : 0,
        effect_json: r.effect_json != null && String(r.effect_json).trim() ? String(r.effect_json) : null,
        is_active: r.is_active !== false && r.is_active !== 0,
      };
      try {
        await adminFetch("/api/admin/items", { method: "POST", body: JSON.stringify(body) });
        okn += 1;
      } catch (e) {
        fail.push(`${body.key}: ${parseApiError(e, "failed")}`);
      }
    }
    resultPre.textContent = `Created: ${okn}. Failed: ${fail.length}${fail.length ? `\n${fail.join("\n")}` : ""}`;
    showToast(`Commit done: ${okn} created, ${fail.length} failed.`, fail.length ? "info" : "success");
    await refreshItems(host);
  });

  host.appendChild(root);
  void refreshItems(host);
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
      <label class="field loot-desc-field"><span>Description</span><textarea data-loot-desc-edit rows="2"></textarea></label>
      <h4 class="loot-entries-title">Entries</h4>
      <div class="loot-entries-table-wrap" data-loot-entries-wrap></div>
      <div class="loot-add-entry add-form-grid">
        <label class="field"><span>Item</span><select data-loot-item-select></select></label>
        <label class="field"><span>Weight</span><input data-loot-w type="number" value="10" min="1" /></label>
        <label class="field"><span>Qty min</span><input data-loot-qmin type="number" value="1" min="1" /></label>
        <label class="field"><span>Qty max</span><input data-loot-qmax type="number" value="1" min="1" /></label>
        <button type="button" class="primary-btn" data-loot-add-entry>+ Add</button>
      </div>
      <div class="loot-weight-viz" data-loot-viz></div>
    </div>`;
  root.appendChild(left);
  root.appendChild(right);
  host.appendChild(root);

  let selectedKey = null;
  let selectedLabel = "";
  const listMount = left.querySelector(".loot-table-list-mount");
  const addForm = left.querySelector("[data-loot-add-form]");
  const addToggle = left.querySelector("[data-loot-add-toggle]");
  addToggle.addEventListener("click", () => {
    addForm.classList.toggle("admin-add-form-collapsed");
    addToggle.textContent = addForm.classList.contains("admin-add-form-collapsed") ? "Add table ▾" : "Add table ▴";
  });

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
      const lab = el("span", "loot-weight-label", `${e.item_label || e.item_key}`);
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

  async function loadItemOptions(selectEl) {
    selectEl.innerHTML = "";
    try {
      const d = await adminFetch("/api/admin/items");
      (d.items || []).forEach((it) => {
        const o = document.createElement("option");
        o.value = it.key;
        o.textContent = `${it.label} (${it.key})`;
        selectEl.appendChild(o);
      });
    } catch (_e) {
      selectEl.appendChild(el("option", "", "(failed to load items)"));
    }
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
    wrap.innerHTML = "";
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
    ["Item", "Weight", "Qty min", "Qty max", ""].forEach((h) => {
      const th = el("th", "", h);
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    tbl.appendChild(thead);
    const tb = el("tbody");
    const recalcViz = () => {
      const live = [];
      tb.querySelectorAll("tr").forEach((tr) => {
        const ik = tr.dataset.itemKey;
        if (!ik) {
          return;
        }
        const ins = tr.querySelectorAll("input[type='number']");
        if (ins.length < 3) {
          return;
        }
        live.push({
          item_key: ik,
          item_label: tr.cells[0]?.textContent?.trim() || ik,
          weight: Number(ins[0].value) || 0,
          qty_min: Number(ins[1].value) || 0,
          qty_max: Number(ins[2].value) || 0,
        });
      });
      renderWeightViz(live);
    };
    entries.forEach((en) => {
      const tr = el("tr");
      tr.dataset.itemKey = en.item_key;
      const td1 = el("td", "", en.item_label || en.item_key);
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
          await adminFetch(
            `/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries/${encodeURIComponent(en.item_key)}`,
            { method: "DELETE" },
          );
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
        try {
          await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries`, {
            method: "POST",
            body: JSON.stringify({ item_key: en.item_key, weight, qty_min, qty_max }),
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
    const sel = right.querySelector("[data-loot-item-select]");
    await loadItemOptions(sel);
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
    const sel = right.querySelector("[data-loot-item-select]");
    const item_key = sel.value;
    if (!item_key) {
      showToast("Select an item.", "info");
      return;
    }
    const weight = Number(right.querySelector("[data-loot-w]").value || 10);
    const qty_min = Number(right.querySelector("[data-loot-qmin]").value || 1);
    const qty_max = Number(right.querySelector("[data-loot-qmax]").value || 1);
    try {
      await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(selectedKey)}/entries`, {
        method: "POST",
        body: JSON.stringify({ item_key, weight, qty_min, qty_max }),
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
            const res = await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(row.key)}`, {
              method: "PATCH",
              body: JSON.stringify(body),
            });
            Object.assign(row, res.item || {});
            if (selectedKey === row.key) {
              selectedLabel = row.label || selectedLabel;
            }
            showToast("Loot table updated.", "success");
          },
          onDelete: async (row) => {
            try {
              await adminFetch(`/api/admin/loot-tables/${encodeURIComponent(row.key)}`, {
                method: "DELETE",
                body: JSON.stringify({ force: false }),
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
              label: "Edit",
              class: "secondary-btn",
              onClick: async () => {
                selectedKey = row.key;
                selectedLabel = row.label;
                await refreshEntriesPanel();
              },
            },
          ],
        },
      );
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
