/**
 * Smart Entry v3 — form-first AI creator
 * Usage: openSmartEntry(table?) — opens overlay for creating/editing records
 */
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const TABLE_LABELS = {
  game_config_weapons:     "Broń",
  game_config_items:       "Przedmioty",
  game_config_consumables: "Konsumable",
  game_config_enemies:     "Wrogowie",
};
const SUPPORTED_TABLES = Object.keys(TABLE_LABELS);

let _overlay = null;
let _sessionId = null;
let _currentTable = null;
let _schemaFields = [];
let _draft = {};
let _existingKey = null;
const _schemaCache = {};

function _genId() { return "se-" + Math.random().toString(36).slice(2, 10); }
function _esc(s)  { return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function _slugify(str) {
  const map = {"ą":"a","ć":"c","ę":"e","ł":"l","ń":"n","ó":"o","ś":"s","ź":"z","ż":"z","Ą":"a","Ć":"c","Ę":"e","Ł":"l","Ń":"n","Ó":"o","Ś":"s","Ź":"z","Ż":"z"};
  return str.split("").map(c => map[c] || c).join("")
    .toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "").slice(0, 50);
}

// ── Schema ──────────────────────────────────────────────────────────────────

async function _fetchSchema(table) {
  if (_schemaCache[table]) return _schemaCache[table];
  const data = await adminFetch(`/api/admin/smart-entry/schema?table=${table}`);
  _schemaCache[table] = data;
  return data;
}

async function _fetchList(table) {
  try {
    const data = await adminFetch(`/api/admin/smart-entry/list?table=${table}`);
    return data.items || [];
  } catch { return []; }
}

// ── Overlay ──────────────────────────────────────────────────────────────────

function _ensureOverlay() {
  if (_overlay) return _overlay;
  const el = document.createElement("div");
  el.id = "smart-entry-overlay";
  el.className = "smart-entry-overlay";
  el.innerHTML = `
    <div class="smart-entry-panel">
      <div class="smart-entry-header">
        <span class="smart-entry-title">🤖 Kreator AI</span>
        <select id="se-table-select" class="field-input" style="font-size:0.82rem;padding:4px 8px;margin-left:8px">
          ${SUPPORTED_TABLES.map(t => `<option value="${t}">${TABLE_LABELS[t]}</option>`).join("")}
        </select>
        <button class="smart-entry-close" id="se-close-btn" type="button">✕ Zamknij</button>
      </div>
      <div class="smart-entry-body">
        <div class="smart-entry-chat-col">
          <div class="smart-entry-messages" id="se-messages"></div>
          <div class="smart-entry-input-row" style="align-items:flex-end">
            <textarea id="se-input" class="field-input" placeholder="Opisz rekord który chcesz stworzyć lub zmienić…" rows="3" maxlength="1000" style="resize:vertical;min-height:60px;flex:1"></textarea>
            <button class="primary-btn" id="se-send-btn" type="button">Wyślij</button>
          </div>
        </div>
        <div class="smart-entry-form-col">
          <div class="se-form-toolbar">
            <select id="se-existing-select" class="field-input" style="flex:1;font-size:0.82rem">
              <option value="">+ Nowy rekord</option>
            </select>
            <button class="secondary-btn" id="se-load-btn" type="button" style="font-size:0.78rem;white-space:nowrap">Załaduj</button>
          </div>
          <div id="se-form-fields" class="se-form-fields-panel"></div>
          <div class="se-form-footer">
            <button class="primary-btn" id="se-save-btn" type="button" disabled style="width:100%">✅ Zapisz rekord</button>
          </div>
        </div>
      </div>
    </div>`;
  document.body.appendChild(el);
  _overlay = el;

  el.querySelector("#se-close-btn").addEventListener("click", closeSmartEntry);
  el.addEventListener("click", e => { if (e.target === el) closeSmartEntry(); });
  el.querySelector("#se-send-btn").addEventListener("click", _send);
  el.querySelector("#se-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); _send(); }
  });
  el.querySelector("#se-table-select").addEventListener("change", e => {
    void _switchTable(e.target.value);
  });
  el.querySelector("#se-load-btn").addEventListener("click", async () => {
    const key = el.querySelector("#se-existing-select").value;
    if (!key) {
      _draft = {}; _existingKey = null;
      _renderFormValues(); _updateSaveBtn();
      _overlay.querySelector("#se-messages").innerHTML = "";
      _appendMsg("Tryb nowego rekordu — opisz co chcesz stworzyć.", "agent");
      return;
    }
    await _loadExisting(key);
  });
  el.querySelector("#se-save-btn").addEventListener("click", _save);
  return el;
}

// ── Table switch ──────────────────────────────────────────────────────────────

async function _switchTable(table) {
  _currentTable = table;
  _draft = {}; _existingKey = null;
  _sessionId = _genId();
  if (_overlay) {
    _overlay.querySelector("#se-messages").innerHTML = "";
    _overlay.querySelector("#se-form-fields").innerHTML = `<div style="padding:16px;color:var(--text-muted)">Ładowanie schematu…</div>`;
    _appendMsg(`Tabela: ${TABLE_LABELS[table] || table}. Opisz rekord lub wybierz istniejący z listy po prawej.`, "agent");
  }
  try {
    const schema = await _fetchSchema(table);
    _schemaFields = schema.fields || [];
    _renderFormFields();
    _updateSaveBtn();
  } catch (e) {
    showToast("Błąd schematu: " + e.message, "error");
  }
  // Populate dropdown
  const items = await _fetchList(table);
  if (_overlay) {
    const sel = _overlay.querySelector("#se-existing-select");
    sel.innerHTML = `<option value="">+ Nowy rekord</option>`;
    items.forEach(item => {
      const o = document.createElement("option");
      o.value = item.key;
      o.textContent = item.label ? `${item.label} (${item.key})` : item.key;
      sel.appendChild(o);
    });
  }
}

// ── Form rendering ────────────────────────────────────────────────────────────

function _renderFormFields() {
  const container = _overlay.querySelector("#se-form-fields");
  container.innerHTML = "";
  _schemaFields.forEach(field => {
    const row = document.createElement("div");
    row.className = "se-field-row" + (field.required ? " required" : "");
    row.dataset.fieldKey = field.key;
    const lbl = document.createElement("div");
    lbl.className = "se-field-label";
    lbl.textContent = field.label + (field.required ? " *" : "");
    row.appendChild(lbl);
    const input = _buildInput(field);
    _bindInputEvents(input, field);
    row.appendChild(input);
    container.appendChild(row);
  });
}

function _buildInput(field) {
  let el;
  if (field.type === "single_choice" && field.options) {
    el = document.createElement("select");
    el.className = "field-input se-field-input";
    const empty = document.createElement("option");
    empty.value = ""; empty.textContent = "— wybierz —";
    el.appendChild(empty);
    field.options.forEach(opt => {
      const o = document.createElement("option");
      const val = typeof opt === "object" ? (opt.label || opt.value) : opt;
      o.value = val;
      o.textContent = val + (opt.description ? ` — ${opt.description}` : "");
      el.appendChild(o);
    });
  } else if (field.type === "boolean") {
    const wrap = document.createElement("label");
    wrap.className = "se-bool-wrap";
    el = document.createElement("input");
    el.type = "checkbox";
    el.className = "se-field-checkbox";
    wrap.appendChild(el);
    return wrap;
  } else if (field.type === "number") {
    el = document.createElement("input");
    el.type = "number";
    el.className = "field-input se-field-input";
    if (field.min !== undefined) el.min = field.min;
    if (field.max !== undefined) el.max = field.max;
  } else if (field.type === "multi_choice" && field.options) {
    el = document.createElement("div");
    el.className = "se-multi-choice";
    field.options.forEach(opt => {
      const val = typeof opt === "object" ? (opt.label || opt.value) : opt;
      const lbl = document.createElement("label");
      lbl.className = "se-multi-option";
      const cb = document.createElement("input");
      cb.type = "checkbox"; cb.value = val;
      lbl.appendChild(cb);
      lbl.appendChild(document.createTextNode(" " + val));
      el.appendChild(lbl);
    });
  } else if (field.type === "textarea") {
    el = document.createElement("textarea");
    el.className = "field-input se-field-textarea";
    el.rows = 3;
    if (field.placeholder) el.placeholder = field.placeholder.slice(0, 120);
  } else {
    el = document.createElement("input");
    el.type = "text";
    el.className = "field-input se-field-input";
    if (field.placeholder) el.placeholder = field.placeholder.slice(0, 80);
  }
  el.dataset.fieldKey = field.key;
  return el;
}

function _bindInputEvents(el, field) {
  const update = () => {
    _draft[field.key] = _readValue(field, el);
    _updateFieldRow(field.key);
    _updateSaveBtn();
    // Auto-slug: when label changes and key is empty
    if (field.key === "label") {
      const keyField = _schemaFields.find(f => f.key === "key");
      if (keyField && !_draft["key"]) {
        const slug = _slugify(String(_draft["label"] || ""));
        const keyRow = _overlay.querySelector(`[data-field-key="key"]`);
        const keyInput = keyRow ? keyRow.querySelector("input,select") : null;
        if (keyInput) { keyInput.value = slug; _draft["key"] = slug; _updateFieldRow("key"); }
      }
    }
  };
  if (el.tagName === "LABEL") {
    el.querySelector("input")?.addEventListener("change", update);
  } else if (el.classList.contains("se-multi-choice")) {
    el.querySelectorAll("input").forEach(cb => cb.addEventListener("change", update));
  } else {
    el.addEventListener("input", update);
    el.addEventListener("change", update);
  }
}

function _readValue(field, el) {
  if (field.type === "boolean") {
    const cb = el.tagName === "LABEL" ? el.querySelector("input") : el;
    return cb?.checked ? 1 : 0;
  }
  if (field.type === "multi_choice") {
    return Array.from(el.querySelectorAll("input:checked")).map(c => c.value).join(",");
  }
  return el.value || "";
}

function _renderFormValues() {
  if (!_overlay) return;
  _schemaFields.forEach(field => {
    const row = _overlay.querySelector(`.se-field-row[data-field-key="${field.key}"]`);
    if (!row) return;
    const el = row.querySelector("input,select,textarea,div.se-multi-choice");
    if (!el) return;
    const val = _draft[field.key] ?? "";
    if (field.type === "boolean") {
      const cb = row.querySelector("input[type=checkbox]");
      if (cb) cb.checked = !!val;
    } else if (field.type === "multi_choice") {
      const vals = String(val).split(",").filter(Boolean);
      el.querySelectorAll("input").forEach(cb => { cb.checked = vals.includes(cb.value); });
    } else {
      el.value = val;
    }
    _updateFieldRow(field.key);
  });
}

function _updateFieldRow(key) {
  if (!_overlay) return;
  const row = _overlay.querySelector(`.se-field-row[data-field-key="${key}"]`);
  if (!row) return;
  const val = _draft[key];
  row.classList.toggle("filled", !!(val !== undefined && val !== "" && val !== null));
}

function _updateSaveBtn() {
  const btn = _overlay?.querySelector("#se-save-btn");
  if (!btn) return;
  const allFilled = _schemaFields.filter(f => f.required).every(f => {
    const v = _draft[f.key];
    return v !== undefined && v !== "" && v !== null;
  });
  btn.disabled = !allFilled;
  btn.textContent = _existingKey ? "✅ Zaktualizuj rekord" : "✅ Zapisz rekord";
}

// ── Load existing ──────────────────────────────────────────────────────────────

async function _loadExisting(key) {
  try {
    const record = await adminFetch(`/api/admin/smart-entry/record?table=${_currentTable}&key=${encodeURIComponent(key)}`);
    _draft = { ...record };
    _existingKey = key;
    _sessionId = _genId();
    _renderFormValues();
    _updateSaveBtn();
    if (_overlay) {
      _overlay.querySelector("#se-messages").innerHTML = "";
      _appendMsg(`Załadowano: "${record.label || key}". Opisz co chcesz zmienić.`, "agent");
    }
  } catch (e) {
    showToast("Błąd ładowania: " + e.message, "error");
  }
}

// ── LLM call ──────────────────────────────────────────────────────────────────

async function _send() {
  const input = _overlay.querySelector("#se-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  _appendMsg(text, "user");
  await _callAgent(text);
}

async function _callAgent(message) {
  const sendBtn = _overlay.querySelector("#se-send-btn");
  sendBtn.disabled = true;
  const typing = _appendMsg("…", "agent");
  try {
    const resp = await adminFetch("/api/admin/smart-entry/message", {
      method: "POST",
      body: JSON.stringify({
        session_id: _sessionId,
        table: _currentTable,
        message,
        current_draft: _draft,
        target_key: _existingKey || null,
      }),
    });
    typing.remove();
    if (resp.reply) _appendMsg(resp.reply, "agent");
    if (resp.draft && typeof resp.draft === "object") {
      _draft = { ..._draft, ...Object.fromEntries(
        Object.entries(resp.draft).filter(([, v]) => v !== null && v !== undefined)
      )};
      _renderFormValues();
      _updateSaveBtn();
    }
  } catch (e) {
    typing.remove();
    const msg = typeof e?.message === "string" ? e.message : JSON.stringify(e);
    _appendMsg(`Błąd: ${msg}`, "agent error");
  } finally {
    sendBtn.disabled = false;
  }
}

// ── Save ──────────────────────────────────────────────────────────────────────

async function _save() {
  const btn = _overlay.querySelector("#se-save-btn");
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = "Zapisuję…";
  try {
    const resp = await adminFetch("/api/admin/smart-entry/save", {
      method: "POST",
      body: JSON.stringify({
        session_id: _sessionId,
        draft: _draft,
        table: _currentTable,
        target_key: _existingKey || null,
      }),
    });
    const verb = resp.mode === "update" ? "Zaktualizowano" : "Zapisano";
    showToast(`${verb}: ${resp.key}`, "success");
    _appendMsg(`✓ Rekord "${resp.key}" ${resp.mode === "update" ? "zaktualizowany" : "zapisany"}. Możesz tworzyć kolejny lub zamknąć.`, "agent success");
    window.dispatchEvent(new CustomEvent("smart-entry-saved", {
      detail: { table: resp.table || _currentTable, key: resp.key, mode: resp.mode },
    }));
    // Reset for new record
    _draft = {}; _existingKey = null; _sessionId = _genId();
    if (_overlay) {
      _overlay.querySelector("#se-existing-select").value = "";
      _renderFormValues();
      _updateSaveBtn();
    }
  } catch (e) {
    const msg = typeof e?.message === "string" ? e.message : JSON.stringify(e);
    showToast(msg || "Błąd zapisu.", "error");
    btn.textContent = orig;
    _updateSaveBtn();
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

function _appendMsg(text, type) {
  if (!_overlay) return { remove: () => {} };
  const messages = _overlay.querySelector("#se-messages");
  const div = document.createElement("div");
  div.className = `chat-msg ${type}`;
  div.innerHTML = `<div class="chat-bubble">${_esc(text).replace(/\n/g, "<br>")}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

// ── Public ────────────────────────────────────────────────────────────────────

export async function openSmartEntry(table = null) {
  const overlay = _ensureOverlay();
  overlay.classList.add("visible");
  _sessionId = _genId();
  const tableSelect = overlay.querySelector("#se-table-select");
  const target = table || tableSelect.value || SUPPORTED_TABLES[0];
  if (tableSelect.value !== target) tableSelect.value = target;
  await _switchTable(target);
}

export function closeSmartEntry() {
  if (_overlay) _overlay.classList.remove("visible");
}
