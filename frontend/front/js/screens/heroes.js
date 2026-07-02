// ============================================================================
// Heroes (character-first flow — Task 42)
// ============================================================================
let currentHero = null;

async function loadHeroes() {
    if (!currentUser?.id) return;
    try {
        // Stage 6 H1: use the enriched /heroes endpoint.
        const response = await apiRequest('GET', `/heroes?user_id=${currentUser.id}`);
        const heroes = response.heroes || [];
        renderHeroes(heroes);
    } catch (error) {
        console.error('[Heroes] Failed to load:', error);
        showToast('Nie udało się załadować bohaterów', 'error');
    }
}

// Stage 6 H3: status chip mapping (label + CSS modifier class).
const HERO_STATUS_META = {
    idle:         { label: 'Wolny',      cls: 'hero-status--idle' },
    in_campaign:  { label: 'W kampanii', cls: 'hero-status--campaign' },
    in_dungeon:   { label: 'W lochu',    cls: 'hero-status--dungeon' },
};

// Human-friendly relative time: <1h → "Dzisiaj", <1d → "Wczoraj", <7d → "X dni temu", else date.
function _relativeTimePL(iso) {
    if (!iso) return '';
    const t = new Date(iso.replace(' ', 'T') + (iso.includes('Z') ? '' : 'Z'));
    if (isNaN(t)) return '';
    const diffMs = Date.now() - t.getTime();
    const dayMs = 86_400_000;
    if (diffMs < 60_000) return 'przed chwilą';
    if (diffMs < dayMs) return 'dzisiaj';
    if (diffMs < 2 * dayMs) return 'wczoraj';
    if (diffMs < 7 * dayMs) return `${Math.floor(diffMs / dayMs)} dni temu`;
    return t.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

function renderHeroes(heroes) {
    const list = elements.heroesList;
    const empty = elements.heroesEmpty;
    if (!list) return;
    list.innerHTML = '';

    if (heroes.length === 0) {
        if (empty) empty.style.display = '';
        return;
    }
    if (empty) empty.style.display = 'none';

    // Sort: in_campaign first, then in_dungeon, then idle. Newest within each group.
    const sortRank = { in_campaign: 0, in_dungeon: 1, idle: 2 };
    const sorted = [...heroes].sort((a, b) => {
        const ra = sortRank[a.hero_status || a.status || 'idle'] ?? 9;
        const rb = sortRank[b.hero_status || b.status || 'idle'] ?? 9;
        if (ra !== rb) return ra - rb;
        return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    });

    sorted.forEach(hero => {
        const sheet = hero.sheet_json || {};
        const archetype = sheet.archetype || hero.system_id || '?';
        const level = (sheet.xp_lifetime_earned != null)
            ? Math.min(10, Math.floor(Number(sheet.xp_lifetime_earned) / 100) + 1)
            : (sheet.level || 1);
        const hp = sheet.current_hp ?? sheet.max_hp ?? '?';
        const maxHp = sheet.max_hp ?? '?';
        const status = hero.hero_status || hero.status || 'idle';
        const statusMeta = HERO_STATUS_META[status] || HERO_STATUS_META.idle;
        const campaignTitle = hero.campaign_title || '';
        const completed = Number(hero.campaigns_completed ?? 0);
        const xpLifetime = Number(hero.total_xp_lifetime ?? 0);
        const xpAvail = Number(sheet.xp_available || 0);
        const lastSeen = _relativeTimePL(hero.last_activity_at);

        const wrapper = document.createElement('div');
        wrapper.className = 'hero-card-wrapper';

        const card = document.createElement('div');
        card.className = 'hero-card';
        card.dataset.heroId = String(hero.id);
        card.innerHTML = `
            <div class="hero-card__main">
              <div class="hero-card__icon">⚔</div>
              <div class="hero-card__body">
                <div class="hero-card__title-row">
                  <h3 class="hero-card__name">${_esc(hero.name)}</h3>
                  <span class="hero-status-chip ${statusMeta.cls}">${_esc(statusMeta.label)}</span>
                </div>
                <p class="hero-card__sub">${_esc(archetype)} · Poz. ${level} · ${hp}/${maxHp} HP${lastSeen ? ` · <span class="hero-card__lastseen">${_esc(lastSeen)}</span>` : ''}</p>
                ${campaignTitle ? `<p class="hero-card__campaign">📖 ${_esc(campaignTitle)}</p>` : ''}
                <div class="hero-card__trophy">
                  <span title="Zakończone przygody">⚔ ${completed}</span>
                  <span title="Łączna ilość zdobytych PD">🏆 ${xpLifetime} PD</span>
                  <button type="button" class="hero-card__history-btn" data-hero-id="${hero.id}" title="Historia bohatera">📜 Historia</button>
                  <button type="button" class="hero-card__chronicle-btn" data-hero-id="${hero.id}" title="Kronika bohatera — legenda i rozdziały">📖 Kronika</button>
                  ${status === 'idle' && xpAvail > 0 ? `<button type="button" class="hero-card__awansuj-btn" data-hero-id="${hero.id}" title="Wydaj PD na rozwój">⬆ Awansuj (${xpAvail} PD)</button>` : ''}
                </div>
              </div>
            </div>
        `;
        card.addEventListener('click', (e) => {
            // Don't trigger card-select when clicking the inline buttons.
            if (e.target.closest('.hero-card__history-btn, .hero-card__awansuj-btn, .hero-card__chronicle-btn')) return;
            selectHero(hero);
        });

        // Inline button wiring
        card.querySelector('.hero-card__history-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            openHeroHistoryModal(hero);
        });
        card.querySelector('.hero-card__chronicle-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            openHeroChronicleModal(hero);
        });
        card.querySelector('.hero-card__awansuj-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            // Open the existing Awansuj panel — works on idle heroes (no campaign required).
            currentHero = hero;
            characterData = hero;
            openAwansujPanel(hero, sheet);
        });

        const delBtn = document.createElement('button');
        delBtn.className = 'hero-card__delete';
        delBtn.title = 'Usuń bohatera';
        delBtn.textContent = '🗑';
        delBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const confirmed = await showDeleteHeroModal(hero.name);
            if (!confirmed) return;
            try {
                await apiRequest('DELETE', `/characters/${hero.id}?user_id=${currentUser.id}`);
                showToast('Bohater i powiązane kampanie usunięte', 'success');
                await loadHeroes();
            } catch (err) {
                showToast(err.message || 'Błąd usuwania', 'error');
            }
        });

        wrapper.appendChild(card);
        wrapper.appendChild(delBtn);
        list.appendChild(wrapper);
    });
}

// Stage 6 H4: Hero history modal — past campaigns with outcome / XP / turns / date.
async function openHeroHistoryModal(hero) {
    let modal = document.getElementById('hero-history-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'hero-history-modal';
        modal.className = 'hero-history-modal';
        modal.innerHTML = `
          <div class="hero-history-modal__backdrop" data-action="close"></div>
          <div class="hero-history-modal__card">
            <header class="hero-history-modal__header">
              <h3 id="hero-history-modal-title">Historia</h3>
              <button type="button" class="hero-history-modal__close" data-action="close" aria-label="Zamknij">✕</button>
            </header>
            <div class="hero-history-modal__body" id="hero-history-modal-body">
              <p class="hero-history-modal__loading">Wczytywanie…</p>
            </div>
          </div>`;
        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target.dataset.action === 'close') {
                modal.classList.remove('hero-history-modal--open');
            }
        });
    }
    const title = document.getElementById('hero-history-modal-title');
    const body  = document.getElementById('hero-history-modal-body');
    if (title) title.textContent = `📜 ${hero.name} — historia`;
    if (body) body.innerHTML = `<p class="hero-history-modal__loading">Wczytywanie…</p>`;
    modal.classList.add('hero-history-modal--open');

    try {
        const r = await apiRequest('GET', `/characters/${hero.id}/history`);
        const rows = r.history || [];
        if (!body) return;
        if (!rows.length) {
            const isFirstActive = (hero.hero_status || hero.status) === 'in_campaign';
            body.innerHTML = `<p class="hero-history-modal__empty">${isFirstActive
                ? 'Aktualna przygoda jest pierwszą — historia zapełni się po jej zakończeniu.'
                : 'Ten bohater jeszcze nie skończył żadnej przygody.'}</p>`;
            return;
        }
        const outcomeIcon = { victory: '🏆', death: '💀', abandoned: '🚪' };
        const outcomeLabel = { victory: 'Zwycięstwo', death: 'Śmierć', abandoned: 'Porzucono' };
        body.innerHTML = `<ul class="hero-history-list">` + rows.map(h => {
            const icon  = outcomeIcon[h.outcome] || '•';
            const lbl   = outcomeLabel[h.outcome] || h.outcome || '—';
            const title = h.campaign_title || `Kampania #${h.campaign_id}`;
            const when  = _relativeTimePL(h.completed_at || h.created_at) || '—';
            return `
              <li class="hero-history-row hero-history-row--${_esc(h.outcome)}">
                <span class="hero-history-row__icon">${icon}</span>
                <div class="hero-history-row__main">
                  <div class="hero-history-row__title">${_esc(title)}</div>
                  <div class="hero-history-row__meta">${_esc(lbl)} · ${h.xp_earned ?? 0} PD · ${h.turns_count ?? 0} tur · ${_esc(when)}</div>
                  ${h.chapter_summary ? `<div class="hero-history-row__summary">${_esc(h.chapter_summary)}</div>` : ''}
                </div>
              </li>`;
        }).join('') + `</ul>`;
    } catch (err) {
        if (body) body.innerHTML = `<p class="hero-history-modal__empty">Nie udało się wczytać historii: ${_esc(err.message || err)}</p>`;
    }
}

async function selectHero(hero) {
    currentHero = hero;
    // Always show campaigns chooser — let player decide (dungeon, new campaign, etc.)
    if (elements.welcomeUser) {
        elements.welcomeUser.textContent = `Bohater: ${hero.name}`;
    }
    // Save hero to session so F5 restores context
    try { localStorage.setItem('aigm_hero_id', hero.id); localStorage.removeItem('aigm_campaign_id'); } catch {}
    await loadCampaigns();
    showScreen('campaigns');
}

// #1098 — Hero Chronicle modal: LEGENDA + rozdziały + blizny porzuceń (read-only).
async function openHeroChronicleModal(hero) {
    let modal = document.getElementById('hero-chronicle-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'hero-chronicle-modal';
        modal.className = 'hero-history-modal';
        modal.innerHTML = `
          <div class="hero-history-modal__backdrop" data-action="close"></div>
          <div class="hero-history-modal__card hero-chronicle-modal__card">
            <header class="hero-history-modal__header">
              <h3 id="hero-chronicle-modal-title">Kronika</h3>
              <button type="button" class="hero-history-modal__close" data-action="close" aria-label="Zamknij">✕</button>
            </header>
            <div class="hero-history-modal__body" id="hero-chronicle-modal-body">
              <p class="hero-history-modal__loading">Wczytywanie…</p>
            </div>
          </div>`;
        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target.dataset.action === 'close') {
                modal.classList.remove('hero-history-modal--open');
            }
        });
    }

    const title = document.getElementById('hero-chronicle-modal-title');
    const body  = document.getElementById('hero-chronicle-modal-body');
    if (title) title.textContent = `📖 ${hero.name} — Kronika`;
    if (body) body.innerHTML = `<p class="hero-history-modal__loading">Wczytywanie…</p>`;
    modal.classList.add('hero-history-modal--open');

    try {
        const data = await apiRequest('GET', `/characters/${hero.id}/chronicle`);
        if (!body) return;

        const { legend, chapters = [], scars = [] } = data;

        if (!legend && !chapters.length && !scars.length) {
            body.innerHTML = `<p class="hero-history-modal__empty">Twoja legenda dopiero się zaczyna. Ukończ pierwszą przygodę aby zapisać swój rozdział.</p>`;
            return;
        }

        let html = '';

        if (legend) {
            html += `
              <section class="hero-chronicle-section">
                <h4 class="hero-chronicle-section__title">⭐ Legenda</h4>
                <p class="hero-chronicle-legend">${_esc(legend)}</p>
              </section>`;
        }

        if (chapters.length) {
            const outcomeIcon  = { victory: '🏆', death: '💀', abandoned: '🚪' };
            const outcomeLabel = { victory: 'Zwycięstwo', death: 'Śmierć', abandoned: 'Porzucono' };
            html += `
              <section class="hero-chronicle-section">
                <h4 class="hero-chronicle-section__title">📜 Rozdziały</h4>
                <ul class="hero-history-list">` +
                chapters.map(h => {
                    const icon  = outcomeIcon[h.outcome] || '•';
                    const lbl   = outcomeLabel[h.outcome] || h.outcome || '—';
                    const cTitle = h.campaign_title || `Kampania #${h.campaign_id}`;
                    return `
                      <li class="hero-history-row hero-history-row--${_esc(h.outcome)}">
                        <span class="hero-history-row__icon">${icon}</span>
                        <div class="hero-history-row__main">
                          <div class="hero-history-row__title">${_esc(cTitle)}</div>
                          <div class="hero-history-row__meta">${_esc(lbl)} · ${h.xp_earned ?? 0} PD · ${h.turns_count ?? 0} tur</div>
                          ${h.chapter_summary ? `<div class="hero-history-row__summary">${_esc(h.chapter_summary)}</div>` : ''}
                        </div>
                      </li>`;
                }).join('') +
                `</ul>
              </section>`;
        }

        if (scars.length) {
            html += `
              <section class="hero-chronicle-section hero-chronicle-section--scars">
                <h4 class="hero-chronicle-section__title">🔥 Niedokończone sprawy</h4>
                <ul class="hero-history-list">` +
                scars.map(h => {
                    const cTitle = h.campaign_title || `Kampania #${h.campaign_id}`;
                    return `
                      <li class="hero-history-row hero-history-row--abandoned hero-chronicle-scar">
                        <span class="hero-history-row__icon">🚪</span>
                        <div class="hero-history-row__main">
                          <div class="hero-history-row__title">${_esc(cTitle)}</div>
                          <div class="hero-history-row__summary hero-chronicle-scar__note">${_esc(h.abandonment_note)}</div>
                        </div>
                      </li>`;
                }).join('') +
                `</ul>
              </section>`;
        }

        body.innerHTML = html;
    } catch (err) {
        if (body) body.innerHTML = `<p class="hero-history-modal__empty">Nie udało się wczytać kroniki: ${_esc(err.message || err)}</p>`;
    }
}

