import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  title: "Kreator Haków Fabularnych",
  modePrompt: "Prompt",
  modeText: "Tekst / Historia",
  modePdf: "Plik PDF",
  promptPlaceholder: "Opisz kontekst lub motyw przewodni… np. zdradziecka gildia kupców, zniszczone miasto na bagnach, tajemniczy pustelnik",
  textPlaceholder: "Wklej fragment historii, opisu świata lub scenariusza z którego LLM wygeneruje haki…",
  countLabel: "Liczba haków",
  generateBtn: "Generuj haki",
  generating: "Generuję…",
  uploadBtn: "Wybierz PDF / TXT",
  extractBtn: "Wczytaj plik",
  extracting: "Wczytuję…",
  extractedLabel: "Wczytany tekst",
  truncatedWarning: "Plik jest duży — wczytano pierwsze 25 000 znaków.",
  saveBtn: "Zapisz",
  saveAll: "Zapisz wszystkie",
  discardBtn: "Odrzuć",
  libraryTitle: "Biblioteka Haków",
  searchPlaceholder: "Szukaj…",
  noHooks: "Brak zapisanych haków",
  noMatch: "Brak wyników",
  copy: "Kopiuj",
  delete: "Usuń",
  confirmDelete: "Usunąć hak?",
  preset: "Model LLM",
};

export async function init(panel) {
  panel.innerHTML = `
    <div class="designer-layout">

      <!-- ── LEFT: Generator ── -->
      <div class="designer-left">
        <div class="designer-section-title">${LABELS.title}</div>

        <!-- LLM Preset -->
        <div class="designer-preset-row">
          <label class="designer-preset-label">${LABELS.preset}</label>
          <select id="designer-preset-select" class="field-input designer-preset-select">
            <option value="">⚡ Aktywny preset (domyślny)</option>
          </select>
        </div>

        <!-- Mode tabs -->
        <div class="designer-mode-tabs">
          <button type="button" class="designer-mode-btn active" data-mode="prompt">${LABELS.modePrompt}</button>
          <button type="button" class="designer-mode-btn" data-mode="text">${LABELS.modeText}</button>
          <button type="button" class="designer-mode-btn" data-mode="pdf">${LABELS.modePdf}</button>
        </div>

        <!-- Mode: Prompt -->
        <div class="designer-mode-panel active" data-mode="prompt">
          <textarea id="designer-prompt" class="designer-brief" rows="5"
            placeholder="${LABELS.promptPlaceholder}" maxlength="2000"></textarea>
        </div>

        <!-- Mode: Text -->
        <div class="designer-mode-panel" data-mode="text">
          <textarea id="designer-text" class="designer-brief" rows="10"
            placeholder="${LABELS.textPlaceholder}" maxlength="30000"></textarea>
          <div class="designer-char-count" id="text-char-count">0 / 30 000</div>
        </div>

        <!-- Mode: PDF -->
        <div class="designer-mode-panel" data-mode="pdf">
          <div class="designer-upload-area" id="upload-area">
            <input type="file" id="pdf-file-input" accept=".pdf,.txt,.md" style="display:none" />
            <button type="button" class="secondary-btn" id="pdf-pick-btn">${LABELS.uploadBtn}</button>
            <span id="pdf-filename" class="designer-filename">—</span>
            <button type="button" class="secondary-btn" id="pdf-extract-btn" disabled>${LABELS.extractBtn}</button>
          </div>
          <div id="pdf-preview-wrap" style="display:none">
            <div class="designer-extracted-label">
              ${LABELS.extractedLabel}
              <span id="pdf-truncated-warn" class="designer-truncated" style="display:none">⚠ ${LABELS.truncatedWarning}</span>
            </div>
            <textarea id="pdf-extracted-text" class="designer-brief" rows="8" readonly></textarea>
            <div class="designer-char-count" id="pdf-char-count">0 znaków</div>
          </div>
        </div>

        <!-- Count + Generate -->
        <div class="designer-gen-row">
          <label class="designer-preset-label">${LABELS.countLabel}</label>
          <select id="hook-count" class="field-input" style="width:80px">
            <option value="3">3</option>
            <option value="4" selected>4</option>
            <option value="5">5</option>
            <option value="6">6</option>
          </select>
          <button type="button" id="designer-gen-btn" class="primary-btn" style="flex:1">${LABELS.generateBtn}</button>
        </div>

        <!-- Generated hooks preview -->
        <div id="hooks-preview" style="display:none">
          <div class="hooks-preview-header">
            <span class="designer-extracted-label">Wygenerowane haki</span>
            <button type="button" id="save-all-btn" class="secondary-btn" style="font-size:0.78rem">${LABELS.saveAll}</button>
          </div>
          <div id="hooks-list" class="hooks-list"></div>
        </div>
      </div>

      <!-- ── RIGHT: Library ── -->
      <div class="designer-right">
        <div class="designer-library-header">
          <span class="designer-section-title">${LABELS.libraryTitle}</span>
          <input id="lib-search" class="field-input" type="search"
            placeholder="${LABELS.searchPlaceholder}" style="width:200px" />
        </div>
        <div id="lib-grid" class="lib-grid">
          <div class="lib-empty">${LABELS.noHooks}</div>
        </div>
      </div>
    </div>
  `;

  let currentMode = "prompt";
  let generatedHooks = [];
  let allSnippets = [];
  let libSearch = "";
  let extractedText = "";

  // ── load presets ──
  async function loadPresets() {
    try {
      const data = await adminFetch("/api/admin/llm/global-settings");
      const presets = data.presets || [];
      const activeId = data.active_preset_id;
      const sel = panel.querySelector("#designer-preset-select");
      presets.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.label}${p.id === activeId ? " ★" : ""}`;
        sel.appendChild(opt);
      });
    } catch { /* non-critical */ }
  }

  // ── mode switching ──
  panel.querySelectorAll(".designer-mode-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentMode = btn.dataset.mode;
      panel.querySelectorAll(".designer-mode-btn").forEach(b => b.classList.toggle("active", b === btn));
      panel.querySelectorAll(".designer-mode-panel").forEach(p => p.classList.toggle("active", p.dataset.mode === currentMode));
    });
  });

  // ── text mode char counter ──
  panel.querySelector("#designer-text").addEventListener("input", e => {
    panel.querySelector("#text-char-count").textContent = `${e.target.value.length} / 30 000`;
  });

  // ── PDF mode ──
  const fileInput = panel.querySelector("#pdf-file-input");
  const pickBtn = panel.querySelector("#pdf-pick-btn");
  const filenameEl = panel.querySelector("#pdf-filename");
  const extractBtn = panel.querySelector("#pdf-extract-btn");

  pickBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    if (!f) return;
    filenameEl.textContent = f.name;
    extractBtn.disabled = false;
  });

  extractBtn.addEventListener("click", async () => {
    const f = fileInput.files[0];
    if (!f) return;
    extractBtn.disabled = true;
    extractBtn.textContent = LABELS.extracting;
    try {
      const formData = new FormData();
      formData.append("file", f);
      const data = await adminFetch("/api/admin/campaign-designer/extract-pdf", {
        method: "POST",
        body: formData,
      });
      extractedText = data.text || "";
      panel.querySelector("#pdf-extracted-text").value = extractedText;
      panel.querySelector("#pdf-char-count").textContent = `${extractedText.length} znaków (${data.pages ?? "?"} stron)`;
      panel.querySelector("#pdf-truncated-warn").style.display = data.truncated ? "inline" : "none";
      panel.querySelector("#pdf-preview-wrap").style.display = "block";
      showToast("Plik wczytany.", "success");
    } catch (e) {
      showToast(e.message || "Błąd wczytywania pliku.", "error");
    } finally {
      extractBtn.disabled = false;
      extractBtn.textContent = LABELS.extractBtn;
    }
  });

  // ── generate hooks ──
  panel.querySelector("#designer-gen-btn").addEventListener("click", async () => {
    let sourceText = "";
    if (currentMode === "prompt") sourceText = panel.querySelector("#designer-prompt").value.trim();
    else if (currentMode === "text") sourceText = panel.querySelector("#designer-text").value.trim();
    else sourceText = panel.querySelector("#pdf-extracted-text").value.trim();

    if (sourceText.length < 10) {
      showToast("Podaj treść źródłową (min. 10 znaków).", "info");
      return;
    }

    const btn = panel.querySelector("#designer-gen-btn");
    btn.disabled = true;
    btn.textContent = LABELS.generating;
    panel.querySelector("#hooks-preview").style.display = "none";

    try {
      const presetVal = panel.querySelector("#designer-preset-select").value;
      const count = Number(panel.querySelector("#hook-count").value);
      const body = { source_text: sourceText, count };
      if (presetVal) body.preset_id = Number(presetVal);

      const data = await adminFetch("/api/admin/campaign-designer/generate-hooks", {
        method: "POST",
        body: JSON.stringify(body),
      });

      generatedHooks = (data.hooks || []).map((h, i) => ({ ...h, _id: i, _saved: false }));
      renderGeneratedHooks();
      panel.querySelector("#hooks-preview").style.display = "block";
    } catch (e) {
      showToast(e.message || "Błąd generowania.", "error");
    } finally {
      btn.disabled = false;
      btn.textContent = LABELS.generateBtn;
    }
  });

  function renderGeneratedHooks() {
    const list = panel.querySelector("#hooks-list");
    list.innerHTML = generatedHooks.map((h, i) => `
      <div class="hook-card${h._saved ? " hook-saved" : ""}" data-idx="${i}">
        <div class="hook-card-title">
          <input class="hook-title-input" type="text" value="${escHtml(h.title)}" ${h._saved ? "disabled" : ""} />
          ${h._saved
            ? `<span class="badge badge-green" style="font-size:0.68rem">Zapisany</span>`
            : `<button type="button" class="primary-btn hook-save-btn" style="font-size:0.75rem;padding:4px 10px">${LABELS.saveBtn}</button>
               <button type="button" class="secondary-btn hook-discard-btn" style="font-size:0.75rem;padding:4px 8px">${LABELS.discardBtn}</button>`
          }
        </div>
        <div class="hook-card-content">${escHtml(h.content)}</div>
      </div>
    `).join("");

    list.querySelectorAll(".hook-save-btn").forEach(btn => {
      const idx = Number(btn.closest(".hook-card").dataset.idx);
      btn.addEventListener("click", () => saveHook(idx));
    });
    list.querySelectorAll(".hook-discard-btn").forEach(btn => {
      const idx = Number(btn.closest(".hook-card").dataset.idx);
      btn.addEventListener("click", () => {
        generatedHooks[idx]._saved = true;
        generatedHooks[idx]._discarded = true;
        renderGeneratedHooks();
      });
    });
    list.querySelectorAll(".hook-title-input").forEach(input => {
      const idx = Number(input.closest(".hook-card").dataset.idx);
      input.addEventListener("input", e => { generatedHooks[idx].title = e.target.value; });
    });
  }

  async function saveHook(idx) {
    const h = generatedHooks[idx];
    try {
      await adminFetch("/api/admin/campaign-designer/snippets", {
        method: "POST",
        body: JSON.stringify({ snippet_type: "hook", title: h.title, content: h.content }),
      });
      generatedHooks[idx]._saved = true;
      renderGeneratedHooks();
      showToast("Hak zapisany.", "success");
      await loadLibrary();
    } catch (e) {
      showToast(e.message || "Błąd zapisu.", "error");
    }
  }

  // ── save all unsaved ──
  panel.querySelector("#save-all-btn").addEventListener("click", async () => {
    const unsaved = generatedHooks.filter(h => !h._saved && !h._discarded);
    for (const h of unsaved) await saveHook(generatedHooks.indexOf(h));
  });

  // ── library ──
  panel.querySelector("#lib-search").addEventListener("input", e => {
    libSearch = e.target.value.toLowerCase();
    renderLibrary();
  });

  async function loadLibrary() {
    try {
      const data = await adminFetch("/api/admin/campaign-designer/snippets?snippet_type=hook");
      allSnippets = data.items || [];
      renderLibrary();
    } catch (e) {
      panel.querySelector("#lib-grid").innerHTML =
        `<div class="lib-empty" style="color:var(--accent-red)">${e.message}</div>`;
    }
  }

  function renderLibrary() {
    const grid = panel.querySelector("#lib-grid");
    let items = allSnippets;
    if (libSearch) items = items.filter(s =>
      s.title.toLowerCase().includes(libSearch) ||
      (s.content || "").toLowerCase().includes(libSearch)
    );

    if (!items.length) {
      grid.innerHTML = `<div class="lib-empty">${libSearch ? LABELS.noMatch : LABELS.noHooks}</div>`;
      return;
    }

    grid.innerHTML = items.map(s => {
      const date = s.created_at
        ? new Date(s.created_at.replace(" ", "T") + "Z").toLocaleDateString("pl-PL")
        : "";
      const preview = (s.content || "").substring(0, 140);
      return `
        <div class="lib-card" data-id="${s.id}">
          <div class="lib-card-header">
            <span class="badge badge-gold" style="font-size:0.68rem">🎣 Hak</span>
            <span class="lib-card-date">${date}</span>
            <button type="button" class="lib-copy-btn icon-btn" title="${LABELS.copy}">⎘</button>
            <button type="button" class="lib-delete-btn icon-btn lib-delete-icon" title="${LABELS.delete}">✕</button>
          </div>
          <div class="lib-card-body">
            <div class="lib-card-title">${escHtml(s.title)}</div>
            <div class="lib-card-preview">${escHtml(preview)}${s.content.length > 140 ? "…" : ""}</div>
            <div class="lib-card-full" style="display:none">${escHtml(s.content)}</div>
          </div>
        </div>`;
    }).join("");

    grid.querySelectorAll(".lib-card").forEach(card => {
      const id = Number(card.dataset.id);
      const snippet = allSnippets.find(s => s.id === id);

      card.querySelector(".lib-card-body").addEventListener("click", () => {
        const expanded = card.classList.toggle("expanded");
        card.querySelector(".lib-card-preview").style.display = expanded ? "none" : "";
        card.querySelector(".lib-card-full").style.display = expanded ? "" : "none";
      });

      card.querySelector(".lib-copy-btn").addEventListener("click", e => {
        e.stopPropagation();
        navigator.clipboard.writeText(snippet.content).then(() => showToast("Skopiowano.", "success"));
      });

      card.querySelector(".lib-delete-btn").addEventListener("click", async e => {
        e.stopPropagation();
        if (!confirm(LABELS.confirmDelete)) return;
        try {
          await adminFetch(`/api/admin/campaign-designer/snippets/${id}`, { method: "DELETE" });
          allSnippets = allSnippets.filter(s => s.id !== id);
          renderLibrary();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  }

  await Promise.all([loadPresets(), loadLibrary()]);
}

function escHtml(str) {
  return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
