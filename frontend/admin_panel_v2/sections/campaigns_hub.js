import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const TABS = [
  { key: "monitor",  label: "🗺 Monitor",    module: "/admin_panel_v2/sections/campaigns.js?v=6-bug03" },
  { key: "settings", label: "⚙ Ustawienia", module: "/admin_panel_v2/sections/campaigns_settings.js?v=1" },
];

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content">
      <div class="subtab-bar">
        ${TABS.map((t, i) =>
          `<button class="subtab-btn${i === 0 ? " active" : ""}" data-tab="${t.key}">${t.label}</button>`
        ).join("")}
      </div>
      <div class="subtab-panels" style="flex:1;min-height:0;overflow:hidden">
        ${TABS.map((t, i) =>
          `<div class="subtab-panel${i === 0 ? " active" : ""}" data-tab="${t.key}" style="height:100%;overflow:auto"></div>`
        ).join("")}
      </div>
    </div>`;

  const initialized = new Set();

  const activateTab = async (key) => {
    if (initialized.has(key)) return;
    initialized.add(key);
    const tab    = TABS.find(t => t.key === key);
    const target = panel.querySelector(`.subtab-panel[data-tab="${key}"]`);
    if (!tab || !target) return;
    try {
      const mod = await import(tab.module);
      await mod.init(target);
    } catch (e) {
      target.innerHTML = `<p style="color:var(--accent-red);padding:20px">Błąd ładowania: ${e.message}</p>`;
    }
  };

  panel.querySelectorAll(".subtab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      panel.querySelectorAll(".subtab-btn").forEach(b => b.classList.remove("active"));
      panel.querySelectorAll(".subtab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      panel.querySelector(`.subtab-panel[data-tab="${btn.dataset.tab}"]`).classList.add("active");
      void activateTab(btn.dataset.tab);
    });
  });

  await activateTab("monitor");
}
