import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const TABS = [
  { key: "monitor", label: "🗺 Monitor",   module: "/admin_panel_v2/sections/campaigns.js?v=1" },
  { key: "creator", label: "✨ Kreator",   module: "/admin_panel_v2/sections/designer.js?v=2"  },
  { key: "workshop", label: "🔧 Warsztat", module: null },
];

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content">
      <div class="subtab-bar">
        ${TABS.map((t, i) =>
          `<button class="subtab-btn${i === 0 ? " active" : ""}" data-tab="${t.key}">${t.label}</button>`
        ).join("")}
      </div>
      <div class="subtab-panels" style="flex:1;min-height:0;overflow:hidden">
        ${TABS.map((t, i) =>
          `<div class="subtab-panel${i === 0 ? " active" : ""}" data-tab="${t.key}" style="height:100%;overflow:auto"></div>`
        ).join("")}
      </div>
    </div>`;

  const initialized = new Set();

  const activateTab = async (key) => {
    if (initialized.has(key)) return;
    initialized.add(key);
    const tab    = TABS.find(t => t.key === key);
    const target = panel.querySelector(`.subtab-panel[data-tab="${key}"]`);
    if (!tab || !target) return;
    try {
      if (tab.key === "workshop") {
        await _initCampaignWorkshop(target);
        return;
      }
      const mod = await import(tab.module);
      await mod.init(target);
    } catch (e) {
      target.innerHTML = `<p style="color:var(--accent-red);padding:20px">Błąd ładowania: ${e.message}</p>`;
    }
  };

  panel.querySelectorAll(".subtab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      panel.querySelectorAll(".subtab-btn").forEach(b => b.classList.remove("active"));
      panel.querySelectorAll(".subtab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      panel.querySelector(`.subtab-panel[data-tab="${btn.dataset.tab}"]`).classList.add("active");
      void activateTab(btn.dataset.tab);
    });
  });

  await activateTab("monitor");
}

// ── Campaign Workshop (Task 31) ────────────────────────────────────────────

function _esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function _genId() {
  return "cw-" + Math.random().toString(36).slice(2, 10);
}

async function _initCampaignWorkshop(container) {
  container.innerHTML = `
    <div class="workshop-layout">
      <div class="workshop-chat-col">
        <div class="workshop-header">
          <h2 class="section-heading">🔧 Warsztat Kampanii</h2>
        </div>

        <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
          <label style="font-size:0.82rem;color:var(--text-muted)">Kampania:</label>
          <select id="cw-campaign-select" class="field-input" style="flex:1">
            <option value="">— wybierz kampanię —</option>
          </select>
          <button class="secondary-btn" id="cw-load-btn" type="button" style="font-size:0.78rem">Załaduj</button>
        </div>

        <div class="workshop-messages" id="cw-messages">
          <div class="chat-msg agent"><div class="chat-bubble">Wybierz kampanię i zacznij rozmowę. Mogę analizować plan, proponować zmiany, wykrywać luki fabularne.</div></div>
        </div>
        <div class="workshop-input-row">
          <textarea id="cw-input" class="workshop-textarea" rows="2"
            placeholder="Zapytaj o kampanię lub poproś o zmiany…" maxlength="2000" disabled></textarea>
          <button class="primary-btn" id="cw-send-btn" type="button" disabled>Wyślij</button>
        </div>
      </div>

      <div class="workshop-draft-col" id="cw-changes-col">
        <div class="workshop-draft-header">Proponowane zmiany</div>
        <div id="cw-proposed" style="color:var(--text-muted);font-size:0.82rem;padding:8px">
          Zmiany zaproponowane przez agenta pojawią się tutaj.
        </div>
      </div>
    </div>`;

  let _sessionId = _genId();
  let _campaignId = null;

  // Load campaigns list
  try {
    const data = await adminFetch("/api/campaigns?status=active&limit=50");
    const campaigns = data.campaigns || data || [];
    const sel = container.querySelector("#cw-campaign-select");
    campaigns.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.title || c.id} (${c.character_name || "?"})`;
      sel.appendChild(opt);
    });
  } catch {}

  container.querySelector("#cw-load-btn").addEventListener("click", () => {
    _campaignId = container.querySelector("#cw-campaign-select").value;
    if (!_campaignId) { showToast("Wybierz kampanię.", "error"); return; }
    _sessionId = _genId();
    container.querySelector("#cw-input").disabled = false;
    container.querySelector("#cw-send-btn").disabled = false;
    container.querySelector("#cw-messages").innerHTML =
      `<div class="chat-msg agent"><div class="chat-bubble">Kampania załadowana. Mogę analizować plan, proponować nowe wątki, lub pomóc z zakończeniami. O co pytasz?</div></div>`;
    container.querySelector("#cw-proposed").innerHTML =
      `<span style="color:var(--text-muted);font-size:0.82rem">Brak proponowanych zmian.</span>`;
  });

  async function sendMessage() {
    if (!_campaignId) { showToast("Najpierw załaduj kampanię.", "error"); return; }
    const text = container.querySelector("#cw-input").value.trim();
    if (!text) return;
    container.querySelector("#cw-input").value = "";
    _appendCwMsg(container, text, "user");
    container.querySelector("#cw-send-btn").disabled = true;
    const typing = _appendCwMsg(container, "…", "agent");
    try {
      const resp = await adminFetch(`/api/admin/campaigns/${_campaignId}/workshop/message`, {
        method: "POST",
        body: JSON.stringify({ session_id: _sessionId, message: text }),
      });
      typing.remove();
      _appendCwMsg(container, resp.reply || "—", "agent");
      if (resp.proposed_changes?.length) _renderProposedChanges(container, resp.proposed_changes, _sessionId, _campaignId);
    } catch (e) {
      typing.remove();
      _appendCwMsg(container, `Błąd: ${e.message}`, "agent error");
    } finally {
      container.querySelector("#cw-send-btn").disabled = false;
    }
  }

  container.querySelector("#cw-send-btn").addEventListener("click", sendMessage);
  container.querySelector("#cw-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}

function _appendCwMsg(container, text, type) {
  const messages = container.querySelector("#cw-messages");
  const div = document.createElement("div");
  div.className = `chat-msg ${type}`;
  div.innerHTML = `<div class="chat-bubble">${_esc(text).replace(/\n/g, "<br>")}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function _renderProposedChanges(container, changes, sessionId, campaignId) {
  const area = container.querySelector("#cw-proposed");
  area.innerHTML = "";
  changes.forEach((ch, i) => {
    const row = document.createElement("div");
    row.className = "se-change-row";
    row.style.marginBottom = "8px";
    row.innerHTML = `
      <div class="se-change-info">
        <strong>${_esc(ch.field)}</strong><br>
        <span style="color:var(--text-muted);font-size:0.76rem">Było: ${_esc(String(ch.old_value ?? "—"))}</span><br>
        <span style="color:#66ff99;font-size:0.82rem">Będzie: ${_esc(String(ch.new_value ?? "?"))}</span>
        ${ch.reason ? `<div style="color:var(--text-muted);font-size:0.74rem;margin-top:2px">${_esc(ch.reason)}</div>` : ""}
      </div>
      <button class="primary-btn se-apply-btn" type="button" data-idx="${i}" style="font-size:0.76rem;padding:4px 8px;margin-top:4px">Zatwierdź</button>`;

    row.querySelector(".se-apply-btn").addEventListener("click", async () => {
      try {
        await adminFetch(`/api/admin/campaigns/${campaignId}/workshop/apply`, {
          method: "POST",
          body: JSON.stringify({ session_id: sessionId, change_index: i }),
        });
        showToast("Zmiana zastosowana.", "success");
        row.querySelector(".se-apply-btn").textContent = "✓ Zastosowano";
        row.querySelector(".se-apply-btn").disabled = true;
      } catch (e) { showToast(e.message, "error"); }
    });
    area.appendChild(row);
  });
}
