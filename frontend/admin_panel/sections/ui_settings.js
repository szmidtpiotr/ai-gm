import { adminFetch } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";

const PANELS = [
  { id: "stats", label: "Statystyki" },
  { id: "skills", label: "Umiejętności" },
  { id: "identity", label: "Postać" },
  { id: "inventory", label: "Ekwipunek" },
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
  const intro = el("p", "admin-note muted");
  intro.textContent =
    "Domyślne stany zwinięcia sekcji w panelu karty postaci (gracz). Stosowane, gdy w przeglądarce nie ma wpisu localStorage dla danej sekcji.";
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
  host.appendChild(root);

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
