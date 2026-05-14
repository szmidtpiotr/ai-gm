import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable, showConfirm } from "/admin_panel_v2/shared/table.js?v=5";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";

const LABELS = {
  stats:         "Statystyki",
  skills:        "Umiejętności",
  dc:            "Poziomy DC",
  conditions:    "Stany",
  archetypes:    "Archetypy",
  key:           "Klucz",
  label:         "Nazwa",
  description:   "Opis",
  linkedStat:    "Powiązana statystyka",
  rankCeiling:   "Maks. rang",
  value:         "Wartość",
  effectJson:    "Efekt (JSON)",
  stackable:     "Kumulowalny",
  autoRemove:    "Auto-usuń",
  isActive:      "Aktywny",
  addSkill:      "Dodaj umiejętność",
  addCondition:  "Dodaj stan",
  locked:        "Zablokowane",
  save:          "Zapisz",
  cancel:        "Anuluj",
  assistant:     "Asystent AI",
  assistantHelp: "Opisz umiejętność lub stan do wygenerowania…",
  generate:      "Generuj",
  saveDraft:     "Zapisz szkic",
  clearChat:     "Wyczyść",
  resource:      "Katalog",
};

const TABS = ["stats", "skills", "dc", "conditions", "archetypes"];

const ASSISTANT_RESOURCES = [
  { value: "skills",     label: LABELS.skills },
  { value: "conditions", label: LABELS.conditions },
];

const TAB_TO_RESOURCE = {
  skills:     "skills",
  conditions: "conditions",
};

const _rendered = new Set();
let _statsCache = null;
let _aiHistory  = [];
let _aiDraft    = null;
let _aiResource = "skills";

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content content-layout">
      <div class="content-main">
        <div class="subtab-bar">
          <button class="subtab-btn active" data-tab="stats">${LABELS.stats}</button>
          <button class="subtab-btn" data-tab="skills">${LABELS.skills}</button>
          <button class="subtab-btn" data-tab="dc">${LABELS.dc}</button>
          <button class="subtab-btn" data-tab="conditions">${LABELS.conditions}</button>
          <button class="subtab-btn" data-tab="archetypes">${LABELS.archetypes}</button>
        </div>
        <div class="subtab-panels">
          ${TABS.map((t) => `<div class="subtab-panel${t === "stats" ? " active" : ""}" data-tab="${t}"></div>`).join("")}
        </div>
      </div>
    </div>

    <!-- AI bubble trigger -->
    <button class="ai-bubble-btn" id="ai-fab-btn" title="${LABELS.assistant}">⚡</button>

    <!-- Floating AI assistant popup -->
    <aside class="ai-assistant-popup" id="ai-assistant-popup">
      <div class="ai-assistant-header">
        <span>⚡ ${LABELS.assistant}</span>
        <div style="display:flex;gap:6px">
          <button class="secondary-btn small-btn" id="ai-clear-btn">${LABELS.clearChat}</button>
          <button class="icon-btn ai-popup-close-btn" id="ai-popup-close-btn" title="Zamknij">✕</button>
        </div>
      </div>
      <div class="ai-resource-row">
        <label>${LABELS.resource}
          <select id="ai-resource-select">
            ${ASSISTANT_RESOURCES.map((r) => `<option value="${r.value}">${r.label}</option>`).join("")}
          </select>
        </label>
      </div>
      <div class="ai-history" id="ai-history"></div>
      <div class="ai-draft-wrap" id="ai-draft-wrap" style="display:none"></div>
      <div class="ai-input-row">
        <textarea id="ai-prompt" rows="3" placeholder="${LABELS.assistantHelp}"></textarea>
        <button class="primary-btn" id="ai-generate-btn">${LABELS.generate}</button>
      </div>
    </aside>`;

  _rendered.clear();
  _statsCache = null;
  _aiHistory  = [];
  _aiDraft    = null;

  // ── AI popup toggle ──
  const aiPopup  = panel.querySelector("#ai-assistant-popup");
  const aiBubble = panel.querySelector("#ai-fab-btn");
  aiBubble.addEventListener("click", () => {
    const open = aiPopup.classList.toggle("open");
    aiBubble.classList.toggle("active", open);
  });
  panel.querySelector("#ai-popup-close-btn").addEventListener("click", () => {
    aiPopup.classList.remove("open");
    aiBubble.classList.remove("active");
  });

  panel.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
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

  panel.querySelector("#ai-resource-select").addEventListener("change", (e) => {
    _aiResource = e.target.value;
  });

  panel.querySelector("#ai-clear-btn").addEventListener("click", () => {
    _aiHistory = [];
    _aiDraft   = null;
    _renderAiHistory(panel);
    _renderAiDraft(panel);
  });

  panel.querySelector("#ai-generate-btn").addEventListener("click", () => _handleGenerate(panel));

  panel.querySelector("#ai-prompt").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      _handleGenerate(panel);
    }
  });

  await _activateTab(panel, "stats");
}

async function _activateTab(panel, tab) {
  if (_rendered.has(tab)) return;
  _rendered.add(tab);
  const container = panel.querySelector(`.subtab-panel[data-tab="${tab}"]`);
  if (!container) return;
  switch (tab) {
    case "stats":      await _renderStats(container); break;
    case "skills":     await _renderSkills(container); break;
    case "dc":         await _renderDc(container); break;
    case "conditions": await _renderConditions(container); break;
    case "archetypes": await _renderArchetypes(container); break;
  }
}

function _reloadTab(panel, tab) {
  _rendered.delete(tab);
  _activateTab(panel, tab);
}

async function _fetchStats() {
  if (_statsCache) return _statsCache;
  _statsCache = ((await adminFetch("/api/admin/stats")).items || []);
  return _statsCache;
}

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Stats ─────────────────────────────────────────────────────────────────────

async function _renderStats(container) {
  container.innerHTML = `<p class="section-note">Statystyki są zasiane z danymi startowymi. Możesz edytować tylko nazwę i opis.</p>`;
  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  const columns = [
    { key: "key",         label: LABELS.key,         editable: false },
    { key: "label",       label: LABELS.label,       editable: true },
    { key: "description", label: LABELS.description, editable: true, type: "textarea" },
    { key: "locked_at",   label: LABELS.locked,      type: "locked", editable: false },
  ];

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try {
      rows = (await adminFetch("/api/admin/stats")).items || [];
    } catch (e) {
      showToast("Błąd ładowania statystyk: " + (e.message || "unknown"), "error");
      return;
    }
    renderTable(tableHost, columns, rows, {
      showTextSearch: true,
      searchPlaceholder: "Szukaj statystyk…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        try {
          await adminFetch(`/api/admin/stats/${row.key}`, {
            method: "PATCH",
            body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success");
          _statsCache = null;
          await load();
        } catch (e) {
          showToast("Błąd zapisu: " + (e.message || "unknown"), "error");
          throw e;
        }
      },
    });
  };

  await load();
}

// ── Skills ────────────────────────────────────────────────────────────────────

async function _renderSkills(container) {
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addSkill;
  container.appendChild(addBtn);

  const tableHost = document.createElement("div");
  tableHost.style.marginTop = "12px";
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let [rows, stats] = [[], []];
    try {
      [rows, stats] = await Promise.all([
        adminFetch("/api/admin/skills").then((r) => r.items || []),
        _fetchStats(),
      ]);
    } catch (e) {
      showToast("Błąd ładowania umiejętności: " + (e.message || "unknown"), "error");
      return;
    }

    const statOptions = stats.map((s) => ({ value: s.key, label: s.label || s.key }));

    const columns = [
      { key: "key",          label: LABELS.key,         editable: false },
      { key: "label",        label: LABELS.label,       editable: true },
      { key: "linked_stat",  label: LABELS.linkedStat,  editable: true, type: "select-dropdown", editOptions: statOptions },
      { key: "rank_ceiling", label: LABELS.rankCeiling, editable: true, type: "number", min: 1 },
      { key: "description",       label: LABELS.description,        editable: true, type: "textarea" },
      { key: "trigger_keywords",  label: "Słowa kluczowe (trigger)", editable: true, popup: true },
      { key: "locked_at",    label: LABELS.locked,      type: "locked", editable: false },
    ];

    renderTable(tableHost, columns, rows, {
      selectable: true,
      showTextSearch: true,
      searchPlaceholder: "Szukaj umiejętności…",
      async onEdit(row, colKey, newVal, { force }) {
        try {
          await adminFetch(`/api/admin/skills/${row.key}`, {
            method: "PATCH",
            body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success");
          await load();
        } catch (e) {
          showToast("Błąd zapisu: " + (e.message || "unknown"), "error");
          throw e;
        }
      },
      async onDelete(row, { force }) {
        try {
          await adminFetch(`/api/admin/skills/${row.key}?${force ? "force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success");
          await load();
        } catch (e) {
          showToast("Błąd usuwania: " + (e.message || "unknown"), "error");
          throw e;
        }
      },
    });
  };

  addBtn.addEventListener("click", async () => {
    let stats;
    try {
      stats = await _fetchStats();
    } catch (e) {
      showToast("Błąd ładowania statystyk: " + (e.message || "unknown"), "error");
      return;
    }
    _openSkillModal(stats, async (data) => {
      try {
        await adminFetch("/api/admin/skills", {
          method: "POST",
          body: JSON.stringify(data),
        });
        showToast("Dodano umiejętność.", "success");
        await load();
      } catch (e) {
        showToast("Błąd dodawania: " + (e.message || "unknown"), "error");
      }
    });
  });

  await load();
}

function _openSkillModal(stats, onSubmit, prefill = {}) {
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field">
      <span>${LABELS.key}</span>
      <input type="text" name="key" value="${_esc(prefill.key ?? "")}" placeholder="np. acrobatics" autocomplete="off" />
    </label>
    <label class="modal-field">
      <span>${LABELS.label}</span>
      <input type="text" name="label" value="${_esc(prefill.label ?? "")}" placeholder="Akrobatyka" autocomplete="off" />
    </label>
    <label class="modal-field">
      <span>${LABELS.linkedStat}</span>
      <select name="linked_stat">
        ${stats.map((s) => `<option value="${_esc(s.key)}" ${prefill.linked_stat === s.key ? "selected" : ""}>${_esc(s.label || s.key)}</option>`).join("")}
      </select>
    </label>
    <label class="modal-field">
      <span>${LABELS.rankCeiling}</span>
      <input type="number" name="rank_ceiling" value="${prefill.rank_ceiling ?? 5}" min="1" />
    </label>
    <label class="modal-field">
      <span>${LABELS.description}</span>
      <textarea name="description" rows="3">${_esc(prefill.description ?? "")}</textarea>
    </label>
    <label class="modal-field">
      <span>Słowa kluczowe gracza (trigger_keywords)</span>
      <input type="text" name="trigger_keywords" value="${_esc(prefill.trigger_keywords ?? "")}"
        placeholder="np. miecz,broń,wykuć,kowal — oddzielone przecinkami" autocomplete="off" />
      <span style="font-size:0.7rem;color:var(--text-muted);margin-top:3px">
        Gdy gracz używa tych słów → ten skill jest wybierany niezależnie od AI.
      </span>
    </label>`;

  const { close } = openModal({
    title: LABELS.addSkill,
    content: form,
    footer: [
      {
        label: LABELS.cancel,
        class: "secondary-btn",
        onClick: (c) => c(),
      },
      {
        label: LABELS.save,
        class: "primary-btn",
        onClick: async (c) => {
          const key          = form.querySelector('[name="key"]').value.trim();
          const label        = form.querySelector('[name="label"]').value.trim();
          const linked_stat  = form.querySelector('[name="linked_stat"]').value;
          const rank_ceiling = parseInt(form.querySelector('[name="rank_ceiling"]').value, 10);
          const description  = form.querySelector('[name="description"]').value.trim();

          if (!key)         { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label)       { showToast("Nazwa jest wymagana.", "error"); return; }
          if (!linked_stat) { showToast("Powiązana statystyka jest wymagana.", "error"); return; }
          if (!Number.isFinite(rank_ceiling) || rank_ceiling < 1) { showToast("Maks. rang musi być liczbą ≥ 1.", "error"); return; }

          const trigger_keywords = form.querySelector('[name="trigger_keywords"]').value.trim();
          c();
          await onSubmit({ key, label, linked_stat, rank_ceiling, description, trigger_keywords: trigger_keywords || null });
        },
      },
    ],
  });
}

// ── DC ────────────────────────────────────────────────────────────────────────

async function _renderDc(container) {
  container.innerHTML = `<p class="section-note">Poziomy DC są stałe. Możesz edytować nazwę, wartość i opis.</p>`;
  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  renderTable(tableHost, null, null, {});

  let rows;
  try {
    rows = (await adminFetch("/api/admin/dc")).items || [];
  } catch (e) {
    showToast("Błąd ładowania poziomów DC: " + (e.message || "unknown"), "error");
    return;
  }

  const columns = [
    { key: "key",         label: LABELS.key,         editable: false },
    { key: "label",       label: LABELS.label,       editable: true },
    { key: "value",       label: LABELS.value,       editable: true, type: "number", min: 0 },
    { key: "description", label: LABELS.description, editable: true, type: "textarea" },
    { key: "locked_at",   label: LABELS.locked,      type: "locked", editable: false },
  ];

  const load = async () => {
    try {
      rows = (await adminFetch("/api/admin/dc")).items || [];
    } catch (e) {
      showToast("Błąd ładowania poziomów DC: " + (e.message || "unknown"), "error");
      return;
    }
    renderTable(tableHost, columns, rows, opts);
  };

  const opts = {
    showTextSearch: true,
    searchPlaceholder: "Szukaj poziomów DC…",
    async onEdit(row, colKey, newVal, { force }) {
      try {
        await adminFetch(`/api/admin/dc/${row.key}`, {
          method: "PATCH",
          body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }),
        });
        showToast("Zapisano.", "success");
        await load();
      } catch (e) {
        showToast("Błąd zapisu: " + (e.message || "unknown"), "error");
        throw e;
      }
    },
  };

  renderTable(tableHost, columns, rows, opts);
}

// ── Conditions ────────────────────────────────────────────────────────────────

async function _renderConditions(container) {
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addCondition;
  container.appendChild(addBtn);

  const tableHost = document.createElement("div");
  tableHost.style.marginTop = "12px";
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try {
      rows = (await adminFetch("/api/admin/conditions")).items || [];
    } catch (e) {
      showToast("Błąd ładowania stanów: " + (e.message || "unknown"), "error");
      return;
    }

    const columns = [
      { key: "key",         label: LABELS.key,         editable: false },
      { key: "label",       label: LABELS.label,       editable: true },
      { key: "effect_json", label: LABELS.effectJson,  editable: true, type: "textarea" },
      { key: "description", label: LABELS.description, editable: true, type: "textarea" },
      { key: "stackable",   label: LABELS.stackable,   editable: true, type: "boolean" },
      { key: "auto_remove", label: LABELS.autoRemove,  editable: true },
      { key: "is_active",   label: LABELS.isActive,    editable: true, type: "boolean" },
      { key: "locked_at",   label: LABELS.locked,      type: "locked", editable: false },
    ];

    renderTable(tableHost, columns, rows, {
      selectable: true,
      showTextSearch: true,
      searchPlaceholder: "Szukaj stanów…",
      async onEdit(row, colKey, newVal, { force }) {
        try {
          await adminFetch(`/api/admin/conditions/${row.key}`, {
            method: "PATCH",
            body: JSON.stringify({ [colKey]: newVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success");
          await load();
        } catch (e) {
          showToast("Błąd zapisu: " + (e.message || "unknown"), "error");
          throw e;
        }
      },
      async onDelete(row, { force }) {
        try {
          await adminFetch(`/api/admin/conditions/${row.key}?${force ? "force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success");
          await load();
        } catch (e) {
          showToast("Błąd usuwania: " + (e.message || "unknown"), "error");
          throw e;
        }
      },
    });
  };

  addBtn.addEventListener("click", () => {
    _openConditionModal({}, async (data) => {
      try {
        await adminFetch("/api/admin/conditions", {
          method: "POST",
          body: JSON.stringify(data),
        });
        showToast("Dodano stan.", "success");
        await load();
      } catch (e) {
        showToast("Błąd dodawania: " + (e.message || "unknown"), "error");
      }
    });
  });

  await load();
}

function _openConditionModal(prefill, onSubmit) {
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field">
      <span>${LABELS.key}</span>
      <input type="text" name="key" value="${_esc(prefill.key ?? "")}" placeholder="np. poisoned" autocomplete="off" />
    </label>
    <label class="modal-field">
      <span>${LABELS.label}</span>
      <input type="text" name="label" value="${_esc(prefill.label ?? "")}" placeholder="Zatruty" autocomplete="off" />
    </label>
    <label class="modal-field">
      <span>${LABELS.effectJson}</span>
      <textarea name="effect_json" rows="4" placeholder='{"penalty": -2}'>${_esc(typeof prefill.effect_json === "object" ? JSON.stringify(prefill.effect_json, null, 2) : (prefill.effect_json ?? ""))}</textarea>
    </label>
    <label class="modal-field">
      <span>${LABELS.description}</span>
      <textarea name="description" rows="3">${_esc(prefill.description ?? "")}</textarea>
    </label>
    <label class="modal-field">
      <span>${LABELS.autoRemove}</span>
      <input type="text" name="auto_remove" value="${_esc(prefill.auto_remove ?? "")}" placeholder="np. on_turn_end" autocomplete="off" />
    </label>
    <label class="modal-checkbox-row">
      <input type="checkbox" name="stackable" ${prefill.stackable ? "checked" : ""} />
      <span>${LABELS.stackable}</span>
    </label>
    <label class="modal-checkbox-row">
      <input type="checkbox" name="is_active" ${(prefill.is_active ?? true) ? "checked" : ""} />
      <span>${LABELS.isActive}</span>
    </label>`;

  openModal({
    title: LABELS.addCondition,
    content: form,
    footer: [
      {
        label: LABELS.cancel,
        class: "secondary-btn",
        onClick: (c) => c(),
      },
      {
        label: LABELS.save,
        class: "primary-btn",
        onClick: async (c) => {
          const key            = form.querySelector('[name="key"]').value.trim();
          const label          = form.querySelector('[name="label"]').value.trim();
          const effect_json_raw = form.querySelector('[name="effect_json"]').value.trim();
          const description    = form.querySelector('[name="description"]').value.trim();
          const auto_remove    = form.querySelector('[name="auto_remove"]').value.trim();
          const stackable      = form.querySelector('[name="stackable"]').checked;
          const is_active      = form.querySelector('[name="is_active"]').checked;

          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }

          let effect_json = effect_json_raw || null;
          if (effect_json_raw) {
            try { JSON.parse(effect_json_raw); }
            catch { showToast("Efekt (JSON) zawiera nieprawidłowy JSON.", "error"); return; }
          }

          c();
          await onSubmit({ key, label, effect_json, description, stackable, auto_remove: auto_remove || null, is_active });
        },
      },
    ],
  });
}

// ── Archetypes ────────────────────────────────────────────────────────────────

async function _renderArchetypes(container) {
  container.innerHTML = `<p class="section-note">Archetypy są zasiane z danymi startowymi. Definiują ekwipunek startowy i złoto dla klas postaci.</p>`;
  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  renderTable(tableHost, null, null, {});

  let rows;
  try { rows = (await adminFetch("/api/admin/archetypes")).items || []; }
  catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

  const cols = [
    { key: "key",         label: LABELS.key,         editable: false },
    { key: "label",       label: LABELS.label,        editable: false },
    { key: "hp_base",     label: "HP bazowe",         editable: false },
    { key: "description", label: LABELS.description,  editable: false },
    { key: "locked_at",   label: LABELS.locked,       type: "locked", editable: false },
  ];

  renderTable(tableHost, cols, rows, { showTextSearch: true, searchPlaceholder: "Szukaj archetypów…" });
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
      const tab = d.resource === "skills" ? "skills" : d.resource === "conditions" ? "conditions" : null;
      if (tab) _reloadTab(panel, tab);
    } catch (e) {
      showToast("Błąd zapisu: " + (e.message || "?"), "error");
    }
  });
}
