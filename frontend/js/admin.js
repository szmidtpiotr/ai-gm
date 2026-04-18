(function () {
  const state = {
    baseUrl: "/api",
    token: "",
    connected: false,
    selectedImportPayload: null,
  };

  const el = {};

  function bindEls() {
    el.baseUrl = document.getElementById("admin-base-url");
    el.token = document.getElementById("admin-token");
    el.loginBtn = document.getElementById("admin-login-btn");
    el.logoutBtn = document.getElementById("admin-logout-btn");
    el.loginStatus = document.getElementById("admin-login-status");
    el.statsList = document.getElementById("stats-list");
    el.skillsList = document.getElementById("skills-list");
    el.dcList = document.getElementById("dc-list");
    el.weaponsList = document.getElementById("weapons-list");
    el.enemiesList = document.getElementById("enemies-list");
    el.conditionsList = document.getElementById("conditions-list");
    el.accountsList = document.getElementById("accounts-list");
    el.logBox = document.getElementById("admin-log-box");
    el.exportBtn = document.getElementById("export-config-btn");
    el.importFile = document.getElementById("import-config-file");
    el.importDryBtn = document.getElementById("import-config-dry-btn");
    el.importCommitBtn = document.getElementById("import-config-commit-btn");
    el.newSkillKey = document.getElementById("new-skill-key");
    el.newSkillLabel = document.getElementById("new-skill-label");
    el.newSkillStat = document.getElementById("new-skill-stat");
    el.newSkillRank = document.getElementById("new-skill-rank");
    el.newSkillDescription = document.getElementById("new-skill-description");
    el.newSkillBtn = document.getElementById("new-skill-btn");
    el.newWeaponKey = document.getElementById("new-weapon-key");
    el.newWeaponLabel = document.getElementById("new-weapon-label");
    el.newWeaponDie = document.getElementById("new-weapon-die");
    el.newWeaponStat = document.getElementById("new-weapon-stat");
    el.newWeaponClasses = document.getElementById("new-weapon-classes");
    el.newWeaponActive = document.getElementById("new-weapon-active");
    el.newWeaponBtn = document.getElementById("new-weapon-btn");
    el.newEnemyKey = document.getElementById("new-enemy-key");
    el.newEnemyLabel = document.getElementById("new-enemy-label");
    el.newEnemyHp = document.getElementById("new-enemy-hp");
    el.newEnemyAc = document.getElementById("new-enemy-ac");
    el.newEnemyAtk = document.getElementById("new-enemy-atk");
    el.newEnemyDie = document.getElementById("new-enemy-die");
    el.newEnemyDesc = document.getElementById("new-enemy-desc");
    el.newEnemyActive = document.getElementById("new-enemy-active");
    el.newEnemyBtn = document.getElementById("new-enemy-btn");
    el.newConditionKey = document.getElementById("new-condition-key");
    el.newConditionLabel = document.getElementById("new-condition-label");
    el.newConditionEffect = document.getElementById("new-condition-effect");
    el.newConditionDesc = document.getElementById("new-condition-desc");
    el.newConditionActive = document.getElementById("new-condition-active");
    el.newConditionBtn = document.getElementById("new-condition-btn");
    el.devUsername = document.getElementById("admin-dev-username");
    el.devPassword = document.getElementById("admin-dev-password");
    el.devLoginBtn = document.getElementById("admin-dev-login-btn");
    el.userLlmUserSelect = document.getElementById("user-llm-user-select");
    el.userLlmLoadBtn = document.getElementById("user-llm-load-btn");
    el.userLlmSaveBtn = document.getElementById("user-llm-save-btn");
    el.userLlmProvider = document.getElementById("user-llm-provider");
    el.userLlmBaseUrl = document.getElementById("user-llm-base-url");
    el.userLlmApiKey = document.getElementById("user-llm-api-key");
    el.userLlmModel = document.getElementById("user-llm-model");
    el.campaignHistoryList = document.getElementById("campaign-history-list");
    el.campaignHistoryRefreshBtn = document.getElementById("campaign-history-refresh-btn");
    el.campaignHistoryMaxTurns = document.getElementById("campaign-history-max-turns");
    el.lokiUrlInput = document.getElementById("loki-url-input");
    el.lokiRetrieveBtn = document.getElementById("loki-retrieve-btn");
    el.lokiSaveBtn = document.getElementById("loki-save-btn");
    el.lokiUrlHint = document.getElementById("loki-url-hint");
    el.characterRecreateId = document.getElementById("character-recreate-id");
    el.characterRecreateName = document.getElementById("character-recreate-name");
    el.characterRecreateClearInv = document.getElementById("character-recreate-clear-inv");
    el.characterRecreateJson = document.getElementById("character-recreate-json");
    el.characterRecreateLoadBtn = document.getElementById("character-recreate-load-btn");
    el.characterRecreateApplyBtn = document.getElementById("character-recreate-apply-btn");
    el.characterRecreateList = document.getElementById("character-recreate-list");
    el.characterRecreateRefreshBtn = document.getElementById("character-recreate-refresh-btn");
    el.tabButtons = Array.from(document.querySelectorAll(".admin-tab"));
    el.tabPanels = Array.from(document.querySelectorAll(".admin-tab-panel"));
  }

  function log(msg) {
    const now = new Date().toISOString();
    el.logBox.textContent = `[${now}] ${msg}\n` + el.logBox.textContent;
  }

  function setConnected(connected) {
    state.connected = connected;
    el.logoutBtn.disabled = !connected;
    el.exportBtn.disabled = !connected;
    el.importFile.disabled = !connected;
    el.importDryBtn.disabled = !connected || !state.selectedImportPayload;
    el.importCommitBtn.disabled = !connected || !state.selectedImportPayload;
    el.newSkillBtn.disabled = !connected;
    if (el.newWeaponBtn) el.newWeaponBtn.disabled = !connected;
    if (el.newEnemyBtn) el.newEnemyBtn.disabled = !connected;
    if (el.newConditionBtn) el.newConditionBtn.disabled = !connected;
    if (el.userLlmLoadBtn) el.userLlmLoadBtn.disabled = !connected;
    if (el.userLlmSaveBtn) el.userLlmSaveBtn.disabled = !connected;
    if (el.campaignHistoryRefreshBtn) el.campaignHistoryRefreshBtn.disabled = !connected;
    if (el.campaignHistoryMaxTurns) el.campaignHistoryMaxTurns.disabled = !connected;
    if (el.lokiRetrieveBtn) el.lokiRetrieveBtn.disabled = !connected;
    if (el.lokiSaveBtn) el.lokiSaveBtn.disabled = !connected;
    if (el.characterRecreateLoadBtn) el.characterRecreateLoadBtn.disabled = !connected;
    if (el.characterRecreateApplyBtn) el.characterRecreateApplyBtn.disabled = !connected;
    if (el.characterRecreateRefreshBtn) el.characterRecreateRefreshBtn.disabled = !connected;
    el.loginStatus.textContent = connected ? "Connected." : "Not connected.";
  }

  async function api(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    if (state.token) {
      headers.Authorization = `Bearer ${state.token}`;
    }
    const response = await fetch(`${state.baseUrl}${path}`, {
      ...options,
      headers,
    });
    const raw = await response.text();
    const data = raw ? JSON.parse(raw) : {};
    if (!response.ok) {
      const detail = data.detail ? JSON.stringify(data.detail) : response.statusText;
      throw new Error(`${response.status} ${detail}`);
    }
    return data;
  }

  function parseAllowedClasses(str) {
    return String(str || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function classesToInput(val) {
    if (Array.isArray(val)) return val.join(",");
    if (typeof val === "string" && val.trim().startsWith("[")) {
      try {
        const arr = JSON.parse(val);
        return Array.isArray(arr) ? arr.join(",") : val;
      } catch {
        return val;
      }
    }
    return String(val || "");
  }

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\"", "&quot;");
  }

  function table(headers, rowsHtml) {
    return `<table class="admin-table"><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rowsHtml}</tbody></table>`;
  }

  function isLocked(record) {
    return Boolean(record && record.locked_at);
  }

  async function loadStats() {
    const data = await api("/admin/stats");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="stat" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="stat" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description)}"></td>
        <td><input type="number" data-row="stat" data-key="${esc(x.key)}" data-field="sort_order" value="${esc(x.sort_order)}"></td>
        <td><button data-save="stat" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button></td>
      </tr>
    `).join("");
    el.statsList.innerHTML = table(["Key", "Label", "Description", "Order", "Action"], rows);
  }

  async function loadSkills() {
    const data = await api("/admin/skills");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="skill" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="skill" data-key="${esc(x.key)}" data-field="linked_stat" value="${esc(x.linked_stat)}"></td>
        <td><input type="number" data-row="skill" data-key="${esc(x.key)}" data-field="rank_ceiling" value="${esc(x.rank_ceiling)}"></td>
        <td><input data-row="skill" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description || '')}"></td>
        <td><input type="number" data-row="skill" data-key="${esc(x.key)}" data-field="sort_order" value="${esc(x.sort_order)}"></td>
        <td>
          <button data-save="skill" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="skill" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>
    `).join("");
    el.skillsList.innerHTML = table(["Key", "Label", "Linked Stat", "Rank", "Description", "Order", "Action"], rows);
  }

  async function loadDc() {
    const data = await api("/admin/dc");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="dc" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input type="number" data-row="dc" data-key="${esc(x.key)}" data-field="value" value="${esc(x.value)}"></td>
        <td><input data-row="dc" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description || '')}"></td>
        <td><input type="number" data-row="dc" data-key="${esc(x.key)}" data-field="sort_order" value="${esc(x.sort_order)}"></td>
        <td><button data-save="dc" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button></td>
      </tr>
    `).join("");
    el.dcList.innerHTML = table(["Key", "Label", "Value", "Description", "Order", "Action"], rows);
  }

  async function loadWeapons() {
    if (!el.weaponsList) return;
    const data = await api("/admin/weapons");
    const rows = data.items.map((x) => {
      const active = x.is_active ? "1" : "0";
      const cls = classesToInput(x.allowed_classes);
      return `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="damage_die" value="${esc(x.damage_die)}"></td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="linked_stat" value="${esc(x.linked_stat)}"></td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="allowed_classes" value="${esc(cls)}"></td>
        <td>
          <select data-row="weapon" data-key="${esc(x.key)}" data-field="is_active">
            <option value="1" ${active === "1" ? "selected" : ""}>yes</option>
            <option value="0" ${active === "0" ? "selected" : ""}>no</option>
          </select>
        </td>
        <td>
          <button data-save="weapon" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="weapon" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>`;
    }).join("");
    el.weaponsList.innerHTML = table(
      ["Key", "Label", "Die", "Stat", "Classes", "Active", "Action"],
      rows
    );
  }

  async function loadEnemies() {
    if (!el.enemiesList) return;
    const data = await api("/admin/enemies");
    const rows = data.items.map((x) => {
      const active = x.is_active ? "1" : "0";
      return `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="enemy" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input type="number" data-row="enemy" data-key="${esc(x.key)}" data-field="hp_base" value="${esc(x.hp_base)}"></td>
        <td><input type="number" data-row="enemy" data-key="${esc(x.key)}" data-field="ac_base" value="${esc(x.ac_base)}"></td>
        <td><input type="number" data-row="enemy" data-key="${esc(x.key)}" data-field="attack_bonus" value="${esc(x.attack_bonus)}"></td>
        <td><input data-row="enemy" data-key="${esc(x.key)}" data-field="damage_die" value="${esc(x.damage_die)}"></td>
        <td><input data-row="enemy" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description || "")}"></td>
        <td>
          <select data-row="enemy" data-key="${esc(x.key)}" data-field="is_active">
            <option value="1" ${active === "1" ? "selected" : ""}>yes</option>
            <option value="0" ${active === "0" ? "selected" : ""}>no</option>
          </select>
        </td>
        <td>
          <button data-save="enemy" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="enemy" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>`;
    }).join("");
    el.enemiesList.innerHTML = table(
      ["Key", "Label", "HP", "AC", "Atk", "Die", "Desc", "Active", "Action"],
      rows
    );
  }

  async function loadConditions() {
    if (!el.conditionsList) return;
    const data = await api("/admin/conditions");
    const rows = data.items.map((x) => {
      const active = x.is_active ? "1" : "0";
      return `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="condition" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="condition" data-key="${esc(x.key)}" data-field="effect_json" value="${esc(x.effect_json || "")}" class="wide-input"></td>
        <td><input data-row="condition" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description || "")}"></td>
        <td>
          <select data-row="condition" data-key="${esc(x.key)}" data-field="is_active">
            <option value="1" ${active === "1" ? "selected" : ""}>yes</option>
            <option value="0" ${active === "0" ? "selected" : ""}>no</option>
          </select>
        </td>
        <td>
          <button data-save="condition" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="condition" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>`;
    }).join("");
    el.conditionsList.innerHTML = table(
      ["Key", "Label", "effect_json", "Description", "Active", "Action"],
      rows
    );
  }

  function clampCampaignHistoryMaxTurns(raw) {
    const n = Number.parseInt(String(raw || "200"), 10);
    if (Number.isNaN(n)) return 200;
    return Math.min(2000, Math.max(5, n));
  }

  async function loadCampaignHistory() {
    if (!el.campaignHistoryList) return;
    const data = await api("/campaigns");
    const campaigns = Array.isArray(data.campaigns) ? data.campaigns : [];
    if (campaigns.length === 0) {
      el.campaignHistoryList.innerHTML = "<p class=\"muted\">Brak kampanii.</p>";
      return;
    }
    const rows = campaigns.map((c) => {
      const id = c.id;
      const owner = c.owner_user_id;
      return `
      <tr>
        <td>${esc(id)}</td>
        <td>${esc(c.title || "")}</td>
        <td>${esc(owner)}</td>
        <td>${esc(c.status || "")}</td>
        <td>
          <button type="button" class="secondary" data-campaign-summary-fetch="${esc(id)}">Pobierz zapisane</button>
          <button type="button" class="danger" data-campaign-summary-regen="${esc(id)}" data-owner-id="${esc(owner)}">Regeneruj</button>
        </td>
      </tr>`;
    }).join("");
    el.campaignHistoryList.innerHTML = table(
      ["ID kampanii", "Tytuł", "Właściciel (user_id)", "Status", "Historia"],
      rows
    );
  }

  async function loadCharacterRecreateList() {
    if (!el.characterRecreateList) return;
    const data = await api("/admin/characters");
    const items = Array.isArray(data.items) ? data.items : [];
    if (items.length === 0) {
      el.characterRecreateList.innerHTML = "<p class=\"muted\">Brak postaci.</p>";
      return;
    }
    const rows = items.map((c) => {
      const id = c.id;
      return `
      <tr>
        <td>${esc(id)}</td>
        <td>${esc(c.name || "")}</td>
        <td>${esc(c.campaign_id)}</td>
        <td>${esc(c.campaign_title || "")}</td>
        <td>${esc(c.user_id)}</td>
        <td>
          <button type="button" class="secondary" data-cr-select="${esc(id)}" data-cr-name="${esc(c.name || "")}">Wybierz</button>
          <button type="button" class="danger" data-char-delete="${esc(id)}" data-char-name="${esc(c.name || "")}">Usuń bohatera</button>
        </td>
      </tr>`;
    }).join("");
    el.characterRecreateList.innerHTML = table(
      ["ID", "Imię", "Kampania (id)", "Kampania (tytuł)", "user_id", "Akcja"],
      rows
    );
  }

  async function loadAccounts() {
    const data = await api("/admin/accounts");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.id)}</td>
        <td>${esc(x.username)}</td>
        <td><input data-row="account" data-key="${esc(x.id)}" data-field="display_name" value="${esc(x.display_name)}"></td>
        <td><input type="number" min="0" max="1" data-row="account" data-key="${esc(x.id)}" data-field="is_active" value="${esc(x.is_active)}"></td>
        <td>${esc(x.characters_count)}</td>
        <td>
          <button data-save="account" data-key="${esc(x.id)}" class="secondary">Save</button>
          <button data-reset="account" data-key="${esc(x.id)}" class="secondary">Reset Sheet</button>
          <button data-delete="account" data-key="${esc(x.id)}" class="danger">Soft Delete</button>
        </td>
      </tr>
    `).join("");
    el.accountsList.innerHTML = table(["ID", "Username", "Display Name", "Active", "Chars", "Action"], rows);
  }

  async function loadUserLlmUsers() {
    const data = await api("/admin/accounts");
    const items = Array.isArray(data.items) ? data.items : [];
    const sel = el.userLlmUserSelect;
    if (!sel) return;
    sel.innerHTML = '<option value="" selected disabled>Select user...</option>';
    items.forEach((x) => {
      const opt = document.createElement("option");
      opt.value = String(x.id);
      opt.textContent = `${x.id} — ${x.username} (${x.display_name})`;
      sel.appendChild(opt);
    });
    el.userLlmLoadBtn && (el.userLlmLoadBtn.disabled = !sel.value);
  }

  function formatLokiHint(data) {
    if (!data) return "";
    const stored = data.stored != null && String(data.stored).trim() !== "" ? data.stored : "—";
    const env = data.from_env != null && String(data.from_env).trim() !== "" ? data.from_env : "—";
    const def = data.builtin_default || "http://loki:3100";
    return `Stored in DB: ${stored}\nLOKI_URL env: ${env}\nFallback default: ${def}`;
  }

  async function loadLokiSettings() {
    if (!state.connected) return;
    const data = await api("/admin/settings/loki");
    if (el.lokiUrlInput) el.lokiUrlInput.value = data.loki_url || "";
    if (el.lokiUrlHint) el.lokiUrlHint.textContent = formatLokiHint(data);
  }

  async function loadUserLlmSettingsForUser(userId) {
    if (!userId) return;
    const result = await api(`/admin/users/${encodeURIComponent(userId)}/llm-settings`);
    const settings = result?.settings || {};

    if (el.userLlmProvider) el.userLlmProvider.value = settings.provider || "ollama";
    if (el.userLlmBaseUrl) el.userLlmBaseUrl.value = settings.base_url || "";
    if (el.userLlmModel) el.userLlmModel.value = settings.model || "";
    if (el.userLlmApiKey) el.userLlmApiKey.value = "";

    if (el.userLlmSaveBtn) el.userLlmSaveBtn.disabled = false;
  }

  async function refreshAll() {
    await Promise.all([
      loadStats(),
      loadSkills(),
      loadDc(),
      loadWeapons(),
      loadEnemies(),
      loadConditions(),
      loadAccounts(),
      loadUserLlmUsers(),
      loadCampaignHistory(),
      loadCharacterRecreateList(),
      loadLokiSettings(),
    ]);
  }

  function getInputValue(rowType, key, field) {
    const escKey = CSS.escape(String(key));
    const sel = `input[data-row="${rowType}"][data-key="${escKey}"][data-field="${field}"],select[data-row="${rowType}"][data-key="${escKey}"][data-field="${field}"]`;
    const node = document.querySelector(sel);
    return node ? node.value : "";
  }

  async function handleSave(event) {
    const btn = event.target.closest("[data-save]");
    if (!btn) return;
    const type = btn.dataset.save;
    const key = btn.dataset.key;
    const locked = btn.dataset.locked === "1";
    try {
      if (locked) {
        const accepted = window.confirm(`Row ${type}:${key} is locked. Override with force=true?`);
        if (!accepted) return;
      }
      if (type === "stat") {
        await api(`/admin/stats/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("stat", key, "label"),
            description: getInputValue("stat", key, "description"),
            sort_order: Number(getInputValue("stat", key, "sort_order")),
            force: true,
          }),
        });
      } else if (type === "skill") {
        await api(`/admin/skills/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("skill", key, "label"),
            linked_stat: getInputValue("skill", key, "linked_stat").toUpperCase(),
            rank_ceiling: Number(getInputValue("skill", key, "rank_ceiling")),
            description: getInputValue("skill", key, "description"),
            sort_order: Number(getInputValue("skill", key, "sort_order")),
            force: true,
          }),
        });
      } else if (type === "dc") {
        await api(`/admin/dc/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("dc", key, "label"),
            value: Number(getInputValue("dc", key, "value")),
            description: getInputValue("dc", key, "description"),
            sort_order: Number(getInputValue("dc", key, "sort_order")),
            force: true,
          }),
        });
      } else if (type === "account") {
        await api(`/admin/accounts/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            display_name: getInputValue("account", key, "display_name"),
            is_active: Number(getInputValue("account", key, "is_active")),
          }),
        });
      } else if (type === "weapon") {
        const active = getInputValue("weapon", key, "is_active") === "1";
        await api(`/admin/weapons/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("weapon", key, "label"),
            damage_die: getInputValue("weapon", key, "damage_die"),
            linked_stat: getInputValue("weapon", key, "linked_stat").toUpperCase(),
            allowed_classes: parseAllowedClasses(getInputValue("weapon", key, "allowed_classes")),
            is_active: active,
            force: true,
          }),
        });
      } else if (type === "enemy") {
        const active = getInputValue("enemy", key, "is_active") === "1";
        await api(`/admin/enemies/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("enemy", key, "label"),
            hp_base: Number(getInputValue("enemy", key, "hp_base")),
            ac_base: Number(getInputValue("enemy", key, "ac_base")),
            attack_bonus: Number(getInputValue("enemy", key, "attack_bonus")),
            damage_die: getInputValue("enemy", key, "damage_die"),
            description: getInputValue("enemy", key, "description"),
            is_active: active,
            force: true,
          }),
        });
      } else if (type === "condition") {
        const active = getInputValue("condition", key, "is_active") === "1";
        await api(`/admin/conditions/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("condition", key, "label"),
            effect_json: getInputValue("condition", key, "effect_json"),
            description: getInputValue("condition", key, "description"),
            is_active: active,
            force: true,
          }),
        });
      }
      log(`Saved ${type}:${key}`);
      await refreshAll();
    } catch (err) {
      log(`Save failed ${type}:${key} -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleDelete(event) {
    const btn = event.target.closest("[data-delete]");
    if (!btn) return;
    const type = btn.dataset.delete;
    const key = btn.dataset.key;
    const locked = btn.dataset.locked === "1";
    try {
      const accepted = window.confirm(
        locked
          ? `Locked ${type}:${key}. Confirm force delete?`
          : `Confirm delete ${type}:${key}?`
      );
      if (!accepted) return;
      if (type === "skill") {
        await api(`/admin/skills/${encodeURIComponent(key)}`, {
          method: "DELETE",
          body: JSON.stringify({ force: true }),
        });
      } else if (type === "account") {
        await api(`/admin/accounts/${encodeURIComponent(key)}`, { method: "DELETE" });
      } else if (type === "weapon") {
        await api(`/admin/weapons/${encodeURIComponent(key)}`, {
          method: "DELETE",
          body: JSON.stringify({ force: true }),
        });
      } else if (type === "enemy") {
        await api(`/admin/enemies/${encodeURIComponent(key)}`, {
          method: "DELETE",
          body: JSON.stringify({ force: true }),
        });
      } else if (type === "condition") {
        await api(`/admin/conditions/${encodeURIComponent(key)}`, {
          method: "DELETE",
          body: JSON.stringify({ force: true }),
        });
      }
      log(`Deleted ${type}:${key}`);
      await refreshAll();
    } catch (err) {
      log(`Delete failed ${type}:${key} -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleReset(event) {
    const btn = event.target.closest("[data-reset]");
    if (!btn) return;
    const key = btn.dataset.key;
    try {
      const accepted = window.confirm(`Reset sheet for account:${key}? This cannot be undone.`);
      if (!accepted) return;
      await api(`/admin/accounts/${encodeURIComponent(key)}/reset-sheet`, { method: "POST" });
      log(`Reset sheet for account:${key}`);
      await refreshAll();
    } catch (err) {
      log(`Reset failed account:${key} -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleCreateWeapon() {
    if (!el.newWeaponBtn) return;
    try {
      await api("/admin/weapons", {
        method: "POST",
        body: JSON.stringify({
          key: el.newWeaponKey.value.trim(),
          label: el.newWeaponLabel.value.trim(),
          damage_die: el.newWeaponDie.value.trim(),
          linked_stat: el.newWeaponStat.value.trim().toUpperCase(),
          allowed_classes: parseAllowedClasses(el.newWeaponClasses.value),
          is_active: !!(el.newWeaponActive && el.newWeaponActive.checked),
        }),
      });
      log(`Created weapon:${el.newWeaponKey.value.trim()}`);
      el.newWeaponKey.value = "";
      el.newWeaponLabel.value = "";
      el.newWeaponDie.value = "";
      el.newWeaponStat.value = "";
      el.newWeaponClasses.value = "";
      await loadWeapons();
    } catch (err) {
      log(`Create weapon failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleCreateEnemy() {
    if (!el.newEnemyBtn) return;
    try {
      await api("/admin/enemies", {
        method: "POST",
        body: JSON.stringify({
          key: el.newEnemyKey.value.trim(),
          label: el.newEnemyLabel.value.trim(),
          hp_base: Number(el.newEnemyHp.value),
          ac_base: Number(el.newEnemyAc.value),
          attack_bonus: Number(el.newEnemyAtk.value),
          damage_die: el.newEnemyDie.value.trim(),
          description: (el.newEnemyDesc && el.newEnemyDesc.value.trim()) || null,
          is_active: !!(el.newEnemyActive && el.newEnemyActive.checked),
        }),
      });
      log(`Created enemy:${el.newEnemyKey.value.trim()}`);
      el.newEnemyKey.value = "";
      el.newEnemyLabel.value = "";
      el.newEnemyHp.value = "";
      el.newEnemyAc.value = "";
      el.newEnemyAtk.value = "";
      el.newEnemyDie.value = "";
      if (el.newEnemyDesc) el.newEnemyDesc.value = "";
      await loadEnemies();
    } catch (err) {
      log(`Create enemy failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleCreateCondition() {
    if (!el.newConditionBtn) return;
    try {
      await api("/admin/conditions", {
        method: "POST",
        body: JSON.stringify({
          key: el.newConditionKey.value.trim(),
          label: el.newConditionLabel.value.trim(),
          effect_json: el.newConditionEffect.value.trim(),
          description: (el.newConditionDesc && el.newConditionDesc.value.trim()) || null,
          is_active: !!(el.newConditionActive && el.newConditionActive.checked),
        }),
      });
      log(`Created condition:${el.newConditionKey.value.trim()}`);
      el.newConditionKey.value = "";
      el.newConditionLabel.value = "";
      el.newConditionEffect.value = "";
      if (el.newConditionDesc) el.newConditionDesc.value = "";
      await loadConditions();
    } catch (err) {
      log(`Create condition failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleCreateSkill() {
    try {
      await api("/admin/skills", {
        method: "POST",
        body: JSON.stringify({
          key: el.newSkillKey.value.trim(),
          label: el.newSkillLabel.value.trim(),
          linked_stat: el.newSkillStat.value.trim().toUpperCase(),
          rank_ceiling: Number(el.newSkillRank.value || 5),
          sort_order: 999,
          description: (el.newSkillDescription?.value || "").trim(),
        }),
      });
      log(`Created skill:${el.newSkillKey.value.trim()}`);
      el.newSkillKey.value = "";
      el.newSkillLabel.value = "";
      el.newSkillStat.value = "";
      if (el.newSkillDescription) el.newSkillDescription.value = "";
      await loadSkills();
    } catch (err) {
      log(`Create skill failed -> ${err.message}`);
      alert(err.message);
    }
  }

  function downloadJson(payload, filename) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleExport() {
    try {
      const payload = await api("/admin/config/export");
      const ts = new Date().toISOString().replaceAll(":", "-");
      downloadJson(payload, `ai-gm-config-${ts}.json`);
      log("Exported config.");
    } catch (err) {
      log(`Export failed -> ${err.message}`);
      alert(err.message);
    }
  }

  function handleImportFileChange() {
    const file = el.importFile.files && el.importFile.files[0];
    if (!file) {
      state.selectedImportPayload = null;
      setConnected(state.connected);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        state.selectedImportPayload = JSON.parse(reader.result);
        log(`Loaded import file: ${file.name}`);
      } catch (err) {
        state.selectedImportPayload = null;
        alert(`Invalid JSON file: ${err.message}`);
      }
      setConnected(state.connected);
    };
    reader.readAsText(file);
  }

  async function handleImport(dryRun) {
    if (!state.selectedImportPayload) {
      alert("Choose JSON file first.");
      return;
    }
    try {
      if (!dryRun) {
        const accepted = window.confirm("Commit import will overwrite current config tables. Continue?");
        if (!accepted) return;
      }
      const result = await api(`/admin/config/import?dry_run=${dryRun ? "true" : "false"}`, {
        method: "POST",
        body: JSON.stringify(state.selectedImportPayload),
      });
      log(`${dryRun ? "Dry run" : "Import commit"} success: ${JSON.stringify(result)}`);
      if (!dryRun) {
        await refreshAll();
      }
    } catch (err) {
      log(`Import failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function connect() {
    state.baseUrl = (el.baseUrl.value || "/api").trim().replace(/\/+$/, "");
    state.token = (el.token.value || "").trim();
    if (!state.token) {
      alert("Token is required.");
      return;
    }
    try {
      await api("/admin/verify");
      setConnected(true);
      log("Connected to admin API.");
      await refreshAll();
    } catch (err) {
      setConnected(false);
      state.token = "";
      log(`Connection failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function devLogin() {
    state.baseUrl = (el.baseUrl.value || "/api").trim().replace(/\/+$/, "");
    try {
      const result = await api("/admin/dev-login", {
        method: "POST",
        body: JSON.stringify({
          username: (el.devUsername.value || "").trim(),
          password: el.devPassword.value || "",
        }),
      });
      if (!result.token) {
        throw new Error("dev login returned no token");
      }
      el.token.value = result.token;
      await connect();
      log("Dev login generated token and connected.");
    } catch (err) {
      log(`Dev login failed -> ${err.message}`);
      alert(err.message);
    }
  }

  function logout() {
    state.token = "";
    state.connected = false;
    state.selectedImportPayload = null;
    el.token.value = "";
    el.importFile.value = "";
    setConnected(false);
    el.statsList.innerHTML = "";
    el.skillsList.innerHTML = "";
    el.dcList.innerHTML = "";
    if (el.weaponsList) el.weaponsList.innerHTML = "";
    if (el.enemiesList) el.enemiesList.innerHTML = "";
    if (el.conditionsList) el.conditionsList.innerHTML = "";
    el.accountsList.innerHTML = "";
    if (el.campaignHistoryList) el.campaignHistoryList.innerHTML = "";
    log("Logged out.");
  }

  function bindEvents() {
    el.loginBtn.addEventListener("click", connect);
    el.logoutBtn.addEventListener("click", logout);
    el.newSkillBtn.addEventListener("click", handleCreateSkill);
    if (el.newWeaponBtn) el.newWeaponBtn.addEventListener("click", handleCreateWeapon);
    if (el.newEnemyBtn) el.newEnemyBtn.addEventListener("click", handleCreateEnemy);
    if (el.newConditionBtn) el.newConditionBtn.addEventListener("click", handleCreateCondition);
    el.exportBtn.addEventListener("click", handleExport);
    el.importFile.addEventListener("change", handleImportFileChange);
    el.importDryBtn.addEventListener("click", () => handleImport(true));
    el.importCommitBtn.addEventListener("click", () => handleImport(false));
    el.devLoginBtn.addEventListener("click", devLogin);
    if (el.campaignHistoryRefreshBtn) {
      el.campaignHistoryRefreshBtn.addEventListener("click", async () => {
        try {
          await loadCampaignHistory();
          log("Lista kampanii odświeżona (zakładka Historia).");
        } catch (err) {
          log(`Odświeżenie listy kampanii nie powiodło się -> ${err.message}`);
          alert(err.message);
        }
      });
    }
    if (el.campaignHistoryList) {
      el.campaignHistoryList.addEventListener("click", async (event) => {
        const fetchBtn = event.target.closest("[data-campaign-summary-fetch]");
        const regenBtn = event.target.closest("[data-campaign-summary-regen]");
        if (!fetchBtn && !regenBtn) return;
        if (!state.connected) return;
        const maxTurns = clampCampaignHistoryMaxTurns(el.campaignHistoryMaxTurns?.value);
        try {
          if (fetchBtn) {
            const campaignId = fetchBtn.getAttribute("data-campaign-summary-fetch");
            const saved = await api(`/campaigns/${encodeURIComponent(campaignId)}/history/summary`);
            const preview = (saved.summary || "").slice(0, 800);
            log(
              `Zapisane podsumowanie kampania:${campaignId} summary_id:${saved.summary_id ?? "brak"} ` +
                `tury:${saved.included_turn_count ?? "?"} fragment:${preview || "(pusto)"}`
            );
            return;
          }
          const campaignId = regenBtn.getAttribute("data-campaign-summary-regen");
          const ownerId = regenBtn.getAttribute("data-owner-id");
          if (!campaignId || !ownerId) return;
          const ok = window.confirm(
            `Wygenerować ponownie podsumowanie AI dla kampanii ${campaignId} (właściciel user ${ownerId})? To wywołuje model LLM.`
          );
          if (!ok) return;
          const result = await api(
            `/campaigns/${encodeURIComponent(campaignId)}/history/summary?user_id=${encodeURIComponent(
              ownerId
            )}&persist=true&max_turns=${encodeURIComponent(String(maxTurns))}`,
            { method: "POST", body: "{}" }
          );
          const snippet = (result.summary || "").slice(0, 400);
          log(
            `Zregenerowano kampania:${campaignId} zapis:${result.persisted} ` +
              `tury:${result.included_turn_count} model:${result.model_used || "?"} ` +
              `fragment:${snippet || "(pusto)"}`
          );
        } catch (err) {
          log(`Akcja historii kampanii nie powiodła się -> ${err.message}`);
          alert(err.message);
        }
      });
    }
    if (el.userLlmUserSelect && el.userLlmLoadBtn) {
      el.userLlmUserSelect.addEventListener("change", () => {
        el.userLlmLoadBtn.disabled = !el.userLlmUserSelect.value;
        if (el.userLlmSaveBtn) el.userLlmSaveBtn.disabled = true;
      });
      el.userLlmLoadBtn.addEventListener("click", async () => {
        try {
          const userId = el.userLlmUserSelect.value;
          if (!userId) return;
          await loadUserLlmSettingsForUser(userId);
          log(`Loaded user LLM for user:${userId}`);
        } catch (err) {
          log(`Load user LLM failed -> ${err.message}`);
          alert(err.message);
        }
      });
    }

    if (el.lokiRetrieveBtn) {
      el.lokiRetrieveBtn.addEventListener("click", async () => {
        try {
          await loadLokiSettings();
          log("Loki settings retrieved from server.");
        } catch (err) {
          log(`Loki retrieve failed -> ${err.message}`);
          alert(err.message);
        }
      });
    }
    if (el.characterRecreateRefreshBtn) {
      el.characterRecreateRefreshBtn.addEventListener("click", async () => {
        try {
          await loadCharacterRecreateList();
          log("Lista postaci (admin) odświeżona.");
        } catch (err) {
          log(`Lista postaci nie powiodła się -> ${err.message}`);
          alert(err.message);
        }
      });
    }
    document.body.addEventListener("click", (e) => {
      const delBtn = e.target.closest("[data-char-delete]");
      if (delBtn) {
        if (!state.connected) return;
        const sid = delBtn.getAttribute("data-char-delete");
        const nid = Number(sid);
        if (!nid || nid < 1) return;
        const nm = (delBtn.getAttribute("data-char-name") || "").trim();
        const ok = window.confirm(
          `Usunąć bohatera id=${nid}${nm ? ` (${nm})` : ""}? ` +
            "Zniknie wiersz postaci, wszystkie tury (campaign_turns) przypisane do tej postaci oraz ekwipunek. " +
            "Kampania zostaje (może nie mieć bohatera). Operacji nie cofnie się automatycznie."
        );
        if (!ok) return;
        (async () => {
          try {
            await api(`/admin/characters/${encodeURIComponent(String(nid))}`, { method: "DELETE" });
            log(`Usunięto postać id=${nid} (DELETE /admin/characters).`);
            if (el.characterRecreateId && Number(el.characterRecreateId.value) === nid) {
              el.characterRecreateId.value = "";
            }
            await loadCharacterRecreateList();
          } catch (err) {
            log(`Usuwanie postaci nie powiodło się -> ${err.message}`);
            alert(err.message);
          }
        })();
        return;
      }
      const pick = e.target.closest("[data-cr-select]");
      if (!pick || !el.characterRecreateId) return;
      const sid = pick.getAttribute("data-cr-select");
      const nid = Number(sid);
      if (!nid || nid < 1) return;
      el.characterRecreateId.value = String(nid);
      if (el.characterRecreateName) {
        const nm = pick.getAttribute("data-cr-name");
        el.characterRecreateName.value = nm != null ? nm : "";
      }
      log(`Wybrano postać id=${nid} (wypełniono character_id i imię).`);
    });
    if (el.characterRecreateLoadBtn && el.characterRecreateJson) {
      el.characterRecreateLoadBtn.addEventListener("click", async () => {
        try {
          const id = Number(el.characterRecreateId?.value);
          if (!id || id < 1) {
            alert("Podaj poprawne character_id.");
            return;
          }
          const r = await fetch(`${state.baseUrl}/characters/${encodeURIComponent(String(id))}`);
          const raw = await r.text();
          const data = raw ? JSON.parse(raw) : {};
          if (!r.ok) {
            throw new Error(data.detail ? JSON.stringify(data.detail) : r.statusText);
          }
          if (data.sheet_json) {
            el.characterRecreateJson.value = JSON.stringify(data.sheet_json, null, 2);
          }
          if (el.characterRecreateName && !String(el.characterRecreateName.value || "").trim() && data.name) {
            el.characterRecreateName.value = data.name;
          }
          log(`Wczytano sheet_json dla character_id=${id} (GET /characters).`);
        } catch (err) {
          log(`Wczytanie karty nie powiodło się -> ${err.message}`);
          alert(err.message);
        }
      });
    }
    if (el.characterRecreateApplyBtn) {
      el.characterRecreateApplyBtn.addEventListener("click", async () => {
        if (!state.connected) return;
        try {
          const id = Number(el.characterRecreateId?.value);
          if (!id || id < 1) {
            alert("Podaj poprawne character_id.");
            return;
          }
          let sheet;
          try {
            sheet = JSON.parse(el.characterRecreateJson.value || "{}");
          } catch (e) {
            alert("sheet_json: niepoprawny JSON.");
            return;
          }
          const nameRaw = String(el.characterRecreateName?.value || "").trim();
          const payload = {
            sheet_json: sheet,
            clear_inventory: !!(el.characterRecreateClearInv && el.characterRecreateClearInv.checked),
          };
          if (nameRaw) payload.name = nameRaw;
          const ok = window.confirm(
            `Nadpisać kartę postaci id=${id} w miejscu (historia tur bez zmian)? Tej operacji nie cofnie się automatycznie.`
          );
          if (!ok) return;
          const result = await api(`/admin/characters/${encodeURIComponent(String(id))}/recreate`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          log(`Recreate OK: character_id=${result.character_id} name=${result.name || ""}`);
        } catch (err) {
          log(`Recreate nie powiodło się -> ${err.message}`);
          alert(err.message);
        }
      });
    }

    if (el.lokiSaveBtn) {
      el.lokiSaveBtn.addEventListener("click", async () => {
        try {
          const url = (el.lokiUrlInput?.value || "").trim();
          const data = await api("/admin/settings/loki", {
            method: "PUT",
            body: JSON.stringify({ loki_url: url }),
          });
          if (el.lokiUrlInput) el.lokiUrlInput.value = data.loki_url || "";
          if (el.lokiUrlHint) el.lokiUrlHint.textContent = formatLokiHint(data);
          log(`Loki URL saved (${url ? "non-empty" : "cleared — env only"}).`);
        } catch (err) {
          log(`Loki save failed -> ${err.message}`);
          alert(err.message);
        }
      });
    }

    if (el.userLlmSaveBtn) {
      el.userLlmSaveBtn.addEventListener("click", async () => {
        try {
          const userId = el.userLlmUserSelect?.value;
          if (!userId) return;
          const apiKeyRaw = (el.userLlmApiKey?.value || "").trim();
          const apiKey = apiKeyRaw ? apiKeyRaw : null; // null => keep current api_key

          await api(`/admin/users/${encodeURIComponent(userId)}/llm-settings`, {
            method: "PUT",
            body: JSON.stringify({
              provider: el.userLlmProvider?.value || "ollama",
              base_url: el.userLlmBaseUrl?.value || "",
              model: el.userLlmModel?.value || "",
              api_key: apiKey,
            }),
          });

          log(`Saved user LLM for user:${userId}`);
          await loadUserLlmSettingsForUser(userId);
        } catch (err) {
          log(`Save user LLM failed -> ${err.message}`);
          alert(err.message);
        }
      });
    }
    document.body.addEventListener("click", handleSave);
    document.body.addEventListener("click", handleDelete);
    document.body.addEventListener("click", handleReset);
    el.tabButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.dataset.tab;
        el.tabButtons.forEach((x) => x.classList.toggle("active", x === btn));
        el.tabPanels.forEach((panel) => {
          panel.classList.toggle("active", panel.dataset.panel === tab);
        });

        if (tab === "user-llm" && state.connected) {
          // Ensure users list exists (cheap) and keep panel ready.
          if (el.userLlmUserSelect && el.userLlmUserSelect.value) {
            // Don't auto-load settings to avoid surprises; user clicks Load.
            if (el.userLlmLoadBtn) el.userLlmLoadBtn.disabled = false;
          }
        }
        if (tab === "campaign-history" && state.connected && el.campaignHistoryList) {
          loadCampaignHistory().catch((err) => {
            log(`Ładowanie zakładki Historia nie powiodło się -> ${err.message}`);
            alert(err.message);
          });
        }
        if (tab === "character-recreate" && state.connected && el.characterRecreateList) {
          loadCharacterRecreateList().catch((err) => {
            log(`Ładowanie listy postaci nie powiodło się -> ${err.message}`);
            alert(err.message);
          });
        }
        if (tab === "observability" && state.connected) {
          loadLokiSettings().catch((err) => {
            log(`Loki settings load failed -> ${err.message}`);
            alert(err.message);
          });
        }
      });
    });
  }

  function init() {
    bindEls();
    bindEvents();
    setConnected(false);
    log("Admin panel initialized.");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
