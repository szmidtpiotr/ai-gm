/**
 * Smart Entry Agent overlay — Phase 08 Task 33
 * Import and call openSmartEntry(table?) from any admin section.
 */
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

let _overlay = null;
let _sessionId = null;
let _currentTable = null;

function _genId() {
  return "se-" + Math.random().toString(36).slice(2, 10);
}

function _esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

const TABLE_LABELS = {
  game_config_weapons: "Broń",
  game_config_items: "Przedmioty",
  game_config_consumables: "Konsumable",
  game_config_enemies: "Wrogowie",
};

function _ensureOverlay() {
  if (_overlay) return _overlay;

  const el = document.createElement("div");
  el.id = "smart-entry-overlay";
  el.className = "smart-entry-overlay";
  el.innerHTML = `
    <div class="smart-entry-panel">
      <div class="smart-entry-header">
        <span class="smart-entry-title">🤖 Asystent kreacji</span>
        <button class="smart-entry-close" id="se-close-btn" type="button">✕ Zamknij</button>
      </div>
      <div class="smart-entry-body">
        <!-- LEFT: chat + questions -->
        <div class="smart-entry-chat-col">
          <div class="smart-entry-messages" id="se-messages"></div>
          <div id="se-questions" class="se-questions-area"></div>
          <div class="smart-entry-input-row">
            <input type="text" id="se-input" class="field-input" placeholder="Wpisz lub wybierz opcję…" maxlength="500" />
            <button class="primary-btn" id="se-send-btn" type="button">Wyślij</button>
          </div>
        </div>
        <!-- RIGHT: draft preview -->
        <div class="smart-entry-preview-col">
          <div class="se-preview-header">Podgląd rekordu</div>
          <div id="se-draft-preview" class="se-draft-preview-empty">Szkic pojawi się po udzieleniu odpowiedzi.</div>
          <div id="se-proposed-changes"></div>
          <div class="se-preview-actions">
            <button class="primary-btn" id="se-save-btn" type="button" style="display:none;width:100%">✅ Zapisz</button>
          </div>
        </div>
      </div>
    </div>`;

  document.body.appendChild(el);
  _overlay = el;

  el.querySelector("#se-close-btn").addEventListener("click", closeSmartEntry);
  el.addEventListener("click", e => { if (e.target === el) closeSmartEntry(); });

  const sendBtn = el.querySelector("#se-send-btn");
  const input = el.querySelector("#se-input");
  sendBtn.addEventListener("click", _send);
  input.addEventListener("keydown", e => { if (e.key === "Enter") _send(); });

  el.querySelector("#se-save-btn").addEventListener("click", _save);

  return el;
}

async function _send() {
  const overlay = _overlay;
  const input = overlay.querySelector("#se-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  _appendMsg(text, "user");
  await _callAgent({ message: text });
}

async function _answerQuestion(questionId, value) {
  _appendMsg(`${questionId}: ${value}`, "user");
  await _callAgent({ answer: { question_id: questionId, value } });
}

async function _callAgent(extra = {}) {
  const overlay = _overlay;
  const sendBtn = overlay.querySelector("#se-send-btn");
  sendBtn.disabled = true;
  const typing = _appendMsg("…", "agent");

  try {
    const body = { session_id: _sessionId, ...extra };
    if (_currentTable) body.table = _currentTable;

    const resp = await adminFetch("/api/admin/smart-entry/message", {
      method: "POST",
      body: JSON.stringify(body),
    });

    typing.remove();
    if (resp.reply) _appendMsg(resp.reply, "agent");
    if (resp.questions) _renderQuestions(resp.questions);
    else overlay.querySelector("#se-questions").innerHTML = "";
    if (resp.draft) _renderDraft(resp.draft);
    if (resp.proposed_changes?.length) _renderChanges(resp.proposed_changes);
    if (resp.ready_to_save) {
      overlay.querySelector("#se-save-btn").style.display = "";
    }
    if (resp.db_context) {
      const info = JSON.stringify(resp.db_context, null, 2);
      _appendMsg(`Znaleziono w DB:\n${info}`, "agent info");
    }
  } catch (e) {
    typing.remove();
    _appendMsg(`Błąd: ${e.message}`, "agent error");
  } finally {
    sendBtn.disabled = false;
  }
}

async function _save() {
  try {
    const resp = await adminFetch("/api/admin/smart-entry/save", {
      method: "POST",
      body: JSON.stringify({ session_id: _sessionId }),
    });
    showToast(`Zapisano: ${resp.key}`, "success");
    _appendMsg(`✓ Rekord "${resp.key}" zapisany.`, "agent success");
    _overlay.querySelector("#se-save-btn").style.display = "none";
    _sessionId = _genId();
  } catch (e) {
    showToast(e.message || "Błąd zapisu.", "error");
  }
}

function _appendMsg(text, type) {
  const messages = _overlay.querySelector("#se-messages");
  const div = document.createElement("div");
  div.className = `chat-msg ${type}`;
  div.innerHTML = `<div class="chat-bubble">${_esc(text).replace(/\n/g, "<br>")}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function _renderQuestions(questions) {
  const area = _overlay.querySelector("#se-questions");
  area.innerHTML = "";
  questions.forEach(q => {
    const wrap = document.createElement("div");
    wrap.className = "se-question-block";
    wrap.innerHTML = `<div class="se-question-label">${_esc(q.question)}</div>`;

    if (q.type === "single_choice" || q.type === "multi_choice") {
      const optRow = document.createElement("div");
      optRow.className = "se-options-row";
      q.options.forEach(opt => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "se-option-card";
        card.innerHTML = `
          <div class="se-opt-label">${_esc(opt.label)}</div>
          ${opt.description ? `<div class="se-opt-desc">${_esc(opt.description)}</div>` : ""}
          ${opt.preview ? `<pre class="se-opt-preview">${_esc(opt.preview)}</pre>` : ""}`;
        card.addEventListener("click", () => {
          area.innerHTML = "";
          _answerQuestion(q.id, opt.label);
        });
        optRow.appendChild(card);
      });
      wrap.appendChild(optRow);
    } else if (q.type === "boolean") {
      ["Tak", "Nie"].forEach(v => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "se-option-card se-bool-btn";
        btn.textContent = v;
        btn.addEventListener("click", () => {
          area.innerHTML = "";
          _answerQuestion(q.id, v === "Tak" ? "true" : "false");
        });
        wrap.appendChild(btn);
      });
    } else if (q.type === "number") {
      const row = document.createElement("div");
      row.innerHTML = `<input type="number" class="field-input" id="se-num-${_esc(q.id)}"
        min="${q.min ?? 0}" max="${q.max ?? 9999}" step="${q.step ?? 1}" style="width:100px" />
        <button type="button" class="primary-btn se-num-ok" style="margin-left:8px">OK</button>`;
      row.querySelector(".se-num-ok").addEventListener("click", () => {
        const val = row.querySelector("input").value;
        area.innerHTML = "";
        _answerQuestion(q.id, val);
      });
      wrap.appendChild(row);
    } else {
      // text
      const row = document.createElement("div");
      row.innerHTML = `<input type="text" class="field-input" id="se-txt-${_esc(q.id)}" style="flex:1" maxlength="200" />
        <button type="button" class="primary-btn se-txt-ok" style="margin-left:8px">OK</button>`;
      row.querySelector(".se-txt-ok").addEventListener("click", () => {
        const val = row.querySelector("input").value.trim();
        if (!val) return;
        area.innerHTML = "";
        _answerQuestion(q.id, val);
      });
      wrap.appendChild(row);
    }

    area.appendChild(wrap);
  });
}

function _renderDraft(draft) {
  const preview = _overlay.querySelector("#se-draft-preview");
  let html = `<div class="draft-fields">`;
  for (const [k, v] of Object.entries(draft)) {
    const val = typeof v === "object" ? JSON.stringify(v) : String(v ?? "");
    html += `<div class="draft-field"><span class="draft-key">${_esc(k)}</span><span class="draft-val">${_esc(val)}</span></div>`;
  }
  html += `</div>`;
  preview.innerHTML = html;
  preview.className = "se-draft-preview";
}

function _renderChanges(changes) {
  const area = _overlay.querySelector("#se-proposed-changes");
  area.innerHTML = `<div class="se-changes-header">Proponowane zmiany</div>`;
  changes.forEach((ch, i) => {
    const row = document.createElement("div");
    row.className = "se-change-row";
    row.innerHTML = `
      <div class="se-change-info">
        <strong>${_esc(ch.field)}</strong>: ${_esc(String(ch.old ?? "—"))} → <strong>${_esc(String(ch.new_value ?? ch.new ?? "?"))}</strong>
        ${ch.reason ? `<div style="color:var(--text-muted);font-size:0.76rem">${_esc(ch.reason)}</div>` : ""}
      </div>
      <button class="primary-btn se-apply-btn" type="button" data-idx="${i}" style="font-size:0.76rem;padding:3px 8px">Zatwierdź</button>`;
    row.querySelector(".se-apply-btn").addEventListener("click", async () => {
      try {
        await adminFetch("/api/admin/smart-entry/apply-change", {
          method: "POST",
          body: JSON.stringify({ session_id: _sessionId, change_index: i }),
        });
        showToast("Zmiana zastosowana.", "success");
        row.querySelector(".se-apply-btn").textContent = "✓";
        row.querySelector(".se-apply-btn").disabled = true;
      } catch (e) { showToast(e.message, "error"); }
    });
    area.appendChild(row);
  });
}

// ── Public API ──────────────────────────────────────────────────────────────

export function openSmartEntry(table = null) {
  _sessionId = _genId();
  _currentTable = table;
  const overlay = _ensureOverlay();
  overlay.querySelector("#se-messages").innerHTML = "";
  overlay.querySelector("#se-questions").innerHTML = "";
  overlay.querySelector("#se-proposed-changes").innerHTML = "";
  overlay.querySelector("#se-draft-preview").innerHTML = "Szkic pojawi się po udzieleniu odpowiedzi.";
  overlay.querySelector("#se-draft-preview").className = "se-draft-preview-empty";
  overlay.querySelector("#se-save-btn").style.display = "none";
  overlay.classList.add("visible");

  const tableLabel = TABLE_LABELS[table] || table || "zawartości";
  _appendMsg(
    table
      ? `Cześć! Pomogę Ci stworzyć lub edytować ${tableLabel}. Opisz co chcesz dodać lub zmienić.`
      : "Cześć! Opisz co chcesz stworzyć — broń, przedmiot, wroga, lub coś innego.",
    "agent"
  );
}

export function closeSmartEntry() {
  if (_overlay) _overlay.classList.remove("visible");
}
