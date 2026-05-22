// Visual settings — admin panel section
// Subtabs structure designed to grow: "Pora dnia" first, future: fonts, ui-themes, particles.
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const PERIODS = [
  { key: "rano",       label: "Rano",       hours: "06–11", icon: "🌅" },
  { key: "popoludnie", label: "Popołudnie", hours: "12–17", icon: "☀️" },
  { key: "wieczor",    label: "Wieczór",    hours: "18–21", icon: "🌇" },
  { key: "noc",        label: "Noc",        hours: "22–05", icon: "🌙" },
];

const state = {
  settings: {},
  previewPeriod: "popoludnie",
};

export async function init(panel) {
  panel.innerHTML = layout();
  await loadSettings();
  renderTabPora(panel);
  bindEvents(panel);
}

function layout() {
  return `
    <div class="visual-root">
      <header class="visual-header">
        <h2>🎨 Wygląd gry</h2>
        <p class="section-note">Konfiguruj wizualne elementy gry: pora dnia, czcionki, motywy. Zmiany widoczne natychmiast w grze.</p>
      </header>

      <nav class="visual-subtabs">
        <button class="visual-subtab visual-subtab--active" data-subtab="pora">🌗 Pora dnia</button>
        <button class="visual-subtab" data-subtab="bg">🖼 Tła ekranów</button>
        <button class="visual-subtab" data-subtab="fonts" disabled title="Wkrótce">🅰 Czcionki (wkrótce)</button>
        <button class="visual-subtab" data-subtab="theme" disabled title="Wkrótce">🎭 Motywy UI (wkrótce)</button>
      </nav>

      <div class="visual-subpane" id="visual-subpane-pora"></div>
      <div class="visual-subpane" id="visual-subpane-bg" hidden></div>
    </div>
  `;
}

async function loadSettings() {
  try {
    const res = await adminFetch("/api/admin/visual");
    state.settings = res?.settings || {};
  } catch (e) {
    showToast("Błąd ładowania ustawień: " + (e.message || "?"), "error");
    state.settings = {};
  }
}

function s(key, fallback = null) { return state.settings[key] ?? fallback; }

function renderTabPora(panel) {
  const enabled = s("time_of_day.enabled", true);
  const mode = s("time_of_day.mode", "frame");
  const intensity = s("time_of_day.intensity", 60);

  const cards = PERIODS.map(p => {
    const periodSettings = s(`time_of_day.${p.key}`, {}) || {};
    const color = periodSettings.color || "#c9a54a";
    const accent = periodSettings.accent || "#d4b65e";
    return `
      <div class="visual-period-card" data-period="${p.key}" style="--p-color: ${color}; --p-accent: ${accent};">
        <div class="visual-period-head">
          <span class="visual-period-icon">${p.icon}</span>
          <div class="visual-period-title">
            <strong>${esc(p.label)}</strong>
            <span class="visual-period-hours">godziny ${p.hours}</span>
          </div>
          <button type="button" class="visual-preview-btn" data-preview-period="${p.key}" title="Podgląd na podglądzie poniżej">Podgląd</button>
        </div>
        <div class="visual-color-row">
          <label class="visual-color-field">
            <span>Główny</span>
            <div class="visual-color-input-wrap">
              <input type="color" data-field="color" data-period="${p.key}" value="${color}">
              <input type="text" data-field="color-hex" data-period="${p.key}" value="${color}" maxlength="7" pattern="#[0-9a-fA-F]{6}">
            </div>
          </label>
          <label class="visual-color-field">
            <span>Akcent</span>
            <div class="visual-color-input-wrap">
              <input type="color" data-field="accent" data-period="${p.key}" value="${accent}">
              <input type="text" data-field="accent-hex" data-period="${p.key}" value="${accent}" maxlength="7" pattern="#[0-9a-fA-F]{6}">
            </div>
          </label>
        </div>
      </div>
    `;
  }).join("");

  const subpane = panel.querySelector("#visual-subpane-pora");
  subpane.innerHTML = `
    <div class="visual-grid">
      <section class="visual-controls">
        <div class="visual-toggle-row">
          <label class="visual-toggle">
            <input type="checkbox" data-field="enabled" ${enabled ? "checked" : ""}>
            <span>Włącz nakładkę pory dnia</span>
          </label>
        </div>

        <div class="visual-mode-row">
          <span class="visual-mode-label">Tryb:</span>
          ${["frame", "bg", "both", "off"].map(m => `
            <label class="visual-mode-pill${m === mode ? " visual-mode-pill--active" : ""}">
              <input type="radio" name="tod-mode" value="${m}" ${m === mode ? "checked" : ""}>
              <span>${m === "frame" ? "Ramka" : m === "bg" ? "Tło" : m === "both" ? "Oba" : "Wyłączone"}</span>
            </label>
          `).join("")}
        </div>

        <div class="visual-intensity-row">
          <label class="visual-intensity-label">
            <span>Intensywność</span>
            <span class="visual-intensity-value" id="intensity-value">${intensity}%</span>
          </label>
          <input type="range" min="0" max="100" step="5" value="${intensity}" data-field="intensity" class="visual-intensity-slider">
        </div>

        <h3 class="visual-cards-title">Kolory dla każdej pory</h3>
        <div class="visual-cards">${cards}</div>

        <div class="visual-actions">
          <button type="button" class="primary-btn" id="visual-reset-btn">Przywróć domyślne</button>
        </div>
      </section>

      <aside class="visual-preview" id="visual-preview">
        <div class="visual-preview-header">
          <span>Podgląd:</span>
          <span class="visual-preview-period" id="visual-preview-period-label">Popołudnie</span>
        </div>
        <div class="visual-preview-frame" id="visual-preview-frame">
          <div class="visual-preview-chat">
            <div class="vp-msg vp-msg--gm">
              <span class="vp-tag">GM</span>
              <span>Słońce chyli się ku zachodowi, a w karczmie rozbrzmiewa muzyka. Karczmarz patrzy na ciebie z ciekawością...</span>
            </div>
            <div class="vp-msg vp-msg--player">
              <span class="vp-tag vp-tag--player">Ty</span>
              <span>Podchodzę do karczmarza i pytam o pracę.</span>
            </div>
            <div class="vp-msg vp-msg--gm">
              <span class="vp-tag">GM</span>
              <span>"Pracy nie brak" — odpowiada — "ale czy unieś taki ciężar?"</span>
            </div>
          </div>
        </div>
        <p class="visual-preview-note">Przesuń kursorem na kartę pory dnia powyżej, aby podejrzeć w tym ramie. Zapis trafia natychmiast do bazy i jest widoczny w grze.</p>
      </aside>
    </div>
  `;

  updatePreview(panel);
}

function updatePreview(panel) {
  const preview = panel.querySelector("#visual-preview-frame");
  const label = panel.querySelector("#visual-preview-period-label");
  if (!preview) return;
  const period = state.previewPeriod;
  const periodSettings = s(`time_of_day.${period}`, {}) || {};
  const color = periodSettings.color || "#c9a54a";
  const accent = periodSettings.accent || "#d4b65e";
  const mode = s("time_of_day.mode", "frame");
  const intensity = Number(s("time_of_day.intensity", 60)) / 100;

  preview.style.setProperty("--tod-color", color);
  preview.style.setProperty("--tod-accent", accent);
  preview.style.setProperty("--tod-intensity", String(intensity));
  preview.dataset.todMode = mode;
  preview.dataset.todPeriod = PERIODS.find(p => p.key === period)?.label || "";

  if (label) label.textContent = PERIODS.find(p => p.key === period)?.label || "";
}

// Stage 9 follow-up — Tła ekranów subtab.
// Lists each backend-supported screen as a card. Each card: preview image
// (from /api/ui/bg/<screen> with cachebust), file picker, Wgraj button,
// Usuń button. Uploads go to POST /api/admin/ui/bg/<screen>.
const BG_SCREENS = [
  { key: 'login',         label: 'Logowanie',          hint: 'Ekran logowania' },
  { key: 'heroes',        label: 'Postacie (heroes)',  hint: 'Wybór bohatera' },
  { key: 'campaigns',     label: 'Kampanie',           hint: 'Lista kampanii' },
  { key: 'new-campaign',  label: 'Nowa kampania',      hint: 'Formularz tworzenia kampanii' },
  { key: 'wizard',        label: 'Kreator postaci',    hint: 'Cztery kroki wizard' },
  { key: 'game',          label: 'Gra (chat)',         hint: 'Ekran rozgrywki' },
  { key: 'sheet',         label: 'Karta postaci',      hint: 'Panel z atrybutami / ekwipunkiem' },
  { key: 'settings',      label: 'Ustawienia',         hint: 'Panel ustawień gry' },
  { key: 'death',         label: 'Śmierć',             hint: 'Ekran końcowy — porażka' },
  { key: 'victory',       label: 'Zwycięstwo',         hint: 'Ekran końcowy — sukces' },
];

async function renderTabBg(pane) {
  pane.innerHTML = `
    <div class="bg-screens-grid">
      ${BG_SCREENS.map(s => `
        <div class="bg-screen-card" data-screen="${s.key}">
          <div class="bg-screen-card__head">
            <h3>${esc(s.label)}</h3>
            <span class="bg-screen-card__key">${esc(s.key)}</span>
          </div>
          <p class="bg-screen-card__hint">${esc(s.hint)}</p>
          <div class="bg-screen-card__preview" data-preview="${s.key}">
            <span class="bg-screen-card__empty">— brak —</span>
          </div>
          <div class="bg-screen-card__actions">
            <label class="bg-screen-card__file">
              <span class="bg-screen-card__file-label">Wybierz plik</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" data-file="${s.key}" hidden>
            </label>
            <button type="button" class="primary-btn" data-upload="${s.key}" disabled>Wgraj</button>
            <button type="button" class="secondary-btn" data-delete="${s.key}">Usuń</button>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  // Load existing backgrounds
  try {
    const r = await fetch('/api/ui/backgrounds');
    if (r.ok) {
      const data = await r.json();
      const bgs = data?.backgrounds || {};
      for (const s of BG_SCREENS) {
        if (bgs[s.key]) _setPreview(pane, s.key, bgs[s.key]);
      }
    }
  } catch (e) { /* silent */ }

  // File picker → enable Upload button + preview locally
  pane.querySelectorAll('input[type="file"][data-file]').forEach(input => {
    input.addEventListener('change', (e) => {
      const screen = input.dataset.file;
      const file = e.target.files?.[0];
      const upBtn = pane.querySelector(`button[data-upload="${screen}"]`);
      const fileLabel = pane.querySelector(`.bg-screen-card[data-screen="${screen}"] .bg-screen-card__file-label`);
      if (upBtn) upBtn.disabled = !file;
      if (file && fileLabel) fileLabel.textContent = file.name.length > 28 ? file.name.slice(0, 25) + '…' : file.name;
    });
  });

  // Upload
  pane.querySelectorAll('button[data-upload]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const screen = btn.dataset.upload;
      const input = pane.querySelector(`input[data-file="${screen}"]`);
      const file = input?.files?.[0];
      if (!file) { showToast('Wybierz plik najpierw.', 'error'); return; }
      btn.disabled = true;
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await adminFetch(`/api/admin/ui/bg/${screen}`, { method: 'POST', body: fd });
        if (resp?.url) {
          _setPreview(pane, screen, resp.url + `?ts=${Date.now()}`);
        }
        showToast(`Tło dla "${screen}" wgrane.`, 'success');
        // Reset the picker label
        const fileLabel = pane.querySelector(`.bg-screen-card[data-screen="${screen}"] .bg-screen-card__file-label`);
        if (fileLabel) fileLabel.textContent = 'Wybierz plik';
        if (input) input.value = '';
      } catch (e) {
        showToast(`Błąd wysyłki: ${e?.message || e}`, 'error');
      } finally {
        btn.disabled = true;
      }
    });
  });

  // Delete
  pane.querySelectorAll('button[data-delete]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const screen = btn.dataset.delete;
      if (!confirm(`Usunąć tło dla ekranu "${screen}"?`)) return;
      try {
        await adminFetch(`/api/admin/ui/bg/${screen}`, { method: 'DELETE' });
        _clearPreview(pane, screen);
        showToast(`Tło dla "${screen}" usunięte.`, 'success');
      } catch (e) {
        showToast(`Błąd usuwania: ${e?.message || e}`, 'error');
      }
    });
  });
}

function _setPreview(pane, screen, url) {
  const wrap = pane.querySelector(`.bg-screen-card__preview[data-preview="${screen}"]`);
  if (!wrap) return;
  wrap.innerHTML = `<img src="${esc(url)}" alt="${esc(screen)} background" />`;
}
function _clearPreview(pane, screen) {
  const wrap = pane.querySelector(`.bg-screen-card__preview[data-preview="${screen}"]`);
  if (wrap) wrap.innerHTML = `<span class="bg-screen-card__empty">— brak —</span>`;
}

function bindEvents(panel) {
  // Subtab switcher (Stage 9 follow-up)
  panel.querySelectorAll('.visual-subtab[data-subtab]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.disabled) return;
      const target = btn.dataset.subtab;
      panel.querySelectorAll('.visual-subtab').forEach(b => b.classList.toggle('visual-subtab--active', b === btn));
      panel.querySelector('#visual-subpane-pora').hidden = target !== 'pora';
      const bgPane = panel.querySelector('#visual-subpane-bg');
      if (bgPane) {
        bgPane.hidden = target !== 'bg';
        if (target === 'bg' && !bgPane.dataset.loaded) {
          renderTabBg(bgPane);
          bgPane.dataset.loaded = '1';
        }
      }
    });
  });

  // Enabled toggle
  panel.querySelector('input[data-field="enabled"]')?.addEventListener("change", async (e) => {
    const enabled = e.target.checked;
    state.settings["time_of_day.enabled"] = enabled;
    await save("time_of_day.enabled", enabled);
    showToast(enabled ? "Nakładka włączona" : "Nakładka wyłączona", "success", 1500);
  });

  // Mode radio
  panel.querySelectorAll('input[name="tod-mode"]').forEach(input => {
    input.addEventListener("change", async (e) => {
      const mode = e.target.value;
      state.settings["time_of_day.mode"] = mode;
      // Update pill classes
      panel.querySelectorAll('.visual-mode-pill').forEach(p => p.classList.toggle('visual-mode-pill--active', p.querySelector('input').value === mode));
      await save("time_of_day.mode", mode);
      updatePreview(panel);
    });
  });

  // Intensity slider
  const intensitySlider = panel.querySelector('input[data-field="intensity"]');
  const intensityLabel = panel.querySelector("#intensity-value");
  intensitySlider?.addEventListener("input", (e) => {
    const v = Number(e.target.value);
    if (intensityLabel) intensityLabel.textContent = `${v}%`;
    state.settings["time_of_day.intensity"] = v;
    updatePreview(panel);
  });
  intensitySlider?.addEventListener("change", async (e) => {
    await save("time_of_day.intensity", Number(e.target.value));
  });

  // Color pickers
  panel.querySelectorAll('input[type="color"][data-period]').forEach(picker => {
    const field = picker.dataset.field; // "color" or "accent"
    const period = picker.dataset.period;
    const hexInput = panel.querySelector(`input[data-field="${field}-hex"][data-period="${period}"]`);
    const card = panel.querySelector(`.visual-period-card[data-period="${period}"]`);

    picker.addEventListener("input", (e) => {
      const v = e.target.value;
      if (hexInput) hexInput.value = v;
      if (card) card.style.setProperty(`--p-${field === "color" ? "color" : "accent"}`, v);
      const key = `time_of_day.${period}`;
      const cur = state.settings[key] || {};
      state.settings[key] = { ...cur, [field]: v };
      updatePreview(panel);
    });
    picker.addEventListener("change", async (e) => {
      const key = `time_of_day.${period}`;
      await save(key, state.settings[key]);
    });
  });
  panel.querySelectorAll('input[data-field$="-hex"]').forEach(input => {
    input.addEventListener("input", (e) => {
      const v = e.target.value.trim();
      if (!/^#[0-9a-fA-F]{6}$/.test(v)) return;
      const field = input.dataset.field.replace("-hex", "");
      const period = input.dataset.period;
      const picker = panel.querySelector(`input[type="color"][data-field="${field}"][data-period="${period}"]`);
      if (picker) picker.value = v;
      const card = panel.querySelector(`.visual-period-card[data-period="${period}"]`);
      if (card) card.style.setProperty(`--p-${field === "color" ? "color" : "accent"}`, v);
      const key = `time_of_day.${period}`;
      const cur = state.settings[key] || {};
      state.settings[key] = { ...cur, [field]: v };
      updatePreview(panel);
    });
    input.addEventListener("blur", async () => {
      const period = input.dataset.period;
      const key = `time_of_day.${period}`;
      if (state.settings[key]) await save(key, state.settings[key]);
    });
  });

  // Preview period selectors
  panel.querySelectorAll('button[data-preview-period]').forEach(btn => {
    btn.addEventListener("click", () => {
      state.previewPeriod = btn.dataset.previewPeriod;
      updatePreview(panel);
    });
  });

  // Reset to defaults
  panel.querySelector("#visual-reset-btn")?.addEventListener("click", async () => {
    if (!confirm("Przywrócić wszystkie kolory pór dnia do domyślnych?")) return;
    const defaults = {
      "time_of_day.enabled": true,
      "time_of_day.mode": "frame",
      "time_of_day.intensity": 60,
      "time_of_day.rano":       { color: "#ffd97a", accent: "#f7e7a3", label: "Rano" },
      "time_of_day.popoludnie": { color: "#c9a54a", accent: "#d4b65e", label: "Popołudnie" },
      "time_of_day.wieczor":    { color: "#c95c2e", accent: "#e07555", label: "Wieczór" },
      "time_of_day.noc":        { color: "#5a6d99", accent: "#7a8cb8", label: "Noc" },
    };
    for (const [k, v] of Object.entries(defaults)) {
      state.settings[k] = v;
      await save(k, v);
    }
    renderTabPora(panel);
    bindEvents(panel);
    showToast("Domyślne kolory przywrócone", "success");
  });
}

async function save(key, value) {
  try {
    await adminFetch(`/api/admin/visual/${encodeURIComponent(key)}`, {
      method: "PATCH",
      body: JSON.stringify({ value }),
    });
  } catch (e) {
    showToast("Błąd zapisu: " + (e.message || "?"), "error");
  }
}
