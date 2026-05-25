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
let _lastChangedFields = [];
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
          <div class="se-mode-badge" id="se-mode-badge">✨ Tworzenie</div>
          <div class="smart-entry-input-row" style="align-items:flex-end">
            <textarea id="se-input" class="field-input" placeholder="Opisz rekord który chcesz stworzyć…" rows="3" maxlength="1000" style="resize:vertical;min-height:60px;flex:1"></textarea>
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
  _draft = {}; _existingKey = null; _lastChangedFields = [];
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
    _updateModeBadge();
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

// ── Effect Builder ────────────────────────────────────────────────────────────

const EFFECT_DAMAGE_TYPES = ["fire","cold","poison","lightning","magic","physical"];
const EFFECT_CONDITIONS   = ["poisoned","burning","bleeding","stunned","blinded","frightened","cursed"];
const EFFECT_STATS        = ["CON","STR","DEX","INT","WIS","CHA"];
const DICE_OPTIONS        = ["1d4","1d6","1d8","1d10","1d12","2d4","2d6"];

function _buildEffectBuilder(field) {
  const wrap = document.createElement("div");
  wrap.className = "se-effect-builder";
  wrap.dataset.fieldKey = field.key;

  const list = document.createElement("div");
  list.className = "se-effect-list";
  wrap.appendChild(list);

  const toolbar = document.createElement("div");
  toolbar.className = "se-effect-toolbar";
  toolbar.innerHTML = `
    <select class="field-input se-effect-add-type" style="font-size:0.78rem;flex:1">
      <option value="">+ Dodaj efekt…</option>
      <option value="extra_damage">Dodatkowe obrażenia</option>
      <option value="on_hit_save">Test obronny przy trafieniu</option>
    </select>`;
  wrap.appendChild(toolbar);

  toolbar.querySelector(".se-effect-add-type").addEventListener("change", e => {
    const type = e.target.value;
    e.target.value = "";
    if (!type) return;
    const effects = _readEffects(wrap);
    if (type === "extra_damage") {
      effects.push({ type: "extra_damage", dice: "1d6", damage_type: "fire" });
    } else {
      effects.push({ type: "on_hit_save", stat: "CON", dc: 12, on_fail: { type: "apply_condition", condition_key: "poisoned", duration_rounds: 2 } });
    }
    _setEffects(wrap, effects);
    _notifyChange(wrap);
  });

  return wrap;
}

function _readEffects(wrap) {
  const cards = wrap.querySelectorAll(".se-effect-card");
  const effects = [];
  cards.forEach(card => {
    const type = card.dataset.effectType;
    if (type === "extra_damage") {
      effects.push({
        type: "extra_damage",
        dice: card.querySelector(".ef-dice")?.value || "1d6",
        damage_type: card.querySelector(".ef-dmgtype")?.value || "fire",
      });
    } else if (type === "on_hit_save") {
      const onFailType = card.querySelector(".ef-onfail-type")?.value || "apply_condition";
      const on_fail = onFailType === "extra_damage"
        ? { type: "extra_damage", dice: card.querySelector(".ef-fail-dice")?.value || "1d6", damage_type: card.querySelector(".ef-fail-dmgtype")?.value || "poison" }
        : { type: "apply_condition", condition_key: card.querySelector(".ef-condkey")?.value || "poisoned", duration_rounds: parseInt(card.querySelector(".ef-duration")?.value || "2") };
      effects.push({
        type: "on_hit_save",
        stat: card.querySelector(".ef-stat")?.value || "CON",
        dc: parseInt(card.querySelector(".ef-dc")?.value || "12"),
        on_fail,
      });
    }
  });
  return effects;
}

function _setEffects(wrap, effects) {
  const list = wrap.querySelector(".se-effect-list");
  list.innerHTML = "";
  effects.forEach((eff, i) => {
    const card = document.createElement("div");
    card.className = "se-effect-card";
    card.dataset.effectType = eff.type;

    if (eff.type === "extra_damage") {
      card.innerHTML = `
        <div class="se-effect-header">
          <span class="se-effect-badge">⚡ Dodatkowe obrażenia</span>
          <button class="se-effect-remove" type="button" data-idx="${i}">✕</button>
        </div>
        <div class="se-effect-row">
          <label>Kości</label>
          <select class="field-input ef-dice" style="width:80px">${DICE_OPTIONS.map(d=>`<option ${d===eff.dice?"selected":""}>${d}</option>`).join("")}</select>
          <label>Typ</label>
          <select class="field-input ef-dmgtype" style="width:90px">${EFFECT_DAMAGE_TYPES.map(t=>`<option ${t===eff.damage_type?"selected":""}>${t}</option>`).join("")}</select>
        </div>`;
    } else if (eff.type === "on_hit_save") {
      const of = eff.on_fail || {};
      const failIsDmg = of.type === "extra_damage";
      card.innerHTML = `
        <div class="se-effect-header">
          <span class="se-effect-badge">🎲 Test obronny</span>
          <button class="se-effect-remove" type="button" data-idx="${i}">✕</button>
        </div>
        <div class="se-effect-row">
          <label>Stat</label>
          <select class="field-input ef-stat" style="width:70px">${EFFECT_STATS.map(s=>`<option ${s===eff.stat?"selected":""}>${s}</option>`).join("")}</select>
          <label>DC</label>
          <input class="field-input ef-dc" type="number" value="${eff.dc||12}" min="5" max="30" style="width:55px">
        </div>
        <div class="se-effect-row">
          <label>Przy porażce</label>
          <select class="field-input ef-onfail-type" style="width:130px">
            <option value="apply_condition" ${!failIsDmg?"selected":""}>Efekt statusu</option>
            <option value="extra_damage" ${failIsDmg?"selected":""}>Dodatkowe obrażenia</option>
          </select>
        </div>
        <div class="se-effect-row se-onfail-cond" style="${failIsDmg?"display:none":""}">
          <label>Stan</label>
          <select class="field-input ef-condkey" style="width:110px">${EFFECT_CONDITIONS.map(c=>`<option ${c===of.condition_key?"selected":""}>${c}</option>`).join("")}</select>
          <label>Rundy</label>
          <input class="field-input ef-duration" type="number" value="${of.duration_rounds||2}" min="1" max="10" style="width:50px">
        </div>
        <div class="se-effect-row se-onfail-dmg" style="${failIsDmg?"":"display:none"}">
          <label>Kości</label>
          <select class="field-input ef-fail-dice" style="width:80px">${DICE_OPTIONS.map(d=>`<option ${d===of.dice?"selected":""}>${d}</option>`).join("")}</select>
          <label>Typ</label>
          <select class="field-input ef-fail-dmgtype" style="width:90px">${EFFECT_DAMAGE_TYPES.map(t=>`<option ${t===of.damage_type?"selected":""}>${t}</option>`).join("")}</select>
        </div>`;
      card.querySelector(".ef-onfail-type").addEventListener("change", e => {
        const isDmg = e.target.value === "extra_damage";
        card.querySelector(".se-onfail-cond").style.display = isDmg ? "none" : "";
        card.querySelector(".se-onfail-dmg").style.display = isDmg ? "" : "none";
        _notifyChange(wrap);
      });
    }

    card.querySelectorAll("input,select").forEach(el => el.addEventListener("change", () => _notifyChange(wrap)));
    card.querySelector(".se-effect-remove").addEventListener("click", e => {
      const idx = parseInt(e.target.dataset.idx);
      const effs = _readEffects(wrap);
      effs.splice(idx, 1);
      _setEffects(wrap, effs);
      _notifyChange(wrap);
    });
    list.appendChild(card);
  });
}

function _notifyChange(wrap) {
  wrap.dispatchEvent(new Event("change", { bubbles: true }));
}

function _readEffectBuilderValue(wrap) {
  const effects = _readEffects(wrap);
  if (!effects.length) return null;
  return JSON.stringify({ effects });
}

function _setEffectBuilderValue(wrap, jsonStr) {
  if (!jsonStr) { _setEffects(wrap, []); return; }
  try {
    const parsed = typeof jsonStr === "string" ? JSON.parse(jsonStr) : jsonStr;
    _setEffects(wrap, parsed.effects || []);
  } catch { _setEffects(wrap, []); }
}

// ─────────────────────────────────────────────────────────────────────────────

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
  } else if (field.type === "effect_builder") {
    el = _buildEffectBuilder(field);
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
  } else if (el.classList.contains("se-effect-builder")) {
    el.addEventListener("change", update);
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
  if (field.type === "effect_builder") {
    return _readEffectBuilderValue(el);
  }
  return el.value || "";
}

function _renderFormValues() {
  if (!_overlay) return;
  _schemaFields.forEach(field => {
    const row = _overlay.querySelector(`.se-field-row[data-field-key="${field.key}"]`);
    if (!row) return;
    const val = _draft[field.key] ?? "";
    if (field.type === "effect_builder") {
      const eb = row.querySelector(".se-effect-builder");
      if (eb) _setEffectBuilderValue(eb, val || null);
      _updateFieldRow(field.key);
      return;
    }
    const el = row.querySelector("input,select,textarea,div.se-multi-choice");
    if (!el) return;
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
    _updateModeBadge();
    if (_overlay) {
      _overlay.querySelector("#se-messages").innerHTML = "";
      _appendMsg(`Załadowano: "${record.label || key}". Opisz co chcesz zmienić.`, "agent");
    }
  } catch (e) {
    showToast("Błąd ładowania: " + e.message, "error");
  }
}

// ── Mode helpers ──────────────────────────────────────────────────────────────

function _updateModeBadge() {
  const badge = _overlay?.querySelector("#se-mode-badge");
  const input = _overlay?.querySelector("#se-input");
  if (!badge) return;
  const hasContent = Object.values(_draft).some(v => v !== undefined && v !== "" && v !== null);
  if (hasContent) {
    badge.textContent = "🔄 Tryb uzupełniania";
    badge.classList.add("refine");
    if (input) input.placeholder = "Opisz co chcesz zmienić…";
  } else {
    badge.textContent = "✨ Tryb tworzenia";
    badge.classList.remove("refine");
    if (input) input.placeholder = "Opisz rekord który chcesz stworzyć…";
  }
}

function _flashChangedFields(fields) {
  if (!fields?.length || !_overlay) return;
  fields.forEach(key => {
    const row = _overlay.querySelector(`.se-field-row[data-field-key="${key}"]`);
    if (!row) return;
    row.classList.add("se-field-changed");
    setTimeout(() => row.classList.remove("se-field-changed"), 2000);
  });
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
      _lastChangedFields = Array.isArray(resp.changed_fields) ? resp.changed_fields : [];
      _renderFormValues();
      _flashChangedFields(_lastChangedFields);
      _updateSaveBtn();
      _updateModeBadge();
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
    _draft = {}; _existingKey = null; _lastChangedFields = []; _sessionId = _genId();
    if (_overlay) {
      _overlay.querySelector("#se-existing-select").value = "";
      _renderFormValues();
      _updateSaveBtn();
      _updateModeBadge();
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
