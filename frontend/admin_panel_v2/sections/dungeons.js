/* Dungeons section — top-level sidebar entry that hosts
   the Lochy + Zagadki tabs (moved out of Świat). */

const TABS = [
    { key: "dungeons", label: "⚔ Lochy",    module: "/admin_panel_v2/sections/world.js?v=36", fn: "_renderDungeons" },
    { key: "riddles",  label: "🔮 Zagadki", module: "/admin_panel_v2/sections/world.js?v=36", fn: "_renderRiddles"  },
];

export async function init(panel) {
    panel.innerHTML = `
        <div class="system-tabs">
            ${TABS.map((t, i) => `
                <button type="button" class="system-tab ${i === 0 ? 'system-tab--active' : ''}" data-dng-tab="${t.key}">${t.label}</button>
            `).join('')}
        </div>
        ${TABS.map((t, i) => `
            <div class="system-tab-panel ${i === 0 ? 'system-tab-panel--active' : ''}" data-dng-panel="${t.key}"></div>
        `).join('')}
    `;

    const loaded = new Set();

    async function loadTab(key) {
        if (loaded.has(key)) return;
        const cfg = TABS.find(t => t.key === key);
        if (!cfg) return;
        const sub = panel.querySelector(`[data-dng-panel="${key}"]`);
        if (!sub) return;
        try {
            const mod = await import(cfg.module);
            const renderFn = mod[cfg.fn];
            if (typeof renderFn !== "function") {
                throw new Error(`${cfg.fn} not exported from ${cfg.module}`);
            }
            await renderFn(sub);
            loaded.add(key);
        } catch (err) {
            sub.innerHTML = `<div style="padding:24px;color:var(--danger,#c94a4a)">Błąd ładowania: ${err.message}</div>`;
            console.error('[dungeons] failed to load', key, err);
        }
    }

    panel.querySelectorAll('.system-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.dngTab;
            panel.querySelectorAll('.system-tab').forEach(b => b.classList.toggle('system-tab--active', b === btn));
            panel.querySelectorAll('.system-tab-panel').forEach(p => p.classList.toggle('system-tab-panel--active', p.dataset.dngPanel === key));
            loadTab(key);
        });
    });

    await loadTab(TABS[0].key);
}
