import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  title: "Monitor Kampanii",
  noData: "Brak kampanii",
  loading: "Ładowanie kampanii…",
  owner: "Gracz",
  character: "Postać",
  location: "Lokacja",
  status: "Status",
  turns: "Tury",
  scene: "Scena",
  lastActivity: "Ostatnia aktywność",
  statusActive: "aktywna",
  statusEnded: "zakończona",
  statusDead: "zginął",
  hpLabel: "HP",
  arcLabel: "Łuk",
  conditionsLabel: "Stany",
  lastPlayerMsg: "Ostatni ruch gracza",
  lastGmMsg: "Ostatnia odpowiedź GM",
  advanceScene: "Następna scena",
  regenPlan: "Regeneruj plan",
  regenSummary: "Regeneruj podsumowanie",
  endCampaign: "Zakończ kampanię",
  gmPlanTitle: "Plan GM",
  turnsTitle: "Ostatnie tury",
  noGmPlan: "Brak planu GM",
  noTurns: "Brak tur",
  confirmAdvance: "Przejść do następnej sceny?",
  confirmRegen: "Regenerować plan GM? To zajmie chwilę.",
  confirmEnd: "Na pewno zakończyć kampanię?",
};

let refreshInterval = null;

export async function init(panel) {
  panel.innerHTML = `
    <div class="campaigns-monitor">
      <div class="campaigns-toolbar">
        <h2 class="section-heading">${LABELS.title}</h2>
        <div class="campaigns-toolbar-right">
          <select id="camp-status-filter" class="field-input" style="width:140px">
            <option value="">Wszystkie</option>
            <option value="active" selected>Aktywne</option>
            <option value="ended">Zakończone</option>
          </select>
          <button id="camp-refresh-btn" class="secondary-btn" type="button">↻ Odśwież</button>
        </div>
      </div>
      <div id="camp-grid" class="campaigns-grid">
        <div class="camp-loading">${LABELS.loading}</div>
      </div>
    </div>

    <!-- Campaign Detail Modal -->
    <div id="camp-modal" class="camp-modal-overlay" style="display:none">
      <div class="camp-modal-box">
        <div class="camp-modal-header">
          <h3 id="camp-modal-title">—</h3>
          <button id="camp-modal-close" class="icon-btn" type="button" title="Zamknij">✕</button>
        </div>
        <div class="camp-modal-tabs">
          <button class="camp-tab-btn active" data-tab="overview" type="button">Przegląd</button>
          <button class="camp-tab-btn" data-tab="plan" type="button">Plan GM</button>
          <button class="camp-tab-btn" data-tab="turns" type="button">Tury</button>
        </div>
        <div class="camp-modal-body" id="camp-modal-body">
        </div>
        <div class="camp-modal-actions" id="camp-modal-actions">
        </div>
      </div>
    </div>
  `;

  const grid = panel.querySelector("#camp-grid");
  const modal = panel.querySelector("#camp-modal");
  const modalTitle = panel.querySelector("#camp-modal-title");
  const modalBody = panel.querySelector("#camp-modal-body");
  const modalActions = panel.querySelector("#camp-modal-actions");
  const statusFilter = panel.querySelector("#camp-status-filter");

  let campaigns = [];
  let currentCampaign = null;
  let currentTab = "overview";

  // ── fetch & render grid ──
  async function load() {
    grid.innerHTML = `<div class="camp-loading">${LABELS.loading}</div>`;
    try {
      const data = await adminFetch("/api/admin/campaigns/live");
      campaigns = data.items || [];
      renderGrid();
    } catch (e) {
      grid.innerHTML = `<div class="camp-loading" style="color:var(--accent-red)">${e.message}</div>`;
    }
  }

  function renderGrid() {
    const filter = statusFilter.value;
    const filtered = filter ? campaigns.filter(c => c.status === filter) : campaigns;

    if (!filtered.length) {
      grid.innerHTML = `<div class="camp-loading">${LABELS.noData}</div>`;
      return;
    }

    grid.innerHTML = filtered.map(c => campCardHtml(c)).join("");

    filtered.forEach(c => {
      const card = grid.querySelector(`.camp-card[data-id="${c.id}"]`);
      if (card) card.addEventListener("click", () => openModal(c));
    });
  }

  function campCardHtml(c) {
    const hp = c.char_current_hp ?? "?";
    const maxHp = c.char_max_hp ?? "?";
    const hpPct = (c.char_max_hp && c.char_current_hp != null)
      ? Math.max(0, Math.min(100, Math.round((c.char_current_hp / c.char_max_hp) * 100)))
      : null;
    const hpColor = hpPct == null ? "#6b7280"
      : hpPct > 60 ? "var(--accent-green)"
      : hpPct > 25 ? "#f59e0b"
      : "var(--accent-red)";

    const statusBadge = c.status === "active"
      ? `<span class="badge badge-green">${LABELS.statusActive}</span>`
      : c.death_reason
        ? `<span class="badge badge-red">${LABELS.statusDead}</span>`
        : `<span class="badge badge-muted">${LABELS.statusEnded}</span>`;

    const conditions = Array.isArray(c.char_conditions) && c.char_conditions.length
      ? `<div class="camp-conditions">${c.char_conditions.map(cond =>
          `<span class="badge badge-muted" style="font-size:0.65rem">${typeof cond === "string" ? cond : (cond.name || cond.id || "?")}</span>`
        ).join(" ")}</div>`
      : "";

    const sceneStr = c.scene_total
      ? `<span class="camp-meta-val">${c.scene_current}/${c.scene_total}</span>`
      : `<span class="camp-meta-val muted">—</span>`;

    const lastAt = c.last_turn_at
      ? new Date(c.last_turn_at + "Z").toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" })
      : "—";

    const snippet = c.last_turn_player
      ? `<div class="camp-snippet">${escHtml(c.last_turn_player.substring(0, 120))}${c.last_turn_player.length > 120 ? "…" : ""}</div>`
      : "";

    return `
      <div class="camp-card" data-id="${c.id}" tabindex="0" role="button" aria-label="${escHtml(c.title)}">
        <div class="camp-card-header">
          <span class="camp-title">${escHtml(c.title)}</span>
          ${statusBadge}
        </div>
        <div class="camp-card-body">
          <div class="camp-char-row">
            <span class="camp-char-name">${escHtml(c.char_name || "—")}</span>
            ${c.char_archetype ? `<span class="badge badge-muted" style="font-size:0.65rem">${escHtml(c.char_archetype)}</span>` : ""}
          </div>
          ${hpPct !== null ? `
            <div class="camp-hp-bar-wrap">
              <div class="camp-hp-bar" style="width:${hpPct}%;background:${hpColor}"></div>
            </div>
            <div class="camp-hp-label" style="color:${hpColor}">${LABELS.hpLabel}: ${hp}/${maxHp}</div>
          ` : ""}
          ${conditions}
          <div class="camp-meta-grid">
            <span class="camp-meta-key">${LABELS.owner}:</span>
            <span class="camp-meta-val">${escHtml(c.owner_username || "—")}</span>
            <span class="camp-meta-key">${LABELS.location}:</span>
            <span class="camp-meta-val">${escHtml(c.char_location || "—")}</span>
            <span class="camp-meta-key">${LABELS.scene}:</span>
            ${sceneStr}
            <span class="camp-meta-key">${LABELS.turns}:</span>
            <span class="camp-meta-val">${c.turn_count ?? 0}</span>
            <span class="camp-meta-key">${LABELS.lastActivity}:</span>
            <span class="camp-meta-val">${lastAt}</span>
          </div>
          ${snippet}
        </div>
      </div>
    `;
  }

  // ── modal ──
  async function openModal(c) {
    currentCampaign = c;
    currentTab = "overview";
    modalTitle.textContent = c.title;
    modal.style.display = "flex";
    document.body.style.overflow = "hidden";

    panel.querySelectorAll(".camp-tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === currentTab));
    await renderModalTab();
  }

  function closeModal() {
    modal.style.display = "none";
    document.body.style.overflow = "";
    currentCampaign = null;
  }

  async function renderModalTab() {
    if (!currentCampaign) return;
    const c = currentCampaign;

    if (currentTab === "overview") {
      renderOverviewTab(c);
    } else if (currentTab === "plan") {
      await renderPlanTab(c);
    } else if (currentTab === "turns") {
      await renderTurnsTab(c);
    }

    renderModalActions(c);
  }

  function renderOverviewTab(c) {
    const hp = c.char_current_hp ?? "?";
    const maxHp = c.char_max_hp ?? "?";
    const hpPct = (c.char_max_hp && c.char_current_hp != null)
      ? Math.max(0, Math.min(100, Math.round((c.char_current_hp / c.char_max_hp) * 100)))
      : null;
    const hpColor = hpPct == null ? "#6b7280"
      : hpPct > 60 ? "var(--accent-green)"
      : hpPct > 25 ? "#f59e0b"
      : "var(--accent-red)";

    const lastAt = c.last_turn_at
      ? new Date(c.last_turn_at + "Z").toLocaleString("pl-PL", { dateStyle: "medium", timeStyle: "short" })
      : "—";

    const conditions = Array.isArray(c.char_conditions) && c.char_conditions.length
      ? c.char_conditions.map(cond => `<span class="badge badge-muted">${escHtml(typeof cond === "string" ? cond : (cond.name || cond.id || "?"))}</span>`).join(" ")
      : `<span class="muted">brak</span>`;

    const sceneStr = c.scene_total
      ? `${c.scene_current} / ${c.scene_total}${c.arc_title ? ` — ${escHtml(c.arc_title)}` : ""}`
      : "—";

    modalBody.innerHTML = `
      <div class="camp-overview-grid">
        <div class="camp-info-block">
          <div class="camp-info-label">Postać</div>
          <div class="camp-info-val">${escHtml(c.char_name || "—")} ${c.char_archetype ? `<span class="badge badge-muted">${escHtml(c.char_archetype)}</span>` : ""}</div>
        </div>
        <div class="camp-info-block">
          <div class="camp-info-label">Gracz</div>
          <div class="camp-info-val">${escHtml(c.owner_username || "—")}</div>
        </div>
        <div class="camp-info-block">
          <div class="camp-info-label">Status</div>
          <div class="camp-info-val">${c.status === "active" ? `<span class="badge badge-green">${LABELS.statusActive}</span>` : `<span class="badge badge-muted">${LABELS.statusEnded}</span>`}</div>
        </div>
        <div class="camp-info-block">
          <div class="camp-info-label">Lokacja</div>
          <div class="camp-info-val">${escHtml(c.char_location || "—")}</div>
        </div>
        ${hpPct !== null ? `
        <div class="camp-info-block" style="grid-column: span 2">
          <div class="camp-info-label">HP</div>
          <div class="camp-info-val">
            <div class="camp-hp-bar-wrap" style="height:8px;margin-bottom:4px">
              <div class="camp-hp-bar" style="width:${hpPct}%;background:${hpColor};height:8px"></div>
            </div>
            <span style="color:${hpColor}">${hp} / ${maxHp}</span>
          </div>
        </div>
        ` : ""}
        <div class="camp-info-block" style="grid-column: span 2">
          <div class="camp-info-label">Stany</div>
          <div class="camp-info-val">${conditions}</div>
        </div>
        <div class="camp-info-block">
          <div class="camp-info-label">Scena</div>
          <div class="camp-info-val">${sceneStr}</div>
        </div>
        <div class="camp-info-block">
          <div class="camp-info-label">Tury łącznie</div>
          <div class="camp-info-val">${c.turn_count ?? 0}</div>
        </div>
        <div class="camp-info-block" style="grid-column: span 2">
          <div class="camp-info-label">Ostatnia aktywność</div>
          <div class="camp-info-val">${lastAt}</div>
        </div>
        ${c.last_turn_player ? `
        <div class="camp-info-block" style="grid-column: span 2">
          <div class="camp-info-label">${LABELS.lastPlayerMsg}</div>
          <div class="camp-info-val camp-turn-text">${escHtml(c.last_turn_player)}</div>
        </div>
        ` : ""}
        ${c.last_turn_gm ? `
        <div class="camp-info-block" style="grid-column: span 2">
          <div class="camp-info-label">${LABELS.lastGmMsg}</div>
          <div class="camp-info-val camp-turn-text">${escHtml(c.last_turn_gm)}</div>
        </div>
        ` : ""}
      </div>
    `;
  }

  async function renderPlanTab(c) {
    modalBody.innerHTML = `<div class="camp-loading">Ładowanie planu GM…</div>`;
    try {
      const data = await adminFetch(`/api/admin/campaigns/${c.id}/gm-plan`);
      const plan = data.gm_plan_json;

      if (!plan || typeof plan !== "object") {
        modalBody.innerHTML = `<div class="camp-loading muted">${LABELS.noGmPlan}</div>`;
        return;
      }

      const arcs = plan.arcs || {};
      const activeArcId = plan.active_arc_id;
      const arcEntries = Object.entries(arcs);

      if (!arcEntries.length) {
        modalBody.innerHTML = `<div class="camp-loading muted">${LABELS.noGmPlan}</div>`;
        return;
      }

      modalBody.innerHTML = arcEntries.map(([arcId, arc]) => {
        const isActive = arcId === activeArcId;
        const scenes = arc.scene_goals || [];
        const sceneHtml = scenes.map((sg, i) => {
          if (typeof sg === "string") {
            return `<div class="camp-scene-item">${i + 1}. ${escHtml(sg)}</div>`;
          }
          const done = sg.status === "completed";
          return `<div class="camp-scene-item ${done ? "camp-scene-done" : ""}">
            ${done ? "✓" : `${i + 1}.`} ${escHtml(sg.text || sg.description || sg.goal || JSON.stringify(sg))}
          </div>`;
        }).join("");

        return `
          <div class="camp-arc-block ${isActive ? "camp-arc-active" : ""}">
            <div class="camp-arc-header">
              ${isActive ? `<span class="badge badge-green" style="font-size:0.65rem">aktywny</span>` : ""}
              <span class="camp-arc-title">${escHtml(arc.title || arcId)}</span>
              <span class="camp-arc-status badge badge-muted">${arc.status || ""}</span>
            </div>
            ${arc.hooks ? `<div class="camp-arc-hooks muted" style="font-size:0.8rem;margin-bottom:8px">${escHtml(arc.hooks)}</div>` : ""}
            <div class="camp-scenes-list">${sceneHtml || '<span class="muted">brak scen</span>'}</div>
          </div>
        `;
      }).join("");
    } catch (e) {
      modalBody.innerHTML = `<div class="camp-loading" style="color:var(--accent-red)">${e.message}</div>`;
    }
  }

  async function renderTurnsTab(c) {
    modalBody.innerHTML = `<div class="camp-loading">Ładowanie tur…</div>`;
    try {
      // Use the campaigns by owner endpoint to get basic info, then fetch turns separately
      // Since there's no direct turns endpoint in admin, we use the characters endpoint approach
      // Actually, let's try to fetch from campaigns endpoint
      const data = await adminFetch(`/api/admin/campaigns/${c.id}/turns?limit=10`).catch(() => null);
      if (!data) {
        // Fallback: just show what we have
        modalBody.innerHTML = `
          <div class="camp-turns-list">
            ${c.last_turn_player || c.last_turn_gm ? `
              <div class="camp-turn-item">
                <div class="camp-turn-role camp-turn-player">Gracz</div>
                <div class="camp-turn-text">${escHtml(c.last_turn_player || "")}</div>
              </div>
              ${c.last_turn_gm ? `
                <div class="camp-turn-item">
                  <div class="camp-turn-role camp-turn-gm">GM</div>
                  <div class="camp-turn-text">${escHtml(c.last_turn_gm)}</div>
                </div>
              ` : ""}
            ` : `<div class="camp-loading muted">${LABELS.noTurns}</div>`}
          </div>
        `;
        return;
      }
      const turns = data.items || data.turns || [];
      if (!turns.length) {
        modalBody.innerHTML = `<div class="camp-loading muted">${LABELS.noTurns}</div>`;
        return;
      }
      modalBody.innerHTML = `<div class="camp-turns-list">
        ${turns.map(t => `
          <div class="camp-turn-item">
            <div class="camp-turn-meta">Tura ${t.turn_number ?? ""} · ${t.created_at ? new Date(t.created_at + "Z").toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" }) : ""}</div>
            <div class="camp-turn-role camp-turn-player">Gracz</div>
            <div class="camp-turn-text">${escHtml(t.user_text || "")}</div>
            ${t.assistant_text ? `
              <div class="camp-turn-role camp-turn-gm">GM</div>
              <div class="camp-turn-text">${escHtml(t.assistant_text)}</div>
            ` : ""}
          </div>
        `).join("")}
      </div>`;
    } catch (e) {
      modalBody.innerHTML = `<div class="camp-loading" style="color:var(--accent-red)">${e.message}</div>`;
    }
  }

  function renderModalActions(c) {
    if (c.status !== "active") {
      modalActions.innerHTML = "";
      return;
    }
    modalActions.innerHTML = `
      <button class="secondary-btn" id="ma-advance" type="button">${LABELS.advanceScene}</button>
      <button class="secondary-btn" id="ma-regen-plan" type="button">${LABELS.regenPlan}</button>
      <button class="secondary-btn" id="ma-regen-summary" type="button">${LABELS.regenSummary}</button>
    `;

    modalActions.querySelector("#ma-advance")?.addEventListener("click", async () => {
      if (!confirm(LABELS.confirmAdvance)) return;
      try {
        await adminFetch(`/api/admin/campaigns/${c.id}/gm-plan/advance-scene`, { method: "POST", body: JSON.stringify({}) });
        showToast("Scena przesunięta.", "success");
        await load();
        // Refresh gm_plan data in currentCampaign
        const updated = campaigns.find(x => x.id === c.id);
        if (updated) { currentCampaign = updated; if (currentTab === "overview") renderOverviewTab(updated); }
      } catch (e) {
        showToast(e.message, "error");
      }
    });

    modalActions.querySelector("#ma-regen-plan")?.addEventListener("click", async () => {
      if (!confirm(LABELS.confirmRegen)) return;
      const btn = modalActions.querySelector("#ma-regen-plan");
      btn.disabled = true; btn.textContent = "Regeneruję…";
      try {
        await adminFetch(`/api/admin/campaigns/${c.id}/gm-plan/regenerate-initial`, { method: "POST" });
        showToast("Plan GM zregenerowany.", "success");
        if (currentTab === "plan") await renderPlanTab(c);
      } catch (e) {
        showToast(e.message, "error");
      } finally {
        btn.disabled = false; btn.textContent = LABELS.regenPlan;
      }
    });

    modalActions.querySelector("#ma-regen-summary")?.addEventListener("click", async () => {
      try {
        await adminFetch(`/api/admin/campaigns/${c.id}/regenerate-summary`, { method: "POST" });
        showToast("Podsumowanie zregenerowane.", "success");
      } catch (e) {
        showToast(e.message, "error");
      }
    });
  }

  // ── tab switching ──
  panel.querySelectorAll(".camp-tab-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      currentTab = btn.dataset.tab;
      panel.querySelectorAll(".camp-tab-btn").forEach(b => b.classList.toggle("active", b === btn));
      await renderModalTab();
    });
  });

  // ── modal close ──
  panel.querySelector("#camp-modal-close").addEventListener("click", closeModal);
  modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && modal.style.display !== "none") closeModal(); });

  // ── filter + refresh ──
  statusFilter.addEventListener("change", renderGrid);
  panel.querySelector("#camp-refresh-btn").addEventListener("click", load);

  // ── auto-refresh every 60s ──
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(load, 60000);

  await load();
}

function escHtml(str) {
  return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
