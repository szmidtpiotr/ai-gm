/**
 * Workshops section — Phase 08
 * Tab 1: Warsztat Pomysłów (Ideas Workshop — Task 30)
 * Tab 2: Bank Pomysłów (Ideas Bank browser)
 */
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

let _sessionId = null;
let _currentDraft = null;

function _genSessionId() {
  return "ws-" + Math.random().toString(36).slice(2, 10) + "-" + Date.now();
}

function _esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

const CATEGORY_LABELS = {
  seed: "Kampania",
  scene_module: "Moduł sceny",
  npc_concept: "Postać NPC",
  location: "Lokacja",
  plot_twist: "Zwrot akcji",
  encounter: "Starcie",
};

const CATEGORY_ICONS = {
  seed: "📖",
  scene_module: "🎬",
  npc_concept: "👤",
  location: "🗺",
  plot_twist: "🔀",
  encounter: "⚔",
};

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content">
      <div class="subtab-bar">
        <button class="subtab-btn active" data-tab="workshop">💡 Warsztat Pomysłów</button>
        <button class="subtab-btn" data-tab="bank">📚 Bank Pomysłów</button>
      </div>
      <div class="subtab-panels">
        <div class="subtab-panel active" data-tab="workshop"></div>
        <div class="subtab-panel" data-tab="bank"></div>
      </div>
    </div>`;

  panel.querySelectorAll(".subtab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      panel.querySelectorAll(".subtab-btn").forEach(b => b.classList.remove("active"));
      panel.querySelectorAll(".subtab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      panel.querySelector(`.subtab-panel[data-tab="${tab}"]`).classList.add("active");
      if (tab === "bank") _initBank(panel.querySelector('[data-tab="bank"]'));
    });
  });

  _initWorkshop(panel.querySelector('[data-tab="workshop"]'));
}

// ── Ideas Workshop ──────────────────────────────────────────────────────────

function _initWorkshop(container) {
  _sessionId = _genSessionId();
  _currentDraft = null;

  container.innerHTML = `
    <div class="workshop-layout">
      <div class="workshop-chat-col">
        <div class="workshop-header">
          <h2 class="section-heading">💡 Warsztat Pomysłów</h2>
          <button class="secondary-btn" id="workshop-new-btn" type="button" style="font-size:0.78rem">↺ Nowy pomysł</button>
        </div>
        <div class="workshop-messages" id="workshop-messages">
          <div class="chat-msg agent">
            <div class="chat-bubble">
              Cześć! Opisz swój pomysł na kampanię, scenę, postać lub lokację. Mogę też pomóc ulepszyć istniejący pomysł.
            </div>
          </div>
        </div>
        <div class="workshop-input-row">
          <textarea id="workshop-input" class="workshop-textarea" rows="2"
            placeholder="Opisz pomysł lub odpowiedz na pytanie agenta…" maxlength="2000"></textarea>
          <button class="primary-btn" id="workshop-send-btn" type="button">Wyślij</button>
        </div>
      </div>
      <div class="workshop-draft-col" id="workshop-draft-col">
        <div class="workshop-draft-header">Szkic pomysłu</div>
        <div id="workshop-draft-preview" class="workshop-draft-empty">
          Tutaj pojawi się szkic gdy agent go zaproponuje.
        </div>
        <button class="primary-btn" id="workshop-save-btn" type="button" style="display:none;width:100%;margin-top:12px">
          💾 Zapisz do Banku
        </button>
      </div>
    </div>`;

  const messages = container.querySelector("#workshop-messages");
  const input = container.querySelector("#workshop-input");
  const sendBtn = container.querySelector("#workshop-send-btn");
  const saveBtn = container.querySelector("#workshop-save-btn");
  const newBtn = container.querySelector("#workshop-new-btn");

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    _appendMsg(messages, text, "user");
    sendBtn.disabled = true;

    const typing = _appendMsg(messages, "…", "agent");
    try {
      const resp = await adminFetch("/api/admin/ideas/workshop/message", {
        method: "POST",
        body: JSON.stringify({ session_id: _sessionId, message: text }),
      });
      typing.remove();
      _appendMsg(messages, resp.reply || "—", "agent");
      if (resp.draft) {
        _currentDraft = resp.draft;
        _renderDraft(container, resp.draft);
      }
      if (resp.ready_to_save) {
        saveBtn.style.display = "";
      }
    } catch (e) {
      typing.remove();
      _appendMsg(messages, `Błąd: ${e.message}`, "agent error");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  saveBtn.addEventListener("click", async () => {
    try {
      const resp = await adminFetch("/api/admin/ideas/save", {
        method: "POST",
        body: JSON.stringify({ session_id: _sessionId }),
      });
      showToast("Pomysł zapisany do Banku.", "success");
      saveBtn.style.display = "none";
      _appendMsg(messages, `✓ Pomysł "${_currentDraft?.title || "?"}" zapisany do Banku Pomysłów.`, "agent success");
      _sessionId = _genSessionId();
      _currentDraft = null;
    } catch (e) {
      showToast(e.message || "Błąd zapisu.", "error");
    }
  });

  newBtn.addEventListener("click", () => {
    _sessionId = _genSessionId();
    _currentDraft = null;
    messages.innerHTML = `<div class="chat-msg agent"><div class="chat-bubble">Nowa sesja. Opisz swój pomysł!</div></div>`;
    saveBtn.style.display = "none";
    container.querySelector("#workshop-draft-preview").innerHTML = `<span class="workshop-draft-empty">Tutaj pojawi się szkic gdy agent go zaproponuje.</span>`;
  });
}

function _appendMsg(container, text, type) {
  const div = document.createElement("div");
  div.className = `chat-msg ${type}`;
  div.innerHTML = `<div class="chat-bubble">${_esc(text).replace(/\n/g, "<br>")}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function _renderDraft(container, draft) {
  const preview = container.querySelector("#workshop-draft-preview");
  const category = draft.category || "unknown";
  const icon = CATEGORY_ICONS[category] || "💡";
  const label = CATEGORY_LABELS[category] || category;

  let fields = "";
  const skip = new Set(["category"]);
  for (const [k, v] of Object.entries(draft)) {
    if (skip.has(k)) continue;
    const val = typeof v === "object" ? JSON.stringify(v, null, 2) : String(v ?? "");
    fields += `<div class="draft-field"><span class="draft-key">${_esc(k)}</span><span class="draft-val">${_esc(val)}</span></div>`;
  }

  preview.innerHTML = `
    <div class="draft-category-badge">${icon} ${_esc(label)}</div>
    <div class="draft-title">${_esc(draft.title || "—")}</div>
    <div class="draft-fields">${fields}</div>`;
}

// ── Ideas Bank ──────────────────────────────────────────────────────────────

async function _initBank(container) {
  container.innerHTML = `
    <div class="bank-toolbar">
      <h2 class="section-heading">📚 Bank Pomysłów</h2>
      <div class="bank-filters">
        <select id="bank-cat-filter" class="field-input" style="width:140px">
          <option value="">Wszystkie kategorie</option>
          ${Object.entries(CATEGORY_LABELS).map(([k,v]) => `<option value="${k}">${v}</option>`).join("")}
        </select>
        <select id="bank-rating-filter" class="field-input" style="width:120px">
          <option value="0">Min. ocena: 0★</option>
          <option value="3">Min. ocena: 3★</option>
          <option value="4">Min. ocena: 4★</option>
          <option value="5">Tylko 5★</option>
        </select>
        <button class="secondary-btn" id="bank-refresh-btn" type="button">↻ Odśwież</button>
      </div>
    </div>
    <div id="bank-grid" class="bank-grid">
      <div class="camp-loading">Ładowanie…</div>
    </div>`;

  async function loadBank() {
    const cat = container.querySelector("#bank-cat-filter").value;
    const rating = container.querySelector("#bank-rating-filter").value;
    const grid = container.querySelector("#bank-grid");
    grid.innerHTML = `<div class="camp-loading">Ładowanie…</div>`;
    try {
      const params = new URLSearchParams({ active_only: "true", min_rating: rating });
      if (cat) params.set("category", cat);
      const data = await adminFetch(`/api/admin/ideas?${params}`);
      const items = data.items || [];
      if (!items.length) {
        grid.innerHTML = `<p class="section-note">Brak pomysłów w banku. Utwórz pierwszy w Warsztacie.</p>`;
        return;
      }
      grid.innerHTML = "";
      items.forEach(idea => grid.appendChild(_renderBankCard(idea, loadBank)));
    } catch (e) {
      grid.innerHTML = `<p style="color:var(--accent-red)">${_esc(e.message)}</p>`;
    }
  }

  container.querySelector("#bank-refresh-btn").addEventListener("click", loadBank);
  container.querySelector("#bank-cat-filter").addEventListener("change", loadBank);
  container.querySelector("#bank-rating-filter").addEventListener("change", loadBank);
  await loadBank();
}

function _renderBankCard(idea, onRefresh) {
  const card = document.createElement("div");
  card.className = "bank-card";
  const icon = CATEGORY_ICONS[idea.category] || "💡";
  const label = CATEGORY_LABELS[idea.category] || idea.category;
  const stars = "★".repeat(idea.quality_rating || 0) + "☆".repeat(5 - (idea.quality_rating || 0));

  card.innerHTML = `
    <div class="bank-card-header">
      <span class="bank-card-category">${icon} ${_esc(label)}</span>
      <span class="bank-card-stars" title="Jakość">${stars}</span>
    </div>
    <div class="bank-card-title">${_esc(idea.title || "Bez tytułu")}</div>
    <div class="bank-card-premise">${_esc((idea.structured_data?.premise || idea.structured_data?.setup || "").slice(0, 120))}${(idea.structured_data?.premise || "").length > 120 ? "…" : ""}</div>
    <div class="bank-card-meta">
      Użyto: ${idea.times_used || 0}× &nbsp;|&nbsp;
      ${new Date(idea.created_at || Date.now()).toLocaleDateString("pl-PL")}
    </div>
    <div class="bank-card-actions">
      <select class="field-input bank-rating-select" style="width:80px" title="Oceń">
        ${[0,1,2,3,4,5].map(n => `<option value="${n}" ${n === (idea.quality_rating||0) ? "selected":""}>★ ${n}</option>`).join("")}
      </select>
      <button class="secondary-btn danger-outline bank-delete-btn" style="font-size:0.74rem;padding:3px 8px">Usuń</button>
    </div>`;

  card.querySelector(".bank-rating-select").addEventListener("change", async e => {
    try {
      await adminFetch(`/api/admin/ideas/${idea.id}`, {
        method: "PATCH",
        body: JSON.stringify({ quality_rating: parseInt(e.target.value) }),
      });
      showToast("Ocena zapisana.", "success");
    } catch (err) { showToast(err.message, "error"); }
  });

  card.querySelector(".bank-delete-btn").addEventListener("click", async () => {
    if (!confirm(`Usunąć "${idea.title}"?`)) return;
    try {
      await adminFetch(`/api/admin/ideas/${idea.id}`, { method: "DELETE" });
      showToast("Usunięto.", "success");
      onRefresh();
    } catch (err) { showToast(err.message, "error"); }
  });

  return card;
}
