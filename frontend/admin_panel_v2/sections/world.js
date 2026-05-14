import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable, showConfirm } from "/admin_panel_v2/shared/table.js?v=5";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";
import { openSmartEntry } from "/admin_panel_v2/shared/smart_entry.js?v=5";

const LABELS = {
  locations:    "Lokacje",
  npcs:         "Postacie NPC",
  enemies:      "Wrogowie",
  key:          "Klucz",
  label:        "Nazwa",
  type:         "Typ",
  parentKey:    "Lokacja nadrzędna",
  description:  "Opis",
  isActive:     "Aktywny",
  isShop:       "Sklep",
  personality:  "Osobowość (JSON)",
  shopInv:      "Ekwipunek sklepu (JSON)",
  locationKeys: "Klucze lokacji (przecinki)",
  addLocation:  "Dodaj lokację",
  addNpc:       "Dodaj NPC",
  addEnemy:     "Dodaj wroga",
  npcType:      "Typ NPC",
  save:         "Zapisz",
  cancel:       "Anuluj",
  locked:       "Blokada",
  tiers: { weak: "Słaby", standard: "Standardowy", elite: "Elita", boss: "Boss" },
  damageTypes: { physical: "Fizyczne", fire: "Ogień", cold: "Zimno", poison: "Trucizna", magic: "Magia" },
};

const NPC_TYPES = [
  { value: "neutral",     label: "Neutralny" },
  { value: "merchant",    label: "Kupiec" },
  { value: "quest_giver", label: "Dawca zadań" },
  { value: "ally",        label: "Sojusznik" },
];

const LOC_TYPES = [
  { value: "macro", label: "Makro" },
  { value: "sub",   label: "Pod-lokacja" },
];

const LOCATION_RULES = [
  { key: "no_combat",        label: "No Combat",        type: "boolean", description: "Combat forbidden (temples, safe zones)" },
  { key: "no_loot",          label: "No Loot",          type: "boolean", description: "Enemies don't drop loot" },
  { key: "teleport_blocked", label: "Teleport Blocked", type: "boolean", description: "Teleportation spells don't work" },
  { key: "stealth_check",    label: "Stealth Check",    type: "boolean", description: "Entry requires successful stealth roll" },
  { key: "rest_bonus",       label: "Rest Bonus",       type: "number",  default: 2,         description: "HP regen multiplier (2 = 2× HP)" },
  { key: "mana_regen",       label: "Mana Regen",       type: "number",  default: 0,         description: "Natural mana regen (0 = none)" },
  { key: "required_item",    label: "Required Item",    type: "text",    default: "torch",   description: "Item key required to enter" },
  { key: "reason",           label: "Reason",           type: "text",    default: "Sacred ground", description: "Reason shown to player" },
];

const TABS = ["locations", "npcs", "enemies", "dungeons", "rules", "pending", "builder"];
const _rendered = new Set();
let _aiTrigger = null;  // updated by each tab render; called by the bubble

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content">
      <div class="subtab-bar">
        <button class="subtab-btn active" data-tab="locations">${LABELS.locations}</button>
        <button class="subtab-btn" data-tab="npcs">${LABELS.npcs}</button>
        <button class="subtab-btn" data-tab="enemies">${LABELS.enemies}</button>
        <button class="subtab-btn" data-tab="dungeons">⚔️ Lochy</button>
        <button class="subtab-btn" data-tab="rules">📋 Reguły</button>
        <button class="subtab-btn" data-tab="pending">⏳ Oczekujące <span id="pending-nav-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
        <button class="subtab-btn" data-tab="builder">🗺 Mapa Świata</button>
      </div>
      <div class="subtab-panels">
        ${TABS.map((t) => `<div class="subtab-panel${t === "locations" ? " active" : ""}" data-tab="${t}"></div>`).join("")}
      </div>
    </div>`;

  _rendered.clear();
  _aiTrigger = null;

  // Floating AI bubble
  const aiBubble = document.createElement("button");
  aiBubble.className = "ai-bubble-btn";
  aiBubble.title = "Generuj z AI";
  aiBubble.textContent = "✨";
  aiBubble.addEventListener("click", () => { if (_aiTrigger) _aiTrigger(); });
  panel.appendChild(aiBubble);

  panel.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      panel.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
      panel.querySelectorAll(".subtab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      panel.querySelector(`.subtab-panel[data-tab="${tab}"]`).classList.add("active");
      _aiTrigger = null;
      const bubble = panel.querySelector(".ai-bubble-btn");
      if (bubble) bubble.style.display = (tab === "rules" || tab === "pending" || tab === "builder") ? "none" : "";
      _activateTab(panel, tab);
    });
  });

  await _activateTab(panel, "locations");
}

async function _activateTab(panel, tab) {
  if (_rendered.has(tab)) return;
  _rendered.add(tab);
  const container = panel.querySelector(`.subtab-panel[data-tab="${tab}"]`);
  if (!container) return;
  // Hide AI bubble on Rules tab (it has its own AI UI)
  const bubble = panel.querySelector(".ai-bubble-btn");
  if (bubble) bubble.style.display = tab === "rules" ? "none" : "";
  if      (tab === "locations") await _renderLocations(container);
  else if (tab === "npcs")      await _renderNpcs(container);
  else if (tab === "enemies")   await _renderEnemies(container);
  else if (tab === "dungeons")  await _renderDungeons(container);
  else if (tab === "rules")     await _renderRules(container);
  else if (tab === "pending")   await _renderPendingReview(container, panel);
  else if (tab === "builder") {
    const { init: initBuilder } = await import("/admin_panel_v2/sections/world_builder.js?v=2");
    await initBuilder(container);
  }
}

// ── AI generation helper ──────────────────────────────────────────────────────

async function _openAiGenerateModal({ entityType, title, onFill }) {
  const { openModal } = await import("/admin_panel_v2/shared/modal.js?v=1");
  const { showToast } = await import("/admin_panel_v2/shared/toast.js?v=1");

  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="modal-form">
      <label class="modal-field">
        <span>Brief</span>
        <textarea name="brief" rows="4" placeholder="Opisz krótko postać/miejsce/wroga…" style="width:100%"></textarea>
      </label>
      <div id="ai-gen-result" style="display:none;margin-top:10px">
        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:6px">Podgląd (edytowalny po wstawieniu)</div>
        <pre id="ai-gen-json" style="font-size:0.75rem;background:var(--bg-elevated);padding:10px;border-radius:6px;overflow:auto;max-height:200px;white-space:pre-wrap"></pre>
      </div>
    </div>`;

  let generated = null;

  openModal({
    title,
    content: wrap,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (c) => c() },
      {
        label: "Generuj AI",
        class: "secondary-btn",
        onClick: async (_c, btn) => {
          const brief = wrap.querySelector('[name="brief"]').value.trim();
          if (brief.length < 3) { showToast("Podaj brief.", "info"); return; }
          btn.disabled = true; btn.textContent = "Generuję…";
          try {
            const data = await (await import("/admin_panel_v2/shared/api.js?v=3")).adminFetch(
              "/api/admin/campaign-designer/generate-entity",
              { method: "POST", body: JSON.stringify({ entity_type: entityType, brief }) }
            );
            generated = data.entity;
            wrap.querySelector("#ai-gen-result").style.display = "block";
            wrap.querySelector("#ai-gen-json").textContent = JSON.stringify(generated, null, 2);
            btn.textContent = "Generuj ponownie";
          } catch (e) {
            showToast(e.message || "Błąd generowania.", "error");
          } finally {
            btn.disabled = false;
          }
        },
      },
      {
        label: "Wstaw do formularza",
        class: "primary-btn",
        onClick: (c) => {
          if (!generated) { showToast("Najpierw wygeneruj.", "info"); return; }
          c();
          onFill(generated);
        },
      },
    ],
  });
}

// ── Location rules editor ─────────────────────────────────────────────────────

function _buildRulesEditor(currentRules) {
  const wrap = document.createElement("div");
  wrap.className = "rules-editor";

  // Predefined rules
  const presetSection = document.createElement("div");
  presetSection.className = "rules-preset-section";
  const checkboxes = [];
  const valueInputs = {};

  LOCATION_RULES.forEach(rule => {
    const isChecked = rule.key in currentRules;
    const row = document.createElement("div");
    row.className = "rule-row";

    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.name = `rule_${rule.key}`; cb.checked = isChecked;
    checkboxes.push({ rule, cb });

    const label = document.createElement("label");
    label.className = "rule-row-label";
    label.appendChild(cb);
    label.innerHTML += ` <strong>${rule.label}</strong> <span class="rule-desc">${rule.description}</span>`;
    row.appendChild(label);

    if (rule.type !== "boolean") {
      const inp = document.createElement("input");
      inp.type = rule.type === "number" ? "number" : "text";
      inp.className = "field-input rule-value-input";
      inp.placeholder = String(rule.default ?? "");
      inp.value = isChecked ? String(currentRules[rule.key] ?? rule.default ?? "") : "";
      inp.style.display = isChecked ? "block" : "none";
      inp.style.marginTop = "4px";
      inp.dataset.ruleKey = rule.key;
      valueInputs[rule.key] = inp;
      cb.addEventListener("change", () => { inp.style.display = cb.checked ? "block" : "none"; });
      row.appendChild(inp);
    }

    presetSection.appendChild(row);
  });
  wrap.appendChild(presetSection);

  // Custom rules
  const customSection = document.createElement("div");
  customSection.className = "rules-custom-section";

  const customHeader = document.createElement("div");
  customHeader.className = "rules-custom-header";
  customHeader.innerHTML = `<span style="font-size:0.78rem;font-weight:600;color:var(--text-muted)">Własne reguły</span>`;
  const addCustomBtn = document.createElement("button");
  addCustomBtn.type = "button"; addCustomBtn.className = "secondary-btn"; addCustomBtn.style.fontSize = "0.75rem";
  addCustomBtn.textContent = "+ Dodaj";
  const aiRuleBtn = document.createElement("button");
  aiRuleBtn.type = "button"; aiRuleBtn.className = "secondary-btn"; aiRuleBtn.style.fontSize = "0.75rem";
  aiRuleBtn.textContent = "✨ AI";
  aiRuleBtn.title = "Generuj regułę z AI";
  customHeader.appendChild(addCustomBtn);
  customHeader.appendChild(aiRuleBtn);
  customSection.appendChild(customHeader);

  const customList = document.createElement("div");
  customList.className = "rules-custom-list";
  customSection.appendChild(customList);
  wrap.appendChild(customSection);

  // Pre-populate custom rules (any keys not in LOCATION_RULES)
  const knownKeys = new Set(LOCATION_RULES.map(r => r.key));
  Object.entries(currentRules).forEach(([k, v]) => {
    if (!knownKeys.has(k)) _addCustomRuleRow(customList, k, String(v));
  });

  addCustomBtn.addEventListener("click", () => _addCustomRuleRow(customList, "", ""));

  aiRuleBtn.addEventListener("click", async () => {
    const brief = prompt("Opisz krótko efekt reguły (np. 'gracze tracą 1 HP co turę z powodu trucizny'):");
    if (!brief) return;
    aiRuleBtn.disabled = true; aiRuleBtn.textContent = "⏳";
    try {
      const data = await adminFetch("/api/admin/campaign-designer/generate-entity", {
        method: "POST",
        body: JSON.stringify({ entity_type: "rule", brief }),
      });
      const rule = data.entity || {};
      _addCustomRuleRow(customList, rule.key || "", rule.value !== undefined ? String(rule.value) : "");
      showToast("Reguła wygenerowana.", "success");
    } catch (e) {
      showToast(e.message || "Błąd generowania.", "error");
    } finally { aiRuleBtn.disabled = false; aiRuleBtn.textContent = "✨ AI"; }
  });

  // Store references for _getRulesFromEditor
  wrap._checkboxes   = checkboxes;
  wrap._valueInputs  = valueInputs;
  wrap._customList   = customList;
  return wrap;
}

function _addCustomRuleRow(list, key, value) {
  const row = document.createElement("div");
  row.className = "rule-custom-row";
  row.innerHTML = `
    <input type="text" class="field-input rule-custom-key" placeholder="klucz_reguły" value="${_esc(key)}" style="flex:1;min-width:80px" />
    <input type="text" class="field-input rule-custom-val" placeholder="wartość" value="${_esc(value)}" style="flex:1;min-width:80px" />
    <button type="button" class="icon-btn rule-custom-del" style="color:var(--accent-red)">✕</button>`;
  row.querySelector(".rule-custom-del").addEventListener("click", () => row.remove());
  list.appendChild(row);
}

function _getRulesFromEditor(wrap) {
  const result = {};
  (wrap._checkboxes || []).forEach(({ rule, cb }) => {
    if (!cb.checked) return;
    if (rule.type === "boolean") {
      result[rule.key] = true;
    } else {
      const inp = wrap._valueInputs[rule.key];
      const raw = inp ? inp.value.trim() : String(rule.default ?? "");
      result[rule.key] = rule.type === "number" ? Number(raw) : raw;
    }
  });
  (wrap._customList?.querySelectorAll(".rule-custom-row") || []).forEach(row => {
    const k = row.querySelector(".rule-custom-key").value.trim();
    const v = row.querySelector(".rule-custom-val").value.trim();
    if (k) {
      const n = Number(v);
      result[k] = (v === "true") ? true : (v === "false") ? false : (Number.isFinite(n) && v !== "") ? n : v;
    }
  });
  return result;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _tryJson(str, fallback) {
  if (!str || !String(str).trim()) return { ok: true, value: fallback };
  try { return { ok: true, value: JSON.parse(str) }; }
  catch { return { ok: false, value: null }; }
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

// ── Locations ─────────────────────────────────────────────────────────────────

async function _renderLocations(container) {
  const toolbar = document.createElement("div");
  toolbar.className = "tab-toolbar";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addLocation;
  toolbar.appendChild(addBtn);
  container.appendChild(toolbar);

  // Pending review moved to dedicated "Oczekujące" tab
  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  let locations = [];

  const load = async () => {
    renderTable(tableHost, null, null, {});
    try {
      locations = await adminFetch("/api/locations/admin/locations");
    } catch (e) {
      showToast("Błąd ładowania lokacji: " + (e.message || "?"), "error");
      return;
    }

    // Build lookup map for parent labels (by id)
    const locById = new Map((locations).map(l => [l.id, l]));
    const rows = locations.map(loc => ({
      ...loc,
      _parent_label: loc.parent_id
        ? (locById.get(loc.parent_id)?.label ?? `#${loc.parent_id}`)
        : "—",
      _enemy_count: Array.isArray(loc.enemy_keys) ? loc.enemy_keys.length : 0,
      _rules_preview: (loc.rules && typeof loc.rules === "object" && Object.keys(loc.rules).length)
        ? Object.keys(loc.rules).join(", ")
        : "",
    }));

    const columns = [
      { key: "key",            label: LABELS.key,         editable: false },
      { key: "label",          label: LABELS.label,       editable: true },
      {
        key: "location_type",  label: LABELS.type,
        type: "badge", editType: "select",
        editOptions: LOC_TYPES.map((t) => t.value),
        badgeClass: (row) => row.location_type === "macro" ? "admin-badge-gold" : "admin-badge-muted",
        filterOptions: LOC_TYPES,
      },
      { key: "_parent_label",  label: "Nadrzędna",        editable: false },
      { key: "_enemy_count",   label: "Wrogowie",         type: "number", editable: false },
      { key: "_rules_preview", label: "Reguły",           editable: false, popup: true,
        formatDisplay: (r) => r._rules_preview },
      { key: "description",    label: LABELS.description, editable: true, popup: true },
      { key: "is_active",      label: LABELS.isActive,    type: "boolean", editable: true },
      { key: "locked_at",      label: LABELS.locked,      type: "locked",  editable: false },
    ];

    renderTable(tableHost, columns, rows, {
      tableId:           "locations",
      selectable:        true,
      showTextSearch:    true,
      searchPlaceholder: "Szukaj lokacji…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/locations/admin/locations/${row.key}`, {
            method: "PATCH",
            body:   JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success");
          await load();
        } catch (e) {
          showToast("Błąd zapisu: " + (e.message || "?"), "error");
          throw e;
        }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/locations/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success");
          await load();
        } catch (e) {
          showToast("Błąd usuwania: " + (e.message || "?"), "error");
          throw e;
        }
      },
      extraActions: (row) => [{
        label: "Edytuj",
        class: "secondary-btn",
        onClick: () => {
          // Pass the original location object (with rules, enemy_keys etc.)
          const orig = locations.find(l => l.key === row.key) || row;
          _openLocationModal(orig, locations, load);
        },
      }],
    });
  };

  addBtn.addEventListener("click", () => _openLocationModal(null, locations, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "location",
    title: "Generuj lokację z AI",
    onFill: (e) => _openLocationModal(e, locations, load),
  });

  await load();
}

function _openLocationModal(row, allLocations, onDone) {
  const isEdit = !!row;
  const macros = allLocations.filter((l) => l.location_type === "macro");

  const form = document.createElement("div");
  form.className = "modal-form";

  form.appendChild(_field(`${LABELS.key} *`,
    `<input type="text" name="key" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. tavern_main" autocomplete="off" />`));
  form.appendChild(_field(`${LABELS.label} *`,
    `<input type="text" name="label" value="${_esc(row?.label ?? "")}" placeholder="np. Tawerna" autocomplete="off" />`));

  form.appendChild(_field(LABELS.type,
    `<select name="location_type">
      ${LOC_TYPES.map((t) => `<option value="${t.value}" ${(row?.location_type ?? "macro") === t.value ? "selected" : ""}>${t.label}</option>`).join("")}
    </select>`));

  form.appendChild(_field(LABELS.parentKey,
    `<select name="parent_key">
      <option value="">— brak —</option>
      ${macros.map((m) => `<option value="${_esc(m.key)}" ${row?.parent_key === m.key ? "selected" : ""}>${_esc(m.label)} (${_esc(m.key)})</option>`).join("")}
    </select>`));

  form.appendChild(_field(LABELS.description,
    `<textarea name="description" rows="3">${_esc(row?.description ?? "")}</textarea>`));

  // ── Rules editor ──
  const rulesDiv = _buildRulesEditor(row?.rules || {});
  const rulesLabel = document.createElement("div");
  rulesLabel.innerHTML = `<span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary);display:block;margin-bottom:6px">Reguły lokacji</span>`;
  rulesLabel.appendChild(rulesDiv);
  form.appendChild(rulesLabel);

  form.appendChild(_checkbox("is_active", LABELS.isActive, row?.is_active ?? true));

  const { close } = openModal({
    title:   isEdit ? `Edytuj lokację: ${row.key}` : LABELS.addLocation,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : "Dodaj",
        class: "primary-btn",
        onClick: async (c) => {
          const key         = form.querySelector('[name="key"]').value.trim();
          const label       = form.querySelector('[name="label"]').value.trim();
          const loc_type    = form.querySelector('[name="location_type"]').value;
          const parent_key  = form.querySelector('[name="parent_key"]').value || null;
          const description = form.querySelector('[name="description"]').value.trim();
          const is_active   = form.querySelector('[name="is_active"]').checked;
          const rules_json  = _getRulesFromEditor(rulesDiv);  // sent as "rules" to API

          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }

          const body = { key, label, location_type: loc_type, parent_key, description, rules: rules_json, is_active };

          try {
            if (isEdit) {
              await adminFetch(`/api/locations/admin/locations/${row.key}`, {
                method: "PATCH", body: JSON.stringify(body),
              });
            } else {
              await adminFetch("/api/locations/admin/locations", {
                method: "POST", body: JSON.stringify(body),
              });
            }
            showToast(isEdit ? "Zapisano." : "Dodano lokację.", "success");
            c();
            await onDone();
          } catch (e) {
            showToast((e.message || "Błąd zapisu"), "error");
          }
        },
      },
    ],
  });
}

// ── NPCs ──────────────────────────────────────────────────────────────────────

async function _renderNpcs(container) {
  const toolbar = document.createElement("div");
  toolbar.className = "tab-toolbar";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addNpc;
  toolbar.appendChild(addBtn);
  container.appendChild(toolbar);

  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try {
      const data = await adminFetch("/api/admin/npcs");
      rows = (data.data || data.items || []).map(r => ({
        ...r,
        _location_keys_text: Array.isArray(r.location_keys)
          ? r.location_keys.join(", ")
          : (r.location_keys_json ? JSON.stringify(r.location_keys_json) : ""),
      }));
    } catch (e) {
      showToast("Błąd ładowania NPC: " + (e.message || "?"), "error");
      return;
    }

    const columns = [
      { key: "id",       label: "ID",          editable: false },
      { key: "key",      label: LABELS.key,    editable: false },
      { key: "label",    label: LABELS.label,  editable: true },
      {
        key: "npc_type", label: LABELS.npcType,
        type: "badge", editType: "select",
        editOptions: NPC_TYPES.map((t) => t.value),
        badgeClass: (row) => row.npc_type === "merchant" ? "admin-badge-gold" : "admin-badge-muted",
        filterOptions: NPC_TYPES,
      },
      { key: "_location_keys_text", label: "Lokacje",            editable: false, popup: true },
      { key: "is_shop",             label: LABELS.isShop,        type: "boolean", editable: true },
      { key: "is_active",           label: LABELS.isActive,      type: "boolean", editable: true },
      { key: "description",         label: LABELS.description,   editable: true, popup: true },
      { key: "personality_json",    label: "Osobowość JSON",     editable: true, popup: true },
      { key: "shop_inventory_json", label: "Ekwipunek sklepu",   editable: true, popup: true },
      { key: "locked_at",           label: LABELS.locked,        type: "locked",  editable: false },
    ];

    renderTable(tableHost, columns, rows, {
      tableId:           "npcs",
      selectable:        true,
      showTextSearch:    true,
      searchPlaceholder: "Szukaj NPC…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        let apiVal = newVal;
        // personality_json and shop_inventory_json must be sent as strings
        if (colKey === "personality_json" || colKey === "shop_inventory_json") {
          const p = _tryJson(String(newVal), null);
          if (!p.ok) { showToast("Nieprawidłowy JSON.", "error"); throw new Error("bad json"); }
          apiVal = JSON.stringify(p.value);
        }
        try {
          await adminFetch(`/api/npcs/${row.id}`, {
            method: "PATCH",
            body:   JSON.stringify({ [colKey]: apiVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success");
          await load();
        } catch (e) {
          showToast("Błąd zapisu: " + (e.message || "?"), "error");
          throw e;
        }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/npcs/${row.id}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success");
          await load();
        } catch (e) {
          showToast("Błąd usuwania: " + (e.message || "?"), "error");
          throw e;
        }
      },
      extraActions: (row) => [
        {
          label: "Edytuj",
          class: "secondary-btn",
          onClick: () => _openNpcModal(row, load),
        },
      ],
    });
  };

  addBtn.addEventListener("click", () => _openNpcModal(null, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "npc",
    title: "Generuj NPC z AI",
    onFill: (e) => _openNpcModal(e, load),
  });
  await load();
}

async function _openNpcModal(row, onDone) {
  const isEdit = !!row;
  const persJson = row?.personality_json
    ? (typeof row.personality_json === "string" ? row.personality_json : JSON.stringify(row.personality_json, null, 2))
    : "{}";
  const shopJson = row?.shop_inventory_json
    ? (typeof row.shop_inventory_json === "string" ? row.shop_inventory_json : JSON.stringify(row.shop_inventory_json, null, 2))
    : "[]";
  const currentLocKeys = new Set(Array.isArray(row?.location_keys) ? row.location_keys : []);

  const form = document.createElement("div");
  form.className = "modal-form";

  form.appendChild(_field(`${LABELS.key} *`,
    `<input type="text" name="key" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. innkeeper" autocomplete="off" />`));
  form.appendChild(_field(`${LABELS.label} *`,
    `<input type="text" name="label" value="${_esc(row?.label ?? "")}" placeholder="np. Karczmarz" autocomplete="off" />`));
  form.appendChild(_field(LABELS.npcType,
    `<select name="npc_type">
      ${NPC_TYPES.map((t) => `<option value="${t.value}" ${(row?.npc_type ?? "neutral") === t.value ? "selected" : ""}>${t.label}</option>`).join("")}
    </select>`));
  form.appendChild(_field(LABELS.description,
    `<textarea name="description" rows="3">${_esc(row?.description ?? "")}</textarea>`));
  form.appendChild(_field(LABELS.personality,
    `<textarea name="personality_json" rows="4">${_esc(persJson)}</textarea>`));

  // ── Location checkbox list ──
  const locFieldWrap = document.createElement("div");
  const locLabel = document.createElement("span");
  locLabel.style.cssText = "font-size:0.8rem;font-weight:600;color:var(--text-secondary);display:block;margin-bottom:6px";
  locLabel.textContent = LABELS.locationKeys;
  locFieldWrap.appendChild(locLabel);

  const locListWrap = document.createElement("div");
  locListWrap.className = "npc-location-list";
  locListWrap.innerHTML = `<p style="font-size:0.78rem;color:var(--text-muted);padding:8px">Ładowanie lokacji…</p>`;
  locFieldWrap.appendChild(locListWrap);
  form.appendChild(locFieldWrap);

  // Load locations async and render checkboxes
  adminFetch("/api/locations/admin/locations").then(data => {
    const locs = Array.isArray(data) ? data : (data.locations ?? data.items ?? []);
    if (!locs.length) {
      locListWrap.innerHTML = `<p style="font-size:0.78rem;color:var(--text-muted);padding:8px">Brak lokacji.</p>`;
      return;
    }
    locListWrap.innerHTML = "";
    locs.forEach(l => {
      const item = document.createElement("label");
      item.className = "npc-location-item";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.name = "location_key_cb";
      cb.value = l.key;
      cb.checked = currentLocKeys.has(l.key);
      item.appendChild(cb);
      const txt = document.createElement("span");
      txt.innerHTML = `<strong>${_esc(l.label)}</strong> <code style="font-size:0.72rem;color:var(--text-muted)">${_esc(l.key)}</code>`;
      item.appendChild(txt);
      locListWrap.appendChild(item);
    });
  }).catch(() => {
    locListWrap.innerHTML = `<p style="font-size:0.78rem;color:var(--accent-red);padding:8px">Błąd ładowania lokacji.</p>`;
  });

  const shopChkRow = _checkbox("is_shop", LABELS.isShop, row?.is_shop ?? false);
  form.appendChild(shopChkRow);

  const shopInvWrap = document.createElement("div");
  shopInvWrap.id = "shop-inv-wrap";
  shopInvWrap.style.display = row?.is_shop ? "" : "none";
  shopInvWrap.appendChild(_field(LABELS.shopInv,
    `<textarea name="shop_inventory_json" rows="4">${_esc(shopJson)}</textarea>`));
  form.appendChild(shopInvWrap);

  form.appendChild(_checkbox("is_active", LABELS.isActive, row?.is_active ?? true));

  shopChkRow.querySelector("input").addEventListener("change", (e) => {
    shopInvWrap.style.display = e.target.checked ? "" : "none";
  });

  openModal({
    title:   isEdit ? `Edytuj NPC: ${row.label}` : LABELS.addNpc,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : "Dodaj",
        class: "primary-btn",
        onClick: async (c) => {
          const key          = form.querySelector('[name="key"]').value.trim();
          const label        = form.querySelector('[name="label"]').value.trim();
          const npc_type     = form.querySelector('[name="npc_type"]').value;
          const description  = form.querySelector('[name="description"]').value.trim();
          const is_shop      = form.querySelector('[name="is_shop"]').checked;
          const is_active    = form.querySelector('[name="is_active"]').checked;
          const location_keys = Array.from(
            form.querySelectorAll('[name="location_key_cb"]:checked')
          ).map(cb => cb.value);

          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }

          const persRaw = form.querySelector('[name="personality_json"]').value.trim() || "{}";
          const pJSON = _tryJson(persRaw, {});
          if (!pJSON.ok) { showToast("Osobowość musi być poprawnym JSON.", "error"); return; }

          // API expects personality_json as a JSON string, not an object
          const body = {
            key, label, npc_type, description, is_shop: is_shop ? 1 : 0,
            is_active: is_active ? 1 : 0,
            personality_json: JSON.stringify(pJSON.value),
            location_keys,
          };

          if (is_shop) {
            const shopRaw = form.querySelector('[name="shop_inventory_json"]').value.trim() || "[]";
            const sJSON = _tryJson(shopRaw, []);
            if (!sJSON.ok) { showToast("Ekwipunek sklepu musi być poprawnym JSON.", "error"); return; }
            body.shop_inventory_json = JSON.stringify(sJSON.value);
          }

          try {
            if (isEdit) {
              await adminFetch(`/api/npcs/${row.id}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/npcs", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano NPC.", "success");
            c();
            await onDone();
          } catch (e) {
            showToast((e.message || "Błąd zapisu"), "error");
          }
        },
      },
    ],
  });
}

// ── Enemies ───────────────────────────────────────────────────────────────────

async function _renderEnemies(container) {
  const toolbar = document.createElement("div");
  toolbar.className = "tab-toolbar";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addEnemy;
  toolbar.appendChild(addBtn);
  container.appendChild(toolbar);

  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows, lootOpts = [];
    try {
      const [enemyData, lootData] = await Promise.all([
        adminFetch("/api/admin/enemies"),
        adminFetch("/api/admin/loot-tables").catch(() => ({ items: [] })),
      ]);
      rows = (enemyData.items || []).map(r => ({
        ...r,
        _skills: r.skills_json ? JSON.stringify(r.skills_json) : "{}",
        _ci:     Array.isArray(r.conditions_immune) ? JSON.stringify(r.conditions_immune) : "[]",
        _drop_pct: r.drop_chance != null ? Math.round(Number(r.drop_chance) * 100) : 0,
      }));
      lootOpts = (lootData.items || []).map(t => ({ value: t.key, label: t.label || t.key }));
    } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",              label: LABELS.key,   editable: false },
      { key: "label",            label: LABELS.label, editable: true },
      { key: "tier",             label: "Poziom",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.tiers),
        formatDisplay: (r) => LABELS.tiers[r.tier] || r.tier,
        badgeClass: (r) => ({ weak: "admin-badge-muted", standard: "admin-badge-blue", elite: "admin-badge-gold", boss: "admin-badge-red" }[r.tier] ?? "admin-badge-muted"),
        filterOptions: Object.entries(LABELS.tiers).map(([v,l])=>({value:v,label:l})),
      },
      { key: "hp_base",          label: "HP",          type: "number", editable: true },
      { key: "ac_base",          label: "AC",          type: "number", editable: true },
      { key: "attack_bonus",     label: "Atk+",        type: "number", editable: true },
      { key: "damage_die",       label: "Kość",        editable: true },
      { key: "damage_bonus",     label: "Dmg+",        type: "number", editable: true },
      { key: "attacks_per_turn", label: "Atk/turę",    type: "number", editable: true },
      { key: "damage_type",      label: "Typ dmg",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.damageTypes),
        badgeClass: (r) => ({ fire:"admin-badge-red", magic:"admin-badge-blue", poison:"admin-badge-green", cold:"admin-badge-muted" }[r.damage_type] ?? "admin-badge-muted"),
        filterOptions: Object.entries(LABELS.damageTypes).map(([v,l])=>({value:v,label:l})),
      },
      { key: "xp_award",         label: "XP",          type: "number", editable: true },
      { key: "loot_table_key",   label: "Loot",        type: "select-dropdown", editable: true, editOptions: [{ value: "", label: "— brak —" }, ...lootOpts] },
      { key: "_drop_pct",        label: "Drop %",      type: "number", editable: true,
        formatDisplay: (r) => r.drop_chance != null ? Math.round(Number(r.drop_chance) * 100) + "%" : "—" },
      { key: "_skills",          label: "Skills JSON", editable: true, popup: true },
      { key: "_ci",              label: "Immune JSON", editable: true, popup: true },
      { key: "note",             label: "Notatka",     editable: true, popup: true },
      { key: "description",      label: "Opis",        editable: true, popup: true },
      { key: "is_active",        label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",        label: LABELS.locked,   type: "locked",  editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      tableId: "enemies",
      selectable: true,
      showTextSearch: true, searchPlaceholder: "Szukaj wrogów…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        // Map computed display keys back to actual API fields
        const apiKey = colKey === "_skills" ? "skills_json"
                     : colKey === "_ci"     ? "conditions_immune"
                     : colKey === "_drop_pct" ? "drop_chance"
                     : colKey;
        let apiVal = newVal;
        if (colKey === "_skills" || colKey === "_ci") {
          try { apiVal = JSON.parse(newVal); } catch { showToast("Nieprawidłowy JSON.", "error"); throw new Error("bad json"); }
        }
        if (colKey === "_drop_pct") apiVal = Number(newVal) / 100;
        try {
          await adminFetch(`/api/admin/enemies/${row.key}`, { method: "PATCH", body: JSON.stringify({ [apiKey]: apiVal, ...(force ? { force: true } : {}) }) });
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

  addBtn.addEventListener("click", () => _openEnemyModal(null, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "enemy",
    title: "Generuj wroga z AI",
    onFill: (e) => _openEnemyModal(e, load),
  });
  await load();
}

// ── Rules library ─────────────────────────────────────────────────────────────

const RULES_STORAGE_KEY = "aigm_admin2_rule_presets";

function _loadRulePresets() {
  try { return JSON.parse(localStorage.getItem(RULES_STORAGE_KEY) || "[]"); } catch { return []; }
}
function _saveRulePresets(list) {
  try { localStorage.setItem(RULES_STORAGE_KEY, JSON.stringify(list)); } catch {}
}

async function _renderRules(container) {
  container.innerHTML = "";

  // ── Section 1: Predefined rules reference ──
  const refSection = document.createElement("div");
  refSection.className = "rules-section-wrap";
  refSection.innerHTML = `
    <div class="rules-section-header">
      <span class="system-section-title" style="font-size:0.72rem">Wbudowane reguły lokacji</span>
      <span class="system-help-text">Gotowe do użycia w każdej lokacji. Zaznacz w edytorze lokacji.</span>
    </div>
    <table class="sys-table" style="margin-bottom:20px">
      <thead><tr><th>Klucz</th><th>Nazwa</th><th>Typ</th><th>Domyślnie</th><th>Opis</th></tr></thead>
      <tbody>
        ${LOCATION_RULES.map(r => `
          <tr>
            <td><code style="font-size:0.72rem;color:var(--text-link)">${_esc(r.key)}</code></td>
            <td><strong>${_esc(r.label)}</strong></td>
            <td><span class="admin-badge ${r.type === "boolean" ? "admin-badge-blue" : r.type === "number" ? "admin-badge-gold" : "admin-badge-muted"}">${_esc(r.type)}</span></td>
            <td>${r.default !== undefined ? _esc(String(r.default)) : "—"}</td>
            <td style="color:var(--text-muted);font-size:0.78rem">${_esc(r.description)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  container.appendChild(refSection);

  // ── Section 2: Custom rule presets ──
  const presetsSection = document.createElement("div");
  presetsSection.className = "rules-section-wrap";

  const presetsHeader = document.createElement("div");
  presetsHeader.className = "rules-section-header";
  presetsHeader.innerHTML = `
    <span class="system-section-title" style="font-size:0.72rem">Szablony reguł (własne zestawy)</span>
    <span class="system-help-text">Zapisz zestaw reguł pod nazwą, by szybko stosować go do lokacji.</span>`;

  const addPresetBtn = document.createElement("button");
  addPresetBtn.className = "primary-btn";
  addPresetBtn.style.marginLeft = "auto";
  addPresetBtn.textContent = "+ Nowy szablon";
  presetsHeader.appendChild(addPresetBtn);
  presetsSection.appendChild(presetsHeader);

  const presetsList = document.createElement("div");
  presetsList.className = "rules-presets-list";
  presetsSection.appendChild(presetsList);
  container.appendChild(presetsSection);

  const renderPresets = () => {
    const presets = _loadRulePresets();
    presetsList.innerHTML = "";
    if (!presets.length) {
      presetsList.innerHTML = `<p class="system-help-text" style="padding:12px">Brak szablonów. Utwórz pierwszy zestaw reguł.</p>`;
      return;
    }
    presets.forEach((preset, idx) => {
      const card = document.createElement("div");
      card.className = "rule-preset-card";
      const ruleKeys = Object.keys(preset.rules || {});
      card.innerHTML = `
        <div class="rule-preset-card-header">
          <strong class="rule-preset-name">${_esc(preset.name)}</strong>
          <span class="system-help-text">${_esc(ruleKeys.join(", ") || "brak reguł")}</span>
        </div>
        <div class="rule-preset-card-actions">
          <button class="secondary-btn preset-edit-btn" style="font-size:0.75rem">Edytuj</button>
          <button class="secondary-btn danger-outline preset-delete-btn" style="font-size:0.75rem">Usuń</button>
        </div>`;
      card.querySelector(".preset-edit-btn").addEventListener("click", () => _openPresetModal(preset, idx, renderPresets));
      card.querySelector(".preset-delete-btn").addEventListener("click", () => {
        if (!confirm(`Usunąć szablon "${preset.name}"?`)) return;
        const list = _loadRulePresets();
        list.splice(idx, 1);
        _saveRulePresets(list);
        renderPresets();
      });
      presetsList.appendChild(card);
    });
  };

  addPresetBtn.addEventListener("click", () => _openPresetModal(null, -1, renderPresets));
  renderPresets();
}

function _openPresetModal(preset, idx, onDone) {
  const isEdit = !!preset;
  const form = document.createElement("div");
  form.className = "modal-form";

  const nameField = document.createElement("label");
  nameField.className = "modal-field";
  nameField.innerHTML = `<span>Nazwa szablonu *</span><input type="text" name="preset_name" value="${_esc(preset?.name ?? "")}" placeholder="np. Strefa bezpieczna, Loch śmierci" />`;
  form.appendChild(nameField);

  const rulesLabel = document.createElement("div");
  rulesLabel.innerHTML = `<span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary);display:block;margin:12px 0 6px">Reguły zestawu</span>`;
  const rulesDiv = _buildRulesEditor(preset?.rules || {});
  rulesLabel.appendChild(rulesDiv);
  form.appendChild(rulesLabel);

  openModal({
    title: isEdit ? `Edytuj szablon: ${preset.name}` : "Nowy szablon reguł",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: c => c() },
      {
        label: isEdit ? "Zapisz" : "Utwórz",
        class: "primary-btn",
        onClick: async c => {
          const name = form.querySelector('[name="preset_name"]').value.trim();
          if (!name) { showToast("Podaj nazwę szablonu.", "error"); return; }
          const rules = _getRulesFromEditor(rulesDiv);
          const list = _loadRulePresets();
          if (isEdit && idx >= 0) list[idx] = { name, rules };
          else list.push({ name, rules });
          _saveRulePresets(list);
          showToast(isEdit ? "Szablon zaktualizowany." : "Szablon utworzony.", "success");
          c();
          onDone();
        },
      },
    ],
  });
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
    title: isEdit ? `Edytuj wroga: ${row.key}` : LABELS.addEnemy,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : "Dodaj",
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

// ── Pending Review Queue (Task 32) ────────────────────────────────────────

async function _renderPendingReview(container, panel) {
  container.innerHTML = `
    <div class="pending-review-layout">
      <h2 class="section-heading">⏳ Oczekujące na weryfikację</h2>
      <p class="section-note">Encje stworzone przez GM podczas sesji. Zatwierdź aby stały się permanentne.</p>
      <div class="subtab-bar" style="margin-bottom:12px">
        <button class="subtab-btn active" data-ptab="locations">Lokacje <span id="pr-loc-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
        <button class="subtab-btn" data-ptab="npcs">NPC <span id="pr-npc-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
        <button class="subtab-btn" data-ptab="enemies">Wrogowie <span id="pr-enemy-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
      </div>
      <div id="pr-loc-panel" class="pr-panel active"></div>
      <div id="pr-npc-panel" class="pr-panel" style="display:none"></div>
      <div id="pr-enemy-panel" class="pr-panel" style="display:none"></div>
    </div>`;

  container.querySelectorAll("[data-ptab]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll("[data-ptab]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      container.querySelectorAll(".pr-panel").forEach(p => p.style.display = "none");
      const map = { locations: "pr-loc-panel", npcs: "pr-npc-panel", enemies: "pr-enemy-panel" };
      const target = container.querySelector(`#${map[btn.dataset.ptab]}`);
      if (target) target.style.display = "";
    });
  });

  await Promise.all([
    _loadPendingType(container, "locations", "pr-loc-panel", "pr-loc-badge", panel),
    _loadPendingType(container, "npcs", "pr-npc-panel", "pr-npc-badge", panel),
    _loadPendingType(container, "enemies", "pr-enemy-panel", "pr-enemy-badge", panel),
  ]);
}

async function _loadPendingType(container, type, panelId, badgeId, panel) {
  const panelEl = container.querySelector(`#${panelId}`);
  const badge = container.querySelector(`#${badgeId}`);
  const navBadge = panel.querySelector("#pending-nav-badge");
  panelEl.innerHTML = `<div class="camp-loading">Ładowanie…</div>`;

  try {
    const data = await adminFetch(`/api/admin/world/pending/${type}`);
    const items = data.items || [];

    badge.textContent = String(items.length);
    badge.style.display = items.length ? "" : "none";

    // Update nav tab badge total
    const total = (parseInt(panel.querySelector("#pr-loc-badge")?.textContent || 0) || 0) +
                  (parseInt(panel.querySelector("#pr-npc-badge")?.textContent || 0) || 0) +
                  (parseInt(panel.querySelector("#pr-enemy-badge")?.textContent || 0) || 0);
    if (navBadge) { navBadge.textContent = String(total); navBadge.style.display = total ? "" : "none"; }

    if (!items.length) {
      panelEl.innerHTML = `<p class="section-note">Brak oczekujących pozycji.</p>`;
      return;
    }

    panelEl.innerHTML = "";
    const entityType = type === "locations" ? "location" : type === "npcs" ? "npc" : "enemy";
    items.forEach(item => {
      const row = document.createElement("div");
      row.className = "pending-row";
      row.innerHTML = `
        <div class="pending-row-info">
          <strong>${_esc(item.label || item.name || item.key)}</strong>
          <code>${_esc(item.key)}</code>
          ${item.description ? `<span style="color:var(--text-muted);font-size:0.76rem">${_esc(item.description.slice(0, 80))}${item.description.length > 80 ? "…" : ""}</span>` : ""}
        </div>
        <div class="pending-row-actions">
          <button class="primary-btn pending-approve-btn" style="font-size:0.78rem;padding:4px 10px">✓ Zatwierdź</button>
          <button class="secondary-btn danger-outline pending-reject-btn" style="font-size:0.78rem;padding:4px 8px">✕ Odrzuć</button>
        </div>`;

      row.querySelector(".pending-approve-btn").addEventListener("click", async () => {
        try {
          await adminFetch(`/api/admin/world/review/${entityType}/${item.key}`, {
            method: "POST", body: JSON.stringify({ action: "approve" }),
          });
          showToast("Zatwierdzone.", "success");
          row.remove();
          badge.textContent = String(Math.max(0, (parseInt(badge.textContent) || 1) - 1));
          if (badge.textContent === "0") badge.style.display = "none";
        } catch (e) { showToast(e.message, "error"); }
      });

      row.querySelector(".pending-reject-btn").addEventListener("click", async () => {
        if (!confirm(`Odrzucić "${item.label || item.key}"?`)) return;
        try {
          await adminFetch(`/api/admin/world/review/${entityType}/${item.key}`, {
            method: "POST", body: JSON.stringify({ action: "discard" }),
          });
          showToast("Odrzucone.", "success");
          row.remove();
          badge.textContent = String(Math.max(0, (parseInt(badge.textContent) || 1) - 1));
          if (badge.textContent === "0") badge.style.display = "none";
        } catch (e) { showToast(e.message, "error"); }
      });

      panelEl.appendChild(row);
    });
  } catch (e) {
    panelEl.innerHTML = `<p style="color:var(--accent-red);font-size:0.82rem">${_esc(e.message)}</p>`;
  }
}

// ── Dungeons ──────────────────────────────────────────────────────────────────

async function _renderDungeons(container) {
  const tableHost = document.createElement("div");
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ Dodaj loch";
  addBtn.style.marginBottom = "12px";

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows = [];
    try { rows = (await adminFetch("/api/admin/dungeons")).items || []; }
    catch (e) { showToast("Błąd ładowania lochów: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",           label: "Klucz",        editable: false },
      { key: "label",         label: "Nazwa",         editable: true },
      { key: "rooms",         label: "Pokoje",        type: "number", editable: true },
      { key: "cooldown_hours",label: "Cooldown (h)",  type: "number", editable: true },
      { key: "min_level",     label: "Min. poziom",   type: "number", editable: true },
      { key: "loot_tier",     label: "Łupy",
        type: "badge", editType: "select",
        editOptions: ["poor", "standard", "rich"],
        badgeClass: (r) => ({ poor: "admin-badge-blue", standard: "admin-badge-green", rich: "admin-badge-gold" }[r.loot_tier] || "admin-badge-blue"),
        formatDisplay: (r) => ({ poor: "Słabe", standard: "Standardowe", rich: "Bogate" }[r.loot_tier] || r.loot_tier),
      },
      { key: "boss_enemy",    label: "Boss",          editable: true },
      { key: "atmosphere",    label: "Atmosfera",     editable: true, popup: true },
      { key: "is_active",     label: "Aktywny",       type: "boolean", editable: true },
    ];

    renderTable(tableHost, cols, rows, {
      tableId: "dungeons",
      showTextSearch: true,
      searchPlaceholder: "Szukaj lochów…",
      async onEdit(row, colKey, newVal) {
        try {
          await adminFetch(`/api/admin/dungeons/${row.key}`, { method: "PATCH", body: JSON.stringify({ [colKey]: newVal }) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row) {
        try {
          await adminFetch(`/api/admin/dungeons/${row.key}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openDungeonModal(row, load) }],
    });
  };

  addBtn.addEventListener("click", () => _openDungeonModal(null, load));
  container.appendChild(addBtn);
  container.appendChild(tableHost);
  await load();
}

function _openDungeonModal(row, onDone) {
  const isEdit = !!row;
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span>
      <input name="key" type="text" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. goblin_warren" autocomplete="off"/>
    </label>
    <label class="modal-field"><span>Nazwa *</span>
      <input name="label" type="text" value="${_esc(row?.label ?? "")}" placeholder="Nora Goblinów"/>
    </label>
    <label class="modal-field"><span>Klucz lokacji</span>
      <input name="location_key" type="text" value="${_esc(row?.location_key ?? "")}" placeholder="Zostaw puste = jak klucz lochu"/>
    </label>
    <label class="modal-field"><span>Pokoje (1–20)</span>
      <input name="rooms" type="number" value="${row?.rooms ?? 5}" min="1" max="20"/>
    </label>
    <label class="modal-field"><span>Pula wrogów (JSON array)</span>
      <input name="enemy_pool" type="text" value="${_esc(row?.enemy_pool ?? '[]')}" placeholder='["goblin","goblin_archer"]'/>
    </label>
    <label class="modal-field"><span>Boss (klucz wroga, opcjonalnie)</span>
      <input name="boss_enemy" type="text" value="${_esc(row?.boss_enemy ?? "")}" placeholder="goblin_shaman"/>
    </label>
    <label class="modal-field"><span>Jakość łupów</span>
      <select name="loot_tier">
        ${["poor","standard","rich"].map(t => `<option value="${t}" ${(row?.loot_tier ?? "standard") === t ? "selected" : ""}>${{ poor:"Słabe", standard:"Standardowe", rich:"Bogate" }[t]}</option>`).join("")}
      </select>
    </label>
    <label class="modal-field"><span>Cooldown (godziny)</span>
      <input name="cooldown_hours" type="number" value="${row?.cooldown_hours ?? 72}" min="1" max="720"/>
    </label>
    <label class="modal-field"><span>Minimalny poziom</span>
      <input name="min_level" type="number" value="${row?.min_level ?? 1}" min="1" max="20"/>
    </label>
    <label class="modal-field"><span>Atmosfera (opis klimatu)</span>
      <textarea name="atmosphere" rows="3" placeholder="Ciasne tunele, smród gnijącego mięsa…">${_esc(row?.atmosphere ?? "")}</textarea>
    </label>
    <label class="modal-checkbox-row">
      <input name="is_active" type="checkbox" ${(row?.is_active ?? 1) ? "checked" : ""}>
      <span>Aktywny</span>
    </label>
  `;

  openModal({
    title: isEdit ? `Edytuj loch: ${row.key}` : "Nowy loch",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (c) => c() },
      { label: isEdit ? "Zapisz" : "Dodaj", class: "primary-btn", onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key || !label) { showToast("Klucz i nazwa są wymagane.", "error"); return; }
          const body = {
            key, label,
            location_key:   g("location_key").value.trim() || key,
            rooms:          parseInt(g("rooms").value) || 5,
            enemy_pool:     g("enemy_pool").value.trim() || "[]",
            boss_enemy:     g("boss_enemy").value.trim() || null,
            loot_tier:      g("loot_tier").value,
            cooldown_hours: parseInt(g("cooldown_hours").value) || 72,
            min_level:      parseInt(g("min_level").value) || 1,
            atmosphere:     g("atmosphere").value.trim() || null,
            is_active:      g("is_active").checked ? 1 : 0,
          };
          try {
            if (isEdit) await adminFetch(`/api/admin/dungeons/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            else        await adminFetch("/api/admin/dungeons",              { method: "POST",  body: JSON.stringify(body) });
            showToast(isEdit ? "Zapisano." : "Dodano loch.", "success");
            c(); await onDone();
          } catch (e) { showToast(e.message || "Błąd zapisu", "error"); }
        }},
    ],
  });
}
