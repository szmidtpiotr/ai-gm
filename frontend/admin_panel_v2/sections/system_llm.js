import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";
import { showConfirm } from "/admin_panel_v2/shared/table.js?v=8";

const LABELS = {
  loki:            "Loki Log Forwarding",
  lokiHelp:        "Zostaw puste, aby użyć zmiennej środowiskowej LOKI_URL.",
  dbInfo:          "Informacje o bazie",
  dbTables:        "Tabele",
  dbRefresh:       "Odśwież",
  dbMigrate:       "Uruchom migracje",
  dbBackup:        "Pobierz kopię bazy",
  dbRestore:       "Przywróć z pliku",
  dbRestoreWarn:   "🚨 Przywrócenie ZASTĄPI bieżącą bazę. Operacja jest nieodwracalna.",
  configExport:    "Eksportuj konfigurację",
  configImport:    "Importuj konfigurację",
  configDryRun:    "Podgląd (Dry Run)",
  configCommit:    "Zatwierdź import",
  summarySettings: "Ustawienia podsumowań",
  slashCmds:       "Komendy czatu",
  slashSave:       "Zapisz komendy",
  adminCmdWarn:    "⚠️ Komendy modyfikują bazę bezpośrednio. Używaj tylko na DEV/TEST.",
  charLabel:       "Postać",
  charSelect:      "— wybierz postać —",
  execute:         "Wykonaj",
  quickActions:    "Szybkie akcje",
  charState:       "Stan postaci",
};

const TABS = ["llm", "database", "config", "slash-cmds", "admin-cmd", "resurrection", "visual", "voice", "email"];
const TAB_LABELS = {
  llm:           "LLM",
  database:      "Database",
  config:        "Config",
  "slash-cmds":  "Slash Commands",
  "admin-cmd":   "Admin Cmd",
  resurrection:  "Wskrzeszenie",
  visual:        "🎨 Wygląd",
  voice:         "🔊 Głos",
  email:         "📨 Email",
};
const TAB_MODULES = {
  visual: "/admin_panel_v2/sections/visual.js?v=2",
  voice:  "/admin_panel_v2/sections/voice.js?v=1",
  email:  "/admin_panel_v2/sections/email.js?v=1",
};

const PROVIDERS = [
  { value: "openai",  label: "OpenAI" },
  { value: "azure",   label: "Azure AI Foundry / Azure OpenAI" },
  { value: "ollama",  label: "Ollama" },
  { value: "other",   label: "Other (OpenAI-compatible)" },
];

let _panel    = null;
let _activeTab = "llm";
let _presets  = [];
let _activeId = null;
let _settings = null;

export async function init(panel) {
  _panel     = panel;
  _activeTab = "llm";

  panel.innerHTML = `
    <div class="system-layout">
      <div class="system-tabnav" id="system-tabnav">
        ${TABS.map(t =>
          `<button class="system-tab-btn${t === _activeTab ? " active" : ""}" data-tab="${t}">${TAB_LABELS[t]}</button>`
        ).join("")}
      </div>
      <div class="system-body" id="system-body"></div>
    </div>`;

  panel.querySelectorAll(".system-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      _activeTab = btn.dataset.tab;
      panel.querySelectorAll(".system-tab-btn").forEach(b => b.classList.toggle("active", b === btn));
      _renderTab(_activeTab);
    });
  });

  await _renderTab(_activeTab);
}

async function _renderTab(tab) {
  const body = _panel.querySelector("#system-body");
  body.innerHTML = `<div class="drawer-loading">Ładowanie…</div>`;
  if      (tab === "llm")          await _renderLlmTab(body);
  else if (tab === "database")     await _renderDatabaseTab(body);
  else if (tab === "config")       await _renderConfigTab(body);
  else if (tab === "slash-cmds")   await _renderSlashTab(body);
  else if (tab === "admin-cmd")    await _renderAdminCmdTab(body);
  else if (tab === "resurrection") await _renderResurrectionTab(body);
  else if (TAB_MODULES[tab])       await _renderModuleTab(body, TAB_MODULES[tab]);
}

async function _renderModuleTab(body, modulePath) {
  body.innerHTML = "";
  try {
    const { init: subInit } = await import(modulePath);
    await subInit(body);
  } catch (err) {
    body.innerHTML = `<p class="drawer-error">Błąd ładowania modułu: ${_esc(err.message)}</p>`;
    console.error("[system] module load failed:", modulePath, err);
  }
}

// ── LLM tab ───────────────────────────────────────────────────────────────────

async function _renderLlmTab(body) {
  try {
    const data = await adminFetch("/api/admin/llm/global-settings");
    _presets  = data.presets || [];
    _activeId = data.active_preset_id ?? null;
    _settings = data.settings || {};
  } catch (e) {
    body.innerHTML = `<p class="drawer-error">Błąd: ${_esc(e.message)}</p>`;
    return;
  }

  const activePreset = _presets.find(p => p.id === _activeId);
  const effModel     = activePreset?.model    || _settings.model    || "—";
  const effProvider  = _providerLabel(activePreset?.provider || _settings.provider);
  const effUrl       = activePreset?.base_url || _settings.base_url || "—";

  body.innerHTML = `
    <div class="system-llm-wrap">

      <div class="system-section">
        <div class="system-section-title">Aktywna konfiguracja LLM</div>
        <div class="llm-active-card">
          <div class="llm-active-row"><span class="llm-active-label">Preset</span>
            <span class="llm-active-value">${activePreset ? _esc(activePreset.label) : '<em style="color:var(--text-muted)">brak — używane zmienne środowiskowe</em>'}</span></div>
          <div class="llm-active-row"><span class="llm-active-label">Dostawca</span><span class="llm-active-value">${_esc(effProvider)}</span></div>
          <div class="llm-active-row"><span class="llm-active-label">Model</span><span class="llm-active-value">${_esc(effModel)}</span></div>
          <div class="llm-active-row"><span class="llm-active-label">URL</span><span class="llm-active-value" style="word-break:break-all">${_esc(effUrl)}</span></div>
        </div>
        ${_activeId !== null ? `<button class="secondary-btn" id="use-env-btn" style="margin-top:8px">Użyj zmiennych środowiskowych (wyczyść preset)</button>` : ""}
      </div>

      <div class="system-section">
        <div class="system-section-title">Presety LLM</div>
        <div id="presets-list"></div>
        <button class="primary-btn" id="add-preset-btn" style="margin-top:12px">+ Dodaj preset</button>
      </div>

      <div class="system-section">
        <div class="system-section-title">${LABELS.loki}</div>
        <div id="loki-table" class="sys-info-table"></div>
        <label class="system-field-label" style="margin-top:10px;display:block">Override URL</label>
        <input id="loki-url-input" class="field-input" type="url" placeholder="http://loki:3100"
          style="width:100%;margin:4px 0 6px" />
        <p class="system-help-text">${LABELS.lokiHelp}</p>
        <div class="system-btn-row" style="margin-top:8px">
          <button class="primary-btn" id="loki-save-btn">Zapisz</button>
          <button class="secondary-btn" id="loki-clear-btn">Wyczyść</button>
        </div>
      </div>

    </div>`;

  _renderPresetsList(body.querySelector("#presets-list"));

  body.querySelector("#add-preset-btn")?.addEventListener("click", () => _openPresetModal(null, body));
  body.querySelector("#use-env-btn")?.addEventListener("click", async () => {
    try {
      await adminFetch("/api/admin/llm/use-env", { method: "POST" });
      showToast("Używane zmienne środowiskowe.", "success");
      await _renderLlmTab(body);
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });

  await _loadLoki(body);
}

async function _loadLoki(body) {
  const table = body.querySelector("#loki-table");
  const input = body.querySelector("#loki-url-input");
  if (!table || !input) return;
  try {
    const data = await adminFetch("/api/admin/settings/loki");
    table.innerHTML = [
      ["Stored URL", data.stored    || "—"],
      ["Env URL",    data.from_env  || "—"],
      ["Effective",  data.loki_url  || "—"],
    ].map(([k, v]) =>
      `<div class="sys-info-row"><span class="sys-info-key">${k}</span><span class="sys-info-val">${_esc(v)}</span></div>`
    ).join("");
    input.value = data.stored || "";
  } catch { /* non-critical */ }

  body.querySelector("#loki-save-btn")?.addEventListener("click", async () => {
    try {
      await adminFetch("/api/admin/settings/loki", {
        method: "PUT", body: JSON.stringify({ loki_url: input.value.trim() }),
      });
      showToast("Loki URL saved.", "success");
    } catch (e) { showToast(e.message || "Save failed.", "error"); }
  });

  body.querySelector("#loki-clear-btn")?.addEventListener("click", async () => {
    try {
      await adminFetch("/api/admin/settings/loki", {
        method: "PUT", body: JSON.stringify({ loki_url: "" }),
      });
      showToast("Wyczyszczono — używane env/default.", "success");
      input.value = "";
    } catch (e) { showToast(e.message || "Clear failed.", "error"); }
  });
}

// ── Database tab ──────────────────────────────────────────────────────────────

async function _renderDatabaseTab(body) {
  body.innerHTML = `
    <div class="system-db-wrap">

      <div class="system-section">
        <div class="system-section-title">${LABELS.dbInfo}</div>
        <div id="db-stats" class="sys-info-table"></div>
        <div class="system-btn-row" style="margin-top:12px">
          <button class="secondary-btn" id="db-refresh-btn">🔄 ${LABELS.dbRefresh}</button>
          <button class="primary-btn"   id="db-migrate-btn">▶ ${LABELS.dbMigrate}</button>
        </div>
      </div>

      <div class="system-section">
        <div class="system-section-title">${LABELS.dbTables}</div>
        <div id="db-tables-wrap"></div>
      </div>

      <div class="system-section">
        <div class="system-section-title">${LABELS.dbBackup}</div>
        <p class="system-help-text">⚠️ Zawsze rób kopię przed masowymi edycjami lub importem.</p>
        <button class="primary-btn" id="db-backup-btn" style="margin-top:10px">⬇ ${LABELS.dbBackup}</button>
      </div>

      <div class="system-section">
        <div class="system-section-title">${LABELS.dbRestore}</div>
        <p class="system-help-text system-help-danger">${LABELS.dbRestoreWarn}</p>
        <input type="file" id="db-restore-file" accept=".db" style="margin-top:10px;display:block" />
        <button class="primary-btn danger-btn" id="db-restore-btn" disabled style="margin-top:8px">
          🔁 ${LABELS.dbRestore}
        </button>
      </div>

    </div>`;

  const loadDbInfo = async () => {
    try {
      const data = await adminFetch("/api/admin/db/info");
      const mb = (Number(data.db_size_bytes) / 1024 / 1024).toFixed(2);
      body.querySelector("#db-stats").innerHTML = [
        ["Path",   data.db_path],
        ["Size",   `${mb} MB`],
        ["SQLite", data.sqlite_version || "—"],
      ].map(([k, v]) =>
        `<div class="sys-info-row"><span class="sys-info-key">${k}</span><span class="sys-info-val">${_esc(v)}</span></div>`
      ).join("");

      const items = [...(data.tables || [])].sort((a, b) => a.name.localeCompare(b.name));
      body.querySelector("#db-tables-wrap").innerHTML = `
        <table class="sys-table">
          <thead><tr><th>Tabela</th><th>Wiersze</th></tr></thead>
          <tbody>${items.map(t =>
            `<tr class="${t.row_count === 0 ? "sys-row-zero" : ""}">
              <td>${_esc(t.name)}</td><td>${t.row_count}</td>
            </tr>`
          ).join("")}</tbody>
        </table>`;
    } catch (e) { showToast(e.message || "Błąd DB info.", "error"); }
  };

  await loadDbInfo();
  body.querySelector("#db-refresh-btn").addEventListener("click", loadDbInfo);

  body.querySelector("#db-migrate-btn").addEventListener("click", async () => {
    const btn = body.querySelector("#db-migrate-btn");
    btn.disabled = true; btn.textContent = "⏳";
    try {
      await adminFetch("/api/admin/db/migrate", { method: "POST" });
      showToast("Migracje zakończone.", "success");
    } catch (e) { showToast(e.message || "Migracje nieudane.", "error"); }
    finally { btn.disabled = false; btn.textContent = `▶ ${LABELS.dbMigrate}`; }
  });

  body.querySelector("#db-backup-btn").addEventListener("click", async () => {
    try {
      const token = localStorage.getItem("aigm_admin_token") || "";
      const resp = await fetch("/api/admin/db/backup", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ai_gm_backup_${Date.now()}.db`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Pobieranie rozpoczęte.", "success");
    } catch (e) { showToast(e.message || "Backup nieudany.", "error"); }
  });

  const restoreFile = body.querySelector("#db-restore-file");
  const restoreBtn  = body.querySelector("#db-restore-btn");
  restoreFile.addEventListener("change", () => {
    restoreBtn.disabled = !restoreFile.files?.length;
  });
  restoreBtn.addEventListener("click", async () => {
    const f = restoreFile.files?.[0];
    if (!f) return;
    const ok = await showConfirm(
      "Przywrócić bazę danych? Zastąpi bieżące dane — nie można tego cofnąć.",
      { dangerous: true }
    );
    if (!ok) return;
    restoreBtn.disabled = true; restoreBtn.textContent = "⏳";
    try {
      const fd = new FormData();
      fd.append("file", f);
      await adminFetch("/api/admin/db/restore", { method: "POST", body: fd });
      showToast("Baza przywrócona. Rozważ restart backendu.", "success");
      restoreFile.value = "";
      restoreBtn.disabled = true;
    } catch (e) { showToast(e.message || "Przywracanie nieudane.", "error"); }
    finally { restoreBtn.textContent = `🔁 ${LABELS.dbRestore}`; }
  });
}

// ── Config tab ────────────────────────────────────────────────────────────────

async function _renderConfigTab(body) {
  body.innerHTML = `
    <div class="system-config-wrap">

      <div class="system-section system-warn-section">
        ⚠️ Eksportuj konfigurację przed masowymi edycjami lub przed zatwierdzeniem importu.
      </div>

      <div class="system-two-col">
        <div class="system-section">
          <div class="system-section-title">${LABELS.configExport}</div>
          <p class="system-help-text">Pełna migawka JSON mechaniki gry (statystyki, umiejętności, DC, broń, wrogowie, warunki). Nie zawiera tokenów, logów ani kont.</p>
          <button class="primary-btn" id="config-export-btn" style="margin-top:10px">⬇ ${LABELS.configExport}</button>
        </div>

        <div class="system-section">
          <div class="system-section-title">${LABELS.configImport}</div>
          <input type="file" id="config-import-file" accept=".json,application/json" style="display:block;margin-bottom:8px" />
          <p class="system-help-text">Zatwierdzenie importu automatycznie tworzy kopię DB. Retencja: 30 dni, min. 3 starsze, maks. 10 plików.</p>
          <div class="system-btn-row" style="margin-top:8px">
            <button class="secondary-btn" id="config-dry-btn" disabled>🔍 ${LABELS.configDryRun}</button>
            <button class="primary-btn danger-btn" id="config-commit-btn" disabled>✅ ${LABELS.configCommit}</button>
          </div>
          <div id="config-diff-wrap" style="display:none;margin-top:12px"></div>
        </div>
      </div>

      <div class="system-section">
        <div class="system-section-title">${LABELS.summarySettings}</div>
        <label class="system-field-label">Cooldown podsumowań (tury narracyjne)</label>
        <input type="number" id="summary-cooldown" class="field-input" min="1" max="500" style="width:120px;display:block;margin:4px 0 6px" />
        <p class="system-help-text" style="margin-bottom:10px">Ile nowych tur wymaganych przed kolejnym odświeżeniem rollup LLM.</p>
        <label class="system-field-label">Tryb podglądu podwójnego (T01 QA)</label>
        <select id="summary-mode" class="field-input" style="width:280px;display:block;margin:4px 0 6px">
          <option value="owner">Właściciel kampanii</option>
          <option value="owner_admin">Właściciel + admin</option>
          <option value="off">Wyłączone</option>
        </select>
        <p class="system-help-text" style="margin-bottom:10px">Kto ma dostęp do przycisku T01 dual preview w modalu Historia.</p>
        <button class="primary-btn" id="summary-save-btn" disabled>Zapisz ustawienia</button>
      </div>

    </div>`;

  body.querySelector("#config-export-btn").addEventListener("click", async () => {
    try {
      const data = await adminFetch("/api/admin/config/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url  = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const d = new Date();
      a.download = `aigm_config_${d.getFullYear()}${String(d.getMonth()+1).padStart(2,"0")}${String(d.getDate()).padStart(2,"0")}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Konfiguracja wyeksportowana.", "success");
    } catch (e) { showToast(e.message || "Błąd eksportu.", "error"); }
  });

  const fileInp   = body.querySelector("#config-import-file");
  const dryBtn    = body.querySelector("#config-dry-btn");
  const commitBtn = body.querySelector("#config-commit-btn");
  const diffWrap  = body.querySelector("#config-diff-wrap");
  let lastParsed = null;
  let lastWarnings = [];

  fileInp.addEventListener("change", () => {
    dryBtn.disabled = !fileInp.files?.length;
    commitBtn.disabled = true;
    lastParsed = null;
    diffWrap.style.display = "none";
    diffWrap.innerHTML = "";
  });

  dryBtn.addEventListener("click", async () => {
    const f = fileInp.files?.[0];
    if (!f) return;
    dryBtn.disabled = true; dryBtn.textContent = "⏳";
    try {
      const text   = await f.text();
      const parsed = JSON.parse(text);
      if (!parsed?.tables) throw new Error("Nieprawidłowy plik: brak tables.");
      lastParsed = parsed;
      const res = await adminFetch("/api/admin/config/import?dry_run=true", {
        method: "POST", body: JSON.stringify(parsed),
      });
      lastWarnings = res?.warnings || [];
      _renderConfigDiff(diffWrap, res, parsed);
      commitBtn.disabled = false;
      showToast(lastWarnings.length ? "Dry run z ostrzeżeniami." : "Dry run OK.", "success");
    } catch (e) {
      lastParsed = null;
      diffWrap.style.display = "none";
      showToast(e instanceof SyntaxError ? "Nieprawidłowy JSON." : e.message || "Błąd dry run.", "error");
    } finally {
      dryBtn.textContent = `🔍 ${LABELS.configDryRun}`;
      dryBtn.disabled = !fileInp.files?.length;
    }
  });

  commitBtn.addEventListener("click", async () => {
    if (!lastParsed) { showToast("Najpierw uruchom dry run.", "info"); return; }
    const ok = await showConfirm(
      "Zatwierdzić import? Bieżąca konfiguracja zostanie zastąpiona." +
      (lastWarnings.length ? `\n\nOstrzeżenia:\n- ${lastWarnings.join("\n- ")}` : ""),
      { dangerous: true }
    );
    if (!ok) return;
    commitBtn.disabled = true; commitBtn.textContent = "⏳";
    try {
      await adminFetch("/api/admin/config/import", {
        method: "POST", body: JSON.stringify(lastParsed),
      });
      showToast("Import zatwierdzony. Kopia DB utworzona automatycznie.", "success");
      fileInp.value = ""; lastParsed = null;
      diffWrap.style.display = "none"; dryBtn.disabled = true; commitBtn.disabled = true;
    } catch (e) {
      showToast(e.message || "Błąd importu.", "error");
      commitBtn.disabled = false;
    } finally {
      commitBtn.textContent = `✅ ${LABELS.configCommit}`;
    }
  });

  try {
    const res  = await adminFetch("/api/settings/summary");
    const data = res?.data || {};
    body.querySelector("#summary-cooldown").value = data.summary_rollup_cooldown_turns ?? 20;
    body.querySelector("#summary-mode").value     = data.dual_summary_preview_mode || "owner_admin";
    body.querySelector("#summary-save-btn").disabled = false;
  } catch { /* non-critical */ }

  body.querySelector("#summary-save-btn").addEventListener("click", async () => {
    const btn = body.querySelector("#summary-save-btn");
    btn.disabled = true; btn.textContent = "⏳";
    try {
      const n = Math.max(1, Math.min(500, Number(body.querySelector("#summary-cooldown").value) || 20));
      await adminFetch("/api/settings/summary", {
        method: "PATCH",
        body: JSON.stringify({
          summary_rollup_cooldown_turns: n,
          dual_summary_preview_mode:     body.querySelector("#summary-mode").value,
        }),
      });
      showToast("Ustawienia zapisane.", "success");
    } catch (e) { showToast(e.message || "Błąd zapisu.", "error"); }
    finally { btn.disabled = false; btn.textContent = "Zapisz ustawienia"; }
  });
}

function _renderConfigDiff(wrap, res, parsed) {
  const tables   = parsed.tables || {};
  const warnings = res?.warnings || [];
  wrap.style.display = "";
  wrap.innerHTML = `
    <div class="system-section-title">Podgląd importu — Dry Run</div>
    ${warnings.length
      ? `<div class="system-warn-section" style="margin-bottom:8px">${warnings.map(w => _esc(w)).join("<br>")}</div>`
      : ""}
    <table class="sys-table">
      <thead><tr><th>Tabela</th><th>Wiersze w pliku</th></tr></thead>
      <tbody>${Object.keys(tables).sort().map(k =>
        `<tr><td>${_esc(k)}</td><td>${Array.isArray(tables[k]) ? tables[k].length : 0}</td></tr>`
      ).join("")}</tbody>
    </table>`;
}

// ── Slash Commands tab ────────────────────────────────────────────────────────

async function _renderSlashTab(body) {
  body.innerHTML = `
    <div class="system-section">
      <div class="system-section-title">${LABELS.slashCmds}</div>
      <p class="system-help-text">
        Lista komend systemowych. Dwa przełączniki na komendę: <strong>Admin</strong> (widoczność dla administratora) oraz <strong>Gracz</strong> (widoczność dla zwykłego gracza).
        Pole tekstowe = opis w podpowiedzi /help i autocomplete'a.
      </p>
      <div class="slash-table-head">
        <span class="slash-th-cmd">Komenda</span>
        <span class="slash-th-alias">Alias (zmień nazwę)</span>
        <span class="slash-th-toggle">Admin</span>
        <span class="slash-th-toggle">Gracz</span>
        <span class="slash-th-desc">Opis</span>
      </div>
      <div id="slash-rows" style="margin-top:6px"></div>
      <button class="primary-btn" id="slash-save-btn" disabled style="margin-top:12px">${LABELS.slashSave}</button>
    </div>`;

  const slashRows = body.querySelector("#slash-rows");
  const saveBtn   = body.querySelector("#slash-save-btn");

  try {
    const data = await adminFetch("/api/admin/slash-commands");
    const cmds = data.commands || [];
    slashRows.innerHTML = cmds.map(c => {
      const adminOn  = c.admin_enabled !== false;
      const playerOn = c.player_enabled !== undefined ? c.player_enabled !== false : c.enabled !== false;
      const alias    = String(c.alias || "");
      return `
      <div class="slash-cmd-row" data-cmd="${_esc(c.command || "")}">
        <span class="slash-cmd-name">${_esc(c.command || "")}</span>
        <input type="text" class="slash-cmd-alias" placeholder="np. /szukaj"
               value="${_esc(alias)}" maxlength="40" spellcheck="false" />
        <label class="slash-toggle">
          <input type="checkbox" class="slash-cmd-admin" ${adminOn ? "checked" : ""} />
        </label>
        <label class="slash-toggle">
          <input type="checkbox" class="slash-cmd-player" ${playerOn ? "checked" : ""} />
        </label>
        <textarea class="slash-cmd-desc" rows="2">${_esc(c.description || "")}</textarea>
      </div>`;
    }).join("");
    saveBtn.disabled = false;
  } catch (e) {
    showToast(e.message || "Nie można załadować komend.", "error");
    slashRows.innerHTML = `<p class="system-help-text" style="color:var(--accent-red)">Błąd ładowania.</p>`;
  }

  saveBtn.addEventListener("click", async () => {
    const rows = slashRows.querySelectorAll(".slash-cmd-row");
    const commands = Array.from(rows).map(row => ({
      command:        row.dataset.cmd,
      alias:          row.querySelector(".slash-cmd-alias").value.trim(),
      description:    row.querySelector(".slash-cmd-desc").value.trim(),
      admin_enabled:  row.querySelector(".slash-cmd-admin").checked,
      player_enabled: row.querySelector(".slash-cmd-player").checked,
    }));
    saveBtn.disabled = true; saveBtn.textContent = "⏳";
    try {
      await adminFetch("/api/admin/slash-commands", {
        method: "PUT", body: JSON.stringify({ commands }),
      });
      showToast("Komendy zapisane.", "success");
    } catch (e) { showToast(e.message || "Błąd zapisu.", "error"); }
    finally { saveBtn.disabled = false; saveBtn.textContent = LABELS.slashSave; }
  });
}

// ── Admin Cmd tab ─────────────────────────────────────────────────────────────

async function _renderAdminCmdTab(body) {
  body.innerHTML = `
    <div class="system-section">
      <div class="system-section-title">${LABELS.adminCmdWarn}</div>

      <label class="system-field-label">${LABELS.charLabel}</label>
      <select id="cmd-char-select" class="field-input" style="max-width:420px;display:block;margin-bottom:14px">
        <option value="">${LABELS.charSelect}</option>
      </select>

      <div class="system-section-title">Terminal</div>
      <div style="display:flex;gap:8px;margin-top:8px">
        <input type="text" id="cmd-input" class="field-input"
          placeholder="np. add gold 100  lub  set health max" style="flex:1" />
        <button class="primary-btn" id="cmd-exec-btn">▶ ${LABELS.execute}</button>
      </div>
      <div id="cmd-history" class="cmd-history-wrap"></div>

      <div class="system-section-title" style="margin-top:16px">${LABELS.quickActions}</div>
      <div id="cmd-quick-row" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px"></div>

      <div class="system-section-title" style="margin-top:16px">${LABELS.charState}</div>
      <pre id="cmd-state" class="cmd-state-pre">— wybierz postać i wykonaj komendę —</pre>
    </div>`;

  const charSelect = body.querySelector("#cmd-char-select");
  try {
    const data = await adminFetch("/api/admin/characters");
    (data.items || []).forEach(c => {
      const opt = document.createElement("option");
      opt.value = String(c.id);
      opt.textContent = `[${c.id}] ${c.name} (${c.campaign_title})`;
      charSelect.appendChild(opt);
    });
  } catch (e) { showToast(e.message || "Nie można załadować postaci.", "error"); }

  const historyEl = body.querySelector("#cmd-history");
  const statePre  = body.querySelector("#cmd-state");
  let cmdHistory  = [];

  function addHistory(label, result, ok) {
    cmdHistory.unshift({ time: new Date().toLocaleTimeString(), label, result, ok });
    if (cmdHistory.length > 20) cmdHistory.pop();
    historyEl.innerHTML = cmdHistory.map(({ time, label, result, ok }) =>
      `<div style="color:${ok ? "#4caf50" : "#f44336"};border-bottom:1px solid #333;padding:2px 0">
        [${time}] ${ok ? "✅" : "❌"} ${_esc(label)} → ${_esc(JSON.stringify(result))}
      </div>`
    ).join("");
  }

  async function refreshState(charId) {
    try {
      const res = await adminFetch(`/api/admin/cheat/${charId}`, {
        method: "POST", body: JSON.stringify({ cmd: "show state" }),
      });
      const r = res.result || {};
      statePre.textContent = [
        `HP:       ${r.current_hp ?? "?"}/${r.max_hp ?? "?"}`,
        `GP:       ${r.gold_gp ?? "?"}`,
        `Level:    ${r.level ?? "?"}`,
        `Location: ${r.location || "?"}`,
        `Stats:    ${JSON.stringify(r.stats || {})}`,
        `Items:    ${(r.inventory || []).join(", ") || "(brak)"}`,
        `Quests:   ${(r.quests_active || []).join(", ") || "(brak)"}`,
      ].join("\n");
    } catch { /* ignore */ }
  }

  function parseCmd(raw) {
    const t = (raw || "").trim().replace(/^\/admin\s*/i, "");
    const parts = t.split(/\s+/);
    const p0 = (parts[0] || "").toLowerCase();
    const p1 = (parts[1] || "").toLowerCase();
    const rest = parts.slice(2).join(" ");
    if (p0 === "add" && (p1 === "gold" || p1 === "health")) {
      const v = rest.toLowerCase() === "max" ? "max" : parseInt(rest, 10);
      return { cmd: `add ${p1}`, value: Number.isNaN(v) ? rest : v };
    }
    if (p0 === "add" && p1 === "weapon")     return { cmd: "add item", key: rest || undefined, kind: "weapon" };
    if (p0 === "add" && p1 === "consumable") return { cmd: "add item", key: rest || undefined, kind: "consumable" };
    if (p0 === "add" && p1 === "item")       return { cmd: "add item", key: rest || undefined };
    if (p0 === "add" && p1 === "stat") {
      const stat = (parts[2] || "").toUpperCase();
      const val  = parseInt(parts[3] || "1", 10);
      return { cmd: "add stat", stat, value: Number.isNaN(val) ? 1 : val };
    }
    if (p0 === "set" && (p1 === "gold" || p1 === "level")) {
      const v = parseInt(rest, 10);
      return { cmd: `set ${p1}`, value: Number.isNaN(v) ? 0 : v };
    }
    if (p0 === "set" && p1 === "health") {
      const v = rest.toLowerCase() === "max" ? "max" : parseInt(rest, 10);
      return { cmd: "set health", value: Number.isNaN(v) ? rest : v };
    }
    if (p0 === "set"    && p1 === "location")  return { cmd: "set location",  key: rest || undefined };
    if (p0 === "remove" && p1 === "item")      return { cmd: "remove item",   key: rest || undefined };
    if (p0 === "clear"  && p1 === "inventory") return { cmd: "clear inventory" };
    if (p0 === "combat" && p1 === "end")       return { cmd: "combat end" };
    if (p0 === "quest"  && (p1 === "add" || p1 === "complete")) return { cmd: `quest ${p1}`, key: rest || undefined };
    if (p0 === "show"   && p1 === "state")     return { cmd: "show state" };
    return null;
  }

  async function executeRaw(cmdBody, label) {
    const charId = charSelect.value;
    if (!charId) { showToast("Wybierz postać.", "info"); return; }
    try {
      const res = await adminFetch(`/api/admin/cheat/${charId}`, {
        method: "POST", body: JSON.stringify(cmdBody),
      });
      addHistory(label, res.result, true);
      await refreshState(charId);
      showToast(`✅ ${label}`, "success");
    } catch (e) {
      const msg = e.message || "Błąd";
      addHistory(label, msg, false);
      showToast(`❌ ${msg}`, "error");
    }
  }

  const QUICK = [
    { label: "💛 +100 GP",    body: { cmd: "add gold",    value: 100 } },
    { label: "❤️ Full Heal",  body: { cmd: "set health",  value: "max" } },
    { label: "🗑 Clear Inv",  body: { cmd: "clear inventory" } },
    { label: "⚔️ End Combat", body: { cmd: "combat end" } },
  ];
  const quickRow = body.querySelector("#cmd-quick-row");
  QUICK.forEach(({ label, body: cmdBody }) => {
    const btn = document.createElement("button");
    btn.className = "secondary-btn";
    btn.textContent = label;
    btn.addEventListener("click", () => executeRaw(cmdBody, label));
    quickRow.appendChild(btn);
  });

  const cmdInput = body.querySelector("#cmd-input");
  const execBtn  = body.querySelector("#cmd-exec-btn");
  execBtn.addEventListener("click", async () => {
    const raw = cmdInput.value.trim();
    if (!raw) return;
    const parsed = parseCmd(raw);
    if (!parsed) { showToast(`Nieznana komenda: ${raw}`, "error"); return; }
    await executeRaw(parsed, raw);
    cmdInput.value = "";
    cmdInput.focus();
  });
  cmdInput.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); execBtn.click(); }
  });
  charSelect.addEventListener("change", () => {
    if (charSelect.value) void refreshState(charSelect.value);
  });
}

// ── LLM Preset helpers ────────────────────────────────────────────────────────

function _providerLabel(provider) {
  const p = PROVIDERS.find(x => x.value === (provider || "").toLowerCase());
  return p ? p.label : (provider || "—");
}

function _renderPresetsList(container) {
  if (!_presets.length) {
    container.innerHTML = `<p class="system-help-text">Brak presetów. Dodaj pierwszy poniżej.</p>`;
    return;
  }
  container.innerHTML = "";
  _presets.forEach(preset => {
    const isActive = preset.id === _activeId;
    const card = document.createElement("div");
    card.className = `llm-preset-card${isActive ? " llm-preset-active" : ""}`;
    card.innerHTML = `
      <div class="llm-preset-card-left">
        <div class="llm-preset-name">${isActive ? "⚡ " : ""}${_esc(preset.label)}</div>
        <div class="llm-preset-meta">${_esc(_providerLabel(preset.provider))} · ${_esc(preset.model)} · ${_esc(preset.base_url || "—")}</div>
        ${preset.api_key_set ? `<div class="llm-preset-meta" style="color:var(--accent-green)">API key: ustawiony</div>` : ""}
      </div>
      <div class="llm-preset-card-actions">
        ${!isActive
          ? `<button class="primary-btn llm-preset-activate-btn" data-id="${preset.id}">Aktywuj</button>`
          : `<span class="admin-badge admin-badge-green">Aktywny</span>`}
        <button class="secondary-btn llm-preset-edit-btn" data-id="${preset.id}">Edytuj</button>
        ${!isActive ? `<button class="secondary-btn danger-outline llm-preset-delete-btn" data-id="${preset.id}">Usuń</button>` : ""}
      </div>`;
    container.appendChild(card);
  });

  container.querySelectorAll(".llm-preset-activate-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        await adminFetch(`/api/admin/llm/presets/${btn.dataset.id}/activate`, { method: "POST" });
        showToast("Preset aktywowany.", "success");
        await _renderLlmTab(_panel.querySelector("#system-body"));
      } catch (e) { showToast(e.message || "Błąd", "error"); }
    });
  });
  container.querySelectorAll(".llm-preset-edit-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const preset = _presets.find(p => p.id === parseInt(btn.dataset.id, 10));
      if (preset) _openPresetModal(preset, _panel.querySelector("#system-body"));
    });
  });
  container.querySelectorAll(".llm-preset-delete-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.dataset.id, 10);
      const preset = _presets.find(p => p.id === id);
      if (!confirm(`Usunąć preset "${preset?.label}"?`)) return;
      try {
        await adminFetch(`/api/admin/llm/presets/${id}`, { method: "DELETE" });
        showToast("Preset usunięty.", "success");
        await _renderLlmTab(_panel.querySelector("#system-body"));
      } catch (e) { showToast(e.message || "Błąd", "error"); }
    });
  });
}

function _openPresetModal(preset, body) {
  const isEdit = !!preset;

  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field">
      <span>Nazwa presetu *</span>
      <input name="label" type="text" value="${_esc(preset?.label || "")}" placeholder="np. OpenAI GPT-4.1" />
    </label>
    <label class="modal-field">
      <span>Dostawca *</span>
      <select name="provider">
        ${PROVIDERS.map(p =>
          `<option value="${p.value}" ${(preset?.provider || "openai") === p.value ? "selected" : ""}>${_esc(p.label)}</option>`
        ).join("")}
      </select>
    </label>
    <label class="modal-field">
      <span>URL API *</span>
      <input name="base_url" type="text" value="${_esc(preset?.base_url || "")}" placeholder="np. https://api.openai.com" />
    </label>
    <div class="llm-azure-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px">
      Azure OpenAI: <code>https://&lt;resource&gt;.openai.azure.com</code><br>
      Azure AI Foundry: <code>https://&lt;project&gt;.inference.ai.azure.com</code>
    </div>
    <div class="llm-ollama-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px">
      Lokalny Ollama: <code>http://localhost:11434</code><br>
      Ollama Cloud: <code>https://ollama.com</code>
    </div>
    <label class="modal-field">
      <span>Klucz API ${isEdit && preset?.api_key_set ? "<em>(ustawiony — zostaw puste by nie zmieniać)</em>" : ""}</span>
      <input name="api_key" type="password" autocomplete="off" placeholder="${isEdit ? "••••••••" : "sk-..."}" />
    </label>
    <div class="llm-azure-key-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px">
      Azure: użyj klucza z sekcji <em>Keys and Endpoint</em> w Azure Portal.
    </div>
    <div class="llm-ollama-key-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px">
      Lokalny Ollama: klucz nie jest wymagany.<br>
      Ollama Cloud: klucz API z <code>ollama.com/settings/api-keys</code>
    </div>
    <label class="modal-field">
      <span>Model *</span>
      <div class="llm-model-row">
        <input name="model" id="model-text-input" type="text"
          value="${_esc(preset?.model || "")}" placeholder="np. gpt-4.1" autocomplete="off" style="flex:1" />
        <button type="button" class="secondary-btn llm-fetch-models-btn">↻ Pobierz modele</button>
      </div>
      <div class="llm-fetch-status" style="font-size:0.73rem;color:var(--text-muted);margin-top:4px;min-height:16px"></div>
    </label>
    <label class="modal-checkbox-row">
      <input name="activate" type="checkbox" ${!isEdit ? "checked" : ""} />
      <span>Aktywuj po zapisaniu</span>
    </label>`;

  const providerSel   = form.querySelector("[name=provider]");
  const baseUrlInput  = form.querySelector("[name=base_url]");
  const azureHint     = form.querySelector(".llm-azure-hint");
  const azureKeyHint  = form.querySelector(".llm-azure-key-hint");
  const ollamaHint    = form.querySelector(".llm-ollama-hint");
  const ollamaKeyHint = form.querySelector(".llm-ollama-key-hint");

  const PLACEHOLDERS = {
    openai: "https://api.openai.com",
    azure:  "https://<resource>.openai.azure.com",
    ollama: "https://ollama.com",
    other:  "https://your-api-host",
  };

  const syncHints = () => {
    const p = providerSel.value;
    azureHint.style.display     = p === "azure"  ? "" : "none";
    azureKeyHint.style.display  = p === "azure"  ? "" : "none";
    ollamaHint.style.display    = p === "ollama" ? "" : "none";
    ollamaKeyHint.style.display = p === "ollama" ? "" : "none";
    if (!baseUrlInput.value.trim()) baseUrlInput.placeholder = PLACEHOLDERS[p] || PLACEHOLDERS.other;
  };
  syncHints();
  providerSel.addEventListener("change", syncHints);

  const fetchBtn    = form.querySelector(".llm-fetch-models-btn");
  const fetchStatus = form.querySelector(".llm-fetch-status");
  const modelRow    = form.querySelector(".llm-model-row");
  const modelText   = form.querySelector("#model-text-input");

  function _applyModelSelect(models) {
    const old = modelRow.querySelector("select.llm-model-select");
    if (old) old.remove();
    const current = modelText.value.trim();
    const sel = document.createElement("select");
    sel.className = "llm-model-select";
    sel.style.flex = "1";
    models.forEach(m => {
      const opt = document.createElement("option");
      opt.value = m; opt.textContent = m;
      if (m === current) opt.selected = true;
      sel.appendChild(opt);
    });
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "— Wpisz nazwę ręcznie —";
    sel.appendChild(customOpt);
    sel.addEventListener("change", () => {
      if (sel.value === "__custom__") {
        sel.remove(); modelText.style.display = ""; modelText.focus(); modelText.select();
      } else {
        modelText.value = sel.value;
      }
    });
    if (!models.includes(current)) { modelText.value = models[0]; sel.value = models[0]; }
    modelText.style.display = "none";
    modelRow.insertBefore(sel, fetchBtn);
  }

  fetchBtn.addEventListener("click", async () => {
    const provider = form.querySelector("[name=provider]").value;
    const base_url = form.querySelector("[name=base_url]").value.trim();
    const api_key  = form.querySelector("[name=api_key]").value.trim() || null;
    if (!base_url) {
      fetchStatus.textContent = "Podaj URL API przed pobraniem modeli.";
      fetchStatus.style.color = "var(--accent-red)"; return;
    }
    fetchBtn.disabled = true; fetchBtn.textContent = "…";
    const isAzure = provider === "azure";
    fetchStatus.style.color = "var(--text-muted)";
    fetchStatus.textContent = isAzure ? "Sprawdzanie wdrożonych modeli…" : "Pobieranie listy modeli…";
    try {
      const payload = { provider, base_url, api_key };
      if (isEdit && preset?.id && !api_key) payload.preset_id = preset.id;
      const data = await adminFetch("/api/admin/llm/fetch-models", {
        method: "POST", body: JSON.stringify(payload),
      });
      if (!data.ok || !data.models?.length) {
        fetchStatus.textContent = data.error ? `Błąd: ${data.error}` : "Brak modeli lub nieprawidłowy klucz API.";
        fetchStatus.style.color = "var(--accent-red)"; return;
      }
      _applyModelSelect(data.models);
      fetchStatus.textContent = `Znaleziono ${data.models.length} modeli.`;
      fetchStatus.style.color = "var(--accent-green)";
    } catch (e) {
      fetchStatus.textContent = `Błąd: ${e.message || "nieznany"}`;
      fetchStatus.style.color = "var(--accent-red)";
    } finally { fetchBtn.disabled = false; fetchBtn.textContent = "↻ Pobierz modele"; }
  });

  openModal({
    title: isEdit ? "Edytuj preset LLM" : "Nowy preset LLM",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: c => c() },
      {
        label: isEdit ? "Zapisz" : "Utwórz",
        class: "primary-btn",
        onClick: async c => {
          const g = n => form.querySelector(`[name="${n}"]`);
          const label    = g("label").value.trim();
          const provider = g("provider").value;
          const base_url = g("base_url").value.trim();
          const model    = g("model").value.trim();
          const api_key  = g("api_key").value || null;
          const activate = g("activate").checked;
          if (!label || !base_url || !model) {
            showToast("Wypełnij wymagane pola (nazwa, URL, model).", "error"); return;
          }
          const payload = {
            label, provider, base_url, model, activate,
            ...(api_key ? { api_key } : {}),
            ...(isEdit ? { preset_id: preset.id } : {}),
          };
          try {
            await adminFetch("/api/admin/llm/presets", { method: "POST", body: JSON.stringify(payload) });
            showToast(isEdit ? "Preset zaktualizowany." : "Preset utworzony.", "success");
            c();
            await _renderLlmTab(body);
          } catch (e) { showToast(e.message || "Błąd", "error"); }
        },
      },
    ],
  });
}

// ── Resurrection global config tab ───────────────────────────────────────────

const _RESURRECT_MODE_LABELS = {
  admin_free:       "🆓 Bezpłatnie (GM mercy / testy)",
  gold_percent:     "💰 Procent obecnego złota",
  gold_recent_days: "📜 Suma niedawnych zarobków (okno dni)",
  xp_revert:        "✦ Cofnij ostatnie zdobycie PD",
  item_loss:        "🎒 Losowa utrata założonego przedmiotu",
};

function _resurrectHelpText(cfg) {
  switch (cfg.mode) {
    case "admin_free":       return "Wskrzeszenie jest bezpłatne dla wszystkich graczy.";
    case "gold_percent":     return `Gracz straci <strong>${cfg.value}%</strong> obecnego złota.`;
    case "gold_recent_days": return `Gracz straci sumę zarobków z ostatnich <strong>${cfg.value} dni gry</strong>, maksymalnie <strong>${cfg.cap_percent}%</strong> bieżącego złota.`;
    case "xp_revert":        return `Cofnięte zostanie <strong>${cfg.value} PD</strong>. Awanse umiejętności i zaklęcia zakupione za te PD zostaną cofnięte.`;
    case "item_loss":        return "Losowo wybrany funkcjonalny przedmiot z ekwipunku zostanie utracony.";
    default:                 return "";
  }
}

async function _renderResurrectionTab(body) {
  const { adminFetch, showToast } = await import("../shared/api.js").catch(() => ({
    adminFetch: window.adminFetch, showToast: window.showToast
  }));
  let cfg = {};
  try {
    const data = await adminFetch("/api/admin/resurrection-config");
    cfg = data.config || {};
  } catch (e) {
    body.innerHTML = `<p class="drawer-error">Błąd: ${_esc(e.message)}</p>`;
    return;
  }

  const modeOpts = Object.entries(_RESURRECT_MODE_LABELS).map(([k, lbl]) =>
    `<option value="${k}"${cfg.mode === k ? " selected" : ""}>${lbl}</option>`
  ).join("");

  body.innerHTML = `
    <div class="drawer-section" style="max-width:640px">
      <div class="drawer-section-title">Wskrzeszenie bohaterów — globalna konfiguracja</div>
      <p style="font-size:0.85rem;opacity:0.7;margin:0 0 16px;line-height:1.5;">
        Ta konfiguracja dotyczy <strong>wszystkich graczy</strong>. Włącz wskrzeszenie i wybierz
        koszt, który zapłaci każdy bohater po śmierci. Indywidualne „życia" możesz ustawiać
        w sekcji <em>Gracze → Kampanie → karta bohatera</em>.
      </p>

      <label class="drawer-toggle-row" style="margin-bottom:16px;">
        <span style="font-weight:600;">Wskrzeszenie włączone</span>
        <input type="checkbox" id="res-enabled" ${cfg.enabled ? "checked" : ""} />
      </label>

      <label class="drawer-field">
        <span>Tryb kosztu</span>
        <select id="res-mode">${modeOpts}</select>
      </label>

      <label class="drawer-field">
        <span>Wartość główna (PD / % / liczba dni gry)</span>
        <input id="res-value" type="number" min="0" max="9999" value="${cfg.value ?? 25}" />
      </label>

      <label class="drawer-field" id="res-cap-row" style="display:${cfg.mode === "gold_recent_days" ? "" : "none"}">
        <span>Górny limit % bieżącego złota (tylko dla trybu „niedawne zarobki")</span>
        <input id="res-cap" type="number" min="0" max="100" value="${cfg.cap_percent ?? 50}" />
      </label>

      <label class="drawer-field">
        <span>Domyślna liczba użyć (puste = bez limitu dla każdego gracza)</span>
        <input id="res-default-uses" type="number" min="0" max="999" value="${cfg.default_uses ?? ""}" placeholder="bez limitu" />
      </label>

      <div id="res-help" style="margin:12px 0;padding:10px;background:rgba(255,255,255,0.04);border-radius:6px;font-size:0.9rem;line-height:1.4;">
        ${_resurrectHelpText(cfg)}
      </div>

      <button class="primary-btn" id="res-save" style="margin-top:4px">Zapisz konfigurację</button>
    </div>`;

  const elMode = body.querySelector("#res-mode");
  const elVal  = body.querySelector("#res-value");
  const elCap  = body.querySelector("#res-cap");
  const elHelp = body.querySelector("#res-help");
  const elCapRow = body.querySelector("#res-cap-row");

  const refresh = () => {
    elHelp.innerHTML = _resurrectHelpText({ mode: elMode.value, value: +elVal.value || 0, cap_percent: +elCap.value || 0 });
    elCapRow.style.display = elMode.value === "gold_recent_days" ? "" : "none";
  };
  elMode.addEventListener("change", refresh);
  elVal.addEventListener("input", refresh);
  elCap.addEventListener("input", refresh);

  body.querySelector("#res-save").addEventListener("click", async () => {
    const usesRaw = body.querySelector("#res-default-uses").value.trim();
    const payload = {
      enabled:    body.querySelector("#res-enabled").checked,
      mode:       elMode.value,
      value:      parseInt(elVal.value, 10) || 0,
      cap_percent: parseInt(elCap.value, 10) || 0,
    };
    if (usesRaw === "") payload.clear_default_uses = true;
    else payload.default_uses = parseInt(usesRaw, 10) || 0;
    try {
      await adminFetch("/api/admin/resurrection-config", { method: "PATCH", body: JSON.stringify(payload) });
      showToast("Konfiguracja wskrzeszenia zapisana.", "success");
      await _renderResurrectionTab(body);
    } catch (e) { showToast(e.message || "Błąd", "error"); }
  });
}

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
