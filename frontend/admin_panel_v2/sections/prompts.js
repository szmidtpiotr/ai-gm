import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  system_prompt:          { label: "System Prompt",       icon: "🧠", desc: "Główny kontrakt mechanik gry dla LLM" },
  history_summary_prompt: { label: "Podsumowanie historii", icon: "📖", desc: "Prompt do skracania historii sesji" },
  memory_qa_prompt:       { label: "Pamięć QA",            icon: "🔍", desc: "Prompt do pytań i odpowiedzi z pamięci" },
  "helpme-gm":            { label: "Doradca GM",           icon: "💡", desc: "Prompt OOC dla trybu helpme" },
};

let _prompts      = [];
let _activeName   = null;
let _origContent  = "";
let _dirty        = false;

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content prompts-layout">
      <nav class="prompts-nav" id="prompts-nav">
        <div class="prompts-nav-loading">Ładowanie…</div>
      </nav>
      <div class="prompts-editor-wrap" id="prompts-editor-wrap">
        <div class="prompts-placeholder">
          <div style="font-size:2rem">📜</div>
          <p style="color:var(--text-muted);margin-top:8px">Wybierz prompt z listy po lewej.</p>
        </div>
      </div>
    </div>`;

  _prompts    = [];
  _activeName = null;
  _origContent = "";
  _dirty      = false;

  await _loadList(panel);
}

async function _loadList(panel) {
  const nav = panel.querySelector("#prompts-nav");
  try {
    const data = await adminFetch("/api/admin/prompts");
    _prompts = data.items || [];
  } catch (e) {
    nav.innerHTML = `<p style="color:var(--accent-red);padding:12px">Błąd: ${_esc(e.message)}</p>`;
    return;
  }
  _renderNav(panel);
}

function _renderNav(panel) {
  const nav = panel.querySelector("#prompts-nav");
  nav.innerHTML = "";
  _prompts.forEach((p) => {
    const meta = LABELS[p.name] || { label: p.name, icon: "📄", desc: "" };
    const btn = document.createElement("button");
    btn.className = "prompt-nav-btn" + (p.name === _activeName ? " active" : "");
    btn.dataset.name = p.name;
    btn.innerHTML = `
      <span class="prompt-nav-icon">${meta.icon}</span>
      <span class="prompt-nav-info">
        <span class="prompt-nav-label">${_esc(meta.label)}</span>
        <span class="prompt-nav-size">${_formatSize(p.size_bytes)}</span>
      </span>`;
    btn.addEventListener("click", () => _openPrompt(panel, p.name));
    nav.appendChild(btn);
  });
}

async function _openPrompt(panel, name) {
  if (_dirty) {
    const leave = confirm("Masz niezapisane zmiany. Opuścić bez zapisywania?");
    if (!leave) return;
  }
  _activeName  = name;
  _dirty       = false;
  _origContent = "";
  _renderNav(panel);

  const wrap = panel.querySelector("#prompts-editor-wrap");
  wrap.innerHTML = `<div class="prompts-loading">Ładowanie…</div>`;

  let data;
  try {
    data = await adminFetch(`/api/admin/prompts/${name}`);
  } catch (e) {
    wrap.innerHTML = `<p style="color:var(--accent-red);padding:16px">Błąd ładowania: ${_esc(e.message)}</p>`;
    return;
  }

  _origContent = data.content ?? "";
  _dirty = false;
  _renderEditor(panel, data);
}

function _renderEditor(panel, data) {
  const meta = LABELS[data.name] || { label: data.name, icon: "📄", desc: "" };
  const wrap = panel.querySelector("#prompts-editor-wrap");
  const modified = data.last_modified
    ? new Date(data.last_modified).toLocaleString("pl-PL")
    : "—";

  wrap.innerHTML = `
    <div class="prompts-editor">
      <div class="prompts-editor-header">
        <div class="prompts-editor-title">
          <span class="prompts-editor-icon">${meta.icon}</span>
          <div>
            <div class="prompts-editor-name">${_esc(meta.label)}</div>
            <div class="prompts-editor-meta">
              Plik: <code>${_esc(data.filename)}</code> &nbsp;·&nbsp;
              Zmieniono: ${modified} &nbsp;·&nbsp;
              ${data.has_backup ? '<span class="has-backup">✓ Backup dostępny</span>' : '<span style="color:var(--text-muted)">Brak backupu</span>'}
            </div>
          </div>
        </div>
        <div class="prompts-editor-actions">
          ${data.has_backup ? `<button class="secondary-btn" id="restore-btn">↩ Przywróć backup</button>` : ""}
          <button class="primary-btn" id="save-btn" disabled>Zapisz</button>
        </div>
      </div>

      <div class="prompts-char-bar">
        <span id="char-count">${data.content?.length ?? 0}</span> znaków
        &nbsp;·&nbsp;
        <span id="line-count">${(data.content?.split("\n") ?? []).length}</span> linii
        <span id="dirty-badge" style="display:none;margin-left:8px;color:var(--accent-gold)">● Niezapisane zmiany</span>
      </div>

      <textarea
        id="prompt-textarea"
        class="prompt-textarea"
        spellcheck="false"
        autocomplete="off"
      >${_escTextarea(data.content ?? "")}</textarea>

      <div class="prompts-diff-wrap" id="diff-wrap" style="display:none">
        <div class="prompts-diff-header">
          <span>Podgląd zmian</span>
          <button class="secondary-btn small-btn" id="diff-close-btn">Ukryj</button>
        </div>
        <div class="prompts-diff" id="diff-output"></div>
      </div>
    </div>`;

  const textarea  = wrap.querySelector("#prompt-textarea");
  const saveBtn   = wrap.querySelector("#save-btn");
  const charCount = wrap.querySelector("#char-count");
  const lineCount = wrap.querySelector("#line-count");
  const dirtyBadge = wrap.querySelector("#dirty-badge");
  const diffWrap  = wrap.querySelector("#diff-wrap");
  const diffOut   = wrap.querySelector("#diff-output");
  const diffClose = wrap.querySelector("#diff-close-btn");
  const restoreBtn = wrap.querySelector("#restore-btn");

  textarea.addEventListener("input", () => {
    const val = textarea.value;
    charCount.textContent = val.length;
    lineCount.textContent = val.split("\n").length;
    const changed = val !== _origContent;
    _dirty = changed;
    saveBtn.disabled = !changed;
    dirtyBadge.style.display = changed ? "" : "none";
    if (changed) {
      _renderDiff(diffOut, _origContent, val);
      diffWrap.style.display = "";
    } else {
      diffWrap.style.display = "none";
    }
  });

  diffClose?.addEventListener("click", () => { diffWrap.style.display = "none"; });

  saveBtn.addEventListener("click", async () => {
    const content = textarea.value;
    saveBtn.disabled = true;
    saveBtn.textContent = "Zapisuję…";
    try {
      await adminFetch(`/api/admin/prompts/${_activeName}`, {
        method: "PUT",
        body: JSON.stringify({ content }),
      });
      _origContent = content;
      _dirty = false;
      dirtyBadge.style.display = "none";
      diffWrap.style.display = "none";
      showToast("Prompt zapisany.", "success");
      await _loadList(panel);
      _renderNav(panel);
    } catch (e) {
      showToast("Błąd zapisu: " + (e.message || "?"), "error");
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Zapisz";
    }
  });

  restoreBtn?.addEventListener("click", async () => {
    const ok = confirm("Przywrócić prompt z backupu? Bieżąca wersja zostanie nadpisana.");
    if (!ok) return;
    restoreBtn.disabled = true;
    try {
      await adminFetch(`/api/admin/prompts/${_activeName}`, {
        method: "PUT",
        body: JSON.stringify({ restore_from_backup: true }),
      });
      showToast("Przywrócono z backupu.", "success");
      _dirty = false;
      await _openPrompt(panel, _activeName);
    } catch (e) {
      showToast("Błąd przywracania: " + (e.message || "?"), "error");
      restoreBtn.disabled = false;
    }
  });
}

// ── Simple line diff ──────────────────────────────────────────────────────────

function _renderDiff(container, original, current) {
  const oldLines = original.split("\n");
  const newLines = current.split("\n");
  const lcs = _lcsLines(oldLines, newLines);

  let html = "";
  let oi = 0, ni = 0, li = 0;
  while (oi < oldLines.length || ni < newLines.length) {
    if (li < lcs.length && oi === lcs[li][0] && ni === lcs[li][1]) {
      html += `<div class="diff-line diff-ctx">${_esc(oldLines[oi])}</div>`;
      oi++; ni++; li++;
    } else if (oi < oldLines.length && (li >= lcs.length || oi < lcs[li][0])) {
      html += `<div class="diff-line diff-del">- ${_esc(oldLines[oi])}</div>`;
      oi++;
    } else {
      html += `<div class="diff-line diff-add">+ ${_esc(newLines[ni])}</div>`;
      ni++;
    }
  }
  container.innerHTML = html || "<em>Brak zmian</em>";
}

function _lcsLines(a, b) {
  const MAX = 400;
  if (a.length > MAX || b.length > MAX) return [];
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);

  const result = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) { result.push([i, j]); i++; j++; }
    else if (dp[i+1][j] >= dp[i][j+1]) i++;
    else j++;
  }
  return result;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function _escTextarea(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function _formatSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}
