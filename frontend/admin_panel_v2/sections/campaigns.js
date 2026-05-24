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
          <button class="camp-tab-btn" data-tab="map" type="button">🗺 Mapa</button>
          <button class="camp-tab-btn" data-tab="workshop" type="button">🔧 Warsztat</button>
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
      if (!card) return;
      card.addEventListener("click", () => openModal(c));
      card.querySelector(".camp-card-delete-btn")?.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm(`Usunąć kampanię "${c.title}"? Operacja nieodwracalna.`)) return;
        try {
          await adminFetch(`/api/campaigns/${c.id}`, { method: "DELETE" });
          showToast("Kampania usunięta.", "success");
          await load();
        } catch (err) { showToast(err.message || "Błąd", "error"); }
      });
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
          <button class="camp-card-delete-btn" data-id="${c.id}" title="Usuń kampanię" type="button" style="margin-left:auto;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:0.85rem;padding:2px 6px;border-radius:4px;line-height:1" onclick="event.stopPropagation()">🗑</button>
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
    } else if (currentTab === "map") {
      await renderMapTab(c);
    } else if (currentTab === "workshop") {
      await renderWorkshopTab(c);
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

      const renderArc = ([arcId, arc]) => {
        const isActive = arcId === activeArcId;
        const scenes = arc.scene_goals || [];
        const currentSceneIdx = typeof plan.current_scene_index === "number" ? plan.current_scene_index : -1;

        const sceneHtml = scenes.map((sg, i) => {
          const isCurrent = isActive && i === currentSceneIdx;
          const text = typeof sg === "string" ? sg : (sg.text || sg.description || sg.goal || JSON.stringify(sg));
          const done = typeof sg === "object" && sg.status === "completed";
          return `<div class="camp-scene-item ${done ? "camp-scene-done" : ""} ${isCurrent ? "camp-scene-current" : ""}">
            <span class="camp-scene-num">${done ? "✓" : (isCurrent ? "▶" : (i + 1) + ".")}</span>
            <span>${escHtml(text)}</span>
          </div>`;
        }).join("");

        // Hooks: could be object {npcs, locations, items} or string
        let hooksHtml = "";
        if (arc.hooks && typeof arc.hooks === "object") {
          const parts = [];
          if (arc.hooks.npcs?.length) {
            parts.push(`<div class="camp-plan-section-label">NPCs</div><ul class="camp-plan-list">${
              arc.hooks.npcs.map(n => `<li>${escHtml(typeof n === "string" ? n : (n.name || JSON.stringify(n)))}</li>`).join("")
            }</ul>`);
          }
          if (arc.hooks.locations?.length) {
            parts.push(`<div class="camp-plan-section-label">Lokacje</div><ul class="camp-plan-list">${
              arc.hooks.locations.map(l => `<li>${escHtml(typeof l === "string" ? l : (l.name || JSON.stringify(l)))}</li>`).join("")
            }</ul>`);
          }
          if (arc.hooks.items?.length) {
            parts.push(`<div class="camp-plan-section-label">Przedmioty / haki</div><ul class="camp-plan-list">${
              arc.hooks.items.map(it => `<li>${escHtml(typeof it === "string" ? it : JSON.stringify(it))}</li>`).join("")
            }</ul>`);
          }
          hooksHtml = parts.join("");
        } else if (arc.hooks && typeof arc.hooks === "string") {
          hooksHtml = `<p class="muted" style="font-size:0.82rem">${escHtml(arc.hooks)}</p>`;
        }

        return `
          <div class="camp-arc-block ${isActive ? "camp-arc-active" : ""}">
            <div class="camp-arc-header">
              <span class="camp-arc-title">${escHtml(arc.title || arcId)}</span>
              ${isActive ? `<span class="badge badge-green" style="font-size:0.65rem">aktywny</span>` : ""}
              ${arc.status && arc.status !== "active" ? `<span class="badge badge-muted" style="font-size:0.65rem">${escHtml(arc.status)}</span>` : ""}
            </div>
            ${arc.roadmap ? `<div class="camp-plan-roadmap">${escHtml(arc.roadmap)}</div>` : ""}
            ${arc.description ? `<div class="camp-plan-roadmap">${escHtml(arc.description)}</div>` : ""}
            <div class="camp-plan-section-label">Cele scen</div>
            <div class="camp-scenes-list">${sceneHtml || '<span class="muted">brak scen</span>'}</div>
            ${hooksHtml ? `<details class="camp-plan-hooks-details"><summary class="camp-plan-section-label" style="cursor:pointer">Haki narracyjne</summary>${hooksHtml}</details>` : ""}
          </div>
        `;
      };

      modalBody.innerHTML = `<div class="camp-plan-scroll">${arcEntries.map(renderArc).join("")}</div>`;
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

// ── Campaign Hex Map Tab ──────────────────────────────────────────────────────

async function renderMapTab(c) {
  const body = document.getElementById("camp-modal-body");
  if (!body) return;
  body.innerHTML = `<div style="padding:16px;color:var(--text-muted)">Ładowanie mapy…</div>`;

  let data;
  try {
    data = await adminFetch(`/api/admin/campaigns/${c.id}/hex-map`);
  } catch (e) {
    body.innerHTML = `<div style="padding:16px;color:var(--accent-red)">${e.message}</div>`;
    return;
  }

  const hexes = data.hexes || [];
  const hexTypes = data.hex_types || {};

  if (!hexes.length) {
    body.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted)">Brak heksów na mapie świata.</div>`;
    return;
  }

  // Hex geometry (flat-top)
  const S = 26; // hex size
  const W = S * 2, H = Math.sqrt(3) * S;
  const toPixel = (q, r) => ({ x: S * 1.5 * q, y: H * (r + q * 0.5) });

  const pixels = hexes.map(h => toPixel(h.q, h.r));
  const minX = Math.min(...pixels.map(p => p.x)) - S;
  const minY = Math.min(...pixels.map(p => p.y)) - H / 2;
  const maxX = Math.max(...pixels.map(p => p.x)) + S;
  const maxY = Math.max(...pixels.map(p => p.y)) + H / 2;
  const svgW = maxX - minX + 20, svgH = maxY - minY + 20;

  const TYPE_COLORS = { plains: "#2a3a1a", forest: "#1a2e1a", mountain: "#2d2820", water: "#102030", desert: "#3a2e10", swamp: "#1a2a20", dungeon: "#1a1020", ruins: "#2a2220", town: "#2a2215", road: "#2a2a1a" };
  // Merge with API colors (darken them for SVG background)
  Object.entries(hexTypes).forEach(([k, v]) => { if (v.map_color) TYPE_COLORS[k] = v.map_color; });
  const hexPath = (cx, cy) => {
    const pts = [];
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 180 * (60 * i);
      pts.push(`${cx + S * Math.cos(a)},${cy + S * Math.sin(a)}`);
    }
    return `M${pts.join("L")}Z`;
  };

  let selectedHex = null;

  const svgHtml = hexes.map((h) => {
    const { x, y } = toPixel(h.q, h.r);
    const cx = x - minX + 10, cy = y - minY + 10;
    const col = TYPE_COLORS[h.hex_type] || "#1a1a1a";
    const discStroke = h.discovered ? "#c9a62a" : "#333";
    const discSw = h.discovered ? 1.5 : 0.5;
    const clearedIcon = h.encounter_cleared ? "✓" : "";
    const lbl = h.campaign_label || h.label || "";
    const icon = hexTypes[h.hex_type]?.map_icon || "";
    return `<g class="adm-hex" data-q="${h.q}" data-r="${h.r}" style="cursor:pointer">
      <path d="${hexPath(cx, cy)}" fill="${col}" stroke="${discStroke}" stroke-width="${discSw}" opacity="${h.discovered ? 1 : 0.45}"/>
      ${h.discovered ? `<text x="${cx}" y="${cy - 4}" text-anchor="middle" font-size="11" fill="#c8b87a" style="pointer-events:none">${escHtml(icon)}</text>` : ""}
      ${lbl ? `<text x="${cx}" y="${cy + 10}" text-anchor="middle" font-size="6" fill="#c8b87a" style="pointer-events:none">${escHtml(lbl.slice(0, 12))}</text>` : ""}
      ${clearedIcon ? `<text x="${cx + S * 0.6}" y="${cy - S * 0.5}" text-anchor="middle" font-size="8" fill="#5ec88a" style="pointer-events:none">${clearedIcon}</text>` : ""}
    </g>`;
  }).join("");

  body.innerHTML = `
    <div class="camp-map-layout">
      <div class="camp-map-canvas-wrap">
        <svg id="camp-map-svg" width="${Math.round(svgW)}" height="${Math.round(svgH)}" style="display:block;min-width:${Math.round(svgW)}px">
          ${svgHtml}
        </svg>
      </div>
      <div class="camp-map-editor" id="camp-map-editor">
        <div class="camp-map-hint">Kliknij hex aby edytować pola kampanii</div>
      </div>
    </div>`;

  const editor = body.querySelector("#camp-map-editor");
  const svg = body.querySelector("#camp-map-svg");

  const openHexEditor = (h) => {
    selectedHex = h;
    svg.querySelectorAll(".adm-hex path").forEach(p => p.setAttribute("stroke-width", "0.5"));
    const sel = svg.querySelector(`.adm-hex[data-q="${h.q}"][data-r="${h.r}"] path`);
    if (sel) { sel.setAttribute("stroke", "#fff"); sel.setAttribute("stroke-width", "2"); }

    editor.innerHTML = `
      <div class="camp-map-editor-title">${escHtml(h.campaign_label || h.label || h.hex_type || `(${h.q}, ${h.r})`)}<span class="camp-map-editor-coords"> (${h.q}, ${h.r})</span></div>
      <div class="camp-map-field-group">
        <div class="camp-map-field-label">Odkryty przez gracza</div>
        <label class="camp-map-toggle"><input type="checkbox" id="cme-discovered" ${h.discovered ? "checked" : ""}><span>Odkryty</span></label>
      </div>
      <div class="camp-map-field-group">
        <div class="camp-map-field-label">Encounter wyczyszczony</div>
        <label class="camp-map-toggle"><input type="checkbox" id="cme-cleared" ${h.encounter_cleared ? "checked" : ""}><span>Wyczyszczony</span></label>
      </div>
      <div class="camp-map-field-group">
        <div class="camp-map-field-label">Etykieta kampanii</div>
        <input id="cme-label" class="camp-map-input" type="text" value="${escHtml(h.campaign_label || "")}" placeholder="np. Wioska Aelwyna"/>
      </div>
      <div class="camp-map-field-group">
        <div class="camp-map-field-label">Notatki GM</div>
        <textarea id="cme-notes" class="camp-map-input" rows="4" placeholder="Prywatne notatki GM o tym hexie…">${escHtml(h.campaign_notes || "")}</textarea>
      </div>
      <button class="primary-btn camp-map-save-btn" id="cme-save">Zapisz</button>`;

    editor.querySelector("#cme-save").addEventListener("click", async () => {
      const btn = editor.querySelector("#cme-save");
      btn.disabled = true; btn.textContent = "Zapisuję…";
      const payload = {
        discovered: editor.querySelector("#cme-discovered").checked,
        encounter_cleared: editor.querySelector("#cme-cleared").checked,
        campaign_label: editor.querySelector("#cme-label").value.trim(),
        campaign_notes: editor.querySelector("#cme-notes").value.trim(),
      };
      try {
        await adminFetch(`/api/admin/campaigns/${c.id}/hex-map/${h.q}/${h.r}`, { method: "PATCH", body: JSON.stringify(payload) });
        // Update local hex data
        Object.assign(h, payload);
        showToast("Zapisano.", "success");
        // Refresh hex visuals
        await renderMapTab(c);
      } catch (err) {
        showToast(err.message || "Błąd", "error");
        btn.disabled = false; btn.textContent = "Zapisz";
      }
    });
  };

  svg.querySelectorAll(".adm-hex").forEach(g => {
    g.addEventListener("click", () => {
      const q = parseInt(g.dataset.q), r = parseInt(g.dataset.r);
      const hex = hexes.find(h => h.q === q && h.r === r);
      if (hex) openHexEditor(hex);
    });
  });
}

// ── Campaign Workshop ──────────────────────────────────────────────────────

function _cwEsc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function _cwGenId() {
  return "cw-" + Math.random().toString(36).slice(2, 10);
}

async function renderWorkshopTab(c) {
  // Get modalBody from the closure scope via the DOM — re-initialize each time
  const modalBodyEl = document.getElementById("camp-modal-body");
  if (!modalBodyEl) return;

  const sessionId = _cwGenId();
  const campaignId = c.id;

  modalBodyEl.innerHTML = `
    <div class="workshop-layout" style="height:100%">
      <div class="workshop-chat-col">
        <div class="workshop-messages" id="cw-messages-${campaignId}">
          <div class="chat-msg agent"><div class="chat-bubble">Kampania "${_cwEsc(c.title)}" załadowana. Mogę analizować plan GM, proponować zmiany narracyjne, wykrywać luki fabularne. O co pytasz?</div></div>
        </div>
        <div class="workshop-input-row">
          <textarea id="cw-input-${campaignId}" class="workshop-textarea" rows="4"
            style="min-height:80px"
            placeholder="Zapytaj o kampanię lub poproś o zmiany…" maxlength="2000"></textarea>
          <button class="primary-btn" id="cw-send-btn-${campaignId}" type="button">Wyślij</button>
        </div>
      </div>

      <div class="workshop-draft-col" id="cw-changes-col-${campaignId}">
        <div class="workshop-draft-header">PROPONOWANE ZMIANY</div>
        <div id="cw-proposed-${campaignId}" style="color:var(--text-muted);font-size:0.82rem;padding:8px">
          Zmiany zaproponowane przez agenta pojawią się tutaj.
        </div>
      </div>
    </div>`;

  const messagesEl = modalBodyEl.querySelector(`#cw-messages-${campaignId}`);
  const inputEl    = modalBodyEl.querySelector(`#cw-input-${campaignId}`);
  const sendBtn    = modalBodyEl.querySelector(`#cw-send-btn-${campaignId}`);
  const proposedEl = modalBodyEl.querySelector(`#cw-proposed-${campaignId}`);

  function appendMsg(text, type) {
    const div = document.createElement("div");
    div.className = `chat-msg ${type}`;
    div.innerHTML = `<div class="chat-bubble">${_cwEsc(text).replace(/\n/g, "<br>")}</div>`;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function renderWorkshopChanges(changes) {
    if (!changes || !changes.length) return;
    proposedEl.innerHTML = "";
    changes.forEach(ch => {
      const row = document.createElement("div");
      row.className = "workshop-change-row";
      const fieldName = _cwEsc(ch.field || ch.path || "?");
      const oldVal = _cwEsc(String(ch.old_value ?? "—").slice(0, 200));
      const newVal = _cwEsc(String(ch.new_value ?? "?").slice(0, 200));
      const reason = ch.reason ? `<div class="workshop-change-reason">${_cwEsc(ch.reason)}</div>` : "";
      row.innerHTML = `
        <div class="workshop-change-field">${fieldName}</div>
        <div class="workshop-change-diff">
          <span class="workshop-old">${oldVal}</span>
          <span class="workshop-arrow">→</span>
          <span class="workshop-new">${newVal}</span>
        </div>
        ${reason}
        <button class="primary-btn workshop-approve-btn" type="button">✓ Zatwierdź</button>`;
      row.querySelector(".workshop-approve-btn").addEventListener("click", async () => {
        try {
          await adminFetch(`/api/admin/campaigns/${campaignId}/workshop/apply`, {
            method: "POST",
            body: JSON.stringify({ field: ch.field || ch.path, new_value: ch.new_value }),
          });
          showToast("Zmiana zatwierdzona.", "success");
          const btn = row.querySelector(".workshop-approve-btn");
          btn.textContent = "✓ Zastosowano";
          btn.disabled = true;
          btn.className = "secondary-btn workshop-approve-btn";
        } catch(e) { showToast(e.message, "error"); }
      });
      proposedEl.appendChild(row);
    });
  }

  async function sendMessage() {
    const msg = inputEl.value.trim();
    if (!msg) return;
    inputEl.value = "";

    appendMsg(msg, "user");
    sendBtn.disabled = true;
    const typing = appendMsg("…", "agent");

    try {
      const resp = await adminFetch(
        `/api/admin/campaigns/${campaignId}/workshop/message`,
        { method: "POST", body: JSON.stringify({ session_id: sessionId, message: msg }) }
      );

      const reply = resp.reply || "";
      const changes = resp.proposed_changes || [];

      // Strip JSON blocks from reply before display
      const cleanReply = reply.replace(/```json[\s\S]*?```/g, "").replace(/```[\s\S]*?```/g, "").trim();

      typing.remove();
      if (cleanReply) appendMsg(cleanReply, "agent");
      renderWorkshopChanges(changes);
    } catch (e) {
      typing.remove();
      appendMsg(`Błąd: ${_cwEsc(e.message || "?")}`, "agent error");
    } finally {
      sendBtn.disabled = false;
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}
