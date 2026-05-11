import { adminFetch } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";

const PANELS = [
  { id: "stats", label: "Statystyki" },
  { id: "skills", label: "Umiejętności" },
  { id: "identity", label: "Postać" },
  { id: "inventory", label: "Ekwipunek" },
];

const BG_SCREENS = [
  { id: "login",        label: "Ekran logowania",   desc: "Strona startowa przed zalogowaniem" },
  { id: "campaigns",   label: "Lista kampanii",     desc: "Po zalogowaniu — wybór kampanii" },
  { id: "new-campaign",label: "Nowa kampania",      desc: "Formularz: nazwa, setting, opis kampanii" },
  { id: "wizard",      label: "Kreator postaci",    desc: "4 kroki: imię/archetyp → statystyki (rzut) → umiejętności → wygląd/osobowość (LLM)" },
  { id: "game",        label: "Ekran gry",          desc: "Główny ekran czatu / rozgrywki" },
];

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

export async function init(host) {
  host.innerHTML = "";
  const root = el("div", "admin-subpanel-inner ui-settings-root");

  // ── Section 1: Panel fold defaults ─────────────────────────────────────────
  const panelTitle = el("h3", "admin-section-title", "Domyślne stany sekcji karty postaci");
  root.appendChild(panelTitle);

  const intro = el("p", "admin-note muted");
  intro.textContent =
    "Stosowane, gdy w przeglądarce nie ma wpisu localStorage dla danej sekcji.";
  root.appendChild(intro);

  const form = el("div", "ui-settings-form");
  const state = { radios: {} };

  PANELS.forEach(({ id, label }) => {
    const row = el("div", "ui-settings-row");
    row.appendChild(el("span", "ui-settings-label", label));

    const expanded = el("label", "ui-settings-choice");
    const rExp = el("input", "");
    rExp.type = "radio";
    rExp.name = `ui-panel-${id}`;
    rExp.value = "expanded";
    expanded.appendChild(rExp);
    expanded.appendChild(document.createTextNode(" Rozwinięta"));

    const collapsed = el("label", "ui-settings-choice");
    const rCol = el("input", "");
    rCol.type = "radio";
    rCol.name = `ui-panel-${id}`;
    rCol.value = "collapsed";
    collapsed.appendChild(rCol);
    collapsed.appendChild(document.createTextNode(" Zwinięta"));

    row.appendChild(expanded);
    row.appendChild(collapsed);
    form.appendChild(row);
    state.radios[id] = { expanded: rExp, collapsed: rCol };
  });

  const saveBtn = el("button", "primary-btn", "Zapisz ustawienia");
  saveBtn.type = "button";
  form.appendChild(saveBtn);
  root.appendChild(form);

  // ── Section 2: Background images ───────────────────────────────────────────
  const divider = el("hr", "admin-divider");
  root.appendChild(divider);

  const bgTitle = el("h3", "admin-section-title", "Tła ekranów (Mobile Frontend)");
  root.appendChild(bgTitle);

  const bgNote = el("p", "admin-note muted");
  bgNote.textContent =
    "Wgraj własny obraz (JPG/PNG/WEBP, maks. 10 MB) dla każdego ekranu. Obraz zastępuje domyślne tło. Usuń, aby przywrócić domyślne.";
  root.appendChild(bgNote);

  const bgGrid = el("div", "ui-bg-grid");

  // Load existing backgrounds
  let currentBgs = {};
  try {
    const d = await fetch("/api/ui/backgrounds").then(r => r.json());
    currentBgs = d.backgrounds || {};
  } catch (_e) {}

  BG_SCREENS.forEach(({ id, label, desc }) => {
    const card = el("div", "ui-bg-card");

    const cardLabel = el("div", "ui-bg-card__label", label);
    card.appendChild(cardLabel);
    if (desc) {
      const cardDesc = el("div", "ui-bg-card__desc", desc);
      card.appendChild(cardDesc);
    }

    // Preview
    const preview = el("div", "ui-bg-card__preview");
    preview.id = `bg-preview-${id}`;
    if (currentBgs[id]) {
      preview.style.backgroundImage = `url("${currentBgs[id]}?t=${Date.now()}")`;
      preview.classList.add("ui-bg-card__preview--loaded");
    } else {
      preview.textContent = "brak (domyślne)";
    }
    card.appendChild(preview);

    // Status
    const status = el("div", "ui-bg-card__status");
    status.id = `bg-status-${id}`;
    status.textContent = currentBgs[id] ? "Niestandardowe tło aktywne" : "Domyślne tło";
    status.className = `ui-bg-card__status ${currentBgs[id] ? "ui-bg-card__status--custom" : "ui-bg-card__status--default"}`;
    card.appendChild(status);

    // Upload input
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp";
    fileInput.style.display = "none";
    fileInput.id = `bg-file-${id}`;
    card.appendChild(fileInput);

    // Buttons row
    const btnRow = el("div", "ui-bg-card__btns");

    const uploadBtn = el("button", "primary-btn ui-bg-card__upload-btn", "Wgraj obraz");
    uploadBtn.type = "button";
    uploadBtn.addEventListener("click", () => fileInput.click());
    btnRow.appendChild(uploadBtn);

    const deleteBtn = el("button", "danger-btn ui-bg-card__delete-btn", "Usuń");
    deleteBtn.type = "button";
    deleteBtn.style.display = currentBgs[id] ? "" : "none";
    deleteBtn.id = `bg-delete-${id}`;
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Usunąć niestandardowe tło dla "${label}"?`)) return;
      try {
        await adminFetch(`/api/admin/ui/bg/${id}`, { method: "DELETE" });
        preview.style.backgroundImage = "";
        preview.classList.remove("ui-bg-card__preview--loaded");
        preview.textContent = "brak (domyślne)";
        status.textContent = "Domyślne tło";
        status.className = "ui-bg-card__status ui-bg-card__status--default";
        deleteBtn.style.display = "none";
        showToast(`Przywrócono domyślne tło: ${label}`, "success");
      } catch (e) {
        showToast(e.message || "Nie udało się usunąć tła.", "error");
      }
    });
    btnRow.appendChild(deleteBtn);
    card.appendChild(btnRow);

    // Progress indicator
    const progress = el("div", "ui-bg-card__progress");
    progress.style.display = "none";
    progress.textContent = "Wgrywanie...";
    card.appendChild(progress);

    // File change handler
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files[0];
      if (!file) return;
      progress.style.display = "";
      uploadBtn.disabled = true;
      try {
        const token = localStorage.getItem("aigm_admin_token") || "";
        const formData = new FormData();
        formData.append("file", file);
        const resp = await fetch(`/api/admin/ui/bg/${id}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);

        const url = `${data.url}?t=${Date.now()}`;
        preview.style.backgroundImage = `url("${url}")`;
        preview.classList.add("ui-bg-card__preview--loaded");
        preview.textContent = "";
        status.textContent = "Niestandardowe tło aktywne";
        status.className = "ui-bg-card__status ui-bg-card__status--custom";
        deleteBtn.style.display = "";
        showToast(`Zaktualizowano tło: ${label}`, "success");
      } catch (e) {
        showToast(e.message || "Błąd wgrywania pliku.", "error");
      } finally {
        progress.style.display = "none";
        uploadBtn.disabled = false;
        fileInput.value = "";
      }
    });

    bgGrid.appendChild(card);
  });

  root.appendChild(bgGrid);
  host.appendChild(root);

  // ── Load panel fold defaults ────────────────────────────────────────────────
  async function load() {
    try {
      const data = await adminFetch("/api/settings/ui");
      const panels = (data && data.data && data.data.panels) || {};
      PANELS.forEach(({ id }) => {
        const v = panels[id] === "collapsed" ? "collapsed" : "expanded";
        const { expanded, collapsed } = state.radios[id];
        if (v === "collapsed") {
          collapsed.checked = true;
        } else {
          expanded.checked = true;
        }
      });
    } catch (e) {
      showToast(e.message || "Nie udało się wczytać ustawień UI.", "error");
    }
  }

  saveBtn.addEventListener("click", async () => {
    const panels = {};
    PANELS.forEach(({ id }) => {
      const { expanded, collapsed } = state.radios[id];
      panels[id] = collapsed.checked ? "collapsed" : "expanded";
    });
    try {
      await adminFetch("/api/settings/ui", {
        method: "PATCH",
        body: JSON.stringify({ panels }),
      });
      showToast("Zapisano ustawienia UI.", "success");
      await load();
    } catch (e) {
      showToast(e.message || "Zapis nie powiódł się.", "error");
    }
  });

  await load();
}
