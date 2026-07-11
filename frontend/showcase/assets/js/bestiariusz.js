/* #1191 / #915 — showcase bestiary gallery.
 *
 * Anonymous: portrait + name + one-sentence teaser for every enemy. Logged-in
 * game account (shared token via showcase-auth): enemies the account's heroes
 * have defeated are flagged, show a kill count, and unlock the full lore in a
 * click-through modal. Undefeated stay teaser-only.
 */
(function () {
  const grid = document.getElementById("best-grid");
  const status = document.getElementById("best-status");
  const sub = document.getElementById("best-sub");
  const cta = document.getElementById("best-cta");
  const navAuth = document.getElementById("nav-auth");

  // ── nav auth chip ──────────────────────────────────────────────────────────
  function renderNav(user) {
    if (!navAuth) return;
    if (user) {
      navAuth.innerHTML = `<span class="nav-user">▸ ${escapeHtml(user.displayName || user.username)}</span>
        <button class="nav-logout" type="button">Wyloguj</button>`;
      navAuth.querySelector(".nav-logout").onclick = () => window.AIGMAuth.logout();
    } else {
      navAuth.innerHTML = `<button class="nav-login" type="button">Zaloguj</button>`;
      navAuth.querySelector(".nav-login").onclick = () => window.AIGMAuth.openLogin();
    }
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ── data ─────────────────────────────────────────────────────────────────────
  async function load() {
    const headers = {};
    const tok = window.AIGMAuth && window.AIGMAuth.token();
    if (tok) headers.Authorization = `Bearer ${tok}`;
    status.hidden = false;
    status.textContent = "Wczytywanie bestiariusza…";
    grid.hidden = true;
    try {
      const res = await fetch("/api/showcase/bestiary", { headers, cache: "no-store" });
      const data = await res.json();
      render(data);
    } catch (e) {
      status.textContent = "Nie udało się wczytać bestiariusza. Spróbuj odświeżyć stronę.";
    }
  }

  function render(data) {
    const entries = data.entries || [];
    const s = data.summary || { total: 0, defeated: 0, pct: 0 };
    if (data.authenticated) {
      sub.textContent = `Pokonałeś ${s.defeated} z ${s.total} bestii (${s.pct}%). Kliknij pokonaną bestię, by przeczytać jej wpis.`;
      cta.innerHTML = "";
    } else {
      sub.textContent = "Każda bestia, którą możesz spotkać na Kresach. Zaloguj się i wyrusz na łowy — pokonane potwory odsłaniają pełne wpisy.";
      cta.innerHTML = `<button class="btn btn-gold" id="cta-login">Zaloguj się, by odkrywać</button>`;
      const b = document.getElementById("cta-login");
      if (b) b.onclick = () => window.AIGMAuth.openLogin();
    }

    grid.innerHTML = "";
    for (const e of entries) {
      const card = document.createElement(e.defeated ? "button" : "div");
      card.className = "best-card" + (e.defeated ? " defeated" : "");
      card.innerHTML = `
        <div class="best-portrait">
          ${e.image_url ? `<img src="${escapeHtml(e.image_url)}" alt="${escapeHtml(e.name)}" loading="lazy">` : ""}
          ${e.defeated ? `<span class="best-badge" title="Pokonane">✦ ${e.kills}</span>` : ""}
        </div>
        <div class="best-body">
          <div class="best-name">${escapeHtml(e.name)}</div>
          <div class="best-teaser">${escapeHtml(e.teaser || "")}</div>
        </div>`;
      if (e.defeated) card.onclick = () => openEntry(e);
      grid.appendChild(card);
    }
    status.hidden = true;
    grid.hidden = false;
  }

  // ── entry modal (defeated only) ──────────────────────────────────────────────
  let modal;
  function openEntry(e) {
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "best-overlay";
      modal.innerHTML = `<div class="best-modal" role="dialog" aria-modal="true">
        <button class="best-x" aria-label="Zamknij">✕</button>
        <div class="best-modal-body"></div></div>`;
      document.body.appendChild(modal);
      modal.querySelector(".best-x").onclick = () => (modal.style.display = "none");
      modal.onclick = (ev) => { if (ev.target === modal) modal.style.display = "none"; };
    }
    modal.querySelector(".best-modal-body").innerHTML = `
      ${e.image_url ? `<img class="best-modal-img" src="${escapeHtml(e.image_url)}" alt="${escapeHtml(e.name)}">` : ""}
      <h2>${escapeHtml(e.name)}</h2>
      <div class="best-modal-meta">Pokonane: <b>${e.kills}</b></div>
      <p class="best-modal-lore">${escapeHtml(e.lore_text || e.description || "")}</p>`;
    modal.style.display = "flex";
  }

  // ── boot ─────────────────────────────────────────────────────────────────────
  if (window.AIGMAuth) window.AIGMAuth.onChange((u) => { renderNav(u); load(); });
  else load();
})();
