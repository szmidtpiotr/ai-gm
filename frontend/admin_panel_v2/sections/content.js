import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable, showConfirm } from "/admin_panel_v2/shared/table.js?v=5";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";
import { openSmartEntry } from "/admin_panel_v2/shared/smart_entry.js?v=5";

const LABELS = {
  weapons:      "Broń",
  armor:        "Zbroja",
  spells:       "Zaklęcia",
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

const TABS = ["weapons", "armor", "spells", "items", "consumables", "loot-tables"];

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
          <button class="subtab-btn" data-tab="spells">${LABELS.spells}</button>
          <button class="subtab-btn" data-tab="items">${LABELS.items}</button>
          <button class="subtab-btn" data-tab="consumables">${LABELS.consumables}</button>
          <button class="subtab-btn" data-tab="loot-tables">${LABELS.lootTables}</button>
          <button class="subtab-btn" id="smart-entry-btn" title="AI asystent tworzenia treści" style="margin-left:auto">🤖 Kreator AI</button>
        </div>
        <div class="subtab-panels">
          ${["weapons","armor","spells","items","consumables","loot-tables"].map(
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
  const TABLE_MAP = { weapons: "game_config_weapons", armor: "game_config_items", spells: "game_config_spells", items: "game_config_items", consumables: "game_config_consumables", "loot-tables": null };
  const _getActiveTable = () => TABLE_MAP[panel.querySelector(".subtab-btn.active:not(#smart-entry-btn)")?.dataset?.tab] || null;

  panel.querySelector("#ai-fab-btn").addEventListener("click", () => openSmartEntry(_getActiveTable()));
  panel.querySelector("#smart-entry-btn").addEventListener("click", () => openSmartEntry(_getActiveTable()));

  // ── Auto-refresh table after Smart Entry save ──
  const _onSmartSave = (e) => {
    const table = e.detail?.table;
    const tabMap = { game_config_weapons: "weapons", game_config_items: "items", game_config_consumables: "consumables", game_config_spells: "spells" };
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
    case "spells":      await _renderSpells(container, panel); break;
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
      [rows, stats] = await Promise.all([
        adminFetch("/api/admin/weapons").then((r) => (r.items || []).filter(w => w.weapon_type !== "spell")),
        _fetchStats(),
      ]);
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
      { key: "range_m",       label: "Zasięg (m)",      type: "number",  editable: true },
      { key: "targeting",     label: "Cel",             editable: true },
      { key: "aoe",           label: "AoE",             editable: true },
      { key: "value_gp",      label: "Cena (gp)",       type: "number",  editable: true },
      { key: "weight_kg",     label: "Waga (kg)",       type: "number",  editable: true },
      { key: "source_exclusive", label: "Źródło", editable: true, type: "select-dropdown",
        editOptions: [{value:"",label:"— wszędzie —"},{value:"dungeon",label:"Dungeon"},{value:"boss",label:"Boss"}],
        formatDisplay: (r) => r.source_exclusive ? `🔒 ${r.source_exclusive}` : "—" },
      { key: "description",   label: "Opis",            editable: true, popup: true },
      { key: "note",          label: "Notatka",         editable: true, popup: true },
      { key: "effect_json",   label: "Efekty bojowe",   editable: true, popup: true },
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
    <label class="modal-field"><span>Opis (dla GM)</span><textarea name="description" rows="3">${_esc(row?.description??"")}</textarea></label>
    <label class="modal-field"><span>Notatka / zdolności specjalne</span><textarea name="note" rows="2">${_esc(row?.note??"")}</textarea></label>
    <label class="modal-field"><span>Efekty bojowe (effect_json)</span>
      <textarea name="effect_json" rows="4" placeholder='np. {"effects":[{"type":"extra_damage","dice":"1d6","damage_type":"fire"}]}'>${_esc(row?.effect_json??"")}</textarea>
      <span style="font-size:0.72rem;color:var(--text-muted)">Typy: extra_damage, on_hit_save. Zostaw puste jeśli brak efektów.</span>
    </label>
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
            note: g("note").value.trim(),
            effect_json: g("effect_json").value.trim() || null,
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
      { key: "xp_award",      label: "XP",            type: "number",  editable: true },
      { key: "loot_table_key", label: "Łupy",                           editable: false, formatDisplay: (r) => r.loot_table_key || "—" },
      { key: "drop_chance",  label: "Szansa",        type: "number",  editable: false, formatDisplay: (r) => r.loot_table_key ? `${Math.round((r.drop_chance??1)*100)}%` : "—" },
      { key: "is_active",    label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",    label: LABELS.locked,   type: "locked",  editable: false },
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

async function _openEnemyModal(row, onDone) {
  const isEdit = !!row;
  let lootTables = [];
  try { lootTables = (await adminFetch("/api/admin/loot-tables")).items || []; } catch {}

  const lootTableOpts = `<option value="">— brak —</option>` +
    lootTables.map((t) => `<option value="${t.key}"${row?.loot_table_key === t.key ? " selected" : ""}>${_esc(t.label || t.key)}</option>`).join("");

  const dropChancePct = Math.round((row?.drop_chance ?? 1.0) * 100);

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
    <div class="modal-field-divider"></div>
    <label class="modal-field"><span>Tabela łupów</span><select name="loot_table_key">${lootTableOpts}</select></label>
    <label class="modal-field"><span>Szansa na łup (%)</span><input name="drop_chance_pct" type="number" value="${dropChancePct}" min="0" max="100" title="0 = nigdy, 100 = zawsze"/></label>
    <div class="modal-field-divider"></div>
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
          const lootKey = g("loot_table_key").value.trim() || null;
          const dropPct = Number(g("drop_chance_pct").value);
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
            loot_table_key: lootKey,
            drop_chance: Math.min(1, Math.max(0, dropPct / 100)),
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

// ── Spells (game_config_spells) ───────────────────────────────────────────────

async function _renderSpells(container, panel) {
  const tableHost = document.createElement("div");
  container.appendChild(_toolbar("Dodaj zaklęcie", () => _openSpellModal(null, load)));
  container.appendChild(tableHost);

  const SPELL_TYPES = { attack: "Atak", heal: "Leczenie", defense: "Obrona", effect: "Efekt", attack_aoe: "Atak AoE" };
  const TIER_LABELS = { 1: "T1", 2: "T2", 3: "T3", 4: "T4", 5: "T5" };

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows = [];
    try { rows = (await adminFetch("/api/admin/spells")).items || []; }
    catch (e) { showToast("Błąd ładowania zaklęć: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",           label: LABELS.key,       editable: false },
      { key: "label",         label: LABELS.label,     editable: true },
      { key: "tier",          label: "Tier",           type: "number", editable: true },
      { key: "mana_cost",     label: "Mana",           type: "number", editable: true },
      { key: "spell_type",    label: "Typ",
        type: "badge", editType: "select",
        editOptions: Object.keys(SPELL_TYPES),
        badgeClass: (r) => r.spell_type === "attack" ? "admin-badge-red" : r.spell_type === "heal" ? "admin-badge-green" : r.spell_type === "attack_aoe" ? "admin-badge-red" : "admin-badge-blue",
        formatDisplay: (r) => SPELL_TYPES[r.spell_type] || r.spell_type,
      },
      { key: "damage_die",    label: "Kość dmg",       editable: true },
      { key: "heal_die",      label: "Kość leczenia",  editable: true },
      { key: "effect_stat",   label: "Stat efektu",    editable: true },
      { key: "effect_type",   label: "Efekt",          editable: true },
      { key: "target_zone",   label: "Zasięg",         editable: true },
      { key: "aoe",           label: "AoE",            type: "boolean", editable: true },
      { key: "description",   label: "Opis",           editable: true, popup: true },
      { key: "rank2_json",    label: "Ranga 2 (JSON)", editable: true, popup: true },
      { key: "rank3_json",    label: "Ranga 3 (JSON)", editable: true, popup: true },
      { key: "is_active",     label: LABELS.isActive,  type: "boolean", editable: true },
    ];

    renderTable(tableHost, cols, rows, {
      tableId: "spells",
      selectable: true,
      showTextSearch: true,
      searchPlaceholder: "Szukaj zaklęć…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/spells/${row.key}`, {
            method: "PATCH", body: JSON.stringify({ [colKey]: newVal }),
          });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row) {
        try {
          await adminFetch(`/api/admin/spells/${row.key}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openSpellModal(row, load) }],
    });
  };
  await load();
}

function _openSpellModal(row, onDone) {
  const isEdit = !!row;
  const SPELL_TYPE_OPTS = ["attack","heal","defense","effect","attack_aoe"];
  const ZONE_OPTS = ["any","self","engaged","ranged"];

  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span><input name="key" type="text" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. magic_bolt" autocomplete="off"/></label>
    <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" value="${_esc(row?.label ?? "")}" placeholder="Błysk Magiczny" autocomplete="off"/></label>
    <label class="modal-field"><span>Tier (1–5) *</span><input name="tier" type="number" value="${row?.tier ?? 1}" min="1" max="5"/></label>
    <label class="modal-field"><span>Koszt many *</span><input name="mana_cost" type="number" value="${row?.mana_cost ?? 2}" min="1" max="10"/></label>
    <label class="modal-field"><span>Typ</span>
      <select name="spell_type">${SPELL_TYPE_OPTS.map(t => `<option value="${t}" ${row?.spell_type===t?"selected":""}>${t}</option>`).join("")}</select>
    </label>
    <label class="modal-field"><span>Kość obrażeń</span><input name="damage_die" type="text" value="${_esc(row?.damage_die ?? "")}" placeholder="np. 2d6"/></label>
    <label class="modal-field"><span>Kość leczenia</span><input name="heal_die" type="text" value="${_esc(row?.heal_die ?? "")}" placeholder="np. 2d6"/></label>
    <label class="modal-field"><span>Stat efektu (WIS/CON…)</span><input name="effect_stat" type="text" value="${_esc(row?.effect_stat ?? "")}" placeholder="WIS"/></label>
    <label class="modal-field"><span>Typ efektu (stun/sleep…)</span><input name="effect_type" type="text" value="${_esc(row?.effect_type ?? "")}" placeholder="sleeping"/></label>
    <label class="modal-field"><span>Czas trwania (rundy)</span><input name="effect_duration" type="number" value="${row?.effect_duration ?? 1}" min="1"/></label>
    <label class="modal-field"><span>Zasięg</span>
      <select name="target_zone">${ZONE_OPTS.map(z => `<option value="${z}" ${(row?.target_zone??'any')===z?"selected":""}>${z}</option>`).join("")}</select>
    </label>
    <label class="modal-checkbox-row"><input name="aoe" type="checkbox" ${row?.aoe?"checked":""}><span>AoE (trafia wszystkich wrogów)</span></label>
    <label class="modal-field"><span>Opis</span><textarea name="description" rows="2">${_esc(row?.description ?? "")}</textarea></label>
    <label class="modal-field"><span>Ranga 2 (JSON)</span><textarea name="rank2_json" rows="2" placeholder='{"mana_cost":2,"damage_die":"2d8"}'>${_esc(row?.rank2_json ?? "")}</textarea></label>
    <label class="modal-field"><span>Ranga 3 (JSON)</span><textarea name="rank3_json" rows="2" placeholder='{"mana_cost":1,"damage_die":"3d6"}'>${_esc(row?.rank3_json ?? "")}</textarea></label>`;

  openModal({
    title: isEdit ? `Edytuj zaklęcie: ${row.key}` : "Dodaj zaklęcie",
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      { label: isEdit ? LABELS.save : LABELS.add, class: "primary-btn", onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key || !label) { showToast("Klucz i nazwa są wymagane.", "error"); return; }
          const body = {
            key, label,
            tier: parseInt(g("tier").value) || 1,
            mana_cost: parseInt(g("mana_cost").value) || 2,
            spell_type: g("spell_type").value,
            damage_die: g("damage_die").value.trim() || null,
            heal_die: g("heal_die").value.trim() || null,
            effect_stat: g("effect_stat").value.trim() || null,
            effect_type: g("effect_type").value.trim() || null,
            effect_duration: parseInt(g("effect_duration").value) || 1,
            target_zone: g("target_zone").value,
            aoe: g("aoe").checked ? 1 : 0,
            description: g("description").value.trim(),
            rank2_json: g("rank2_json").value.trim() || null,
            rank3_json: g("rank3_json").value.trim() || null,
          };
          try {
            if (isEdit) await adminFetch(`/api/admin/spells/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            else        await adminFetch("/api/admin/spells",             { method: "POST",  body: JSON.stringify(body) });
            showToast(isEdit ? "Zapisano." : "Dodano zaklęcie.", "success");
            c(); await onDone();
          } catch (e) { showToast((e.message || "Błąd zapisu"), "error"); }
        }},
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
      { key: "value_gp",    label: "Cena (gp)",  type: "number", editable: true },
      { key: "weight_kg",   label: "Waga (kg)",  type: "number", editable: true },
      { key: "description", label: "Opis",        editable: true, popup: true },
      { key: "effect_json", label: "Efekt",       editable: true, popup: true,
        formatDisplay: (r) => r.effect_json ? "✓" : "—" },
      { key: "source_exclusive", label: "Źródło", editable: true, type: "select-dropdown",
        editOptions: [{value:"",label:"— wszędzie —"},{value:"dungeon",label:"Dungeon"},{value:"boss",label:"Boss"}],
        formatDisplay: (r) => r.source_exclusive ? `🔒 ${r.source_exclusive}` : "—" },
      { key: "is_active",   label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",   label: LABELS.locked,   type: "locked",  editable: false },
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
    <label class="modal-field"><span>Efekt (effect_json)</span><textarea name="effect_json" rows="3" placeholder='{"effects":[{"type":"heal_hp","value":"2d6"}]}'>${_esc(row?.effect_json??"")}</textarea></label>
    <label class="modal-field"><span>Źródło dropu</span><select name="source_exclusive"><option value="">— wszędzie —</option><option value="dungeon" ${row?.source_exclusive==="dungeon"?"selected":""}>Dungeon only</option><option value="boss" ${row?.source_exclusive==="boss"?"selected":""}>Boss only</option></select></label>
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
            effect_json: g("effect_json").value.trim() || null,
            source_exclusive: g("source_exclusive").value || null,
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
        <div class="loot-search-wrap">
          <input type="search" id="loot-table-search" class="loot-search-input" placeholder="Szukaj tabeli…" autocomplete="off" />
        </div>
        <div id="loot-table-list" class="loot-table-list"></div>
      </div>
      <div class="loot-editor" id="loot-editor">
        <p class="section-note">Wybierz tabelę po lewej lub utwórz nową.</p>
      </div>
    </div>`;

  let tables = [];
  let selectedKey = null;
  let searchQuery = "";

  const loadTables = async () => {
    try { tables = (await adminFetch("/api/admin/loot-tables")).items || []; }
    catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }
    renderTableList();
    if (selectedKey) openEditor(selectedKey);
  };

  const renderTableList = () => {
    const list = container.querySelector("#loot-table-list");
    list.innerHTML = "";
    const q = searchQuery.trim().toLowerCase();
    const filtered = q
      ? tables.filter((t) => (t.label || "").toLowerCase().includes(q) || (t.key || "").toLowerCase().includes(q))
      : tables;
    if (filtered.length === 0) {
      const empty = document.createElement("div");
      empty.className = "loot-table-empty";
      empty.textContent = q ? "Brak dopasowań." : "Brak tabel.";
      list.appendChild(empty);
      return;
    }
    filtered.forEach((t) => {
      const btn = document.createElement("button");
      btn.className = "loot-table-btn" + (t.key === selectedKey ? " active" : "");
      btn.textContent = t.label || t.key;
      btn.addEventListener("click", () => { selectedKey = t.key; openEditor(t.key); renderTableList(); });
      list.appendChild(btn);
    });
  };

  const searchInput = container.querySelector("#loot-table-search");
  searchInput?.addEventListener("input", (e) => {
    searchQuery = e.target.value || "";
    renderTableList();
  });

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

    const buildEntryRow = (e) => {
      const typeLabel = e.source_type === "item" ? "Przedmiot" : e.source_type === "consumable" ? "Materiał" : "Broń";
      const name = e.source_label || e.source_key || e.item_key || e.consumable_key || e.weapon_key || "?";
      const tr = document.createElement("tr");
      tr.dataset.id = e.id;
      tr.dataset.sourceType = e.source_type;
      tr.dataset.sourceKey = e.source_key || e.item_key || e.consumable_key || e.weapon_key || "";
      tr.innerHTML = `
        <td><span class="loot-type-badge loot-type-${e.source_type}">${typeLabel}</span> ${_esc(name)}</td>
        <td class="loot-inline-cell" data-field="weight" data-val="${e.weight ?? 10}">${e.weight ?? 10}%</td>
        <td class="loot-inline-cell" data-field="qty_min" data-val="${e.qty_min ?? 1}">${e.qty_min ?? 1}</td>
        <td class="loot-inline-cell" data-field="qty_max" data-val="${e.qty_max ?? 1}">${e.qty_max ?? 1}</td>
        <td><button class="danger-btn small-btn del-entry-btn">Usuń</button></td>`;
      return tr;
    };

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
      <div class="loot-entries-search-row">
        <input type="text" id="entries-search" class="field-input" placeholder="Szukaj wpisu…" style="flex:1;font-size:0.78rem;padding:4px 8px"/>
        <span id="entries-count" class="section-note" style="white-space:nowrap;font-size:0.75rem;padding:4px 0"></span>
      </div>
      <div class="loot-entries-scroll">
      <table class="admin-table">
        <thead><tr><th>Źródło</th><th title="Kliknij aby edytować">Waga % ✎</th><th title="Kliknij aby edytować">Min ✎</th><th title="Kliknij aby edytować">Max ✎</th><th></th></tr></thead>
        <tbody id="entries-tbody"></tbody>
      </table>
      </div>
      <div class="loot-add-entry">
        <select id="entry-source">${sourceOpts}</select>
        <label>Waga <input id="entry-weight" type="number" value="10" min="1" max="100"/></label>
        <label>Min <input id="entry-qty-min" type="number" value="1" min="1"/></label>
        <label>Max <input id="entry-qty-max" type="number" value="1" min="1"/></label>
        <button class="primary-btn small-btn" id="add-entry-btn">+ Dodaj</button>
      </div>`;

    const tbody = editor.querySelector("#entries-tbody");
    entries.forEach((e) => tbody.appendChild(buildEntryRow(e)));

    // Search/filter entries
    const searchEl = editor.querySelector("#entries-search");
    const countEl  = editor.querySelector("#entries-count");
    const updateCount = () => {
      const vis = tbody.querySelectorAll("tr:not([hidden])").length;
      countEl.textContent = `${vis} / ${tbody.querySelectorAll("tr").length} wpisów`;
    };
    updateCount();
    searchEl?.addEventListener("input", () => {
      const q = searchEl.value.trim().toLowerCase();
      tbody.querySelectorAll("tr").forEach(tr => {
        tr.hidden = q && !tr.textContent.toLowerCase().includes(q);
      });
      updateCount();
    });

    // Inline cell editing
    const saveEntry = async (tr, field, newVal) => {
      const srcType  = tr.dataset.sourceType;
      const srcKey   = tr.dataset.sourceKey;
      const cells    = tr.querySelectorAll(".loot-inline-cell");
      const getVal   = (f) => Number(tr.querySelector(`[data-field="${f}"]`).dataset.val);
      const weight   = field === "weight"  ? Number(newVal) : getVal("weight");
      const qty_min  = field === "qty_min" ? Number(newVal) : getVal("qty_min");
      const qty_max  = field === "qty_max" ? Number(newVal) : getVal("qty_max");
      await adminFetch(`/api/admin/loot-tables/${key}/entries`, {
        method: "POST",
        body: JSON.stringify({ source_type: srcType, source_key: srcKey, weight, qty_min, qty_max }),
      });
    };

    tbody.addEventListener("click", (evt) => {
      const cell = evt.target.closest(".loot-inline-cell");
      if (!cell || cell.querySelector("input")) return;
      const field   = cell.dataset.field;
      const origVal = cell.dataset.val;
      const suffix  = field === "weight" ? "%" : "";
      cell.innerHTML = `<input class="loot-inline-input" type="number" value="${origVal}" min="1"${field === "weight" ? ' max="100"' : ""}/>`;
      const input = cell.querySelector("input");
      input.focus(); input.select();
      const commit = async () => {
        const v = input.value.trim();
        if (v === "" || isNaN(Number(v))) { cell.textContent = origVal + suffix; cell.dataset.val = origVal; return; }
        const tr = cell.closest("tr");
        try {
          await saveEntry(tr, field, v);
          cell.dataset.val = v;
          cell.textContent = v + suffix;
        } catch (e) {
          showToast("Błąd: " + (e.message || "?"), "error");
          cell.textContent = origVal + suffix;
          cell.dataset.val = origVal;
        }
      };
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); input.blur(); }
        if (e.key === "Escape") { cell.textContent = origVal + suffix; cell.dataset.val = origVal; }
      });
      input.addEventListener("blur", commit);
    });

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
        await adminFetch(`/api/admin/loot-tables/${key}`, { method: "DELETE", body: JSON.stringify({force: false}) });
        showToast("Usunięto.", "success"); selectedKey = null; await loadTables();
        container.querySelector("#loot-editor").innerHTML = `<p class="section-note">Wybierz tabelę po lewej.</p>`;
      } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); }
    });

    tbody.addEventListener("click", async (evt) => {
      const btn = evt.target.closest(".del-entry-btn");
      if (!btn) return;
      const id = btn.closest("tr").dataset.id;
      try {
        await adminFetch(`/api/admin/loot-tables/${key}/entries/by-id/${id}`, { method: "DELETE" });
        btn.closest("tr").remove();
        showToast("Usunięto wpis.", "success");
      } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); }
    });

    editor.querySelector("#add-entry-btn").addEventListener("click", async () => {
      const srcVal   = editor.querySelector("#entry-source").value;
      const [srcType, srcKey] = srcVal.split(":");
      const weight   = Number(editor.querySelector("#entry-weight").value);
      const qty_min  = Number(editor.querySelector("#entry-qty-min").value);
      const qty_max  = Number(editor.querySelector("#entry-qty-max").value);
      if (!srcKey) { showToast("Wybierz źródło.", "error"); return; }
      try {
        const res = await adminFetch(`/api/admin/loot-tables/${key}/entries`, {
          method: "POST",
          body: JSON.stringify({ source_type: srcType, source_key: srcKey, weight, qty_min, qty_max }),
        });
        const newEntry = res.item;
        if (newEntry) {
          // replace existing row if present (upsert updated it)
          const existing = tbody.querySelector(`tr[data-source-key="${newEntry.source_key}"]`);
          if (existing) existing.remove();
          tbody.appendChild(buildEntryRow(newEntry));
        } else {
          openEditor(key);
        }
        showToast("Dodano wpis.", "success");
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
