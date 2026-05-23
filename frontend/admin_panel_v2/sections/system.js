/* System section — single "Konfiguracja" view with accordion sections:
   LLM/Server admin (top, default open) + Wygląd + Głos + Email/SMTP. */

const SECTIONS = [
    { key: 'llm',    label: '⚙ Konfiguracja serwera',  module: '/admin_panel_v2/sections/system_llm.js?v=stage11-resurrect-global', open: true },
    { key: 'visual', label: '🎨 Wygląd gry',           module: '/admin_panel_v2/sections/visual.js?v=2',  open: false },
    { key: 'voice',  label: '🔊 Głos (TTS / STT)',     module: '/admin_panel_v2/sections/voice.js?v=1',   open: false },
    { key: 'email',  label: '📨 Email / SMTP',         module: '/admin_panel_v2/sections/email.js?v=1',   open: false },
];

export async function init(panel) {
    panel.innerHTML = `
        <div class="sys-accordion">
            ${SECTIONS.map(s => `
                <section class="sys-acc-item ${s.open ? 'sys-acc-item--open' : ''}" data-sys-key="${s.key}">
                    <button type="button" class="sys-acc-header">
                        <span class="sys-acc-label">${s.label}</span>
                        <svg class="sys-acc-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"/>
                        </svg>
                    </button>
                    <div class="sys-acc-body">
                        <div class="sys-acc-content" data-sys-content="${s.key}"></div>
                    </div>
                </section>
            `).join('')}
        </div>
    `;

    const loaded = new Set();

    async function loadSection(key) {
        if (loaded.has(key)) return;
        const cfg = SECTIONS.find(s => s.key === key);
        if (!cfg) return;
        const container = panel.querySelector(`[data-sys-content="${key}"]`);
        if (!container) return;
        try {
            const { init: subInit } = await import(cfg.module);
            await subInit(container);
            loaded.add(key);
        } catch (err) {
            container.innerHTML = `<div style="padding:24px;color:var(--danger,#c94a4a)">Błąd ładowania: ${err.message}</div>`;
            console.error('[system] failed to load', key, err);
        }
    }

    // Accordion expand/collapse — load section on first open
    panel.querySelectorAll('.sys-acc-item').forEach(item => {
        const header = item.querySelector('.sys-acc-header');
        const key = item.dataset.sysKey;
        header.addEventListener('click', async () => {
            const willOpen = !item.classList.contains('sys-acc-item--open');
            item.classList.toggle('sys-acc-item--open', willOpen);
            if (willOpen) await loadSection(key);
        });
    });

    // Eagerly load the first (default-open) section
    const firstOpen = SECTIONS.find(s => s.open);
    if (firstOpen) await loadSection(firstOpen.key);
}
