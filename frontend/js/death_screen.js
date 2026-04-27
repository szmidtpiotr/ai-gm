/**
 * Phase 7.6.12 — Tombstone UI when campaign has ended (HTTP 410 on turns).
 */
(function () {
  function esc(s) {
    return window.escapeHtml ? window.escapeHtml(String(s ?? '')) : String(s ?? '');
  }

  function buildTombstoneHtml(d) {
    const name = esc(d.character_name || 'Unknown');
    const cls = esc(d.character_class || '');
    const reason = esc(d.death_reason || '');
    const endedRaw = d.ended_at || '';
    const ended = esc(endedRaw);
    const epitaph = esc(d.epitaph || '');
    const secret = esc(d.secret || '');
    const bonds = Array.isArray(d.bonds) ? d.bonds : [];
    const bondLines = bonds
      .map((b) => {
        const t = esc((b && b.text) || '');
        const st = esc((b && b.strength) || 'strong');
        return `<li>${t} <span class="death-bond-meta">(${st})</span></li>`;
      })
      .join('');

    return `
      <div class="death-tomb-inner">
        <div class="death-cross" aria-hidden="true">✝</div>
        <h1 class="death-title" id="death-title-heading">In Memoriam</h1>
        <p class="death-name">${name}</p>
        <p class="death-meta">${cls ? `${cls} — ` : ''}<span class="muted">died at</span> ${ended || '—'}</p>
        <p class="death-reason">${reason}</p>
        <blockquote class="death-epitaph">"${epitaph}"</blockquote>
        <div class="death-secret-block">
          <div class="death-secret-label">🔒 Secret revealed:</div>
          <p class="death-secret-text">${secret}</p>
        </div>
        <div class="death-bonds-block">
          <div class="death-bonds-label">Bonds at death:</div>
          <ul class="death-bonds-list">${bondLines || '<li class="muted">—</li>'}</ul>
        </div>
        <button type="button" class="death-new-campaign-btn" id="death-start-new-btn">Start New Campaign</button>
      </div>`;
  }

  let deathEscHandler = null;

  window.dismissCampaignDeathScreen = function () {
    document.body.classList.remove('campaign-death-active');
    const el = document.getElementById('campaign-death-screen');
    if (el) {
      el.hidden = true;
      el.setAttribute('aria-hidden', 'true');
    }
    if (deathEscHandler) {
      document.removeEventListener('keydown', deathEscHandler);
      deathEscHandler = null;
    }
  };

  function wireDeathScreenDismissControls() {
    const closeBtn = document.getElementById('campaign-death-close-btn');
    if (closeBtn) {
      closeBtn.onclick = () => window.dismissCampaignDeathScreen();
    }
    const backdrop = document.getElementById('campaign-death-backdrop');
    if (backdrop) {
      backdrop.onclick = () => window.dismissCampaignDeathScreen();
    }
    if (!deathEscHandler) {
      deathEscHandler = function (ev) {
        if (ev.key === 'Escape') window.dismissCampaignDeathScreen();
      };
      document.addEventListener('keydown', deathEscHandler);
    }
  }

  window.showCampaignDeathScreen = async function (campaignId) {
    const el = document.getElementById('campaign-death-screen');
    const inner = document.getElementById('campaign-death-inner');
    if (!el || !inner) return;

    document.body.classList.add('campaign-death-active');
    el.hidden = false;
    el.setAttribute('aria-hidden', 'false');
    wireDeathScreenDismissControls();
    inner.innerHTML = '<p class="muted death-loading">Ładowanie…</p>';

    try {
      const r = await fetch(`/api/campaigns/${campaignId}/death-summary`);
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        const detail = String(err.detail || `HTTP ${r.status}`);
        // Defensive UX: if campaign is active, hide tombstone and continue normal flow.
        if (
          r.status === 404 &&
          detail.toLowerCase().includes('campaign not ended or not found')
        ) {
          window.dismissCampaignDeathScreen();
          return;
        }
        throw new Error(detail);
      }
      const d = await r.json();
      inner.innerHTML = buildTombstoneHtml(d);
      const btn = document.getElementById('death-start-new-btn');
      if (btn) {
        btn.onclick = () => {
          window.dismissCampaignDeathScreen();
          if (typeof window.setCampaignModalOpen === 'function') {
            window.setCampaignModalOpen(true);
          }
          if (typeof window.loadCampaigns === 'function') {
            window.loadCampaigns(window.state?.selectedCampaignId);
          }
        };
      }
      wireDeathScreenDismissControls();
    } catch (e) {
      inner.innerHTML = `<p class="death-error" role="alert">${esc(e.message || 'Nie udało się wczytać.')}</p>
        <button type="button" class="secondary" id="death-dismiss-err">Zamknij</button>`;
      document.getElementById('death-dismiss-err').onclick = () => window.dismissCampaignDeathScreen();
      wireDeathScreenDismissControls();
    }
  };
})();
