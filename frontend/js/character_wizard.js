/**
 * Phase 7.6.9–7.6.11 — Post-creation character wizard (stats → skills → identity → finalize).
 */
(function () {
  const CORE_STATS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];
  const STAT_LABELS = {
    STR: 'STR',
    DEX: 'DEX',
    CON: 'CON',
    INT: 'INT',
    WIS: 'WIS',
    CHA: 'CHA'
  };
  const STAT_API_KEYS = {
    STR: 'strength',
    DEX: 'dexterity',
    CON: 'constitution',
    INT: 'intelligence',
    WIS: 'wisdom',
    CHA: 'charisma'
  };

  const LOCKED_SKILLS = [
    { key: 'athletics', label: 'Athletics', stat: 'STR' },
    { key: 'stealth', label: 'Stealth', stat: 'DEX' },
    { key: 'sleight_of_hand', label: 'Sleight of Hand', stat: 'DEX' },
    { key: 'endurance', label: 'Endurance', stat: 'CON' },
    { key: 'arcana', label: 'Arcana', stat: 'INT' },
    { key: 'investigation', label: 'Investigation', stat: 'INT' },
    { key: 'lore', label: 'Lore', stat: 'INT' },
    { key: 'awareness', label: 'Awareness', stat: 'WIS' },
    { key: 'survival', label: 'Survival', stat: 'WIS' },
    { key: 'medicine', label: 'Medicine', stat: 'WIS' },
    { key: 'persuasion', label: 'Persuasion', stat: 'CHA' },
    { key: 'intimidation', label: 'Intimidation', stat: 'CHA' }
  ];

  const RANK_LABELS = ['Untrained', 'Trained', 'Skilled', 'Expert', 'Master'];
  const MAX_SWAPS = 5;

  /** Skills that can receive a replacement rank (matches backend REPLACEMENT_TARGET_SKILL_NAMES). */
  const SKILL_REPLACEMENT_EXTRA_KEYS = ['melee_attack', 'ranged_attack', 'spell_attack', 'alchemy'];

  function apiRoot() {
    const b = (window.API_BASE_URL || '/api').replace(/\/$/, '');
    return b || '/api';
  }

  function coreBasesFromStoredStats(stats, archetype) {
    const a = String(archetype || 'warrior').toLowerCase();
    const out = {};
    for (const k of CORE_STATS) {
      const lk = k.toLowerCase();
      out[k] = Number(stats[k] ?? stats[lk] ?? 10);
    }
    if (a === 'warrior') {
      out.STR -= 2;
      out.CON -= 1;
    } else {
      out.INT -= 2;
      out.WIS -= 1;
    }
    return out;
  }

  function modifier(n) {
    return Math.floor((Number(n) - 10) / 2);
  }

  function modifierLabel(m) {
    if (m > 0) return `+${m}`;
    return String(m);
  }

  function sumBases(bases) {
    return CORE_STATS.reduce((s, k) => s + Number(bases[k] || 0), 0);
  }

  function skillKeyLabel(key) {
    const found = LOCKED_SKILLS.find((x) => x.key === key);
    if (found) return found.label;
    const extra = {
      melee_attack: 'Melee Attack',
      ranged_attack: 'Ranged Attack',
      spell_attack: 'Spell Attack',
      alchemy: 'Alchemy'
    };
    if (extra[key]) return extra[key];
    return String(key || '')
      .split('_')
      .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : ''))
      .join(' ');
  }

  function replacementPoolKeys() {
    const locked = LOCKED_SKILLS.map((x) => x.key);
    return Array.from(new Set([...locked, ...SKILL_REPLACEMENT_EXTRA_KEYS]));
  }

  /** Replacement targets: inactive (rank 0) and not the selected source slot. */
  function replacementCandidates(w) {
    const from = w.skillReplaceSource;
    if (!from) return [];
    const pool = replacementPoolKeys();
    return pool.filter((k) => {
      if (k === from) return false;
      return Number(w.lockedSkills[k] || 0) === 0;
    });
  }

  function normalizeSkillKeyFromSheet(skills, canonicalKey) {
    const want = canonicalKey.toLowerCase();
    for (const [k, v] of Object.entries(skills || {})) {
      const nk = String(k).toLowerCase().replace(/\s+/g, '_');
      if (nk === want) return Number(v) || 0;
    }
    return 0;
  }

  function buildInitialLockedSkills(sheetSkills) {
    const o = {};
    for (const { key } of LOCKED_SKILLS) {
      o[key] = normalizeSkillKeyFromSheet(sheetSkills, key);
    }
    return o;
  }

  function classBonusNote(archetype) {
    const a = String(archetype || 'warrior').toLowerCase();
    if (a === 'mage') {
      return '+2 INT, +1 WIS applied automatically after confirmation';
    }
    return '+2 STR, +1 CON applied automatically after confirmation';
  }

  function formatDetail(detail) {
    if (detail == null) return 'Request failed';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((x) => (typeof x === 'object' && x && 'msg' in x ? x.msg : JSON.stringify(x)))
        .join('; ');
    }
    if (typeof detail === 'object' && detail.message) return String(detail.message);
    return 'Validation failed';
  }

  function getWizardEls() {
    return {
      stepIndicatorEl: document.getElementById('character-create-step-indicator'),
      step1WrapEl: document.getElementById('character-create-step-1-wrap'),
      wizardHostEl: document.getElementById('character-wizard-host'),
      wizardPanelEl: document.getElementById('character-wizard-panel'),
      wizardNavEl: document.getElementById('character-wizard-nav'),
      wizardBackBtn: document.getElementById('character-wizard-back'),
      titleEl: document.getElementById('character-create-title'),
      subtitleEl: document.getElementById('character-create-subtitle')
    };
  }

  function showStep1Only() {
    const { stepIndicatorEl, step1WrapEl, wizardHostEl, titleEl, subtitleEl } = getWizardEls();
    if (stepIndicatorEl) stepIndicatorEl.style.display = 'none';
    if (step1WrapEl) step1WrapEl.style.display = '';
    if (wizardHostEl) wizardHostEl.style.display = 'none';
    if (titleEl) titleEl.textContent = 'Stwórz postać';
    if (subtitleEl) {
      subtitleEl.style.display = '';
      subtitleEl.textContent =
        'Nie masz jeszcze bohatera w tej kampanii. Przygotuj kartę i zacznij przygodę.';
    }
    const closeBtn = window.getEls().characterCreateCloseEl;
    if (closeBtn) closeBtn.style.display = '';
    const overlay = window.getEls().characterCreateOverlayEl;
    if (overlay) overlay.removeAttribute('data-wizard-active');
  }

  function showWizardChrome(step) {
    const { stepIndicatorEl, step1WrapEl, wizardHostEl, subtitleEl } = getWizardEls();
    if (stepIndicatorEl) {
      stepIndicatorEl.style.display = '';
      stepIndicatorEl.textContent = `Step ${step} of 4`;
    }
    if (step1WrapEl) step1WrapEl.style.display = 'none';
    if (wizardHostEl) wizardHostEl.style.display = '';
    if (subtitleEl) subtitleEl.style.display = 'none';
    const closeBtn = window.getEls().characterCreateCloseEl;
    if (closeBtn) closeBtn.style.display = step >= 2 ? 'none' : '';
    const overlay = window.getEls().characterCreateOverlayEl;
    if (overlay) overlay.setAttribute('data-wizard-active', step >= 2 ? '1' : '');
  }

  function renderStatsStep(w) {
    const sumCur = sumBases(w.bases);
    const unassigned = Number(w.unassignedPoints) || 0;
    const allRange = CORE_STATS.every((k) => w.bases[k] >= 8 && w.bases[k] <= 18);
    const confirmOk = unassigned === 0 && allRange;

    const rows = CORE_STATS.map((k) => {
      const v = w.bases[k];
      const mod = modifierLabel(modifier(v));
      const canPlus = v < 18 && unassigned > 0;
      const canMinus = v > 8;
      const pDis = canPlus ? '' : 'disabled';
      const mDis = canMinus ? '' : 'disabled';
      return `
        <div class="wizard-stat-row" data-stat="${k}">
          <div class="wizard-stat-label">${STAT_LABELS[k]}</div>
          <div class="wizard-stat-mod muted" aria-label="Modifier">${mod}</div>
          <div class="wizard-stat-controls">
            <button type="button" class="wizard-stat-btn secondary" data-act="minus" data-stat="${k}" ${mDis} aria-label="Decrease ${k}">−</button>
            <span class="wizard-stat-val">${v}</span>
            <button type="button" class="wizard-stat-btn secondary" data-act="plus" data-stat="${k}" ${pDis} aria-label="Increase ${k}">+</button>
          </div>
        </div>`;
    }).join('');

    return `
      <div class="wizard-section">
        <h3 class="wizard-section-title">Adjust your stats</h3>
        <p class="muted wizard-hint">Move points into an unassigned pool (down to 8) or spend pool points (up to 18). Class bonuses apply after confirmation.</p>
        <p class="wizard-points"><strong>Unassigned points:</strong> ${unassigned}</p>
        <p class="muted wizard-sum-hint">Current total (bases): ${sumCur} (rolled total ${w.sumTarget})</p>
        <p class="muted wizard-class-note">${window.escapeHtml(classBonusNote(w.archetype))}</p>
        <div class="wizard-stat-grid">${rows}</div>
        <div class="wizard-actions">
          <button type="button" class="secondary" data-act="reset-stats">Reset</button>
          <button type="button" class="primary" data-act="confirm-stats" ${confirmOk ? '' : 'disabled'}>Confirm Stats →</button>
        </div>
      </div>`;
  }

  function renderSkillsStep(w) {
    const used = w.skillSwaps.length;
    const atMax = used >= MAX_SWAPS;
    const src = w.skillReplaceSource || '';
    const rows = LOCKED_SKILLS.map(({ key, label, stat }) => {
      const r = Math.max(0, Math.min(4, Number(w.lockedSkills[key] || 0)));
      const rankName = RANK_LABELS[r] || RANK_LABELS[0];
      const sel = src === key ? ' wizard-skill-row--selected' : '';
      const tip = atMax ? ' title="Maximum replacements reached"' : '';
      const inactive = r <= 0;
      const rowDisabled = atMax || inactive ? ' disabled' : '';
      return `
        <button type="button" class="wizard-skill-row${sel}${inactive ? ' wizard-skill-row--inactive' : ''}" data-skill="${key}" data-skill-kind="active"${tip}${rowDisabled}>
          <span class="wizard-skill-name">${window.escapeHtml(label)} <span class="muted">— ${stat}</span></span>
          <span class="wizard-skill-rank">${r} · ${rankName}</span>
        </button>`;
    }).join('');

    const cands = replacementCandidates(w);
    const repRows = src
      ? cands
          .map((key) => {
            const label = skillKeyLabel(key);
            return `
        <button type="button" class="wizard-skill-rep-row" data-skill="${key}" data-skill-kind="replace">
          <span class="wizard-skill-name">${window.escapeHtml(label)}</span>
        </button>`;
          })
          .join('')
      : '';

    const fromRank = src
      ? Math.max(0, Math.min(4, Number(w.lockedSkills[src] || 0)))
      : 0;
    const preview =
      w.skillReplacePreview && w.skillReplacePreview.from && w.skillReplacePreview.to
        ? `<p class="wizard-skill-preview muted" role="status">${window.escapeHtml(
            `${skillKeyLabel(w.skillReplacePreview.from)} ${fromRank} → ${skillKeyLabel(w.skillReplacePreview.to)} ${fromRank}`
          )}</p>`
        : '';

    return `
      <div class="wizard-section">
        <h3 class="wizard-section-title">Adjust your skills</h3>
        <p class="muted wizard-hint">Select a skill with rank &gt; 0, then pick a replacement that is not on your sheet yet (rank 0).</p>
        <p class="wizard-swaps"><strong>Replacements used:</strong> ${used} / ${MAX_SWAPS}</p>
        <div class="wizard-skill-columns">
          <div>
            <h4 class="wizard-subtitle">Your skills</h4>
            <div class="wizard-skill-list">${rows}</div>
          </div>
          <div>
            <h4 class="wizard-subtitle">${src ? 'Replace with…' : 'Pick a skill first'}</h4>
            ${preview}
            <div class="wizard-skill-rep-list">${src ? repRows || '<p class="muted">No eligible replacements.</p>' : '<p class="muted">Select a skill on the left.</p>'}</div>
            ${src && w.skillReplacePreview && w.skillReplacePreview.from && w.skillReplacePreview.to ? `
            <div class="wizard-actions wizard-actions--inline">
              <button type="button" class="primary" data-act="apply-skill-replace">Apply replacement</button>
              <button type="button" class="secondary" data-act="cancel-skill-replace">Cancel</button>
            </div>` : ''}
          </div>
        </div>
        <div class="wizard-actions">
          <button type="button" class="secondary" data-act="reset-skills">Reset</button>
          <button type="button" class="primary" data-act="confirm-skills">Confirm Skills →</button>
        </div>
      </div>`;
  }

  function renderIdentityLoading() {
    return `
      <div class="wizard-section wizard-center">
        <p class="wizard-loading">Your GM is writing your story...</p>
        <button type="button" class="secondary" data-act="identity-retry" style="display:none">Generate again</button>
      </div>`;
  }

  function renderIdentityForm(w) {
    const err = w.finalizeError
      ? `<p class="wizard-error" role="alert">${window.escapeHtml(w.finalizeError)}</p>`
      : '';

    return `
      <div class="wizard-section">
        <h3 class="wizard-section-title">Your Character</h3>
        ${err}
        <div class="field">
          <label for="wiz-id-appearance">Appearance</label>
          <textarea id="wiz-id-appearance" rows="3"></textarea>
        </div>
        <div class="field">
          <label for="wiz-id-personality">Personality</label>
          <textarea id="wiz-id-personality" rows="3"></textarea>
        </div>
        <div class="field">
          <label for="wiz-id-flaw">Flaw (locked)</label>
          <input id="wiz-id-flaw" type="text" readonly value="">
        </div>
        <div class="field">
          <label for="wiz-id-bond">Bond (locked)</label>
          <input id="wiz-id-bond" type="text" readonly value="">
        </div>
        <p class="muted wizard-secret-hint">🔒 Your secret will be revealed when the story demands it.</p>
        <div class="wizard-actions">
          <button type="button" class="primary" data-act="begin-story">Begin Your Story →</button>
        </div>
      </div>`;
  }

  function fillIdentityFormFields(w) {
    const id = w.identity || {};
    const appEl = document.getElementById('wiz-id-appearance');
    const perEl = document.getElementById('wiz-id-personality');
    const flawEl = document.getElementById('wiz-id-flaw');
    const bondEl = document.getElementById('wiz-id-bond');
    if (appEl) appEl.value = id.appearance != null ? String(id.appearance) : '';
    if (perEl) perEl.value = id.personality != null ? String(id.personality) : '';
    if (flawEl) flawEl.value = id.flaw != null ? String(id.flaw) : '';
    if (bondEl) bondEl.value = id.bond != null ? String(id.bond) : '';
  }

  function renderIdentityErrorStep(w) {
    const msg = w.identityError || 'Generation failed';
    return `
      <div class="wizard-section wizard-center">
        <p class="wizard-error" role="alert">${window.escapeHtml(msg)}</p>
        <button type="button" class="primary" data-act="identity-retry">Generate again</button>
      </div>`;
  }

  function paintWizard(w) {
    const { wizardPanelEl, titleEl, wizardBackBtn } = getWizardEls();
    if (!wizardPanelEl) return;

    showWizardChrome(w.step);
    if (titleEl) {
      if (w.step === 2) titleEl.textContent = 'Adjust your stats';
      else if (w.step === 3) titleEl.textContent = 'Adjust your skills';
      else titleEl.textContent = 'Your Character';
    }
    if (wizardBackBtn) {
      wizardBackBtn.style.display = '';
      wizardBackBtn.textContent = 'Back';
    }

    if (w.step === 2) wizardPanelEl.innerHTML = renderStatsStep(w);
    else if (w.step === 3) wizardPanelEl.innerHTML = renderSkillsStep(w);
    else if (w.step === 4) {
      if (w.identityLoading) wizardPanelEl.innerHTML = renderIdentityLoading();
      else if (w.identityError) wizardPanelEl.innerHTML = renderIdentityErrorStep(w);
      else {
        wizardPanelEl.innerHTML = renderIdentityForm(w);
        fillIdentityFormFields(w);
      }
    }

    bindWizardPanel(w);
    if (wizardBackBtn && !wizardBackBtn._wizBound) {
      wizardBackBtn._wizBound = true;
      wizardBackBtn.addEventListener('click', () => window.characterWizardGoBack());
    }
  }

  function bindWizardPanel(w) {
    const { wizardPanelEl } = getWizardEls();
    if (!wizardPanelEl) return;
    wizardPanelEl.onclick = (e) => {
      const btn = e.target.closest('[data-act]');
      if (btn) {
        const act = btn.getAttribute('data-act');
        if (act === 'plus' || act === 'minus') {
          const stat = btn.getAttribute('data-stat');
          if (!stat || !window.state.charCreationWizard) return;
          const cur = window.state.charCreationWizard;
          if (act === 'plus') {
            if ((Number(cur.unassignedPoints) || 0) <= 0) return;
            if (cur.bases[stat] >= 18) return;
            cur.bases[stat] += 1;
            cur.unassignedPoints = (Number(cur.unassignedPoints) || 0) - 1;
          } else {
            if (cur.bases[stat] <= 8) return;
            cur.bases[stat] -= 1;
            cur.unassignedPoints = (Number(cur.unassignedPoints) || 0) + 1;
          }
          paintWizard(cur);
        } else if (act === 'reset-stats') {
          const cur = window.state.charCreationWizard;
          cur.bases = { ...cur.originalBases };
          cur.unassignedPoints = 0;
          paintWizard(cur);
        } else if (act === 'confirm-stats') {
          window.characterWizardGoToSkills();
        } else if (act === 'reset-skills') {
          const cur = window.state.charCreationWizard;
          cur.lockedSkills = { ...cur.originalLockedSkills };
          cur.skillSwaps = [];
          cur.skillReplaceSource = null;
          cur.skillReplacePreview = null;
          paintWizard(cur);
        } else if (act === 'apply-skill-replace') {
          window.characterWizardApplySkillReplace();
        } else if (act === 'cancel-skill-replace') {
          const cur = window.state.charCreationWizard;
          if (!cur) return;
          cur.skillReplacePreview = null;
          paintWizard(cur);
        } else if (act === 'confirm-skills') {
          window.characterWizardGoToIdentity();
        } else if (act === 'identity-retry') {
          window.characterWizardLoadIdentity(true);
        } else if (act === 'begin-story') {
          window.characterWizardFinalize();
        }
        return;
      }
      const sk = e.target.closest('[data-skill]');
      const cw = window.state.charCreationWizard;
      if (sk && cw && cw.step === 3 && !sk.disabled) {
        const key = sk.getAttribute('data-skill');
        const kind = sk.getAttribute('data-skill-kind');
        if (kind === 'active') {
          window.characterWizardOnActiveSkillTap(key);
        } else if (kind === 'replace') {
          window.characterWizardOnReplaceSkillTap(key);
        }
      }
    };
  }

  window.characterWizardOnActiveSkillTap = function (key) {
    const w = window.state.charCreationWizard;
    if (!w || w.step !== 3 || !key) return;
    if (w.skillSwaps.length >= MAX_SWAPS) return;
    const r = Number(w.lockedSkills[key] || 0);
    if (r <= 0) return;
    if (w.skillReplaceSource === key) {
      w.skillReplaceSource = null;
      w.skillReplacePreview = null;
      paintWizard(w);
      return;
    }
    w.skillReplaceSource = key;
    w.skillReplacePreview = null;
    paintWizard(w);
  };

  window.characterWizardOnReplaceSkillTap = function (toKey) {
    const w = window.state.charCreationWizard;
    if (!w || w.step !== 3 || !toKey) return;
    const from = w.skillReplaceSource;
    if (!from) return;
    const r = Number(w.lockedSkills[from] || 0);
    if (r <= 0) return;
    if (Number(w.lockedSkills[toKey] || 0) !== 0) return;
    if (from === toKey) return;
    w.skillReplacePreview = { from, to: toKey };
    paintWizard(w);
  };

  window.characterWizardApplySkillReplace = function () {
    const w = window.state.charCreationWizard;
    if (!w || w.step !== 3) return;
    const pv = w.skillReplacePreview;
    if (!pv || !pv.from || !pv.to) return;
    if (w.skillSwaps.length >= MAX_SWAPS) return;
    const from = pv.from;
    const to = pv.to;
    const r = Number(w.lockedSkills[from] || 0);
    if (r <= 0) return;
    if (Number(w.lockedSkills[to] || 0) !== 0) return;
    w.lockedSkills[to] = r;
    w.lockedSkills[from] = 0;
    w.skillSwaps.push({ from_skill: from, to_skill: to });
    w.skillReplaceSource = null;
    w.skillReplacePreview = null;
    paintWizard(w);
  };

  window.characterWizardGoBack = function () {
    const w = window.state.charCreationWizard;
    if (!w) return;
    if (w.step === 2) {
      window.state.charCreationWizard = null;
      showStep1Only();
      window.updateUiState();
      return;
    }
    if (w.step === 3) {
      w.step = 2;
      w.finalizeError = null;
      w.skillReplaceSource = null;
      w.skillReplacePreview = null;
      paintWizard(w);
      return;
    }
    if (w.step === 4) {
      w.step = 3;
      w.identityLoading = false;
      w.identityError = null;
      w.finalizeError = null;
      paintWizard(w);
    }
  };

  window.characterWizardGoToSkills = function () {
    const w = window.state.charCreationWizard;
    if (!w) return;
    w.step = 3;
    w.skillReplaceSource = null;
    w.skillReplacePreview = null;
    paintWizard(w);
  };

  window.characterWizardGoToIdentity = function () {
    const w = window.state.charCreationWizard;
    if (!w) return;
    w.step = 4;
    w.finalizeError = null;
    if (w.identity && !w.identityError) {
      paintWizard(w);
      return;
    }
    w.identityError = null;
    w.identity = null;
    window.characterWizardLoadIdentity(false);
  };

  window.characterWizardLoadIdentity = async function (isRetry) {
    const w = window.state.charCreationWizard;
    if (!w) return;

    const uid =
      window.state?.playerUserId ||
      (typeof window.currentUserId === 'function' ? window.currentUserId() : 1);
    try {
      if (typeof window.loadUserLlmSettings === 'function') {
        await window.loadUserLlmSettings(uid);
      }
    } catch (_e) {}
    if (typeof window.computeLlmGate === 'function') {
      const g = window.computeLlmGate();
      if (!g.ok) {
        w.identityLoading = false;
        w.identityError = g.reason;
        w.identity = null;
        paintWizard(w);
        return;
      }
    }

    w.identityLoading = true;
    w.identityError = null;
    w.identity = null;
    paintWizard(w);

    const url = `${apiRoot()}/characters/${w.characterId}/generate-identity`;
    try {
      const resp = await fetch(url, { method: 'POST', headers: window.getApiHeaders() });
      let data = {};
      try {
        data = await resp.json();
      } catch (_) {
        data = {};
      }
      if (!resp.ok) {
        throw new Error(formatDetail(data.detail) || `HTTP ${resp.status}`);
      }
      w.identity = {
        appearance: data.appearance || '',
        personality: data.personality || '',
        flaw: data.flaw || '',
        bond: data.bond || '',
        secret: data.secret || ''
      };
      w.identityLoading = false;
      w.identityError = null;
    } catch (e) {
      w.identityLoading = false;
      w.identityError = e.message || 'Generation failed';
    }
    paintWizard(w);
  };

  window.characterWizardFinalize = async function () {
    const w = window.state.charCreationWizard;
    if (!w) return;
    const appEl = document.getElementById('wiz-id-appearance');
    const perEl = document.getElementById('wiz-id-personality');
    const stat_overrides = {};
    for (const k of CORE_STATS) {
      stat_overrides[STAT_API_KEYS[k]] = Number(w.bases[k]);
    }
    const skill_swaps = w.skillSwaps.map((x) => ({ ...x }));
    const identity_overrides = {
      appearance: (appEl && appEl.value) != null ? appEl.value : w.identity?.appearance || '',
      personality: (perEl && perEl.value) != null ? perEl.value : w.identity?.personality || ''
    };

    const url = `${apiRoot()}/characters/${w.characterId}/finalize-sheet`;
    w.finalizeError = null;

    const beginBtn = document.querySelector('[data-act="begin-story"]');
    if (beginBtn) beginBtn.disabled = true;

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: window.getApiHeaders(),
        body: JSON.stringify({ stat_overrides, skill_swaps, identity_overrides })
      });
      let data = {};
      try {
        data = await resp.json();
      } catch (_) {
        data = {};
      }
      if (!resp.ok) {
        const msg = resp.status === 400 ? formatDetail(data.detail) : formatDetail(data.detail) || `HTTP ${resp.status}`;
        w.finalizeError = msg;
        paintWizard(w);
        return;
      }

      window.state.charCreationWizard = null;
      showStep1Only();

      const { characterCreateFormEl } = window.getEls();
      if (characterCreateFormEl) {
        characterCreateFormEl.reset();
        characterCreateFormEl.dataset.archetype = '';
      }
      document.querySelectorAll('.archetype-card').forEach((c) => c.classList.remove('selected'));

      window.setCharacterModalOpen(false);
      window.updateUiState();

      const cid = w.campaignId;
      const uid =
        window.state?.playerUserId ||
        (typeof window.currentUserId === 'function' ? window.currentUserId() : 1);
      try {
        if (typeof window.loadUserLlmSettings === 'function') {
          await window.loadUserLlmSettings(uid);
        } else if (typeof window.loadLlmSettings === 'function') {
          await window.loadLlmSettings();
        }
      } catch (_e) {
        /* LLM panel optional */
      }

      if (typeof window.loadCharacterSheet === 'function' && window.state.selectedCharacterId) {
        try {
          await window.loadCharacterSheet(Number(window.state.selectedCharacterId));
        } catch (_e) {
          /* optional panel */
        }
      }
      if (cid && typeof window.loadTurns === 'function') {
        await window.loadTurns(cid);
      }

      const hasGmNarrative =
        Array.isArray(window.state.turns) &&
        window.state.turns.some(
          (turn) =>
            turn.route === 'narrative' && String(turn.assistant_text || '').trim().length > 0
        );
      if (!hasGmNarrative && typeof window.requestGmOpeningIfQuiet === 'function') {
        await window.requestGmOpeningIfQuiet(cid, Number(window.state.selectedCharacterId));
      }

      window.addMessage({
        speaker: 'System',
        text: `Postać gotowa: ${w.characterName || ''}`.trim(),
        role: 'system',
        route: 'character'
      });

      const { inputEl } = window.getEls();
      if (inputEl) inputEl.focus();
    } catch (e) {
      w.finalizeError = e.message || 'Finalize failed';
      paintWizard(w);
    } finally {
      const b2 = document.querySelector('[data-act="begin-story"]');
      if (b2) b2.disabled = false;
    }
  };

  window.enterCharacterCreationWizard = function (opts) {
    const sheet = opts.sheetJson || {};
    const stats = sheet.stats || {};
    const archetype = String(sheet.archetype || 'warrior').toLowerCase();
    const originalBases = coreBasesFromStoredStats(stats, archetype);
    const sumTarget = sumBases(originalBases);
    const originalLocked = buildInitialLockedSkills(sheet.skills || {});

    window.state.charCreationWizard = {
      step: 2,
      characterId: opts.characterId,
      campaignId: opts.campaignId,
      archetype,
      characterName: opts.characterName || '',
      originalBases: { ...originalBases },
      bases: { ...originalBases },
      sumTarget,
      unassignedPoints: 0,
      originalLockedSkills: { ...originalLocked },
      lockedSkills: { ...originalLocked },
      skillSwaps: [],
      skillReplaceSource: null,
      skillReplacePreview: null,
      identity: null,
      identityLoading: false,
      identityError: null,
      finalizeError: null
    };

    window.characterModalOpen = true;
    paintWizard(window.state.charCreationWizard);
    window.updateUiState();
  };

  window.resetCharacterCreationWizardUi = function () {
    window.state.charCreationWizard = null;
    showStep1Only();
  };

  window.isCharacterCreationWizardBlockingClose = function () {
    const w = window.state.charCreationWizard;
    return !!(w && w.step >= 2);
  };
})();
