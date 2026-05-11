import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable, showConfirm } from "/admin_panel_v2/shared/table.js?v=5";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";

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

const TABS = ["locations", "npcs", "enemies"];
const _rendered = new Set();
let _aiTrigger = null;  // updated by each tab render; called by the bubble

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content">
      <div class="subtab-bar">
        <button class="subtab-btn active" data-tab="locations">${LABELS.locations}</button>
        <button class="subtab-btn" data-tab="npcs">${LABELS.npcs}</button>
        <button class="subtab-btn" data-tab="enemies">${LABELS.enemies}</button>
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
      _aiTrigger = null;  // will be set by the render function
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
  if (tab === "locations") await _renderLocations(container);
  else if (tab === "npcs") await _renderNpcs(container);
  else if (tab === "enemies") await _renderEnemies(container);
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
            const data = await (await import("/admin_panel_v2/shared/api.js?v=2")).adminFetch(
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

  // Pending locations section (above the main table)
  const pendingWrap = document.createElement("details");
  pendingWrap.className = "pending-details";
  pendingWrap.innerHTML = `
    <summary>
      Oczekujące lokacje
      <span id="pending-badge" class="admin-badge admin-badge-gold" style="display:none"></span>
    </summary>
    <div id="pending-list" class="pending-list-body"></div>`;
  container.appendChild(pendingWrap);

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

    const columns = [
      { key: "key",           label: LABELS.key,       editable: false },
      { key: "label",         label: LABELS.label,     editable: true },
      {
        key: "location_type", label: LABELS.type,
        type: "badge", editType: "select",
        editOptions: LOC_TYPES.map((t) => t.value),
        badgeClass: (row) => row.location_type === "macro" ? "admin-badge-gold" : "admin-badge-muted",
        filterOptions: LOC_TYPES,
      },
      { key: "parent_key",    label: LABELS.parentKey, editable: false },
      { key: "is_active",     label: LABELS.isActive,  type: "boolean", editable: true },
      { key: "locked_at",     label: LABELS.locked,    type: "locked",  editable: false },
    ];

    renderTable(tableHost, columns, locations, {
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
          await adminFetch(`/api/locations/admin/locations/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
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
          onClick: () => _openLocationModal(row, locations, load),
        },
      ],
    });
  };

  addBtn.addEventListener("click", () => _openLocationModal(null, locations, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "location",
    title: "Generuj lokację z AI",
    onFill: (e) => _openLocationModal(e, locations, load),
  });

  const loadPending = async () => {
    const listEl = pendingWrap.querySelector("#pending-list");
    const badge  = pendingWrap.querySelector("#pending-badge");
    listEl.textContent = "Ładowanie…";
    try {
      const data    = await adminFetch("/api/admin/locations/pending");
      const pending = Array.isArray(data) ? data : (data.pending ?? []);
      badge.textContent = String(pending.length);
      badge.style.display = pending.length ? "" : "none";
      if (!pending.length) {
        listEl.innerHTML = `<p class="section-note">Brak oczekujących lokacji.</p>`;
        return;
      }
      listEl.innerHTML = "";
      pending.forEach((p) => {
        const row = document.createElement("div");
        row.className = "pending-row";
        row.innerHTML = `
          <div class="pending-row-info">
            <strong>${_esc(p.label)}</strong>
            <code>${_esc(p.key)}</code>
            <span class="admin-badge admin-badge-muted">${_esc(p.location_type)}</span>
            ${p.parent_key ? `<span style="color:var(--text-muted);font-size:0.78rem">→ ${_esc(p.parent_key)}</span>` : ""}
          </div>
          <div class="pending-row-actions">
            <button class="primary-btn pending-approve-btn" style="font-size:0.78rem;padding:4px 10px" data-id="${p.id}">✓ Zatwierdź</button>
            <button class="secondary-btn danger-outline pending-reject-btn" style="font-size:0.78rem;padding:4px 8px" data-id="${p.id}">✕ Odrzuć</button>
          </div>`;
        row.querySelector(".pending-approve-btn").addEventListener("click", async () => {
          try {
            await adminFetch(`/api/admin/locations/${p.id}/approve`, { method: "POST" });
            showToast("Lokacja zatwierdzona.", "success");
            await Promise.all([load(), loadPending()]);
          } catch (e) { showToast(e.message || "Błąd zatwierdzenia.", "error"); }
        });
        row.querySelector(".pending-reject-btn").addEventListener("click", async () => {
          if (!confirm(`Odrzucić lokację "${p.label}"?`)) return;
          try {
            await adminFetch(`/api/admin/locations/${p.id}/reject`, { method: "POST" });
            showToast("Lokacja odrzucona.", "success");
            await loadPending();
          } catch (e) { showToast(e.message || "Błąd odrzucenia.", "error"); }
        });
        listEl.appendChild(row);
      });
    } catch (e) {
      listEl.innerHTML = `<p style="color:var(--accent-red);font-size:0.82rem">${_esc(e.message)}</p>`;
    }
  };

  pendingWrap.addEventListener("toggle", () => { if (pendingWrap.open) void loadPending(); });

  await load();
  void loadPending(); // show badge count without opening section
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
  const rulesDiv = _buildRulesEditor(row?.rules_json || {});
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
          const rules_json  = _getRulesFromEditor(rulesDiv);

          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }

          const body = { key, label, location_type: loc_type, parent_key, description, rules_json, is_active };

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
