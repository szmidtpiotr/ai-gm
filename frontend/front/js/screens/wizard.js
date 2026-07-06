// ============================================================================
// Character Wizard — real 4-step flow
// ============================================================================
function startCharacterWizard() {
    wizardStepNum = 0;
    wizardRace = 'human';
    wizardCreatedChar = null;
    wizardStatBases = {};
    wizardStatOriginal = {};
    wizardStatUnassigned = 0;
    wizardSkillSnapshot = {};
    wizardSkillLevels = {};
    wizardSkillSwapMap = {};
    wizardSwapModeSlot = null;
    wizardIdentityPreview = null;
    _wizardRender();
    showScreen('characterWizard');
    // E2 (#417) — load tooltip content (descriptions + mechanical examples) and
    // re-render once it arrives so the creator tooltips show roll examples.
    _loadCreatorHelp().then(() => { if (elements.characterWizard?.classList.contains('screen--active')) _wizardRender(); });
}

// E2 (#417) — Creator help cache: archetype/stat/skill examples for tooltips.
let _creatorHelp = null;
async function _loadCreatorHelp() {
    if (_creatorHelp) return _creatorHelp;
    try {
        const r = await fetch('/api/mechanics/creator-help');
        if (r.ok) {
            _creatorHelp = await r.json();
            _mergeSkillCatalog();
        }
    } catch (_e) { /* fall back to local hints */ }
    return _creatorHelp;
}
// FAZA S (#617) — the wizard's hardcoded ALL_SKILL_ROWS only listed the 16 legacy
// creation skills, so the new skill engine (gamble/haggling/lockpick/…) could never
// be picked at creation. Merge the full game_config_skills catalog (already returned
// by /creator-help) into the swap pool so new skills become selectable.
function _mergeSkillCatalog() {
    const cat = _creatorHelp?.skills;
    if (!Array.isArray(cat)) return;
    const have = new Set(ALL_SKILL_ROWS.map(r => r.key));
    for (const s of cat) {
        if (!s?.key || have.has(s.key)) continue;
        ALL_SKILL_ROWS.push({ key: s.key, label: s.label || s.key, stat: s.stat || '?', hint: s.description || '' });
        have.add(s.key);
    }
    ALL_SKILL_ROWS.sort((a, b) => a.key.localeCompare(b.key));
}
function _statExample(key) {
    return (_creatorHelp?.stats || []).find(s => s.key === key)?.example || '';
}
function _skillExample(key) {
    return (_creatorHelp?.skills || []).find(s => s.key === key)?.example || '';
}
function _wizardRender() {
    const step = WIZARD_STEPS[wizardStepNum];
    elements.wizardTitle.textContent = step.title;
    elements.wizardStep.textContent = step.subtitle;
    elements.btnWizardPrev.style.display = wizardStepNum === 0 ? 'none' : 'block';
    elements.btnWizardNext.innerHTML = wizardStepNum === WIZARD_STEPS.length - 1
        ? 'Rozpocznij przygodę <span class="btn__icon">✨</span>'
        : 'Dalej <span class="btn__icon">›</span>';
    elements.btnWizardNext.disabled = false;

    const content = elements.wizardContent;
    if (wizardStepNum === 0) _renderStep0(content);
    else if (wizardStepNum === 1) _renderStep1(content);
    else if (wizardStepNum === 2) _renderStep2(content, true);
    else if (wizardStepNum === 3) _renderStep3(content, true);
    else _renderStep4(content);
}

function _wizardRollAnimate(container, type) {
    const DICE = ['⚀','⚁','⚂','⚃','⚄','⚅'];
    if (type === 'stat') {
        container.querySelectorAll('.wizard-stat-row').forEach((row, i) => {
            row.classList.add('wiz-entering');
            row.style.setProperty('--wiz-i', i);
            const valEl = row.querySelector('.wizard-stat-val');
            if (!valEl) return;
            const finalVal = valEl.textContent.trim();
            const finalNum = parseInt(finalVal);
            if (isNaN(finalNum)) return;
            const rollStart = i * 52 + 90;
            const rollDuration = 320 + i * 35;
            valEl.classList.add('wiz-val-rolling');
            let t;
            setTimeout(() => {
                t = setInterval(() => {
                    valEl.textContent = WIZARD_STAT_MIN + Math.floor(Math.random() * (WIZARD_STAT_MAX - WIZARD_STAT_MIN + 1));
                }, 55);
                setTimeout(() => {
                    clearInterval(t);
                    valEl.textContent = finalVal;
                    valEl.classList.remove('wiz-val-rolling');
                    valEl.classList.add('wiz-val-landed');
                    setTimeout(() => valEl.classList.remove('wiz-val-landed'), 420);
                }, rollDuration);
            }, rollStart);
        });
    } else {
        container.querySelectorAll('.wizard-skill-row:not(.wizard-skill-row--swapping)').forEach((row, i) => {
            row.classList.add('wiz-entering');
            row.style.setProperty('--wiz-i', i);
            const rankEl = row.querySelector('.wizard-skill-rank');
            if (!rankEl) return;
            const finalRank = rankEl.textContent.trim();
            const flashStart = i * 52 + 80;
            const flashDuration = 220 + i * 25;
            rankEl.classList.add('wiz-rank-rolling');
            let t;
            setTimeout(() => {
                t = setInterval(() => { rankEl.textContent = DICE[Math.floor(Math.random() * 6)]; }, 50);
                setTimeout(() => {
                    clearInterval(t);
                    rankEl.textContent = finalRank;
                    rankEl.classList.remove('wiz-rank-rolling');
                    rankEl.classList.add('wiz-rank-landed');
                    setTimeout(() => rankEl.classList.remove('wiz-rank-landed'), 360);
                }, flashDuration);
            }, flashStart);
        });
    }
}

// Step 0 — Race selection (#976 R7)
function _renderStep0(c) {
    const sel = wizardRace || 'human';
    c.innerHTML = `
        <div class="wizard-hero">
            <span class="wizard-hero__icon">🧬</span>
            <h2>Wybierz rasę</h2>
            <p>Rasa kształtuje cechy fizyczne i zdolności twojego bohatera. Krasnoludy są odporne i uparcie pracowite — ale mniej zwinne i charyzmatyczne.</p>
        </div>
        <div class="archetype-grid">
            <button type="button" class="archetype-card${sel === 'human' ? ' archetype-card--selected' : ''}" data-race="human">
                <span class="archetype-icon">🧑</span>
                <span class="archetype-title">Człowiek</span>
                <span class="archetype-desc">Wszechstronny i elastyczny. Brak rasowych modyfikatorów — wszystkie archetypy dostępne w pełni.</span>
                <span class="archetype-bonus">Brak modyfikatorów · Zaklęcia arcańskie</span>
            </button>
            <button type="button" class="archetype-card${sel === 'dwarf' ? ' archetype-card--selected' : ''}" data-race="dwarf">
                <span class="archetype-icon">⛏️</span>
                <span class="archetype-title">Krasnolud</span>
                <span class="archetype-desc">Twardy jak kamień, urodzony pod ziemią. Odporny na trucizny i mroczną magię, widzi w ciemnościach, zna tajemnice Rdzenia.</span>
                <span class="archetype-bonus">+2 KON · +1 SIŁ · −1 CHA · −1 ZRĘ · Rdzeń-magia</span>
            </button>
        </div>
        <p class="wizard-hint" style="margin-top:1rem">Kliknij kartę aby wybrać rasę. Domyślnie: Człowiek.</p>
    `;
    c.querySelectorAll('.archetype-card').forEach(btn => {
        btn.addEventListener('click', () => {
            c.querySelectorAll('.archetype-card').forEach(b => b.classList.remove('archetype-card--selected'));
            btn.classList.add('archetype-card--selected');
            wizardRace = btn.dataset.race || 'human';
        });
    });
}

function _wizardStep0Submit() {
    // race already stored in wizardRace via click handler; default 'human' is always set
    wizardStepNum = 1;
    _wizardRender();
}

// Step 1 — Name, background, archetype
function _renderStep1(c) {
    const sheet = wizardCreatedChar?.sheet_json || {};
    const savedName = wizardCreatedChar?.name || '';
    const savedBg = sheet.backstory || '';
    const savedArch = sheet.archetype || 'warrior';
    c.innerHTML = `
        <div class="wizard-hero">
            <span class="wizard-hero__icon">👤</span>
            <h2>Stwórz postać</h2>
            <p>Nie masz jeszcze bohatera w tej kampanii. Przygotuj kartę i zacznij przygodę.</p>
        </div>
        <div class="wizard-form">
            <div class="form-field">
                <label for="char-name">Imię postaci</label>
                <input type="text" id="char-name" placeholder="np. Aldric z Północy" maxlength="40" value="${_esc(savedName)}">
            </div>
            <div class="form-field">
                <label for="char-bg">Historia / tło postaci</label>
                <textarea id="char-bg" rows="4" placeholder="Kim był twój bohater przed początkiem kampanii?">${_esc(savedBg)}</textarea>
            </div>
            <div class="form-field">
                <label>Archetyp</label>
                <div class="archetype-grid">
                    <button type="button" class="archetype-card${savedArch === 'warrior' ? ' archetype-card--selected' : ''}" data-arch="warrior">
                        <span class="archetype-icon">⚔️</span>
                        <span class="archetype-title">Wojownik</span>
                        <span class="archetype-desc">Frontowy wojownik w ciężkiej zbroi. Wysoki HP, silne ciosy, mistrz broni wręcz.</span>
                        <span class="archetype-bonus">+2 STR · +1 KON · HP: 10</span>
                    </button>
                    <button type="button" class="archetype-card${savedArch === 'rogue' ? ' archetype-card--selected' : ''}" data-arch="rogue">
                        <span class="archetype-icon">🏹</span>
                        <span class="archetype-title">Łotrzyk</span>
                        <span class="archetype-desc">Zwinny cień: snajper z ukrycia lub złodziej w ciemnościach. Skradanie, łuk, inteligentna walka.</span>
                        <span class="archetype-bonus">+2 ZRĘ · +1 SZCZ · HP: 8</span>
                    </button>
                    <button type="button" class="archetype-card${savedArch === 'scholar' ? ' archetype-card--selected' : ''}" data-arch="scholar">
                        <span class="archetype-icon">📜</span>
                        <span class="archetype-title">Uczony</span>
                        <span class="archetype-desc">Tkacz arkanów: kruchy, ale niszczycielski dzięki zaklęciom. Zarządza maną i ryzykiem Omylenia.</span>
                        <span class="archetype-bonus">+2 INT · +1 MĄD · HP: 6 · Mana</span>
                    </button>
                </div>
            </div>
        </div>
    `;
    c.querySelectorAll('.archetype-card').forEach(btn => {
        btn.addEventListener('click', () => {
            c.querySelectorAll('.archetype-card').forEach(b => b.classList.remove('archetype-card--selected'));
            btn.classList.add('archetype-card--selected');
        });
    });
}

// Step 2 — Stat redistribution (pool model matching original frontend)
let _step2FirstRender = false;
function _wizardCalcHP(archetype, con, level = 1) {
    const base = archetype === 'warrior' ? 10 : archetype === 'rogue' ? 8 : archetype === 'scholar' ? 6 : 8;
    const mod = Math.floor((con - 10) / 2);
    return Math.max(1, base + mod * level);
}

function _wizardCalcMana(archetype, int_, level = 1) {
    if (archetype !== 'scholar') return 0;
    const mod = Math.floor((int_ - 10) / 2);
    return Math.max(1, 8 + mod * level);
}

const STAT_HINTS = {
    STR: 'Siła — obrażenia wręcz, atletyka, dźwiganie, forsowanie drzwi',
    DEX: 'Zręczność — inicjatywa, skradanie, uniki, ataki finezyjne i dystansowe',
    CON: 'Kondycja — punkty życia, odporność na trucizny i ból, wytrzymałość',
    INT: 'Inteligencja — magia arkanów, wiedza, badanie, alchemia',
    WIS: 'Mądrość — percepcja, przetrwanie, medycyna, odporność na strach',
    CHA: 'Charyzma — perswazja, zastraszanie, negocjacje, przywódcze zdolności',
    LCK: 'Szczęście — wpływa na rzuty losowe, jakość łupów, szanse ucieczki i zdarzenia losowe',
};

function _renderStep2(c, animate = false) {
    const archetype = wizardCreatedChar?.sheet_json?.archetype || 'warrior';
    const bonus = ARCHETYPE_BONUS[archetype] || {};
    const bonusStr = Object.entries(bonus).map(([k, v]) => `+${v} ${k}`).join(', ');

    let rows = '';
    for (const stat of ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK']) {
        const v = wizardStatBases[stat] ?? (stat === 'LCK' ? 8 : 10);
        const mod = Math.floor((v - 10) / 2);
        const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
        const canMinus = v > WIZARD_STAT_MIN;
        const canPlus = v < WIZARD_STAT_MAX && wizardStatUnassigned > 0;
        const ex = _statExample(stat);
        const hint = (STAT_HINTS[stat] || stat) + (ex ? ` — ${ex}` : '');
        rows += `
            <div class="wizard-stat-row" data-stat="${stat}">
                <div class="wizard-stat-label-wrap">
                    <span class="wizard-stat-label">${stat}</span>
                </div>
                <span class="wizard-stat-mod">${modStr}</span>
                <div class="wizard-stat-controls">
                    <button type="button" class="wizard-stat-btn" data-dir="-" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-stat-val">${v}</span>
                    <button type="button" class="wizard-stat-btn" data-dir="+" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
                ${hint.trim() ? `<div class="wizard-stat-desc">${_esc(hint)}</div>` : ''}
            </div>`;
    }

    const previewCon = wizardStatBases['CON'] ?? 10;
    const previewInt = wizardStatBases['INT'] ?? 10;
    const previewHp   = _wizardCalcHP(archetype, previewCon);
    const previewMana = _wizardCalcMana(archetype, previewInt);
    const manaLine = archetype === 'scholar'
        ? `<span class="wizard-preview-item">✨ Mana: <strong>${previewMana}</strong></span>`
        : `<span class="wizard-preview-item wizard-preview-muted">✨ Mana: —</span>`;

    c.innerHTML = `
        <div class="wizard-form">
            <p class="wizard-hint">Przesuń punkty między statystykami. Zmniejsz stat (−) aby dodać do puli, wydaj pulę (+) na inne. Bonusy klasy dodawane automatycznie.</p>
            <div class="wizard-points">Niezapisane punkty: <strong>${wizardStatUnassigned}</strong></div>
            <p class="wizard-class-note">${bonusStr} dodawane automatycznie po potwierdzeniu</p>
            <div class="wizard-stat-grid">${rows}</div>
            <div class="wizard-vitality-preview">
                <span class="wizard-preview-item">❤️ HP: <strong>${previewHp}</strong></span>
                ${manaLine}
            </div>
            <button type="button" class="btn btn--secondary wizard-reset-btn" id="wiz-stat-reset">Reset</button>
        </div>
    `;

    if (animate) _wizardRollAnimate(c, 'stat');

    c.querySelectorAll('.wizard-stat-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const stat = btn.closest('.wizard-stat-row').dataset.stat;
            if (btn.dataset.dir === '-') {
                if (wizardStatBases[stat] <= WIZARD_STAT_MIN) return;
                wizardStatBases[stat]--;
                wizardStatUnassigned++;
            } else {
                if (wizardStatBases[stat] >= WIZARD_STAT_MAX || wizardStatUnassigned <= 0) return;
                wizardStatBases[stat]++;
                wizardStatUnassigned--;
            }
            _renderStep2(c);
        });
    });

    document.getElementById('wiz-stat-reset')?.addEventListener('click', () => {
        wizardStatBases = { ...wizardStatOriginal };
        wizardStatUnassigned = 0;
        _renderStep2(c);
    });
}

// Step 3 — Skill swaps + level adjustments (matching original frontend mechanic)
function _renderStep3(c, animate = false) {
    const budgetUsed = Math.max(0, _skillBudgetUsed()); // netto może być ujemne (więcej obniżeń niż podniesień) — pokaż 0
    const slotRows = ALL_SKILL_ROWS.filter(r => Number(wizardSkillSnapshot[r.key] || 0) > 0)
        .sort((a, b) => {
            const db = Number(wizardSkillSnapshot[b.key] || 0) - Number(wizardSkillSnapshot[a.key] || 0);
            return db !== 0 ? db : a.key.localeCompare(b.key);
        });

    // Currently visible keys (original or swapped-in)
    const visibleKeys = new Set(slotRows.map(r => wizardSkillSwapMap[r.key] || r.key));

    // Candidates: unrolled skills not currently visible
    const candidates = ALL_SKILL_ROWS
        .filter(r => !Number(wizardSkillSnapshot[r.key] || 0) && !visibleKeys.has(r.key))
        .sort((a, b) => a.label.localeCompare(b.label));

    let rows = slotRows.map(({ key: origKey }) => {
        const isSwapped = origKey in wizardSkillSwapMap;
        const currentKey = isSwapped ? wizardSkillSwapMap[origKey] : origKey;
        const curRow = _skillRow(currentKey);
        const inSwapMode = wizardSwapModeSlot === origKey;

        if (inSwapMode) {
            const opts = candidates.map(cd =>
                `<option value="${cd.key}" title="${_esc(cd.hint||'')}">${_esc(cd.label)} — ${cd.stat}</option>`
            ).join('');
            return `
                <div class="wizard-skill-row wizard-skill-row--swapping" data-orig="${origKey}">
                    <div class="wizard-skill-swap-row">
                        <select class="wizard-skill-swap-sel" data-orig="${origKey}">
                            <option value="">— Wybierz umiejętność —</option>${opts}
                        </select>
                        <button type="button" class="wizard-stat-btn" data-cancel-swap="${origKey}" title="Anuluj">✕</button>
                    </div>
                </div>`;
        }

        const rank = wizardSkillLevels[origKey] ?? Number(wizardSkillSnapshot[origKey] || 0);
        const rankName = RANK_LABEL[rank] || rank;
        const canPlus = _canAdjSkill(origKey, 1);
        const canMinus = _canAdjSkill(origKey, -1);
        const changed = isSwapped || rank !== Number(wizardSkillSnapshot[origKey] || 0);
        const swapBtn = isSwapped
            ? `<button type="button" class="wizard-skill-swap-btn wizard-skill-swap-btn--revert" data-revert="${origKey}" title="Cofnij zamianę">↩</button>`
            : `<button type="button" class="wizard-skill-swap-btn" data-swap="${origKey}" title="Zamień skill">↔</button>`;

        const skillEx = _skillExample(currentKey);
        const skillHint = (curRow.hint || '') + (skillEx ? ` — ${skillEx}` : '');
        return `
            <div class="wizard-skill-row${changed ? ' wizard-skill-row--changed' : ''}" data-orig="${origKey}">
                <span class="wizard-skill-name">
                    ${_esc(curRow.label)} <span class="wizard-skill-stat">— ${curRow.stat}</span>
                    ${swapBtn}
                </span>
                <div class="wizard-stat-controls wizard-skill-controls">
                    <button type="button" class="wizard-stat-btn" data-skill-dir="-" data-orig="${origKey}" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-skill-rank">${rank} · ${rankName}</span>
                    <button type="button" class="wizard-stat-btn" data-skill-dir="+" data-orig="${origKey}" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
                ${skillHint.trim() ? `<div class="wizard-stat-desc">${_esc(skillHint)}</div>` : ''}
            </div>`;
    }).join('');

    c.innerHTML = `
        <div class="wizard-form">
            <p class="wizard-hint">Wylosowane umiejętności. Zamiana (↔) na inną bezpłatna. Podniesienie (+) kosztuje punkt budżetu, obniżenie (−) zwraca punkt do wydania gdzie indziej. Netto max ${WIZARD_MAX_SWAPS}.</p>
            <div class="wizard-swaps">Zmieniono: <strong>${budgetUsed} / ${WIZARD_MAX_SWAPS}</strong></div>
            <div class="wizard-skill-list">${rows}</div>
            <button type="button" class="btn btn--secondary wizard-reset-btn" id="wiz-skill-reset">Reset</button>
        </div>
    `;

    if (animate) _wizardRollAnimate(c, 'skill');

    // Swap mode open
    c.querySelectorAll('[data-swap]').forEach(btn => {
        btn.addEventListener('click', () => { wizardSwapModeSlot = btn.dataset.swap; _renderStep3(c); });
    });
    // Swap mode cancel
    c.querySelectorAll('[data-cancel-swap]').forEach(btn => {
        btn.addEventListener('click', () => { wizardSwapModeSlot = null; _renderStep3(c); });
    });
    // Swap select chosen
    c.querySelectorAll('.wizard-skill-swap-sel').forEach(sel => {
        sel.addEventListener('change', () => {
            if (!sel.value) return;
            wizardSkillSwapMap[sel.dataset.orig] = sel.value;
            wizardSwapModeSlot = null;
            _renderStep3(c);
        });
    });
    // Revert swap
    c.querySelectorAll('[data-revert]').forEach(btn => {
        btn.addEventListener('click', () => {
            delete wizardSkillSwapMap[btn.dataset.revert];
            wizardSwapModeSlot = null;
            _renderStep3(c);
        });
    });
    // Level +/-
    c.querySelectorAll('[data-skill-dir]').forEach(btn => {
        btn.addEventListener('click', () => {
            const origKey = btn.dataset.orig;
            const delta = btn.dataset.skillDir === '+' ? 1 : -1;
            if (!_canAdjSkill(origKey, delta)) return;
            const cur = wizardSkillLevels[origKey] ?? Number(wizardSkillSnapshot[origKey] || 0);
            wizardSkillLevels[origKey] = cur + delta;
            _renderStep3(c);
        });
    });
    // Reset
    document.getElementById('wiz-skill-reset')?.addEventListener('click', () => {
        wizardSkillLevels = {};
        wizardSkillSwapMap = {};
        wizardSwapModeSlot = null;
        _renderStep3(c);
    });
}

// Step 4 — Identity review (LLM-generated)
const BOND_TYPES   = ['person','place','object','ideal'];
const WEAKNESS_TYPES = ['fear','flaw','addiction','trauma'];
const BOND_TYPE_LABELS     = {person:'Osoba',place:'Miejsce',object:'Przedmiot',ideal:'Ideał'};
const WEAKNESS_TYPE_LABELS = {fear:'Strach',flaw:'Wada',addiction:'Nałóg',trauma:'Trauma'};

function _renderStep4(c) {
    const p = wizardIdentityPreview;
    if (!p) {
        c.innerHTML = `<div class="wizard-form"><p class="wizard-hint">GM konsultuje starsze, mroczniejsze księgi...</p></div>`;
        return;
    }
    const bonds     = p.bonds     || [{description:p.bond||'',type:'ideal'},{description:'',type:'ideal'}];
    const weaknesses= p.weaknesses|| [{description:p.flaw||'',type:'flaw'},{description:'',type:'flaw'}];

    const _mkSelect = (id, types, labels, val) =>
      `<select class="wiz-identity-type" id="${id}">
        ${types.map(t=>`<option value="${t}"${val===t?' selected':''}>${labels[t]||t}</option>`).join('')}
       </select>`;

    const bondsHtml = bonds.slice(0,2).map((b,i) => `
        <div class="wiz-identity-pair">
          <div class="wiz-identity-pair-header">
            ${_mkSelect(`wiz-bond-type-${i}`, BOND_TYPES, BOND_TYPE_LABELS, b.type||'ideal')}
          </div>
          <textarea id="wiz-bond-${i}" rows="2" class="wiz-identity-textarea"
            placeholder="Opisz więź…">${_esc(b.description||'')}</textarea>
        </div>`).join('');

    const weakHtml = weaknesses.slice(0,2).map((w,i) => `
        <div class="wiz-identity-pair">
          <div class="wiz-identity-pair-header">
            ${_mkSelect(`wiz-weak-type-${i}`, WEAKNESS_TYPES, WEAKNESS_TYPE_LABELS, w.type||'flaw')}
          </div>
          <textarea id="wiz-weak-${i}" rows="2" class="wiz-identity-textarea"
            placeholder="Opisz słabość…">${_esc(w.description||'')}</textarea>
        </div>`).join('');

    c.innerHTML = `
        <div class="wiz-identity-grid">
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Wygląd</div>
            <textarea id="wiz-appearance" rows="3" class="wiz-identity-textarea"
              placeholder="Jak wygląda twój bohater?">${_esc(p.appearance)}</textarea>
          </div>
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Osobowość</div>
            <textarea id="wiz-personality" rows="3" class="wiz-identity-textarea"
              placeholder="Jak zachowuje się twój bohater?">${_esc(p.personality)}</textarea>
          </div>
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Więzi</div>
            ${bondsHtml}
          </div>
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Słabości</div>
            ${weakHtml}
          </div>
          <div class="wiz-identity-hint">GM zna też to, o czym sam nie wiesz. Objawi się w swoim czasie.</div>
        </div>
    `;
}

function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function handleWizardPrev() {
    if (wizardStepNum > 0) {
        wizardStepNum--;
        _wizardRender();
    }
}

function _wizardSetLoading(loading) {
    const btn = elements.btnWizardNext;
    btn.disabled = loading;
    if (loading) {
        btn.dataset.prevText = btn.innerHTML;
        btn.innerHTML = '<span class="wiz-loading-dots"></span>';
    } else if (btn.dataset.prevText) {
        btn.innerHTML = btn.dataset.prevText;
    }
}

async function handleWizardNext() {
    _wizardSetLoading(true);
    try {
        if (wizardStepNum === 0) {
            _wizardStep0Submit();
        } else if (wizardStepNum === 1) {
            await _wizardStep1Submit();
        } else if (wizardStepNum === 2) {
            wizardStepNum = 3;
            _wizardRender();
        } else if (wizardStepNum === 3) {
            await _wizardStep3Submit();
        } else {
            await _wizardFinalizeAndEnter();
        }
    } catch (err) {
        showToast(err.message || 'Błąd kreatora postaci', 'error');
    } finally {
        _wizardSetLoading(false);
    }
}

async function _wizardStep1Submit() {
    const name = document.getElementById('char-name')?.value?.trim();
    const bg = document.getElementById('char-bg')?.value?.trim() || '';
    const archBtn = elements.wizardContent.querySelector('.archetype-card--selected');
    const archetype = archBtn?.dataset?.arch || 'warrior';

    if (!name) { showToast('Podaj imię postaci', 'error'); elements.btnWizardNext.disabled = false; return; }

    let char;
    if (wizardCreatedChar && wizardCreatedChar.name === name && (wizardCreatedChar.sheet_json?.archetype === archetype)) {
        char = wizardCreatedChar;
    } else if (currentCampaignId) {
        // Classic flow: campaign already exists, create character inside it
        char = await apiRequest('POST', `/campaigns/${currentCampaignId}/characters`, {
            user_id: currentUser?.id,
            name,
            race: wizardRace || 'human',
            system_id: currentCampaign?.system_id || 'fantasy',
            sheet_json: { archetype, background_note: bg, backstory: bg },
        });
    } else {
        // Hero-first flow: create standalone character, no campaign yet
        char = await apiRequest('POST', `/characters`, {
            user_id: currentUser?.id,
            name,
            race: wizardRace || 'human',
            system_id: 'fantasy',
            sheet_json: { archetype, background_note: bg, backstory: bg },
        });
    }

    wizardCreatedChar = char;
    const sheet = char.sheet_json || {};
    const archKey = sheet.archetype || 'warrior';
    const bonus = ARCHETYPE_BONUS[archKey] || {};
    const storedStats = sheet.stats || {};

    // Reverse-engineer pre-bonus base values (LCK defaults to 8)
    for (const k of ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK']) {
        const bonVal = bonus[k] || 0;
        const defVal = k === 'LCK' ? 8 : 10;
        wizardStatBases[k] = Math.max(WIZARD_STAT_MIN, (storedStats[k] || defVal) - bonVal);
    }
    wizardStatOriginal = { ...wizardStatBases };
    wizardStatUnassigned = 0;

    // Build skill snapshot from skills_at_creation
    const skillsOrig = sheet.skills_at_creation || sheet.skills || {};
    wizardSkillSnapshot = {};
    wizardSkillLevels = {};
    wizardSkillSwapMap = {};
    wizardSwapModeSlot = null;
    for (const { key } of ALL_SKILL_ROWS) {
        const v = Math.max(0, Math.min(2, Number(skillsOrig[key] || 0)));
        wizardSkillSnapshot[key] = v;
        if (v > 0) wizardSkillLevels[key] = v;
    }

    wizardStepNum = 1;
    _wizardRender();
}

async function _wizardStep3Submit() {
    // Generate identity while transitioning to step 4
    elements.wizardContent.innerHTML = `<div class="wizard-form"><p class="wizard-hint">Generowanie tożsamości postaci przez AI...</p></div>`;
    wizardStepNum = 4;
    elements.wizardStep.textContent = WIZARD_STEPS[4].subtitle;
    elements.wizardTitle.textContent = WIZARD_STEPS[4].title;
    elements.btnWizardPrev.style.display = 'block';
    elements.btnWizardNext.innerHTML = 'Rozpocznij przygodę <span class="btn__icon">✨</span>';

    const charId = wizardCreatedChar?.id || wizardCreatedChar?.character_id;
    wizardIdentityPreview = await apiRequest('POST', `/characters/${charId}/generate-identity`);
    _renderStep4(elements.wizardContent);
    elements.btnWizardNext.disabled = false;
}

async function _wizardFinalizeAndEnter() {
    const charId = wizardCreatedChar?.id || wizardCreatedChar?.character_id;

    // Build stat_overrides from redistributed bases
    const statOverrides = { ...wizardStatBases };

    // Build skills dict and skill_slot_current from new state model
    const finalSkills = {};
    const skillSlotCurrent = {};
    for (const { key } of ALL_SKILL_ROWS) finalSkills[key] = 0;
    for (const { key: origKey } of ALL_SKILL_ROWS) {
        const snap = Number(wizardSkillSnapshot[origKey] || 0);
        if (!snap) continue;
        const tgt = wizardSkillSwapMap[origKey] || origKey;
        const lv = Math.max(0, Math.min(2, wizardSkillLevels[origKey] ?? snap));
        finalSkills[tgt] = lv;
        skillSlotCurrent[origKey] = tgt;
    }

    // Identity overrides — V2 structured format
    const appearance = document.getElementById('wiz-appearance')?.value?.trim() || wizardIdentityPreview?.appearance || '';
    const personality = document.getElementById('wiz-personality')?.value?.trim() || wizardIdentityPreview?.personality || '';

    const bonds = [0,1].map(i => ({
        description: document.getElementById(`wiz-bond-${i}`)?.value?.trim() || '',
        type: document.getElementById(`wiz-bond-type-${i}`)?.value || 'ideal',
    })).filter(b => b.description);

    const weaknesses = [0,1].map(i => ({
        description: document.getElementById(`wiz-weak-${i}`)?.value?.trim() || '',
        type: document.getElementById(`wiz-weak-type-${i}`)?.value || 'flaw',
    })).filter(w => w.description);

    const result = await apiRequest('POST', `/characters/${charId}/finalize-sheet`, {
        stat_overrides: statOverrides,
        skills: finalSkills,
        skill_slot_current: Object.keys(skillSlotCurrent).length > 0 ? skillSlotCurrent : null,
        identity_overrides: {
            appearance,
            personality,
            bonds: bonds.length > 0 ? bonds : null,
            weaknesses: weaknesses.length > 0 ? weaknesses : null,
        },
    });

    if (currentCampaignId) {
        // Classic flow: reload from campaign and enter game
        const chars = await apiRequest('GET', `/campaigns/${currentCampaignId}/characters`);
        const charList = chars.characters || (Array.isArray(chars) ? chars : []);
        characterData = charList.find(c => c.id === charId) || wizardCreatedChar;
        if (result?.sheet_json) characterData.sheet_json = result.sheet_json;
        await enterGame(currentCampaign);
    } else {
        // Hero-first flow: hero created standalone → go to campaigns chooser
        currentHero = wizardCreatedChar;
        if (elements.welcomeUser) elements.welcomeUser.textContent = `Bohater: ${wizardCreatedChar.name}`;
        showToast(`Bohater ${wizardCreatedChar.name} gotowy! Wybierz przygodę.`, 'success', 3000);
        await loadCampaigns();
        showScreen('campaigns');
    }
}

