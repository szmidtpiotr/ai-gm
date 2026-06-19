/* Tools section — combines Combat Sandbox + Rest Sandbox + Debug under one tab */

const TABS = [
    { key: 'sandbox', label: '⚔ Combat',  module: '/admin_panel_v2/sections/sandbox.js?v=16' },
    { key: 'rest',    label: '💤 Rest',    module: '/admin_panel_v2/sections/rest_sandbox.js?v=1' },
    { key: 'debug',   label: '🐛 Debug',   module: '/admin_panel_v2/sections/debug.js?v=1' },
];

export async function init(panel) {
    panel.innerHTML = `
        <div class="system-tabs">
            ${TABS.map((t, i) => `
                <button type="button" class="system-tab ${i === 0 ? 'system-tab--active' : ''}" data-sys-tab="${t.key}">${t.label}</button>
            `).join('')}
        </div>
        ${TABS.map((t, i) => `
            <div class="system-tab-panel ${i === 0 ? 'system-tab-panel--active' : ''}" data-sys-panel="${t.key}"></div>
        `).join('')}
    `;

    const loaded = new Set();

    async function loadTab(key) {
        if (loaded.has(key)) return;
        const cfg = TABS.find(t => t.key === key);
        if (!cfg) return;
        const sub = panel.querySelector(`[data-sys-panel="${key}"]`);
        if (!sub) return;
        try {
            const { init: subInit } = await import(cfg.module);
            await subInit(sub);
            loaded.add(key);
        } catch (err) {
            sub.innerHTML = `<div style="padding:24px;color:var(--danger,#c94a4a)">Błąd ładowania: ${err.message}</div>`;
            console.error('[tools] failed to load', key, err);
        }
    }

    panel.querySelectorAll('.system-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.sysTab;
            panel.querySelectorAll('.system-tab').forEach(b => b.classList.toggle('system-tab--active', b === btn));
            panel.querySelectorAll('.system-tab-panel').forEach(p => p.classList.toggle('system-tab-panel--active', p.dataset.sysPanel === key));
            loadTab(key);
        });
    });

    await loadTab(TABS[0].key);
}
