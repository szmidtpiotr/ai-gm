import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";

const TABS = ["llm", "database", "config"];

const TAB_LABELS = {
  llm:      "LLM",
  database: "Database",
  config:   "Config",
};

const PROVIDERS = [
  { value: "openai",  label: "OpenAI" },
  { value: "azure",   label: "Azure AI Foundry / Azure OpenAI" },
  { value: "ollama",  label: "Ollama" },
  { value: "other",   label: "Other (OpenAI-compatible)" },
];

let _panel      = null;
let _activeTab  = "llm";
let _presets    = [];
let _activeId   = null;
let _settings   = null;

export async function init(panel) {
  _panel     = panel;
  _activeTab = "llm";

  panel.innerHTML = `
    <div class="system-layout">
      <div class="system-tabnav" id="system-tabnav">
        ${TABS.map((t) =>
          `<button class="system-tab-btn${t === _activeTab ? " active" : ""}" data-tab="${t}">${TAB_LABELS[t]}</button>`
        ).join("")}
      </div>
      <div class="system-body" id="system-body"></div>
    </div>`;

  panel.querySelectorAll(".system-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      _activeTab = btn.dataset.tab;
      panel.querySelectorAll(".system-tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
      _renderTab(_activeTab);
    });
  });

  await _renderTab(_activeTab);
}

async function _renderTab(tab) {
  const body = _panel.querySelector("#system-body");
  body.innerHTML = `<div class="drawer-loading">Ładowanie…</div>`;
  if (tab === "llm")      await _renderLlmTab(body);
  if (tab === "database") _renderPlaceholder(body, "🗄", "Database", "Migracje, backup i info o bazie danych.");
  if (tab === "config")   _renderPlaceholder(body, "📦", "Config", "Eksport i import konfiguracji.");
}

function _renderPlaceholder(body, icon, title, desc) {
  body.innerHTML = `
    <div class="section-placeholder">
      <div class="section-placeholder-icon">${icon}</div>
      <h2>${title}</h2>
      <p style="color:var(--text-muted);font-size:0.8rem">${desc} — Coming soon</p>
    </div>`;
}

// ── LLM Presets ───────────────────────────────────────────────────────────────

async function _renderLlmTab(body) {
  try {
    const data = await adminFetch("/api/admin/llm/global-settings");
    _presets   = data.presets || [];
    _activeId  = data.active_preset_id ?? null;
    _settings  = data.settings || {};
  } catch (e) {
    body.innerHTML = `<p class="drawer-error">Błąd: ${_esc(e.message)}</p>`;
    return;
  }

  const activePreset = _presets.find((p) => p.id === _activeId);
  const effModel     = activePreset?.model || _settings.model || "—";
  const effProvider  = _providerLabel(activePreset?.provider || _settings.provider);
  const effUrl       = activePreset?.base_url || _settings.base_url || "—";

  body.innerHTML = `
    <div class="system-llm-wrap">

      <div class="system-section">
        <div class="system-section-title">Aktywna konfiguracja LLM</div>
        <div class="llm-active-card">
          <div class="llm-active-row">
            <span class="llm-active-label">Preset</span>
            <span class="llm-active-value">${activePreset ? _esc(activePreset.label) : '<em class="muted">brak — używane zmienne środowiskowe</em>'}</span>
          </div>
          <div class="llm-active-row">
            <span class="llm-active-label">Dostawca</span>
            <span class="llm-active-value">${_esc(effProvider)}</span>
          </div>
          <div class="llm-active-row">
            <span class="llm-active-label">Model</span>
            <span class="llm-active-value">${_esc(effModel)}</span>
          </div>
          <div class="llm-active-row">
            <span class="llm-active-label">URL</span>
            <span class="llm-active-value" style="word-break:break-all">${_esc(effUrl)}</span>
          </div>
        </div>
        ${_activeId !== null ? `<button class="secondary-btn" id="use-env-btn" style="margin-top:8px">Użyj zmiennych środowiskowych (wyczyść preset)</button>` : ""}
      </div>

      <div class="system-section">
        <div class="system-section-title">Presety LLM</div>
        <div id="presets-list"></div>
        <button class="primary-btn" id="add-preset-btn" style="margin-top:12px">+ Dodaj preset</button>
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
}

function _providerLabel(provider) {
  const p = PROVIDERS.find((x) => x.value === (provider || "").toLowerCase());
  return p ? p.label : (provider || "—");
}

function _renderPresetsList(container) {
  if (!_presets.length) {
    container.innerHTML = `<p class="muted" style="font-size:0.83rem;padding:12px 0">Brak presetów. Dodaj pierwszy preset poniżej.</p>`;
    return;
  }

  container.innerHTML = "";
  _presets.forEach((preset) => {
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
        ${!isActive ? `<button class="primary-btn llm-preset-activate-btn" data-id="${preset.id}">Aktywuj</button>` : `<span class="admin-badge admin-badge-green">Aktywny</span>`}
        <button class="secondary-btn llm-preset-edit-btn" data-id="${preset.id}">Edytuj</button>
        ${!isActive ? `<button class="secondary-btn danger-outline llm-preset-delete-btn" data-id="${preset.id}">Usuń</button>` : ""}
      </div>`;
    container.appendChild(card);
  });

  container.querySelectorAll(".llm-preset-activate-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.dataset.id, 10);
      try {
        await adminFetch(`/api/admin/llm/presets/${id}/activate`, { method: "POST" });
        showToast("Preset aktywowany.", "success");
        await _renderLlmTab(_panel.querySelector("#system-body"));
      } catch (e) { showToast(e.message || "Błąd", "error"); }
    });
  });

  container.querySelectorAll(".llm-preset-edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = parseInt(btn.dataset.id, 10);
      const preset = _presets.find((p) => p.id === id);
      if (preset) _openPresetModal(preset, _panel.querySelector("#system-body"));
    });
  });

  container.querySelectorAll(".llm-preset-delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.dataset.id, 10);
      const preset = _presets.find((p) => p.id === id);
      if (!confirm(`Usunąć preset "${preset?.label}"?`)) return;
      try {
        await adminFetch(`/api/admin/llm/presets/${id}`, { method: "DELETE" });
        showToast("Preset usunięty.", "success");
        await _renderLlmTab(_panel.querySelector("#system-body"));
      } catch (e) { showToast(e.message || "Błąd", "error"); }
    });
  });
}

// ── Preset modal with model fetcher ──────────────────────────────────────────

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
        ${PROVIDERS.map((p) => `<option value="${p.value}" ${(preset?.provider || "openai") === p.value ? "selected" : ""}>${_esc(p.label)}</option>`).join("")}
      </select>
    </label>

    <label class="modal-field">
      <span>URL API *</span>
      <input name="base_url" type="text" value="${_esc(preset?.base_url || "")}"
        placeholder="np. https://api.openai.com" />
    </label>
    <div class="llm-azure-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px 0">
      Azure OpenAI: <code>https://&lt;resource&gt;.openai.azure.com</code><br>
      Azure AI Foundry: <code>https://&lt;project&gt;.inference.ai.azure.com</code>
    </div>
    <div class="llm-ollama-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px 0">
      Lokalny Ollama: <code>http://localhost:11434</code><br>
      Ollama Cloud: <code>https://ollama.com</code>
    </div>

    <label class="modal-field">
      <span>Klucz API ${isEdit && preset?.api_key_set ? "<em>(ustawiony — zostaw puste by nie zmieniać)</em>" : ""}</span>
      <input name="api_key" type="password" autocomplete="off"
        placeholder="${isEdit ? "••••••••" : "sk-..."}" />
    </label>
    <div class="llm-azure-key-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px 0">
      Azure: użyj klucza z sekcji <em>Keys and Endpoint</em> w Azure Portal.
    </div>
    <div class="llm-ollama-key-hint" style="display:none;font-size:0.75rem;color:var(--text-muted);margin:-8px 0 8px 0">
      Lokalny Ollama: klucz nie jest wymagany.<br>
      Ollama Cloud: klucz API z <code>ollama.com/settings/api-keys</code>
    </div>

    <label class="modal-field">
      <span>Model *</span>
      <div class="llm-model-row">
        <input name="model" id="model-text-input" type="text"
          value="${_esc(preset?.model || "")}" placeholder="np. gpt-4.1" autocomplete="off" style="flex:1" />
        <button type="button" class="secondary-btn llm-fetch-models-btn">
          ↻ Pobierz modele
        </button>
      </div>
      <div class="llm-fetch-status" style="font-size:0.73rem;color:var(--text-muted);margin-top:4px;min-height:16px"></div>
    </label>

    <label class="modal-checkbox-row">
      <input name="activate" type="checkbox" ${!isEdit ? "checked" : ""} />
      <span>Aktywuj po zapisaniu</span>
    </label>`;

  // Show provider-specific hints
  const providerSel    = form.querySelector("[name=provider]");
  const baseUrlInput   = form.querySelector("[name=base_url]");
  const azureHint      = form.querySelector(".llm-azure-hint");
  const azureKeyHint   = form.querySelector(".llm-azure-key-hint");
  const ollamaHint     = form.querySelector(".llm-ollama-hint");
  const ollamaKeyHint  = form.querySelector(".llm-ollama-key-hint");

  const PLACEHOLDERS = {
    openai: "https://api.openai.com",
    azure:  "https://<resource>.openai.azure.com",
    ollama: "https://ollama.com",
    other:  "https://your-api-host",
  };

  const syncProviderHints = () => {
    const p = providerSel.value;
    azureHint.style.display     = p === "azure"  ? "" : "none";
    azureKeyHint.style.display  = p === "azure"  ? "" : "none";
    ollamaHint.style.display    = p === "ollama" ? "" : "none";
    ollamaKeyHint.style.display = p === "ollama" ? "" : "none";
    if (!baseUrlInput.value.trim()) {
      baseUrlInput.placeholder = PLACEHOLDERS[p] || PLACEHOLDERS.other;
    }
  };
  syncProviderHints();
  providerSel.addEventListener("change", syncProviderHints);

  // Model field refs
  const fetchBtn    = form.querySelector(".llm-fetch-models-btn");
  const fetchStatus = form.querySelector(".llm-fetch-status");
  const modelRow    = form.querySelector(".llm-model-row");
  const modelText   = form.querySelector("#model-text-input");

  // Replace text input with a <select> after successful fetch
  function _applyModelSelect(models) {
    // Remove existing select if any
    const old = modelRow.querySelector("select.llm-model-select");
    if (old) old.remove();

    const current = modelText.value.trim();
    const sel = document.createElement("select");
    sel.className = "llm-model-select";
    sel.style.flex = "1";

    // Populate options
    models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      if (m === current) opt.selected = true;
      sel.appendChild(opt);
    });

    // "Custom…" escape hatch
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "— Wpisz nazwę ręcznie —";
    sel.appendChild(customOpt);

    // Sync select → text input
    sel.addEventListener("change", () => {
      if (sel.value === "__custom__") {
        sel.remove();
        modelText.style.display = "";
        modelText.focus();
        modelText.select();
      } else {
        modelText.value = sel.value;
      }
    });

    // Set text input to first model if nothing matched
    if (!models.includes(current)) {
      modelText.value = models[0];
      sel.value = models[0];
    }

    // Insert select before the fetch button, hide text input
    modelText.style.display = "none";
    modelRow.insertBefore(sel, fetchBtn);
  }

  fetchBtn.addEventListener("click", async () => {
    const provider = form.querySelector("[name=provider]").value;
    const base_url = form.querySelector("[name=base_url]").value.trim();
    const api_key  = form.querySelector("[name=api_key]").value.trim() || null;

    if (!base_url) {
      fetchStatus.textContent = "Podaj URL API przed pobraniem modeli.";
      fetchStatus.style.color = "var(--accent-red)";
      return;
    }

    fetchBtn.disabled    = true;
    fetchBtn.textContent = "…";
    fetchStatus.style.color = "var(--text-muted)";

    const isAzure = provider === "azure";
    fetchStatus.textContent = isAzure
      ? "Sprawdzanie wdrożonych modeli… (może potrwać ~5 sekund)"
      : "Pobieranie listy modeli…";

    try {
      const payload = { provider, base_url, api_key };
      if (isEdit && preset?.id && !api_key) payload.preset_id = preset.id;

      const data = await adminFetch("/api/admin/llm/fetch-models", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (!data.ok || !data.models?.length) {
        fetchStatus.textContent = data.error
          ? `Błąd: ${data.error}`
          : "Brak dostępnych modeli lub nieprawidłowy klucz API.";
        fetchStatus.style.color = "var(--accent-red)";
        return;
      }

      _applyModelSelect(data.models);

      const label = isAzure
        ? `Znaleziono ${data.models.length} wdrożonych modeli.`
        : `Znaleziono ${data.models.length} modeli.`;
      fetchStatus.textContent = label;
      fetchStatus.style.color = "var(--accent-green)";
    } catch (e) {
      fetchStatus.textContent = `Błąd: ${e.message || "nieznany"}`;
      fetchStatus.style.color = "var(--accent-red)";
    } finally {
      fetchBtn.disabled    = false;
      fetchBtn.textContent = "↻ Pobierz modele";
    }
  });

  const { close } = openModal({
    title: isEdit ? "Edytuj preset LLM" : "Nowy preset LLM",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? "Zapisz" : "Utwórz",
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const label    = g("label").value.trim();
          const provider = g("provider").value;
          const base_url = g("base_url").value.trim();
          const model    = g("model").value.trim();
          const api_key  = g("api_key").value || null;
          const activate = g("activate").checked;

          if (!label || !base_url || !model) {
            showToast("Wypełnij wymagane pola (nazwa, URL, model).", "error");
            return;
          }
          const payload = {
            label, provider, base_url, model, activate,
            ...(api_key ? { api_key } : {}),
            ...(isEdit ? { preset_id: preset.id } : {}),
          };
          try {
            await adminFetch("/api/admin/llm/presets", {
              method: "POST",
              body: JSON.stringify(payload),
            });
            showToast(isEdit ? "Preset zaktualizowany." : "Preset utworzony.", "success");
            c();
            await _renderLlmTab(body);
          } catch (e) { showToast(e.message || "Błąd", "error"); }
        },
      },
    ],
  });
}

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
