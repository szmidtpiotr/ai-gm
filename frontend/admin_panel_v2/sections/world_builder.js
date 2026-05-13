/**
 * Visual World Builder — Phase 08 Task 40
 * Cytoscape.js node-edge graph editor for location management.
 * Locations = nodes, travel routes = edges.
 */
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

let _cy = null;
let _edgeHandles = null;
let _allLocations = [];
let _allConnections = [];

function _esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

const ARCHETYPE_COLORS = {
  tavern:  "#8b6340",
  dungeon: "#4a3a6e",
  forest:  "#2d5a27",
  city:    "#5a6e7f",
  ruin:    "#6e5a4a",
  road:    "#7a7a5a",
  default: "#5a5a6e",
};

const NODE_STATUS_STYLE = {
  permanent: { border: "#66aaff", opacity: 1 },
  pending_review: { border: "#ffcc44", opacity: 0.85 },
  discarded: { border: "#cc4444", opacity: 0.4 },
};

export async function init(container) {
  container.innerHTML = `
    <div class="builder-layout">
      <div class="builder-toolbar">
        <span class="builder-title">🗺 Mapa Świata</span>
        <div class="builder-toolbar-actions">
          <button class="secondary-btn" id="wb-add-loc-btn" type="button">+ Dodaj lokację</button>
          <button class="secondary-btn" id="wb-fit-btn" type="button">⊡ Dopasuj widok</button>
          <button class="secondary-btn" id="wb-save-positions-btn" type="button">💾 Zapisz układ</button>
          <button class="secondary-btn" id="wb-toggle-edges-btn" type="button">⇄ Tryb połączeń</button>
          <span class="builder-hint" id="wb-hint">Kliknij węzeł aby zobaczyć szczegóły</span>
        </div>
      </div>
      <div class="builder-body">
        <div class="builder-graph" id="wb-graph"></div>
        <div class="builder-sidebar" id="wb-sidebar">
          <div class="builder-sidebar-empty">Kliknij lokację aby zobaczyć szczegóły.</div>
        </div>
      </div>
    </div>`;

  await _loadCytoscape();
  await _loadData(container);
  _initGraph(container);
  _wireToolbar(container);
}

async function _loadCytoscape() {
  if (window.cytoscape) return;
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js";
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://unpkg.com/cytoscape-edgehandles@4.0.1/cytoscape-edgehandles.js";
    s.onload = resolve;
    s.onerror = () => resolve(); // non-critical, continue without it
    document.head.appendChild(s);
  });
  if (window.cytoscapeEdgehandles) {
    window.cytoscape.use(window.cytoscapeEdgehandles);
  }
}

async function _loadData(container) {
  try {
    const [locsData, connData] = await Promise.all([
      adminFetch("/api/admin/locations"),
      adminFetch("/api/admin/locations/connections").catch(() => ({ connections: [] })),
    ]);
    _allLocations = locsData.locations ?? locsData ?? [];
    _allConnections = connData.connections ?? connData ?? [];
  } catch (e) {
    showToast("Błąd ładowania lokacji: " + e.message, "error");
  }
}

function _initGraph(container) {
  const graphEl = container.querySelector("#wb-graph");

  const nodes = _allLocations.map(loc => {
    const color = ARCHETYPE_COLORS[loc.location_type] || ARCHETYPE_COLORS.default;
    const status = loc.review_status || "permanent";
    return {
      data: {
        id: loc.key,
        label: loc.label,
        key: loc.key,
        locType: loc.location_type || "macro",
        archetype: loc.archetype || "default",
        safeForRest: loc.safe_for_rest || false,
        reviewStatus: status,
        description: loc.description || "",
        color,
      },
      position: {
        x: (loc.map_x != null ? loc.map_x : Math.random() * 800),
        y: (loc.map_y != null ? loc.map_y : Math.random() * 500),
      },
    };
  });

  const edges = _allConnections.map(conn => ({
    data: {
      id: `${conn.from_key}-${conn.to_key}`,
      source: conn.from_key,
      target: conn.to_key,
      travelTime: conn.travel_time_minutes || 0,
      isDangerous: conn.is_dangerous || false,
      isBidirectional: conn.is_bidirectional !== false,
    },
  }));

  _cy = window.cytoscape({
    container: graphEl,
    elements: { nodes, edges },
    style: [
      {
        selector: "node",
        style: {
          "background-color": "data(color)",
          "label": "data(label)",
          "color": "#e8e0d0",
          "font-size": "11px",
          "text-valign": "bottom",
          "text-margin-y": "4px",
          "width": 44,
          "height": 44,
          "border-width": 2,
          "border-color": "#66aaff",
          "text-background-color": "#1a1a2e",
          "text-background-opacity": 0.8,
          "text-background-padding": "2px",
        },
      },
      {
        selector: "node[reviewStatus = 'pending_review']",
        style: {
          "border-color": "#ffcc44",
          "border-style": "dashed",
          "opacity": 0.85,
        },
      },
      {
        selector: "node[reviewStatus = 'discarded']",
        style: { "opacity": 0.35, "border-color": "#cc4444" },
      },
      {
        selector: "node[safeForRest]",
        style: { "shape": "round-rectangle" },
      },
      {
        selector: "node:selected",
        style: {
          "border-color": "#ffffff",
          "border-width": 3,
        },
      },
      {
        selector: "edge",
        style: {
          "width": 2,
          "line-color": "#556699",
          "target-arrow-color": "#556699",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "label": "data(travelTime)",
          "font-size": "9px",
          "color": "#aaa",
          "text-rotation": "autorotate",
        },
      },
      {
        selector: "edge[isDangerous]",
        style: { "line-color": "#cc4444", "target-arrow-color": "#cc4444" },
      },
      {
        selector: ".eh-handle",
        style: {
          "background-color": "#88aaff",
          "width": 12,
          "height": 12,
          "shape": "ellipse",
          "overlay-opacity": 0,
          "border-width": 12,
          "border-opacity": 0,
        },
      },
    ],
    layout: { name: "preset" },
    wheelSensitivity: 0.3,
  });

  // Save positions on node drag end
  _cy.on("dragfree", "node", e => {
    const node = e.target;
    _saveNodePosition(node.id(), node.position());
  });

  // Show sidebar on node click
  _cy.on("tap", "node", e => {
    _showLocationDetail(container, e.target.data());
  });

  // Edge click — show connection detail
  _cy.on("tap", "edge", e => {
    _showEdgeDetail(container, e.target.data());
  });

  // Background click — clear sidebar
  _cy.on("tap", e => {
    if (e.target === _cy) {
      container.querySelector("#wb-sidebar").innerHTML =
        `<div class="builder-sidebar-empty">Kliknij lokację aby zobaczyć szczegóły.</div>`;
    }
  });

  // Edge handles for connecting nodes
  if (_cy.edgehandles) {
    _edgeHandles = _cy.edgehandles({
      preview: false,
      hoverDelay: 150,
      snap: false,
      complete: async (sourceNode, targetNode, addedEles) => {
        addedEles.remove();
        await _createConnection(container, sourceNode.id(), targetNode.id());
      },
    });
    _edgeHandles.disable(); // start disabled
  }
}

function _wireToolbar(container) {
  container.querySelector("#wb-fit-btn").addEventListener("click", () => {
    _cy?.fit(undefined, 40);
  });

  container.querySelector("#wb-save-positions-btn").addEventListener("click", async () => {
    await _saveAllPositions();
    showToast("Układ zapisany.", "success");
  });

  let edgeMode = false;
  const toggleBtn = container.querySelector("#wb-toggle-edges-btn");
  const hint = container.querySelector("#wb-hint");
  toggleBtn.addEventListener("click", () => {
    edgeMode = !edgeMode;
    if (edgeMode) {
      _edgeHandles?.enable();
      toggleBtn.classList.add("active");
      hint.textContent = "Tryb połączeń: przeciągnij z jednej lokacji do drugiej";
    } else {
      _edgeHandles?.disable();
      toggleBtn.classList.remove("active");
      hint.textContent = "Kliknij węzeł aby zobaczyć szczegóły";
    }
  });

  container.querySelector("#wb-add-loc-btn").addEventListener("click", () => {
    _showAddLocationForm(container);
  });
}

function _showLocationDetail(container, data) {
  const sidebar = container.querySelector("#wb-sidebar");
  const statusBadge = data.reviewStatus === "pending_review"
    ? `<span style="color:#ffcc44">⏳ Oczekuje</span>`
    : data.reviewStatus === "discarded"
    ? `<span style="color:#cc4444">✕ Odrzucona</span>`
    : `<span style="color:#66ff99">✓ Zatwierdzona</span>`;

  sidebar.innerHTML = `
    <div class="wb-detail">
      <div class="wb-detail-name">${_esc(data.label)}</div>
      <div class="wb-detail-key"><code>${_esc(data.key)}</code> ${statusBadge}</div>
      <div class="wb-detail-meta">
        Typ: ${_esc(data.locType)} &nbsp;|&nbsp;
        Odpoczynek: ${data.safeForRest ? "✓ bezpieczny" : "✗ ryzykowny"}
      </div>
      <div class="wb-detail-desc">${_esc(data.description || "—")}</div>
      <div class="wb-detail-actions">
        ${data.reviewStatus === "pending_review" ? `
          <button class="primary-btn" id="wb-approve-btn" type="button" style="font-size:0.8rem">✓ Zatwierdź</button>
          <button class="secondary-btn danger-outline" id="wb-discard-btn" type="button" style="font-size:0.8rem">✕ Odrzuć</button>
        ` : ""}
        <button class="secondary-btn" id="wb-connections-btn" type="button" style="font-size:0.8rem">⇄ Połączenia</button>
      </div>
    </div>`;

  sidebar.querySelector("#wb-approve-btn")?.addEventListener("click", async () => {
    try {
      await adminFetch(`/api/admin/world/review/location/${_esc(data.key)}`, {
        method: "POST", body: JSON.stringify({ action: "approve" }),
      });
      showToast("Lokacja zatwierdzona.", "success");
      _cy.$(`#${data.key}`).data("reviewStatus", "permanent");
      _cy.$(`#${data.key}`).style("border-style", "solid").style("border-color", "#66aaff").style("opacity", 1);
      _showLocationDetail(container, { ...data, reviewStatus: "permanent" });
    } catch (e) { showToast(e.message, "error"); }
  });

  sidebar.querySelector("#wb-discard-btn")?.addEventListener("click", async () => {
    if (!confirm(`Odrzucić lokację "${data.label}"?`)) return;
    try {
      await adminFetch(`/api/admin/world/review/location/${_esc(data.key)}`, {
        method: "POST", body: JSON.stringify({ action: "discard" }),
      });
      showToast("Lokacja odrzucona.", "success");
      _cy.$(`#${data.key}`).style("opacity", 0.35);
    } catch (e) { showToast(e.message, "error"); }
  });

  sidebar.querySelector("#wb-connections-btn")?.addEventListener("click", () => {
    _showConnectionsPanel(container, data.key, data.label);
  });
}

function _showEdgeDetail(container, data) {
  const sidebar = container.querySelector("#wb-sidebar");
  sidebar.innerHTML = `
    <div class="wb-detail">
      <div class="wb-detail-name">Połączenie</div>
      <div class="wb-detail-meta">${_esc(data.source)} → ${_esc(data.target)}</div>
      <div class="wb-detail-meta">Czas podróży: ${data.travelTime} min &nbsp;|&nbsp; ${data.isDangerous ? "⚠ Niebezpieczna" : "Bezpieczna"}</div>
      <div class="wb-detail-actions">
        <button class="secondary-btn danger-outline" id="wb-del-edge-btn" type="button" style="font-size:0.8rem">✕ Usuń połączenie</button>
      </div>
    </div>`;

  sidebar.querySelector("#wb-del-edge-btn").addEventListener("click", async () => {
    if (!confirm("Usunąć to połączenie?")) return;
    try {
      await adminFetch("/api/admin/locations/connections/delete", {
        method: "POST",
        body: JSON.stringify({ from_key: data.source, to_key: data.target }),
      });
      _cy.$(`#${data.id}`).remove();
      showToast("Połączenie usunięto.", "success");
      sidebar.innerHTML = `<div class="builder-sidebar-empty">Kliknij lokację aby zobaczyć szczegóły.</div>`;
    } catch (e) { showToast(e.message, "error"); }
  });
}

function _showConnectionsPanel(container, key, label) {
  const sidebar = container.querySelector("#wb-sidebar");
  const edges = _cy.edges(`[source = "${key}"], [target = "${key}"]`);
  let list = "";
  edges.forEach(e => {
    const other = e.source().id() === key ? e.target().id() : e.source().id();
    list += `<div class="wb-conn-row">${_esc(other)} (${e.data("travelTime")} min)</div>`;
  });

  sidebar.innerHTML = `
    <div class="wb-detail">
      <div class="wb-detail-name">Połączenia: ${_esc(label)}</div>
      <div>${list || "<p style='color:var(--text-muted)'>Brak połączeń.</p>"}</div>
      <hr style="border-color:var(--border-color);margin:10px 0">
      <div class="wb-detail-meta" style="font-weight:600">Dodaj połączenie:</div>
      <select id="wb-conn-target" class="field-input" style="width:100%;margin:6px 0">
        <option value="">Wybierz lokację docelową</option>
        ${_allLocations.filter(l => l.key !== key).map(l => `<option value="${_esc(l.key)}">${_esc(l.label)}</option>`).join("")}
      </select>
      <div style="display:flex;gap:8px;align-items:center">
        <input type="number" id="wb-conn-time" class="field-input" placeholder="Czas (min)" min="1" max="9999" style="width:90px" value="60" />
        <label style="font-size:0.8rem"><input type="checkbox" id="wb-conn-danger"> Niebezpieczna</label>
      </div>
      <button class="primary-btn" id="wb-add-conn-btn" type="button" style="width:100%;margin-top:8px">Dodaj połączenie</button>
    </div>`;

  sidebar.querySelector("#wb-add-conn-btn").addEventListener("click", async () => {
    const target = sidebar.querySelector("#wb-conn-target").value;
    const time = parseInt(sidebar.querySelector("#wb-conn-time").value) || 60;
    const danger = sidebar.querySelector("#wb-conn-danger").checked;
    if (!target) { showToast("Wybierz lokację docelową.", "error"); return; }
    await _createConnection(container, key, target, time, danger);
  });
}

async function _createConnection(container, fromKey, toKey, travelTime = 60, isDangerous = false) {
  try {
    await adminFetch("/api/admin/locations/connections", {
      method: "POST",
      body: JSON.stringify({
        from_key: fromKey, to_key: toKey,
        travel_time_minutes: travelTime,
        is_dangerous: isDangerous,
        is_bidirectional: true,
      }),
    });
    // Add edge to graph
    _cy.add({ data: {
      id: `${fromKey}-${toKey}`,
      source: fromKey, target: toKey,
      travelTime, isDangerous,
    }});
    showToast(`Połączono: ${fromKey} ↔ ${toKey}`, "success");
    _showConnectionsPanel(container, fromKey, _allLocations.find(l => l.key === fromKey)?.label || fromKey);
  } catch (e) { showToast(e.message, "error"); }
}

function _showAddLocationForm(container) {
  const sidebar = container.querySelector("#wb-sidebar");
  sidebar.innerHTML = `
    <div class="wb-detail">
      <div class="wb-detail-name">+ Nowa lokacja</div>
      <div class="modal-form" style="gap:8px">
        <div><label style="font-size:0.8rem">Klucz *</label>
          <input type="text" id="wb-new-key" class="field-input" placeholder="np. dark_forest" style="width:100%" /></div>
        <div><label style="font-size:0.8rem">Nazwa *</label>
          <input type="text" id="wb-new-label" class="field-input" placeholder="np. Ciemny Las" style="width:100%" /></div>
        <div><label style="font-size:0.8rem">Typ</label>
          <select id="wb-new-type" class="field-input" style="width:100%">
            <option value="macro">Makro</option>
            <option value="sub">Pod-lokacja</option>
          </select></div>
        <div><label style="font-size:0.8rem">Opis</label>
          <textarea id="wb-new-desc" class="field-input" rows="2" style="width:100%" placeholder="Krótki opis atmosferyczny…"></textarea></div>
        <label style="font-size:0.8rem"><input type="checkbox" id="wb-new-safe"> Bezpieczny odpoczynek</label>
        <button class="primary-btn" id="wb-create-loc-btn" type="button" style="width:100%;margin-top:8px">Utwórz</button>
      </div>
    </div>`;

  sidebar.querySelector("#wb-create-loc-btn").addEventListener("click", async () => {
    const key = sidebar.querySelector("#wb-new-key").value.trim();
    const label = sidebar.querySelector("#wb-new-label").value.trim();
    const locationType = sidebar.querySelector("#wb-new-type").value;
    const description = sidebar.querySelector("#wb-new-desc").value.trim();
    const safe = sidebar.querySelector("#wb-new-safe").checked;
    if (!key || !label) { showToast("Klucz i nazwa są wymagane.", "error"); return; }
    try {
      await adminFetch("/api/admin/locations", {
        method: "POST",
        body: JSON.stringify({ key, label, location_type: locationType, description, safe_for_rest: safe }),
      });
      // Add node to graph
      const x = 300 + Math.random() * 200;
      const y = 200 + Math.random() * 200;
      _cy.add({ data: {
        id: key, label, key, locType: locationType,
        safeForRest: safe, reviewStatus: "permanent",
        color: ARCHETYPE_COLORS.default, description,
      }, position: { x, y } });
      _allLocations.push({ key, label, location_type: locationType, description, safe_for_rest: safe });
      showToast("Lokacja dodana.", "success");
      sidebar.innerHTML = `<div class="builder-sidebar-empty">Kliknij lokację aby zobaczyć szczegóły.</div>`;
    } catch (e) { showToast(e.message, "error"); }
  });
}

async function _saveNodePosition(key, pos) {
  try {
    await adminFetch(`/api/admin/locations/${_esc(key)}/position`, {
      method: "PATCH",
      body: JSON.stringify({ map_x: pos.x, map_y: pos.y }),
    });
  } catch { /* silently ignore position save failures */ }
}

async function _saveAllPositions() {
  const updates = _cy.nodes().map(n => ({
    key: n.id(), map_x: n.position("x"), map_y: n.position("y"),
  }));
  await Promise.allSettled(updates.map(u =>
    adminFetch(`/api/admin/locations/${_esc(u.key)}/position`, {
      method: "PATCH",
      body: JSON.stringify({ map_x: u.map_x, map_y: u.map_y }),
    })
  ));
}
