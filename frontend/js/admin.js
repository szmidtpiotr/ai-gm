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
    el.logBox = document.getElementById("admin-log-box");
    el.exportBtn = document.getElementById("export-config-btn");
    el.importFile = document.getElementById("import-config-file");
    el.importDryBtn = document.getElementById("import-config-dry-btn");
    el.importCommitBtn = document.getElementById("import-config-commit-btn");
    el.newSkillKey = document.getElementById("new-skill-key");
    el.newSkillLabel = document.getElementById("new-skill-label");
    el.newSkillStat = document.getElementById("new-skill-stat");
    el.newSkillRank = document.getElementById("new-skill-rank");
    el.newSkillBtn = document.getElementById("new-skill-btn");
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

  async function loadStats() {
    const data = await api("/admin/stats");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}</td>
        <td><input data-row="stat" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="stat" data-key="${esc(x.key)}" data-field="description" value="${esc(x.description)}"></td>
        <td><input type="number" data-row="stat" data-key="${esc(x.key)}" data-field="sort_order" value="${esc(x.sort_order)}"></td>
        <td><button data-save="stat" data-key="${esc(x.key)}" class="secondary">Save</button></td>
      </tr>
    `).join("");
    el.statsList.innerHTML = table(["Key", "Label", "Description", "Order", "Action"], rows);
  }

  async function loadSkills() {
    const data = await api("/admin/skills");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}</td>
        <td><input data-row="skill" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input data-row="skill" data-key="${esc(x.key)}" data-field="linked_stat" value="${esc(x.linked_stat)}"></td>
        <td><input type="number" data-row="skill" data-key="${esc(x.key)}" data-field="rank_ceiling" value="${esc(x.rank_ceiling)}"></td>
        <td><input type="number" data-row="skill" data-key="${esc(x.key)}" data-field="sort_order" value="${esc(x.sort_order)}"></td>
        <td>
          <button data-save="skill" data-key="${esc(x.key)}" class="secondary">Save</button>
          <button data-delete="skill" data-key="${esc(x.key)}" class="danger">Delete</button>
        </td>
      </tr>
    `).join("");
    el.skillsList.innerHTML = table(["Key", "Label", "Linked Stat", "Rank", "Order", "Action"], rows);
  }

  async function loadDc() {
    const data = await api("/admin/dc");
    const rows = data.items.map((x) => `
      <tr>
        <td>${esc(x.key)}</td>
        <td><input data-row="dc" data-key="${esc(x.key)}" data-field="label" value="${esc(x.label)}"></td>
        <td><input type="number" data-row="dc" data-key="${esc(x.key)}" data-field="value" value="${esc(x.value)}"></td>
        <td><input type="number" data-row="dc" data-key="${esc(x.key)}" data-field="sort_order" value="${esc(x.sort_order)}"></td>
        <td><button data-save="dc" data-key="${esc(x.key)}" class="secondary">Save</button></td>
      </tr>
    `).join("");
    el.dcList.innerHTML = table(["Key", "Label", "Value", "Order", "Action"], rows);
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

  async function refreshAll() {
    await Promise.all([loadStats(), loadSkills(), loadDc(), loadAccounts()]);
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
    try {
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
    try {
      if (type === "skill") {
        await api(`/admin/skills/${encodeURIComponent(key)}`, {
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
        }),
      });
      log(`Created skill:${el.newSkillKey.value.trim()}`);
      el.newSkillKey.value = "";
      el.newSkillLabel.value = "";
      el.newSkillStat.value = "";
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
    log("Logged out.");
  }

  function bindEvents() {
    el.loginBtn.addEventListener("click", connect);
    el.logoutBtn.addEventListener("click", logout);
    el.newSkillBtn.addEventListener("click", handleCreateSkill);
    el.exportBtn.addEventListener("click", handleExport);
    el.importFile.addEventListener("change", handleImportFileChange);
    el.importDryBtn.addEventListener("click", () => handleImport(true));
    el.importCommitBtn.addEventListener("click", () => handleImport(false));
    document.body.addEventListener("click", handleSave);
    document.body.addEventListener("click", handleDelete);
    document.body.addEventListener("click", handleReset);
  }

  function init() {
    bindEls();
    bindEvents();
    setConnected(false);
    log("Admin panel initialized.");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
