import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable } from "/admin_panel_v2/shared/table.js?v=8";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";

const LABELS = {
  username:     "Nazwa użytkownika",
  displayName:  "Nazwa wyświetlana",
  createdAt:    "Zarejestrowany",
  isAdmin:      "Administrator",
  isActive:     "Aktywny",
  campaigns:    "Kampanie",
  characters:   "Postacie",
  addUser:      "Dodaj użytkownika",
  save:         "Zapisz",
  cancel:       "Anuluj",
  tabInfo:      "Info",
  tabCampaigns: "Kampanie",
  tabLlm:       "LLM",
  tabResurrect: "Wskrzeszenie",
  resetPassword:"Zmień hasło",
  newPassword:  "Nowe hasło (min. 8 znaków)",
  llmMode:      "Tryb LLM",
  llmProvider:  "Dostawca",
  llmBaseUrl:   "URL API",
  llmModel:     "Model",
  llmApiKey:    "Klucz API",
  modeDefault:  "Domyślny (globalny)",
  modeCustom:   "Własny",
  noCampaigns:  "Brak kampanii",
  loading:      "Ładowanie…",
  statusActive: "Aktywna",
  statusEnded:  "Zakończona",
  statusAborted:"Przerwana",
};

let _users        = [];
let _activeUserId = null;
let _drawerTab    = "info";
let _panel        = null;

export async function init(panel) {
  _panel = panel;
  _activeUserId = null;
  _drawerTab    = "info";

  panel.innerHTML = `
    <div class="players-layout" id="players-layout">
      <div class="players-main" id="players-main">
        <div class="tab-toolbar">
          <button class="primary-btn" id="add-user-btn">+ ${LABELS.addUser}</button>
        </div>
        <div id="users-table-host" style="flex:1;overflow-y:auto"></div>
      </div>
      <div class="players-drawer" id="players-drawer" style="display:none">
        <div class="players-drawer-header" id="drawer-header"></div>
        <div class="players-drawer-tabnav" id="drawer-tabnav"></div>
        <div class="players-drawer-body" id="drawer-body" style="overflow-y:auto;flex:1"></div>
      </div>
    </div>`;

  panel.querySelector("#add-user-btn").addEventListener("click", () => _openCreateModal());

  await _loadUsers();
}

// ── Users list ────────────────────────────────────────────────────────────────

async function _loadUsers() {
  const host = _panel.querySelector("#users-table-host");
  renderTable(host, null, null, {});
  try {
    const data = await adminFetch("/api/admin/accounts");
    _users = data.items || [];
  } catch (e) {
    showToast("Błąd ładowania użytkowników: " + (e.message || "?"), "error");
    return;
  }

  const cols = [
    { key: "id",              label: "ID",              editable: false },
    { key: "username",        label: LABELS.username,   editable: false },
    { key: "display_name",    label: LABELS.displayName, editable: false },
    {
      key: "is_admin",
      label: LABELS.isAdmin,
      type: "badge",
      editable: false,
      badgeClass: (r) => r.is_admin ? "admin-badge-gold" : "admin-badge-muted",
      formatDisplay: (r) => r.is_admin ? "Admin" : "Gracz",
    },
    {
      key: "is_active",
      label: LABELS.isActive,
      type: "badge",
      editable: false,
      badgeClass: (r) => r.is_active ? "admin-badge-green" : "admin-badge-red",
      formatDisplay: (r) => r.is_active ? "Aktywny" : "Zablokowany",
    },
    { key: "campaigns_count", label: LABELS.campaigns,  editable: false },
    { key: "created_at",      label: LABELS.createdAt,  editable: false },
  ];

  renderTable(host, cols, _users, {
    showTextSearch: true,
    searchPlaceholder: "Szukaj użytkownika…",
    rowClass: (r) => r.id === _activeUserId ? "row-selected" : "",
    onRowClick: (r) => _openDrawer(r.id),
  });
}

// ── Drawer ────────────────────────────────────────────────────────────────────

async function _openDrawer(userId) {
  _activeUserId = userId;
  const drawer = _panel.querySelector("#players-drawer");
  drawer.style.display = "flex";
  _panel.querySelector("#players-layout").classList.add("drawer-open");
  _renderDrawerHeader(userId);
  _renderDrawerTabs(userId);
  await _renderDrawerBody(userId, _drawerTab);
  await _loadUsers(); // refresh to highlight row
}

function _closeDrawer() {
  _activeUserId = null;
  _panel.querySelector("#players-drawer").style.display = "none";
  _panel.querySelector("#players-layout").classList.remove("drawer-open");
  _loadUsers();
}

function _renderDrawerHeader(userId) {
  const user = _users.find((u) => u.id === userId);
  if (!user) return;
  const header = _panel.querySelector("#drawer-header");
  const initial = (user.display_name || user.username || "?")[0].toUpperCase();
  header.innerHTML = `
    <div class="drawer-user-avatar">${_esc(initial)}</div>
    <div class="drawer-user-info">
      <div class="drawer-user-name">${_esc(user.display_name || user.username)}</div>
      <div class="drawer-user-meta">
        <code>@${_esc(user.username)}</code>
        ${user.is_admin ? ' <span class="admin-badge admin-badge-gold">Admin</span>' : ''}
        ${!user.is_active ? ' <span class="admin-badge admin-badge-red">Zablokowany</span>' : ''}
      </div>
    </div>
    <button class="drawer-close-btn" id="drawer-close-btn" title="Zamknij">✕</button>`;
  header.querySelector("#drawer-close-btn").addEventListener("click", _closeDrawer);
}

function _renderDrawerTabs(userId) {
  const nav = _panel.querySelector("#drawer-tabnav");
  const tabs = [
    { id: "info",       label: LABELS.tabInfo },
    { id: "campaigns",  label: LABELS.tabCampaigns },
    { id: "llm",        label: LABELS.tabLlm },
    { id: "resurrect",  label: LABELS.tabResurrect },
  ];
  nav.innerHTML = tabs.map((t) =>
    `<button class="drawer-tab-btn${t.id === _drawerTab ? " active" : ""}" data-tab="${t.id}">${t.label}</button>`
  ).join("");
  nav.querySelectorAll(".drawer-tab-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      _drawerTab = btn.dataset.tab;
      nav.querySelectorAll(".drawer-tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
      await _renderDrawerBody(userId, _drawerTab);
    });
  });
}

async function _renderDrawerBody(userId, tab) {
  const body = _panel.querySelector("#drawer-body");
  body.innerHTML = `<div class="drawer-loading">${LABELS.loading}</div>`;
  if (tab === "info")      await _renderInfoTab(userId, body);
  if (tab === "campaigns") await _renderCampaignsTab(userId, body);
  if (tab === "llm")       await _renderLlmTab(userId, body);
  if (tab === "resurrect") await _renderResurrectTab(userId, body);
}

// ── Info tab ──────────────────────────────────────────────────────────────────

async function _renderInfoTab(userId, body) {
  const user = _users.find((u) => u.id === userId);
  if (!user) { body.innerHTML = ""; return; }

  body.innerHTML = `
    <div class="drawer-section">
      <div class="drawer-section-title">Dane konta</div>
      <label class="drawer-field">
        <span>${LABELS.displayName}</span>
        <input id="dn-input" type="text" value="${_esc(user.display_name || "")}" />
      </label>
      <button class="secondary-btn" id="save-dn-btn">Zapisz nazwę</button>
    </div>

    <div class="drawer-section">
      <div class="drawer-section-title">Role i dostęp</div>
      <label class="drawer-toggle-row">
        <span>${LABELS.isAdmin}</span>
        <input type="checkbox" id="is-admin-chk" ${user.is_admin ? "checked" : ""} />
      </label>
      <label class="drawer-toggle-row">
        <span>${LABELS.isActive}</span>
        <input type="checkbox" id="is-active-chk" ${user.is_active ? "checked" : ""} />
      </label>
      <button class="secondary-btn" id="save-roles-btn">Zapisz role</button>
    </div>

    <div class="drawer-section">
      <div class="drawer-section-title">${LABELS.resetPassword}</div>
      <label class="drawer-field">
        <span>${LABELS.newPassword}</span>
        <input id="new-pw-input" type="password" autocomplete="new-password" placeholder="••••••••" />
      </label>
      <button class="secondary-btn" id="reset-pw-btn">Ustaw hasło</button>
    </div>

    <div class="drawer-section drawer-danger-zone">
      <div class="drawer-section-title" style="color:var(--accent-red)">Strefa niebezpieczna</div>
      <button class="danger-btn" id="deactivate-btn">${user.is_active ? "Zablokuj konto" : "Odblokuj konto"}</button>
    </div>`;

  body.querySelector("#save-dn-btn").addEventListener("click", async () => {
    const dn = body.querySelector("#dn-input").value.trim();
    try {
      await adminFetch(`/api/admin/accounts/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: dn }),
      });
      showToast("Nazwa zapisana.", "success");
      await _loadUsers();
      _renderDrawerHeader(userId);
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });

  body.querySelector("#save-roles-btn").addEventListener("click", async () => {
    const is_admin  = body.querySelector("#is-admin-chk").checked ? 1 : 0;
    const is_active = body.querySelector("#is-active-chk").checked ? 1 : 0;
    try {
      await adminFetch(`/api/admin/accounts/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_admin, is_active }),
      });
      showToast("Role zapisane.", "success");
      await _loadUsers();
      _renderDrawerHeader(userId);
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });

  body.querySelector("#reset-pw-btn").addEventListener("click", async () => {
    const pw = body.querySelector("#new-pw-input").value;
    if (!pw || pw.length < 8) { showToast("Hasło musi mieć min. 8 znaków.", "error"); return; }
    try {
      await adminFetch(`/api/admin/accounts/${userId}/set-password`, {
        method: "POST",
        body: JSON.stringify({ new_password: pw }),
      });
      showToast("Hasło zostało zmienione.", "success");
      body.querySelector("#new-pw-input").value = "";
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });

  body.querySelector("#deactivate-btn").addEventListener("click", async () => {
    const nextActive = user.is_active ? 0 : 1;
    const msg = nextActive ? "Odblokować konto?" : "Zablokować konto?";
    if (!confirm(msg)) return;
    try {
      await adminFetch(`/api/admin/accounts/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: nextActive }),
      });
      showToast(nextActive ? "Konto odblokowane." : "Konto zablokowane.", "success");
      await _loadUsers();
      _renderDrawerHeader(userId);
      await _renderInfoTab(userId, body);
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });
}

// ── Campaigns tab ─────────────────────────────────────────────────────────────

async function _renderCampaignsTab(userId, body) {
  let campaigns = [];
  try {
    const data = await adminFetch(`/api/admin/users/${userId}/activity`);
    campaigns = data.items || [];
  } catch (e) {
    body.innerHTML = `<p class="drawer-error">Błąd: ${_esc(e.message)}</p>`;
    return;
  }

  if (!campaigns.length) {
    body.innerHTML = `<p class="drawer-empty">${LABELS.noCampaigns}</p>`;
    return;
  }

  const statusLabel = { active: "Aktywna", ended: "Zakończona", aborted: "Przerwana" };
  const statusBadge = { active: "admin-badge-green", ended: "admin-badge-muted", aborted: "admin-badge-red" };

  body.innerHTML = campaigns.map((c) => {
    const hp     = c.char_current_hp ?? null;
    const maxHp  = c.char_max_hp ?? null;
    const hpPct  = (hp !== null && maxHp) ? Math.round((hp / maxHp) * 100) : null;
    const hpColor = hpPct === null ? "var(--text-muted)" : hpPct > 60 ? "var(--accent-green)" : hpPct > 25 ? "var(--accent-gold)" : "var(--accent-red)";
    const lastTurn = c.last_turn_at ? new Date(c.last_turn_at).toLocaleDateString("pl-PL") : "—";

    // Stage 11 R9 — admin force-resurrect button shown only when char is dead
    const isDead = c.char_status === "dead";
    const resurrectBtn = (isDead && c.char_id) ? `
        <div style="margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08);">
          <span class="admin-badge admin-badge-red" style="margin-bottom:6px; display:inline-block;">💀 Bohater martwy</span>
          <button class="primary-btn" data-resurrect-id="${c.char_id}" data-resurrect-name="${_esc(c.char_name || "")}" style="margin-top:6px; width:100%;">
            ✦ Wskrześ bohatera (bezpłatnie, force)
          </button>
        </div>` : "";

    return `
      <div class="campaign-card">
        <div class="campaign-card-top">
          <div class="campaign-card-title">${_esc(c.title)}</div>
          <span class="admin-badge ${statusBadge[c.status] || "admin-badge-muted"}">${statusLabel[c.status] || c.status}</span>
        </div>
        ${c.char_name ? `
        <div class="campaign-card-char">
          <span>${_esc(c.char_name)}</span>
          ${c.char_archetype ? `<span class="char-archetype">${_esc(c.char_archetype)}</span>` : ""}
        </div>
        ${hpPct !== null ? `
        <div class="hp-bar-wrap" title="HP: ${hp}/${maxHp}">
          <div class="hp-bar-fill" style="width:${hpPct}%;background:${hpColor}"></div>
        </div>
        <div class="hp-bar-label" style="color:${hpColor}">${hp}/${maxHp} HP</div>` : ""}` : ""}
        <div class="campaign-card-meta">
          <span>Tury: ${c.turn_count}</span>
          <span>Ostatnia: ${lastTurn}</span>
        </div>
        ${resurrectBtn}
      </div>`;
  }).join("");

  // Wire any resurrect buttons
  body.querySelectorAll("[data-resurrect-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const charId = btn.dataset.resurrectId;
      const name = btn.dataset.resurrectName || "Bohater";
      if (!confirm(`Wskrzesić bohatera „${name}" bezpłatnie (admin force)?`)) return;
      btn.disabled = true;
      btn.textContent = "Wskrzeszam…";
      try {
        const res = await adminFetch(`/api/admin/characters/${charId}/resurrect`, {
          method: "POST",
          body: JSON.stringify({ force: true }),
        });
        showToast(`✦ ${name} wskrzeszony — HP ${res.revived_hp}/${res.max_hp}`, "success");
        await _renderCampaignsTab(userId, body);
      } catch (e) {
        showToast(e.message || "Błąd wskrzeszenia", "error");
        btn.disabled = false;
        btn.textContent = "✦ Wskrześ bohatera (bezpłatnie, force)";
      }
    });
  });
}

// ── LLM tab ───────────────────────────────────────────────────────────────────

async function _renderLlmTab(userId, body) {
  let settings = {};
  try {
    const data = await adminFetch(`/api/admin/users/${userId}/llm-settings`);
    settings = data.settings || {};
  } catch (e) {
    body.innerHTML = `<p class="drawer-error">Błąd: ${_esc(e.message)}</p>`;
    return;
  }

  const isCustom = settings.mode === "custom";

  body.innerHTML = `
    <div class="drawer-section">
      <div class="drawer-section-title">${LABELS.llmMode}</div>
      <div class="llm-mode-toggle">
        <label class="drawer-toggle-row">
          <span>${LABELS.modeCustom}</span>
          <input type="checkbox" id="llm-custom-chk" ${isCustom ? "checked" : ""} />
        </label>
      </div>
      <div id="llm-custom-fields" style="display:${isCustom ? "" : "none"}">
        <label class="drawer-field">
          <span>${LABELS.llmProvider}</span>
          <select id="llm-provider">
            <option value="openai" ${settings.provider === "openai" ? "selected" : ""}>OpenAI</option>
            <option value="ollama" ${settings.provider === "ollama" ? "selected" : ""}>Ollama</option>
            <option value="other"  ${!["openai","ollama"].includes(settings.provider) && settings.provider ? "selected" : ""}>Inny</option>
          </select>
        </label>
        <label class="drawer-field">
          <span>${LABELS.llmBaseUrl}</span>
          <input id="llm-base-url" type="text" value="${_esc(settings.base_url || "")}" placeholder="https://api.openai.com" />
        </label>
        <label class="drawer-field">
          <span>${LABELS.llmModel}</span>
          <input id="llm-model" type="text" value="${_esc(settings.model || "")}" placeholder="gpt-4.1" />
        </label>
        <label class="drawer-field">
          <span>${LABELS.llmApiKey} ${settings.api_key_set ? "<em>(ustawiony)</em>" : ""}</span>
          <input id="llm-api-key" type="password" autocomplete="off" placeholder="Zostaw puste, by nie zmieniać" />
        </label>
      </div>
      <button class="primary-btn" id="save-llm-btn" style="margin-top:12px">Zapisz LLM</button>
    </div>`;

  body.querySelector("#llm-custom-chk").addEventListener("change", (e) => {
    body.querySelector("#llm-custom-fields").style.display = e.target.checked ? "" : "none";
  });

  body.querySelector("#save-llm-btn").addEventListener("click", async () => {
    const isCustomNow = body.querySelector("#llm-custom-chk").checked;
    const payload = { mode: isCustomNow ? "custom" : "default" };
    if (isCustomNow) {
      payload.provider = body.querySelector("#llm-provider").value;
      payload.base_url = body.querySelector("#llm-base-url").value.trim();
      payload.model    = body.querySelector("#llm-model").value.trim();
      const apiKey = body.querySelector("#llm-api-key").value;
      if (apiKey) payload.api_key = apiKey;
    }
    try {
      await adminFetch(`/api/admin/users/${userId}/llm-settings`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      showToast("Ustawienia LLM zapisane.", "success");
      await _renderLlmTab(userId, body);
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });
}

// ── Resurrect tab (Stage 11 R7 — issue #64) ──────────────────────────────────

const RESURRECT_MODE_LABELS = {
  admin_free:       "🆓 Bezpłatnie (tryb admina/GM)",
  gold_percent:     "💰 Procent obecnego złota",
  gold_recent_days: "📜 Niedawne zarobki (okno dni)",
  xp_revert:        "✦ Cofnij ostatnie zdobycie PD",
  item_loss:        "🎒 Utrata losowego założonego przedmiotu",
};

function _resurrectModeHelpText(cfg) {
  switch (cfg.mode) {
    case "admin_free":
      return "Bohater zostanie wskrzeszony bez żadnego kosztu.";
    case "gold_percent":
      return `Bohater straci <strong>${cfg.value}%</strong> obecnego złota.`;
    case "gold_recent_days":
      return `Bohater straci sumę zarobków z ostatnich <strong>${cfg.value} dni gry</strong>, maksymalnie <strong>${cfg.cap_percent}%</strong> obecnego złota.`;
    case "xp_revert":
      return `Cofnięte zostanie <strong>${cfg.value} PD</strong> (lub więcej, do najbliższego pełnego nadania). Zakupione w tym czasie awanse umiejętności i zaklęć zostaną cofnięte.`;
    case "item_loss":
      return "Losowo wybrany funkcjonalny przedmiot z ekwipunku zostanie utracony.";
    default:
      return "";
  }
}

async function _renderResurrectTab(userId, body) {
  let cfg = {};
  try {
    const data = await adminFetch(`/api/admin/users/${userId}/resurrection-config`);
    cfg = data.config || {};
  } catch (e) {
    body.innerHTML = `<p class="drawer-error">Błąd: ${_esc(e.message)}</p>`;
    return;
  }

  const modeOpts = Object.entries(RESURRECT_MODE_LABELS).map(([k, lbl]) =>
    `<option value="${k}"${cfg.mode === k ? " selected" : ""}>${lbl}</option>`
  ).join("");

  body.innerHTML = `
    <div class="drawer-section">
      <div class="drawer-section-title">Wskrzeszenie bohatera</div>
      <p style="font-size: 0.85rem; opacity: 0.7; margin: 0 0 12px;">
        Po zgonie bohatera ekran śmierci pokaże przycisk „Wskrześ" tylko wtedy, gdy ta opcja
        jest włączona. Koszt zależy od wybranego trybu i jest egzekwowany serwerowo.
      </p>

      <label class="drawer-toggle-row">
        <span>Włączone</span>
        <input type="checkbox" id="res-enabled" ${cfg.enabled ? "checked" : ""} />
      </label>

      <label class="drawer-field">
        <span>Tryb kosztu</span>
        <select id="res-mode">${modeOpts}</select>
      </label>

      <label class="drawer-field">
        <span>Wartość główna (PD / % / dni)</span>
        <input id="res-value" type="number" min="0" max="9999" value="${cfg.value ?? 25}" />
      </label>

      <label class="drawer-field" id="res-cap-row">
        <span>Górny limit % bieżącego złota (tylko dla „niedawne zarobki")</span>
        <input id="res-cap" type="number" min="0" max="100" value="${cfg.cap_percent ?? 50}" />
      </label>

      <label class="drawer-field">
        <span>Pozostałych użyć (puste = bez limitu)</span>
        <input id="res-uses" type="number" min="0" max="999" value="${cfg.uses_remaining ?? ""}" placeholder="bez limitu" />
      </label>

      <div id="res-help" style="margin: 12px 0; padding: 10px; background: rgba(255,255,255,0.04); border-radius: 6px; font-size: 0.9rem; line-height: 1.4;">
        ${_resurrectModeHelpText(cfg)}
      </div>

      <button class="primary-btn" id="res-save-btn" style="margin-top: 4px">Zapisz konfigurację</button>
    </div>`;

  const elMode = body.querySelector("#res-mode");
  const elVal = body.querySelector("#res-value");
  const elCap = body.querySelector("#res-cap");
  const elUses = body.querySelector("#res-uses");
  const elEnabled = body.querySelector("#res-enabled");
  const elHelp = body.querySelector("#res-help");
  const elCapRow = body.querySelector("#res-cap-row");

  const refreshHelp = () => {
    elHelp.innerHTML = _resurrectModeHelpText({
      mode: elMode.value,
      value: parseInt(elVal.value, 10) || 0,
      cap_percent: parseInt(elCap.value, 10) || 0,
    });
    elCapRow.style.display = elMode.value === "gold_recent_days" ? "" : "none";
  };
  elMode.addEventListener("change", refreshHelp);
  elVal.addEventListener("input", refreshHelp);
  elCap.addEventListener("input", refreshHelp);
  refreshHelp();

  body.querySelector("#res-save-btn").addEventListener("click", async () => {
    const usesRaw = elUses.value.trim();
    const payload = {
      enabled: elEnabled.checked,
      mode: elMode.value,
      value: parseInt(elVal.value, 10) || 0,
      cap_percent: parseInt(elCap.value, 10) || 0,
    };
    if (usesRaw === "") {
      payload.clear_uses_remaining = true;
    } else {
      payload.uses_remaining = parseInt(usesRaw, 10) || 0;
    }
    try {
      await adminFetch(`/api/admin/users/${userId}/resurrection-config`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      showToast("Konfiguracja wskrzeszenia zapisana.", "success");
      await _renderResurrectTab(userId, body);
    } catch (e) {
      showToast(e.message || "Błąd zapisu", "error");
    }
  });
}

// ── Create user modal ─────────────────────────────────────────────────────────

function _openCreateModal() {
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Nazwa użytkownika *</span><input name="username" type="text" placeholder="np. jan_kowalski" autocomplete="off" /></label>
    <label class="modal-field"><span>Hasło * (min. 8 znaków)</span><input name="password" type="password" autocomplete="new-password" /></label>
    <label class="modal-field"><span>Nazwa wyświetlana</span><input name="display_name" type="text" placeholder="Jan Kowalski" autocomplete="off" /></label>
    <label class="modal-checkbox-row"><input name="is_admin" type="checkbox" /><span>Administrator</span></label>`;

  openModal({
    title: LABELS.addUser,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: LABELS.addUser,
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const username     = g("username").value.trim();
          const password     = g("password").value;
          const display_name = g("display_name").value.trim();
          const is_admin     = g("is_admin").checked ? 1 : 0;
          if (!username) { showToast("Nazwa użytkownika jest wymagana.", "error"); return; }
          if (!password || password.length < 8) { showToast("Hasło musi mieć min. 8 znaków.", "error"); return; }
          try {
            await adminFetch("/api/admin/accounts/create", {
              method: "POST",
              body: JSON.stringify({ username, password, display_name, is_admin }),
            });
            showToast("Konto utworzone.", "success");
            c();
            await _loadUsers();
          } catch (e) { showToast(e.message || "Błąd tworzenia konta", "error"); }
        },
      },
    ],
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
