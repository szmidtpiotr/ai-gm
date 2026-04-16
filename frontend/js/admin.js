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
    el.accountsList = document.getElementById("accounts-list");
    el.weaponsList = document.getElementById("weapons-list");
    el.enemiesList = document.getElementById("enemies-list");
    el.conditionsList = document.getElementById("conditions-list");
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
    el.newWeaponDamageDie = document.getElementById("new-weapon-damage-die");
    el.newWeaponLinkedStat = document.getElementById("new-weapon-linked-stat");
    el.newWeaponClasses = document.getElementById("new-weapon-classes");
    el.newWeaponBtn = document.getElementById("new-weapon-btn");
    el.newEnemyKey = document.getElementById("new-enemy-key");
    el.newEnemyLabel = document.getElementById("new-enemy-label");
    el.newEnemyHpBase = document.getElementById("new-enemy-hp-base");
    el.newEnemyAcBase = document.getElementById("new-enemy-ac-base");
    el.newEnemyAttackBonus = document.getElementById("new-enemy-attack-bonus");
    el.newEnemyDamageDie = document.getElementById("new-enemy-damage-die");
    el.newEnemyDescription = document.getElementById("new-enemy-description");
    el.newEnemyBtn = document.getElementById("new-enemy-btn");
    el.newConditionKey = document.getElementById("new-condition-key");
    el.newConditionLabel = document.getElementById("new-condition-label");
    el.newConditionDescription = document.getElementById("new-condition-description");
    el.newConditionEffectJson = document.getElementById("new-condition-effect-json");
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

  async function loadWeapons() {
    const data = await api("/admin/weapons");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="damage_die" value="${esc(x.damage_die)}"></td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="linked_stat" value="${esc(x.linked_stat)}"></td>
        <td><input data-row="weapon" data-key="${esc(x.key)}" data-field="allowed_classes" value="${esc((x.allowed_classes || []).join(","))}"></td>
        <td><input type="number" min="0" max="1" data-row="weapon" data-key="${esc(x.key)}" data-field="is_active" value="${esc(x.is_active)}"></td>
        <td>
          <button data-save="weapon" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="weapon" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>
    `).join("");
    el.weaponsList.innerHTML = table(["Key", "Label", "Damage Die", "Linked Stat", "Classes", "Active", "Action"], rows);
  }

  async function loadEnemies() {
    const data = await api("/admin/enemies");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="enemy" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input type="number" min="1" data-row="enemy" data-key="${esc(x.key)}" data-field="hp_base" value="${esc(x.hp_base)}"></td>
        <td><input type="number" min="1" data-row="enemy" data-key="${esc(x.key)}" data-field="ac_base" value="${esc(x.ac_base)}"></td>
        <td><input type="number" min="0" data-row="enemy" data-key="${esc(x.key)}" data-field="attack_bonus" value="${esc(x.attack_bonus)}"></td>
        <td><input data-row="enemy" data-key="${esc(x.key)}" data-field="damage_die" value="${esc(x.damage_die)}"></td>
        <td><input data-row="enemy" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description || "")}"></td>
        <td><input type="number" min="0" max="1" data-row="enemy" data-key="${esc(x.key)}" data-field="is_active" value="${esc(x.is_active)}"></td>
        <td>
          <button data-save="enemy" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="enemy" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>
    `).join("");
    el.enemiesList.innerHTML = table(["Key", "Label", "HP", "AC", "Atk+", "Damage", "Description", "Active", "Action"], rows);
  }

  async function loadConditions() {
    const data = await api("/admin/conditions");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}${isLocked(x) ? '<span class="lock-badge" title="Locked row">🔒</span>' : ""}</td>
        <td><input data-row="condition" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="condition" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description || "")}"></td>
        <td><input data-row="condition" data-key="${esc(x.key)}" data-field="effect_json" value="${esc(x.effect_json || "")}"></td>
        <td><input type="number" min="0" max="1" data-row="condition" data-key="${esc(x.key)}" data-field="is_active" value="${esc(x.is_active)}"></td>
        <td>
          <button data-save="condition" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="secondary">Save</button>
          <button data-delete="condition" data-key="${esc(x.key)}" data-locked="${isLocked(x) ? "1" : "0"}" class="danger">Delete</button>
        </td>
      </tr>
    `).join("");
    el.conditionsList.innerHTML = table(["Key", "Label", "Description", "Effect JSON", "Active", "Action"], rows);
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
    ]);
  }

  function getInputValue(rowType, key, field) {
    const selector = `input[data-row="${rowType}"][data-key="${CSS.escape(String(key))}"][data-field="${field}"]`;
    const node = document.querySelector(selector);
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
        await api(`/admin/weapons/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("weapon", key, "label"),
            damage_die: getInputValue("weapon", key, "damage_die"),
            linked_stat: getInputValue("weapon", key, "linked_stat").toUpperCase(),
            allowed_classes: getInputValue("weapon", key, "allowed_classes")
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
            is_active: Number(getInputValue("weapon", key, "is_active")) === 1,
            force: true,
          }),
        });
      } else if (type === "enemy") {
        await api(`/admin/enemies/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("enemy", key, "label"),
            hp_base: Number(getInputValue("enemy", key, "hp_base")),
            ac_base: Number(getInputValue("enemy", key, "ac_base")),
            attack_bonus: Number(getInputValue("enemy", key, "attack_bonus")),
            damage_die: getInputValue("enemy", key, "damage_die"),
            description: getInputValue("enemy", key, "description"),
            is_active: Number(getInputValue("enemy", key, "is_active")) === 1,
            force: true,
          }),
        });
      } else if (type === "condition") {
        await api(`/admin/conditions/${encodeURIComponent(key)}`, {
          method: "PATCH",
          body: JSON.stringify({
            label: getInputValue("condition", key, "label"),
            description: getInputValue("condition", key, "description"),
            effect_json: getInputValue("condition", key, "effect_json"),
            is_active: Number(getInputValue("condition", key, "is_active")) === 1,
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
      } else if (type === "account") {
        await api(`/admin/accounts/${encodeURIComponent(key)}`, { method: "DELETE" });
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

  async function handleCreateWeapon() {
    try {
      await api("/admin/weapons", {
        method: "POST",
        body: JSON.stringify({
          key: el.newWeaponKey.value.trim(),
          label: el.newWeaponLabel.value.trim(),
          damage_die: el.newWeaponDamageDie.value.trim(),
          linked_stat: el.newWeaponLinkedStat.value.trim().toUpperCase(),
          allowed_classes: el.newWeaponClasses.value.split(",").map((x) => x.trim()).filter(Boolean),
          is_active: true,
        }),
      });
      log(`Created weapon:${el.newWeaponKey.value.trim()}`);
      el.newWeaponKey.value = "";
      el.newWeaponLabel.value = "";
      el.newWeaponDamageDie.value = "";
      el.newWeaponLinkedStat.value = "";
      el.newWeaponClasses.value = "";
      await loadWeapons();
    } catch (err) {
      log(`Create weapon failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleCreateEnemy() {
    try {
      await api("/admin/enemies", {
        method: "POST",
        body: JSON.stringify({
          key: el.newEnemyKey.value.trim(),
          label: el.newEnemyLabel.value.trim(),
          hp_base: Number(el.newEnemyHpBase.value),
          ac_base: Number(el.newEnemyAcBase.value),
          attack_bonus: Number(el.newEnemyAttackBonus.value),
          damage_die: el.newEnemyDamageDie.value.trim(),
          description: el.newEnemyDescription.value.trim(),
          is_active: true,
        }),
      });
      log(`Created enemy:${el.newEnemyKey.value.trim()}`);
      el.newEnemyKey.value = "";
      el.newEnemyLabel.value = "";
      el.newEnemyHpBase.value = "";
      el.newEnemyAcBase.value = "";
      el.newEnemyAttackBonus.value = "";
      el.newEnemyDamageDie.value = "";
      el.newEnemyDescription.value = "";
      await loadEnemies();
    } catch (err) {
      log(`Create enemy failed -> ${err.message}`);
      alert(err.message);
    }
  }

  async function handleCreateCondition() {
    try {
      await api("/admin/conditions", {
        method: "POST",
        body: JSON.stringify({
          key: el.newConditionKey.value.trim(),
          label: el.newConditionLabel.value.trim(),
          description: el.newConditionDescription.value.trim(),
          effect_json: el.newConditionEffectJson.value.trim(),
          is_active: true,
        }),
      });
      log(`Created condition:${el.newConditionKey.value.trim()}`);
      el.newConditionKey.value = "";
      el.newConditionLabel.value = "";
      el.newConditionDescription.value = "";
      el.newConditionEffectJson.value = "";
      await loadConditions();
    } catch (err) {
      log(`Create condition failed -> ${err.message}`);
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
    el.accountsList.innerHTML = "";
    if (el.weaponsList) el.weaponsList.innerHTML = "";
    if (el.enemiesList) el.enemiesList.innerHTML = "";
    if (el.conditionsList) el.conditionsList.innerHTML = "";
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
