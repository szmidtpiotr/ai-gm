import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable, showConfirm } from "/admin_panel_v2/shared/table.js?v=5";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";
import { openSmartEntry } from "/admin_panel_v2/shared/smart_entry.js?v=5";

const LABELS = {
  weapons:      "Broń",
  armor:        "Zbroja",
  enemies:      "Wrogowie",
  items:        "Przedmioty",
  consumables:  "Materiały eksploatacyjne",
  lootTables:   "Tabele łupów",
  archetypes:   "Archetypy",
  key:          "Klucz",
  label:        "Nazwa",
  description:  "Opis",
  isActive:     "Aktywny",
  locked:       "Blokada",
  save:         "Zapisz",
  cancel:       "Anuluj",
  add:          "Dodaj",
  delete:       "Usuń",
  weaponTypes:  { melee: "Wręcz", ranged: "Dystansowa", spell: "Czar" },
  damageTypes:  { physical: "Fizyczne", magic: "Magiczne", fire: "Ogień", poison: "Trucizna", misc: "Inne" },
  tiers:        { weak: "Słaby", standard: "Standardowy", elite: "Elitarny", boss: "Boss" },
  itemTypes:    { weapon: "Broń", armor: "Zbroja", consumable: "Eksploatacja", misc: "Różne", quest: "Zadanie", narrative: "Narracja" },
  effectTypes:  { heal_hp: "Leczenie HP", restore_mana: "Odnowienie many", remove_condition: "Usuń stan", add_condition: "Dodaj stan", stat_buff: "Bufor statystyki", misc: "Inne" },
  classes:      ["warrior", "scholar", "ranger"],
  assistant:    "Asystent AI",
  assistantHelp:"Opisz w kilku zdaniach co chcesz wygenerować (broń, wroga, przedmiot…)",
  generate:     "Generuj",
  saveDraft:    "Zapisz szkic",
  clearChat:    "Wyczyść",
  resource:     "Katalog",
};

const TABS = ["weapons", "armor", "items", "consumables", "loot-tables"];

const ASSISTANT_RESOURCES = [
  { value: "weapons",     label: LABELS.weapons },
  { value: "armor",       label: LABELS.armor },
  { value: "items",       label: LABELS.items },
  { value: "consumables", label: LABELS.consumables },
  { value: "loot-tables", label: LABELS.lootTables },
];

const TAB_TO_RESOURCE = {
  weapons:       "weapons",
  armor:         "armor",
  items:         "items",
  consumables:   "consumables",
  "loot-tables": "loot-tables",
};

const _rendered = new Set();
let _statsCache  = null;
let _aiHistory   = [];
let _aiDraft     = null;
let _aiResource  = "weapons";

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content content-layout">
      <div class="content-main">
        <div class="subtab-bar">
          <button class="subtab-btn active" data-tab="weapons">${LABELS.weapons}</button>
          <button class="subtab-btn" data-tab="armor">${LABELS.armor}</button>
          <button class="subtab-btn" data-tab="items">${LABELS.items}</button>
          <button class="subtab-btn" data-tab="consumables">${LABELS.consumables}</button>
          <button class="subtab-btn" data-tab="loot-tables">${LABELS.lootTables}</button>
          <button class="subtab-btn" id="smart-entry-btn" title="AI asystent tworzenia treści" style="margin-left:auto">🤖 Kreator AI</button>
        </div>
        <div class="subtab-panels">
          ${["weapons","armor","items","consumables","loot-tables"].map(
            (t) => `<div class="subtab-panel${t === "weapons" ? " active" : ""}" data-tab="${t}"></div>`
          ).join("")}
        </div>
      </div>
    </div>

    <!-- Smart Entry bubble (replaces old ⚡ Asystent AI) -->
    <button class="ai-bubble-btn" id="ai-fab-btn" title="🤖 Kreator AI — twórz treści z asystentem">🤖</button>`;

  _rendered.clear();
  _aiHistory = [];
  _aiDraft   = null;

  // ── Smart Entry bubble (bottom-right) + tab button both open Smart Entry ──
  const TABLE_MAP = { weapons: "game_config_weapons", armor: "game_config_items", items: "game_config_items", consumables: "game_config_consumables", "loot-tables": null };
  const _getActiveTable = () => TABLE_MAP[panel.querySelector(".subtab-btn.active:not(#smart-entry-btn)")?.dataset?.tab] || null;

  panel.querySelector("#ai-fab-btn").addEventListener("click", () => openSmartEntry(_getActiveTable()));
  panel.querySelector("#smart-entry-btn").addEventListener("click", () => openSmartEntry(_getActiveTable()));

  // ── Auto-refresh table after Smart Entry save ──
  const _onSmartSave = (e) => {
    const table = e.detail?.table;
    const tabMap = { game_config_weapons: "weapons", game_config_items: "items", game_config_consumables: "consumables" };
    const tab = tabMap[table];
    if (tab) {
      // Re-render the saved tab to show the new record
      _rendered.delete(tab);
      const tabPanel = panel.querySelector(`.subtab-panel[data-tab="${tab}"]`);
      if (tabPanel) _activateTab(panel, tab);
    }
  };
  window.addEventListener("smart-entry-saved", _onSmartSave);
  // Clean up listener when panel is destroyed
  new MutationObserver((_, obs) => {
    if (!document.contains(panel)) { window.removeEventListener("smart-entry-saved", _onSmartSave); obs.disconnect(); }
  }).observe(document.body, { childList: true, subtree: true });

  panel.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.id === "smart-entry-btn") return;
      panel.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
      panel.querySelectorAll(".subtab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      panel.querySelector(`.subtab-panel[data-tab="${tab}"]`).classList.add("active");
      if (TAB_TO_RESOURCE[tab]) {
        const sel = panel.querySelector("#ai-resource-select");
        if (sel) sel.value = TAB_TO_RESOURCE[tab];
        _aiResource = TAB_TO_RESOURCE[tab];
      }
      _activateTab(panel, tab);
    });
  });

  // Old popup elements removed — smart_entry.js handles AI creation now

  await _activateTab(panel, "weapons");
}

async function _activateTab(panel, tab) {
  if (_rendered.has(tab)) return;
  _rendered.add(tab);
  const container = panel.querySelector(`.subtab-panel[data-tab="${tab}"]`);
  if (!container) return;
  container.innerHTML = "";
  switch (tab) {
    case "weapons":     await _renderWeapons(container, panel); break;
    case "armor":       await _renderArmor(container, panel); break;
    case "enemies":     await _renderEnemies(container, panel); break;
    case "items":       await _renderItems(container, panel); break;
    case "consumables": await _renderConsumables(container, panel); break;
    case "loot-tables": await _renderLootTables(container, panel); break;
  }
}

function _reloadTab(panel, tab) {
  _rendered.delete(tab);
  _activateTab(panel, tab);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function _fetchStats() {
  if (_statsCache) return _statsCache;
  _statsCache = ((await adminFetch("/api/admin/stats")).items || []);
  return _statsCache;
}

function _field(label, content) {
  const lbl = document.createElement("label");
  lbl.className = "modal-field";
  lbl.innerHTML = `<span>${label}</span>${content}`;
  return lbl;
}

function _checkbox(name, labelText, checked = false) {
  const lbl = document.createElement("label");
  lbl.className = "modal-checkbox-row";
  lbl.innerHTML = `<input type="checkbox" name="${name}" ${checked ? "checked" : ""}><span>${labelText}</span>`;
  return lbl;
}

function _toolbar(addLabel, onAdd) {
  const wrap = document.createElement("div");
  wrap.className = "tab-toolbar";
  const btn = document.createElement("button");
  btn.className = "primary-btn";
  btn.textContent = "+ " + addLabel;
  btn.addEventListener("click", onAdd);
  wrap.appendChild(btn);
  return wrap;
}

// ── Weapons ───────────────────────────────────────────────────────────────────

async function _renderWeapons(container, panel) {
  const tableHost = document.createElement("div");
  container.appendChild(_toolbar("Dodaj broń", () => _openWeaponModal(null, load)));
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let [rows, stats] = [[], []];
    try {
      [rows, stats] = await Promise.all([adminFetch("/api/admin/weapons").then((r) => r.items || []), _fetchStats()]);
    } catch (e) {
      showToast("Błąd ładowania broni: " + (e.message || "?"), "error"); return;
    }
    const statOpts = stats.map((s) => ({ value: s.key, label: s.label || s.key }));

    const cols = [
      { key: "key",           label: LABELS.key,        editable: false },
      { key: "label",         label: LABELS.label,      editable: true },
      { key: "weapon_type",   label: "Typ",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.weaponTypes),
        badgeClass: (r) => r.weapon_type === "spell" ? "admin-badge-blue" : r.weapon_type === "ranged" ? "admin-badge-gold" : "admin-badge-muted",
        filterOptions: Object.entries(LABELS.weaponTypes).map(([v,l]) => ({value:v,label:l})),
      },
      { key: "damage_die",    label: "Kość",            editable: true },
      { key: "linked_stat",   label: "Stat",            type: "select-dropdown", editable: true, editOptions: statOpts },
      { key: "two_handed",    label: "Oburącz",         type: "boolean", editable: true },
      { key: "finesse",       label: "Finezja",         type: "boolean", editable: true },
      { key: "magic_school",  label: "Szkoła magii",    editable: true },
      { key: "range_m",       label: "Zasięg (m)",      type: "number",  editable: true },
      { key: "targeting",     label: "Cel",             editable: true },
      { key: "aoe",           label: "AoE",             editable: true },
      { key: "value_gp",      label: "Cena (gp)",       type: "number",  editable: true },
      { key: "weight_kg",     label: "Waga (kg)",       type: "number",  editable: true },
      { key: "description",   label: "Opis",            editable: true, popup: true },
      { key: "note",          label: "Notatka",         editable: true, popup: true },
      { key: "is_active",     label: LABELS.isActive,   type: "boolean", editable: true },
      { key: "locked_at",     label: LABELS.locked,     type: "locked",  editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      tableId:           "weapons",
      selectable:        true,
      showTextSearch:    true,
      searchPlaceholder: "Szukaj broni…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/weapons/${row.key}`, {
            method: "PATCH", body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/admin/weapons/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openWeaponModal(row, load) }],
    });
  };

  await load();
}

function _openWeaponModal(row, onDone) {
  const isEdit = !!row;
  const classes = LABELS.classes;

  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span><input name="key" type="text" value="${_esc(row?.key ?? "")}" ${isEdit?"readonly":""} placeholder="np. longsword" autocomplete="off"/></label>
    <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" value="${_esc(row?.label ?? "")}" placeholder="np. Miecz długi" autocomplete="off"/></label>
    <label class="modal-field"><span>Typ broni</span>
      <select name="weapon_type">${Object.entries(LABELS.weaponTypes).map(([v,l])=>`<option value="${v}"${(row?.weapon_type??"melee")===v?" selected":""}>${l}</option>`).join("")}</select>
    </label>
    <label class="modal-field"><span>Kość obrażeń *</span><input name="damage_die" type="text" value="${_esc(row?.damage_die??"d6")}" placeholder="np. d8"/></label>
    <label class="modal-field"><span>Zasięg (m)</span><input name="range_m" type="number" value="${row?.range_m??0}" min="0"/></label>
    <label class="modal-field"><span>Wartość (gp)</span><input name="value_gp" type="number" value="${row?.value_gp??0}" min="0"/></label>
    <label class="modal-field"><span>Waga (kg)</span><input name="weight_kg" type="number" value="${row?.weight_kg??0}" step="0.1" min="0"/></label>
    <label class="modal-field"><span>Opis</span><textarea name="description" rows="3">${_esc(row?.description??"")}</textarea></label>
    <div class="modal-field"><span>Dostępne klasy</span><div class="checkbox-group">${classes.map(c=>`<label class="modal-checkbox-row"><input type="checkbox" name="classes_${c}" ${(row?.allowed_classes??[]).includes(c)?"checked":""}><span>${c}</span></label>`).join("")}</div></div>
    <label class="modal-checkbox-row"><input name="two_handed" type="checkbox" ${row?.two_handed?"checked":""}><span>Oburęczna</span></label>
    <label class="modal-checkbox-row"><input name="finesse" type="checkbox" ${row?.finesse?"checked":""}><span>Finezja</span></label>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>${LABELS.isActive}</span></label>`;

  openModal({
    title: isEdit ? `Edytuj broń: ${row.key}` : "Dodaj broń",
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : LABELS.add,
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          const damage_die = g("damage_die").value.trim();
          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }
          if (!damage_die) { showToast("Kość obrażeń jest wymagana.", "error"); return; }
          const allowed_classes = LABELS.classes.filter((cl) => g(`classes_${cl}`)?.checked);
          if (!allowed_classes.length) { showToast("Wybierz przynajmniej jedną klasę.", "error"); return; }

          const body = {
            key, label, damage_die,
            weapon_type: g("weapon_type").value,
            range_m: Number(g("range_m").value),
            value_gp: Number(g("value_gp").value),
            weight_kg: Number(g("weight_kg").value),
            description: g("description").value.trim(),
            two_handed: g("two_handed").checked,
            finesse: g("finesse").checked,
            is_active: g("is_active").checked,
            allowed_classes,
          };
          try {
            if (isEdit) {
              await adminFetch(`/api/admin/weapons/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/admin/weapons", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano broń.", "success");
            c(); await onDone();
          } catch (e) { showToast((e.message || "Błąd zapisu"), "error"); }
        },
      },
    ],
  });
}

// ── Enemies ───────────────────────────────────────────────────────────────────

async function _renderEnemies(container, panel) {
  const tableHost = document.createElement("div");
  container.appendChild(_toolbar("Dodaj wroga", () => _openEnemyModal(null, load)));
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try { rows = (await adminFetch("/api/admin/enemies")).items || []; }
    catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",         label: LABELS.key,   editable: false },
      { key: "label",       label: LABELS.label, editable: true },
      { key: "tier",        label: "Poziom",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.tiers),
        badgeClass: (r) => ({ weak: "admin-badge-muted", standard: "admin-badge-blue", elite: "admin-badge-gold", boss: "admin-badge-red" }[r.tier] ?? "admin-badge-muted"),
        filterOptions: Object.entries(LABELS.tiers).map(([v,l])=>({value:v,label:l})),
      },
      { key: "hp_base",     label: "HP bazowe",  type: "number", editable: true },
      { key: "damage_die",  label: "Kość",       editable: true },
      { key: "xp_award",    label: "XP",         type: "number", editable: true },
      { key: "is_active",   label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",   label: LABELS.locked,   type: "locked", editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      showTextSearch: true, searchPlaceholder: "Szukaj wrogów…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/enemies/${row.key}`, { method: "PATCH", body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/admin/enemies/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openEnemyModal(row, load) }],
    });
  };
  await load();
}

function _openEnemyModal(row, onDone) {
  const isEdit = !!row;
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span><input name="key" type="text" value="${_esc(row?.key??"")}" ${isEdit?"readonly":""} placeholder="np. goblin_scout" autocomplete="off"/></label>
    <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" value="${_esc(row?.label??"")}" placeholder="np. Goblin zwiadowca" autocomplete="off"/></label>
    <label class="modal-field"><span>Poziom</span><select name="tier">${Object.entries(LABELS.tiers).map(([v,l])=>`<option value="${v}"${(row?.tier??"standard")===v?" selected":""}>${l}</option>`).join("")}</select></label>
    <label class="modal-field"><span>HP bazowe *</span><input name="hp_base" type="number" value="${row?.hp_base??10}" min="1"/></label>
    <label class="modal-field"><span>AC bazowe</span><input name="ac_base" type="number" value="${row?.ac_base??10}" min="0"/></label>
    <label class="modal-field"><span>Bonus do ataku</span><input name="attack_bonus" type="number" value="${row?.attack_bonus??0}"/></label>
    <label class="modal-field"><span>Bonus obrażeń</span><input name="damage_bonus" type="number" value="${row?.damage_bonus??0}"/></label>
    <label class="modal-field"><span>Kość obrażeń *</span><input name="damage_die" type="text" value="${_esc(row?.damage_die??"d6")}" placeholder="d6"/></label>
    <label class="modal-field"><span>Ataki/turę</span><input name="attacks_per_turn" type="number" value="${row?.attacks_per_turn??1}" min="1"/></label>
    <label class="modal-field"><span>Typ obrażeń</span><select name="damage_type">${Object.entries(LABELS.damageTypes).map(([v,l])=>`<option value="${v}"${(row?.damage_type??"physical")===v?" selected":""}>${l}</option>`).join("")}</select></label>
    <label class="modal-field"><span>Nagroda XP</span><input name="xp_award" type="number" value="${row?.xp_award??10}" min="0"/></label>
    <label class="modal-field"><span>Opis</span><textarea name="description" rows="3">${_esc(row?.description??"")}</textarea></label>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>${LABELS.isActive}</span></label>`;

  openModal({
    title: isEdit ? `Edytuj wroga: ${row.key}` : "Dodaj wroga",
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : LABELS.add,
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key) { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }
          const body = {
            key, label,
            tier: g("tier").value,
            hp_base: Number(g("hp_base").value),
            ac_base: Number(g("ac_base").value),
            attack_bonus: Number(g("attack_bonus").value),
            damage_bonus: Number(g("damage_bonus").value),
            damage_die: g("damage_die").value.trim(),
            attacks_per_turn: Number(g("attacks_per_turn").value),
            damage_type: g("damage_type").value,
            xp_award: Number(g("xp_award").value),
            description: g("description").value.trim(),
            is_active: g("is_active").checked,
          };
          try {
            if (isEdit) {
              await adminFetch(`/api/admin/enemies/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/admin/enemies", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano wroga.", "success");
            c(); await onDone();
          } catch (e) { showToast((e.message || "Błąd"), "error"); }
        },
      },
    ],
  });
}

// ── Items ─────────────────────────────────────────────────────────────────────

async function _renderArmor(container, panel) {
  container.appendChild(_toolbar("Dodaj zbroję", () => _openItemModal({ item_type: "armor" }, load, true)));
  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try {
      const data = (await adminFetch("/api/admin/items")).items || [];
      rows = data.filter(r => r.item_type === "armor");
    }
    catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",        label: LABELS.key,    editable: false },
      { key: "label",      label: LABELS.label,  editable: true },
      { key: "value_gp",   label: "Cena (gp)",   type: "number", editable: true },
      { key: "weight_kg",  label: "Waga (kg)",   type: "number", editable: true },
      { key: "ac_bonus",   label: "Bonus AC",    type: "number", editable: true },
      { key: "description",label: "Opis",        editable: true, popup: true },
      { key: "is_active",  label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",  label: LABELS.locked,   type: "locked",  editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      tableId:        "armor",
      selectable:     true,
      showTextSearch: true, searchPlaceholder: "Szukaj zbroi…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/items/${row.key}`, { method: "PATCH", body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/admin/items/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openItemModal(row, load) }],
    });
  };
  await load();
}

async function _renderItems(container, panel) {
  const tableHost = document.createElement("div");
  container.appendChild(_toolbar("Dodaj przedmiot", () => _openItemModal(null, load)));
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try {
      const data = (await adminFetch("/api/admin/items")).items || [];
      rows = data.filter(r => r.item_type !== "armor"); // armor has its own tab
    }
    catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",       label: LABELS.key,   editable: false },
      { key: "label",     label: LABELS.label, editable: true },
      { key: "item_type", label: "Typ",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.itemTypes),
        badgeClass: (r) => ({ weapon:"admin-badge-red", armor:"admin-badge-blue", consumable:"admin-badge-green", quest:"admin-badge-gold", narrative:"admin-badge-muted", misc:"admin-badge-muted" }[r.item_type] ?? "admin-badge-muted"),
        filterOptions: Object.entries(LABELS.itemTypes).map(([v,l])=>({value:v,label:l})),
      },
      { key: "value_gp",  label: "Cena (gp)",  type: "number", editable: true },
      { key: "weight_kg", label: "Waga (kg)",  type: "number", editable: true },
      { key: "is_active", label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at", label: LABELS.locked,   type: "locked",  editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      selectable: true,
      showTextSearch: true, searchPlaceholder: "Szukaj przedmiotów…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/items/${row.key}`, { method: "PATCH", body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/admin/items/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openItemModal(row, load) }],
    });
  };
  await load();
}

function _openItemModal(row, onDone, forceNew = false) {
  const isEdit = !!row && !forceNew;
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span><input name="key" type="text" value="${_esc(row?.key??"")}" ${isEdit?"readonly":""} placeholder="np. iron_sword" autocomplete="off"/></label>
    <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" value="${_esc(row?.label??"")}" placeholder="np. Żelazny miecz" autocomplete="off"/></label>
    <label class="modal-field"><span>Typ przedmiotu *</span><select name="item_type">${Object.entries(LABELS.itemTypes).map(([v,l])=>`<option value="${v}"${(row?.item_type??"misc")===v?" selected":""}>${l}</option>`).join("")}</select></label>
    <label class="modal-field"><span>Cena (gp)</span><input name="value_gp" type="number" value="${row?.value_gp??0}" min="0"/></label>
    <label class="modal-field"><span>Waga (kg)</span><input name="weight_kg" type="number" value="${row?.weight_kg??0}" step="0.1" min="0"/></label>
    <label class="modal-field"><span>Bonus AC</span><input name="ac_bonus" type="number" value="${row?.ac_bonus??0}"/></label>
    <label class="modal-field"><span>Opis</span><textarea name="description" rows="3">${_esc(row?.description??"")}</textarea></label>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>${LABELS.isActive}</span></label>`;

  openModal({
    title: isEdit ? `Edytuj przedmiot: ${row.key}` : "Dodaj przedmiot",
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : LABELS.add,
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key) { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }
          const body = {
            key, label,
            item_type: g("item_type").value,
            value_gp: Number(g("value_gp").value),
            weight_kg: Number(g("weight_kg").value),
            ac_bonus: Number(g("ac_bonus").value),
            description: g("description").value.trim(),
            is_active: g("is_active").checked,
          };
          try {
            if (isEdit) {
              await adminFetch(`/api/admin/items/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/admin/items", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano przedmiot.", "success");
            c(); await onDone();
          } catch (e) { showToast((e.message || "Błąd"), "error"); }
        },
      },
    ],
  });
}

// ── Consumables ───────────────────────────────────────────────────────────────

async function _renderConsumables(container, panel) {
  const tableHost = document.createElement("div");
  container.appendChild(_toolbar("Dodaj materiał", () => _openConsumableModal(null, load)));
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try { rows = (await adminFetch("/api/admin/consumables")).items || []; }
    catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",           label: LABELS.key,   editable: false },
      { key: "label",         label: LABELS.label, editable: true },
      { key: "effect_type",   label: "Efekt",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.effectTypes),
        badgeClass: (r) => r.effect_type === "heal_hp" ? "admin-badge-green" : r.effect_type === "restore_mana" ? "admin-badge-blue" : "admin-badge-muted",
        filterOptions: Object.entries(LABELS.effectTypes).map(([v,l])=>({value:v,label:l})),
      },
      { key: "effect_dice",   label: "Kość",    editable: true },
      { key: "effect_bonus",  label: "Bonus",   type: "number", editable: true },
      { key: "effect_target", label: "Cel",     editable: true },
      { key: "charges",       label: "Ładunki", type: "number", editable: true },
      { key: "base_price",    label: "Cena",    type: "number", editable: true },
      { key: "is_active",     label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",     label: LABELS.locked,   type: "locked",  editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      selectable: true,
      showTextSearch: true, searchPlaceholder: "Szukaj materiałów…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/consumables/${row.key}`, { method: "PATCH", body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/admin/consumables/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openConsumableModal(row, load) }],
    });
  };
  await load();
}

function _openConsumableModal(row, onDone) {
  const isEdit = !!row;
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span><input name="key" type="text" value="${_esc(row?.key??"")}" ${isEdit?"readonly":""} placeholder="np. healing_potion" autocomplete="off"/></label>
    <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" value="${_esc(row?.label??"")}" placeholder="np. Eliksir leczenia" autocomplete="off"/></label>
    <label class="modal-field"><span>Efekt</span><select name="effect_type">${Object.entries(LABELS.effectTypes).map(([v,l])=>`<option value="${v}"${(row?.effect_type??"heal_hp")===v?" selected":""}>${l}</option>`).join("")}</select></label>
    <label class="modal-field"><span>Kość efektu</span><input name="effect_dice" type="text" value="${_esc(row?.effect_dice??"d4")}" placeholder="np. 2d4"/></label>
    <label class="modal-field"><span>Bonus efektu</span><input name="effect_bonus" type="number" value="${row?.effect_bonus??0}"/></label>
    <label class="modal-field"><span>Cel efektu</span><select name="effect_target">
      <option value="self" ${(row?.effect_target??"self")==="self"?"selected":""}>Self</option>
      <option value="ally" ${row?.effect_target==="ally"?"selected":""}>Ally</option>
      <option value="any"  ${row?.effect_target==="any"?"selected":""}>Any</option>
    </select></label>
    <label class="modal-field"><span>Ładunki</span><input name="charges" type="number" value="${row?.charges??1}" min="1"/></label>
    <label class="modal-field"><span>Cena bazowa</span><input name="base_price" type="number" value="${row?.base_price??10}" min="0"/></label>
    <label class="modal-field"><span>Waga (kg)</span><input name="weight_kg" type="number" value="${row?.weight_kg??0}" step="0.1" min="0"/></label>
    <label class="modal-field"><span>Opis</span><textarea name="description" rows="3">${_esc(row?.description??"")}</textarea></label>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>${LABELS.isActive}</span></label>`;

  openModal({
    title: isEdit ? `Edytuj: ${row.key}` : "Dodaj materiał eksploatacyjny",
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : LABELS.add,
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }
          const body = {
            key, label,
            effect_type: g("effect_type").value,
            effect_dice: g("effect_dice").value.trim(),
            effect_bonus: Number(g("effect_bonus").value),
            effect_target: g("effect_target").value,
            charges: Number(g("charges").value),
            base_price: Number(g("base_price").value),
            weight_kg: Number(g("weight_kg").value),
            description: g("description").value.trim(),
            is_active: g("is_active").checked,
          };
          try {
            if (isEdit) {
              await adminFetch(`/api/admin/consumables/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/admin/consumables", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano.", "success");
            c(); await onDone();
          } catch (e) { showToast((e.message || "Błąd"), "error"); }
        },
      },
    ],
  });
}

// ── Loot Tables ───────────────────────────────────────────────────────────────

async function _renderLootTables(container, panel) {
  container.innerHTML = `
    <div class="loot-tables-layout">
      <div class="loot-sidebar">
        <div class="tab-toolbar"><button class="primary-btn" id="add-table-btn">+ Dodaj tabelę</button></div>
        <div id="loot-table-list" class="loot-table-list"></div>
      </div>
      <div class="loot-editor" id="loot-editor">
        <p class="section-note">Wybierz tabelę po lewej lub utwórz nową.</p>
      </div>
    </div>`;

  let tables = [];
  let selectedKey = null;

  const loadTables = async () => {
    try { tables = (await adminFetch("/api/admin/loot-tables")).items || []; }
    catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }
    renderTableList();
    if (selectedKey) openEditor(selectedKey);
  };

  const renderTableList = () => {
    const list = container.querySelector("#loot-table-list");
    list.innerHTML = "";
    tables.forEach((t) => {
      const btn = document.createElement("button");
      btn.className = "loot-table-btn" + (t.key === selectedKey ? " active" : "");
      btn.textContent = t.label || t.key;
      btn.addEventListener("click", () => { selectedKey = t.key; openEditor(t.key); renderTableList(); });
      list.appendChild(btn);
    });
  };

  const openEditor = async (key) => {
    const editor = container.querySelector("#loot-editor");
    const table  = tables.find((t) => t.key === key);
    if (!table) { editor.innerHTML = `<p class="section-note">Nie znaleziono tabeli.</p>`; return; }

    let entries = [];
    let items = [], weapons = [], consumables = [];
    try {
      [entries, items, weapons, consumables] = await Promise.all([
        adminFetch(`/api/admin/loot-tables/${key}/entries`).then((r) => Array.isArray(r) ? r : (r.items ?? r.entries ?? [])).catch(() => []),
        adminFetch("/api/admin/items").then((r) => r.items || []).catch(() => []),
        adminFetch("/api/admin/weapons").then((r) => r.items || []).catch(() => []),
        adminFetch("/api/admin/consumables").then((r) => r.items || []).catch(() => []),
      ]);
    } catch {}

    const sourceOpts = [
      ...items.map((i) => `<option value="item:${i.key}">Przedmiot: ${_esc(i.label)}</option>`),
      ...weapons.map((w) => `<option value="weapon:${w.key}">Broń: ${_esc(w.label)}</option>`),
      ...consumables.map((c) => `<option value="consumable:${c.key}">Materiał: ${_esc(c.label)}</option>`),
    ].join("");

    editor.innerHTML = `
      <div class="loot-editor-header">
        <h3>${_esc(table.label || table.key)}</h3>
        <button class="danger-btn small-btn" id="del-table-btn">Usuń tabelę</button>
      </div>
      <div class="loot-meta-row">
        <label>Złoto min <input name="gold_min" type="number" value="${table.gold_min ?? 0}" min="0"/></label>
        <label>Złoto max <input name="gold_max" type="number" value="${table.gold_max ?? 0}" min="0"/></label>
        <button class="secondary-btn small-btn" id="save-meta-btn">Zapisz</button>
      </div>
      <table class="admin-table">
        <thead><tr><th>Źródło</th><th>Waga (%)</th><th>Min szt.</th><th>Max szt.</th><th></th></tr></thead>
        <tbody id="entries-tbody">
          ${entries.map((e) => `
            <tr data-id="${e.id}">
              <td>${_esc(e.source_type)}: ${_esc(e.source_key)}</td>
              <td>${e.weight ?? 0}</td>
              <td>${e.qty_min ?? 1}</td>
              <td>${e.qty_max ?? 1}</td>
              <td><button class="danger-btn small-btn del-entry-btn">Usuń</button></td>
            </tr>`).join("")}
        </tbody>
      </table>
      <div class="loot-add-entry">
        <select id="entry-source">${sourceOpts}</select>
        <label>Waga <input id="entry-weight" type="number" value="10" min="1"/></label>
        <label>Min <input id="entry-qty-min" type="number" value="1" min="1"/></label>
        <label>Max <input id="entry-qty-max" type="number" value="1" min="1"/></label>
        <button class="primary-btn small-btn" id="add-entry-btn">Dodaj</button>
      </div>`;

    editor.querySelector("#save-meta-btn").addEventListener("click", async () => {
      try {
        await adminFetch(`/api/admin/loot-tables/${key}`, {
          method: "PATCH",
          body: JSON.stringify({
            gold_min: Number(editor.querySelector('[name="gold_min"]').value),
            gold_max: Number(editor.querySelector('[name="gold_max"]').value),
          }),
        });
        showToast("Zapisano.", "success"); await loadTables();
      } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); }
    });

    editor.querySelector("#del-table-btn").addEventListener("click", async () => {
      const ok = await showConfirm(`Usunąć tabelę "${key}"?`, { dangerous: true });
      if (!ok) return;
      try {
        await adminFetch(`/api/admin/loot-tables/${key}`, { method: "DELETE" });
        showToast("Usunięto.", "success"); selectedKey = null; await loadTables();
        container.querySelector("#loot-editor").innerHTML = `<p class="section-note">Wybierz tabelę po lewej.</p>`;
      } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); }
    });

    editor.querySelectorAll(".del-entry-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.closest("tr").dataset.id;
        try {
          await adminFetch(`/api/admin/loot-tables/${key}/entries/${id}`, { method: "DELETE" });
          showToast("Usunięto wpis.", "success"); openEditor(key);
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); }
      });
    });

    editor.querySelector("#add-entry-btn").addEventListener("click", async () => {
      const srcVal   = editor.querySelector("#entry-source").value;
      const [srcType, srcKey] = srcVal.split(":");
      const weight   = Number(editor.querySelector("#entry-weight").value);
      const qty_min  = Number(editor.querySelector("#entry-qty-min").value);
      const qty_max  = Number(editor.querySelector("#entry-qty-max").value);
      if (!srcKey) { showToast("Wybierz źródło.", "error"); return; }
      try {
        await adminFetch(`/api/admin/loot-tables/${key}/entries`, {
          method: "POST",
          body: JSON.stringify({ source_type: srcType, source_key: srcKey, weight, qty_min, qty_max }),
        });
        showToast("Dodano wpis.", "success"); openEditor(key);
      } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); }
    });
  };

  container.querySelector("#add-table-btn").addEventListener("click", () => {
    const form = document.createElement("div");
    form.className = "modal-form";
    form.innerHTML = `
      <label class="modal-field"><span>Klucz *</span><input name="key" type="text" placeholder="np. goblin_loot" autocomplete="off"/></label>
      <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" placeholder="np. Łupy goblinów" autocomplete="off"/></label>
      <label class="modal-field"><span>Opis</span><textarea name="description" rows="3"></textarea></label>`;
    openModal({
      title: "Nowa tabela łupów",
      content: form,
      footer: [
        { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
        {
          label: LABELS.add,
          class: "primary-btn",
          onClick: async (c) => {
            const key = form.querySelector('[name="key"]').value.trim();
            const label = form.querySelector('[name="label"]').value.trim();
            if (!key || !label) { showToast("Klucz i nazwa są wymagane.", "error"); return; }
            try {
              await adminFetch("/api/admin/loot-tables", { method: "POST", body: JSON.stringify({ key, label, description: form.querySelector('[name="description"]').value.trim() }) });
              showToast("Dodano tabelę.", "success"); selectedKey = key; c(); await loadTables();
            } catch (e) { showToast((e.message || "Błąd"), "error"); }
          },
        },
      ],
    });
  });

  await loadTables();
}

// ── AI Assistant ──────────────────────────────────────────────────────────────

async function _handleGenerate(panel) {
  const promptEl = panel.querySelector("#ai-prompt");
  const genBtn   = panel.querySelector("#ai-generate-btn");
  const msg = promptEl.value.trim();
  if (!msg) { showToast("Wpisz opis co wygenerować.", "info"); return; }

  _aiResource = panel.querySelector("#ai-resource-select").value;

  genBtn.disabled = true;
  genBtn.textContent = "Generuję…";

  try {
    const result = await adminFetch("/api/admin/assistant/draft", {
      method: "POST",
      body: JSON.stringify({ resource: _aiResource, message: msg, history: _aiHistory }),
    });

    _aiHistory.push({ role: "user",      content: msg });
    _aiHistory.push({ role: "assistant", content: result.assistant_reply || "" });
    _aiDraft = result;
    promptEl.value = "";
    _renderAiHistory(panel);
    _renderAiDraft(panel);
  } catch (e) {
    showToast("Asystent błąd: " + (e.message || "?"), "error");
  } finally {
    genBtn.disabled = false;
    genBtn.textContent = LABELS.generate;
  }
}

function _renderAiHistory(panel) {
  const histEl = panel.querySelector("#ai-history");
  if (!histEl) return;
  histEl.innerHTML = _aiHistory.map((m) => `
    <div class="ai-msg ai-msg-${m.role}">
      <div class="ai-msg-role">${m.role === "user" ? "Ty" : "Asystent"}</div>
      <div class="ai-msg-text">${_esc(m.content)}</div>
    </div>`).join("");
  histEl.scrollTop = histEl.scrollHeight;
}

function _renderAiDraft(panel) {
  const draftEl = panel.querySelector("#ai-draft-wrap");
  if (!draftEl) return;
  if (!_aiDraft) { draftEl.style.display = "none"; return; }
  draftEl.style.display = "";

  const d = _aiDraft;
  const errHtml = (d.errors?.length)
    ? `<div class="ai-draft-errors">${d.errors.map((e) => `<div>⚠ ${_esc(e)}</div>`).join("")}</div>`
    : "";

  draftEl.innerHTML = `
    <div class="ai-draft">
      <div class="ai-draft-title">Szkic — ${_esc(d.resource)}</div>
      ${errHtml}
      <pre class="ai-draft-json">${_esc(JSON.stringify(d.draft || d.validated_payload, null, 2))}</pre>
      <button class="primary-btn" id="ai-save-btn" ${d.valid ? "" : "disabled"}>
        ${LABELS.saveDraft} ${d.valid ? "" : "(błędy walidacji)"}
      </button>
    </div>`;

  draftEl.querySelector("#ai-save-btn")?.addEventListener("click", async () => {
    try {
      await adminFetch("/api/admin/assistant/save", {
        method: "POST",
        body: JSON.stringify({ resource: d.resource, payload: d.validated_payload }),
      });
      showToast("Zapisano szkic do katalogu.", "success");
      _aiDraft = null;
      _renderAiDraft(panel);
      const tabMap = { weapons: "weapons", enemies: "enemies", items: "items", consumables: "consumables", "loot-tables": "loot-tables" };
      const tab = tabMap[d.resource];
      if (tab) _reloadTab(panel, tab);
    } catch (e) {
      showToast("Błąd zapisu: " + (e.message || "?"), "error");
    }
  });
}
