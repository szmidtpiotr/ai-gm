/* #1191 / #915 — showcase bestiary: gallery + search/filter/sort + full card.
 *
 * Visibility model: coarse descriptors (name, portrait, teaser, zone, attack
 * type) show for every enemy → searchable/filterable by anyone. The full stat
 * card (HP, armour, attack, 7 stats, tier, level, lore) + uncropped portrait
 * shows only for enemies the logged-in account's heroes have DEFEATED.
 */
(function () {
  const grid = document.getElementById("best-grid");
  const status = document.getElementById("best-status");
  const sub = document.getElementById("best-sub");
  const cta = document.getElementById("best-cta");
  const navAuth = document.getElementById("nav-auth");
  const bar = document.getElementById("best-controls");

  let ALL = [];       // full dataset from API
  let authed = false;

  const ZONE = { engaged: "⚔ Zwarcie", ranged: "🏹 Dystans" };
  const DMG = { physical: "fizyczny", magical: "magiczny", necrotic: "nekrotyczny", fire: "ognisty", poison: "trujący" };
  const TIER = { weak: "słaby", standard: "standard", elite: "elita", boss: "boss" };
  const TIER_ORDER = { weak: 0, standard: 1, elite: 2, boss: 3 };

  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ── nav auth chip ──
  function renderNav(user) {
    if (!navAuth) return;
    if (user) {
      navAuth.innerHTML = `<span class="nav-user">▸ ${esc(user.displayName || user.username)}</span>
        <button class="nav-logout" type="button">Wyloguj</button>`;
      navAuth.querySelector(".nav-logout").onclick = () => window.AIGMAuth.logout();
    } else {
      navAuth.innerHTML = `<button class="nav-login" type="button">Zaloguj</button>`;
      navAuth.querySelector(".nav-login").onclick = () => window.AIGMAuth.openLogin();
    }
  }

  // ── data ──
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
      ALL = data.entries || [];
      authed = !!data.authenticated;
      renderHeader(data.summary || {});
      buildControls();
      apply();
    } catch (e) {
      status.textContent = "Nie udało się wczytać bestiariusza. Odśwież stronę.";
    }
  }

  function renderHeader(s) {
    if (authed) {
      sub.textContent = `Pokonałeś ${s.defeated || 0} z ${s.total || 0} bestii (${s.pct || 0}%). Kliknij pokonaną bestię, by zobaczyć pełną kartę.`;
      cta.innerHTML = "";
    } else {
      sub.textContent = "Każda bestia Kresów. Filtruj i przeszukuj katalog — pełne karty ze statystykami odsłaniasz, pokonując potwory w grze.";
      cta.innerHTML = `<button class="btn btn-gold" id="cta-login">Zaloguj się, by odkrywać karty</button>`;
      const b = document.getElementById("cta-login");
      if (b) b.onclick = () => window.AIGMAuth.openLogin();
    }
  }

  // ── controls ──
  const state = { q: "", zone: "", dmg: "", tier: "", fear: "", onlyDefeated: false, sort: "name-asc" };

  function opts(map, ph) {
    return `<option value="">${ph}</option>` +
      Object.entries(map).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  }

  function buildControls() {
    if (!bar || bar.dataset.built) return;
    bar.dataset.built = "1";
    bar.innerHTML = `
      <input id="f-q" class="best-search" type="search" placeholder="Szukaj po nazwie…" autocomplete="off">
      <select id="f-zone" class="best-select">${opts(ZONE, "Strefa: wszystkie")}</select>
      <select id="f-dmg" class="best-select">${opts(DMG, "Atak: wszystkie")}</select>
      <select id="f-tier" class="best-select" title="Trudność — dla pokonanych">${opts(TIER, "Trudność: wszystkie")}</select>
      <select id="f-fear" class="best-select" title="Groza — dla pokonanych"><option value="">Groza: obojętnie</option><option value="1">z grozą</option><option value="0">bez grozy</option></select>
      <select id="f-sort" class="best-select">
        <option value="name-asc">Nazwa A–Z</option>
        <option value="name-desc">Nazwa Z–A</option>
        <option value="hp-desc">HP malejąco</option>
        <option value="hp-asc">HP rosnąco</option>
        <option value="tier-desc">Trudność malejąco</option>
        <option value="level-asc">Poziom rosnąco</option>
        <option value="xp-desc">XP malejąco</option>
      </select>
      <label class="best-check"><input id="f-def" type="checkbox"> Tylko pokonane</label>
      <span class="best-count" id="best-count"></span>`;
    const on = (id, ev, fn) => { const el = document.getElementById(id); if (el) el.addEventListener(ev, fn); };
    on("f-q", "input", (e) => { state.q = e.target.value.trim().toLowerCase(); apply(); });
    on("f-zone", "change", (e) => { state.zone = e.target.value; apply(); });
    on("f-dmg", "change", (e) => { state.dmg = e.target.value; apply(); });
    on("f-tier", "change", (e) => { state.tier = e.target.value; apply(); });
    on("f-fear", "change", (e) => { state.fear = e.target.value; apply(); });
    on("f-sort", "change", (e) => { state.sort = e.target.value; apply(); });
    on("f-def", "change", (e) => { state.onlyDefeated = e.target.checked; apply(); });
  }

  // ── filter + sort ──
  function apply() {
    let list = ALL.filter((e) => {
      if (state.q && !e.name.toLowerCase().includes(state.q)) return false;
      if (state.zone && e.zone !== state.zone) return false;
      if (state.dmg && e.damage_type !== state.dmg) return false;
      if (state.onlyDefeated && !e.defeated) return false;
      // stat-based filters only match defeated (undefeated lack the data)
      if (state.tier && e.tier !== state.tier) return false;
      if (state.fear !== "" && (e.defeated ? (e.fear_aura ? "1" : "0") : "") !== state.fear) return false;
      return true;
    });

    const dir = state.sort.endsWith("asc") ? 1 : -1;
    const key = state.sort.split("-")[0];
    list.sort((a, b) => {
      if (key === "name") return dir * a.name.localeCompare(b.name, "pl");
      // stat sorts: defeated first (known), undefeated sink to the end
      const av = statVal(a, key), bv = statVal(b, key);
      if (av === null && bv === null) return a.name.localeCompare(b.name, "pl");
      if (av === null) return 1;
      if (bv === null) return -1;
      return dir * (av - bv);
    });

    render(list);
  }

  function statVal(e, key) {
    if (!e.defeated) return null;
    if (key === "hp") return e.hp_base ?? null;
    if (key === "tier") return TIER_ORDER[e.tier] ?? null;
    if (key === "level") return e.min_level ?? null;
    if (key === "xp") return e.xp_award ?? null;
    return null;
  }

  function render(list) {
    const cnt = document.getElementById("best-count");
    if (cnt) cnt.textContent = `${list.length} / ${ALL.length}`;
    grid.innerHTML = "";
    for (const e of list) {
      const card = document.createElement("button");
      card.className = "best-card" + (e.defeated ? " defeated" : "");
      card.innerHTML = `
        <div class="best-portrait">
          ${e.image_url ? `<img src="${esc(e.image_url)}" alt="${esc(e.name)}" loading="lazy">` : ""}
          ${e.defeated ? `<span class="best-badge" title="Pokonane">✦ ${e.kills}</span>` : ""}
          <span class="best-zone" title="${e.zone === "ranged" ? "Walczy na dystans" : "Walczy w zwarciu"}">${e.zone === "ranged" ? "🏹" : "⚔"}</span>
        </div>
        <div class="best-body">
          <div class="best-name">${esc(e.name)}</div>
          <div class="best-teaser">${esc(e.teaser || "")}</div>
        </div>`;
      card.onclick = () => openCard(e);
      grid.appendChild(card);
    }
    status.hidden = true;
    grid.hidden = false;
  }

  // ── card modal ──
  let modal;
  function ensureModal() {
    if (modal) return;
    modal = document.createElement("div");
    modal.className = "best-overlay";
    modal.innerHTML = `<div class="best-modal" role="dialog" aria-modal="true">
      <button class="best-x" aria-label="Zamknij">✕</button>
      <div class="best-modal-body"></div></div>`;
    document.body.appendChild(modal);
    modal.querySelector(".best-x").onclick = () => (modal.style.display = "none");
    modal.onclick = (ev) => { if (ev.target === modal) modal.style.display = "none"; };
  }

  function statRow(stats) {
    const order = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];
    return `<div class="card-stats">${order.map((k) =>
      `<div><b>${k}</b><span>${stats && stats[k] != null ? stats[k] : "–"}</span></div>`).join("")}</div>`;
  }

  function openCard(e) {
    ensureModal();
    const body = modal.querySelector(".best-modal-body");
    const zoneTxt = ZONE[e.zone] || "";
    const dmgTxt = DMG[e.damage_type] || e.damage_type || "";
    if (!e.defeated) {
      // Undefeated: no stat card. Portrait + coarse descriptors + unlock prompt.
      body.innerHTML = `
        <img class="best-modal-img" src="${esc(e.image_url)}" alt="${esc(e.name)}">
        <h2>${esc(e.name)}</h2>
        <div class="card-tags"><span>${zoneTxt}</span><span>Atak: ${esc(dmgTxt)}</span></div>
        <p class="best-modal-lore">${esc(e.teaser || "")}</p>
        <div class="card-locked">🔒 Pełna karta ze statystykami odsłoni się, gdy ${authed ? "pokonasz tego wroga w grze." : "zalogujesz się i pokonasz tego wroga."}</div>
        ${authed ? "" : `<button class="btn btn-gold" id="card-login">Zaloguj się</button>`}`;
      const b = body.querySelector("#card-login");
      if (b) b.onclick = () => window.AIGMAuth.openLogin();
    } else {
      const armour = Math.max(0, (e.ac_base || 10) - 10);
      const dmg = `${e.damage_die || "?"}${e.damage_bonus ? "+" + e.damage_bonus : ""}`;
      body.innerHTML = `
        <img class="best-modal-img" src="${esc(e.image_url)}" alt="${esc(e.name)}">
        <h2>${esc(e.name)} <span class="card-tier tier-${esc(e.tier)}">${TIER[e.tier] || esc(e.tier)}</span></h2>
        <div class="card-tags">
          <span>${zoneTxt}</span>
          <span>Atak: ${esc(dmgTxt)}</span>
          <span>✦ pokonany ${e.kills}×</span>
          ${e.fear_aura ? `<span class="card-fear">Groza (DC ${e.fear_dc ?? "?"})</span>` : ""}
        </div>
        <div class="card-grid">
          <div><label>HP</label><b>${e.hp_base ?? "?"}</b></div>
          <div><label>Pancerz</label><b>${armour}</b></div>
          <div><label>Atak</label><b>+${e.attack_bonus ?? 0}</b></div>
          <div><label>Obrażenia</label><b>${esc(dmg)}</b></div>
          <div><label>Ataki/turę</label><b>${e.attacks_per_turn ?? 1}</b></div>
          <div><label>Poziom</label><b>${e.min_level ?? 1}</b></div>
        </div>
        ${statRow(e.stats)}
        <p class="best-modal-lore">${esc(e.lore_text || e.description || "")}</p>`;
    }
    modal.style.display = "flex";
  }

  // ── boot ──
  if (window.AIGMAuth) window.AIGMAuth.onChange((u) => { renderNav(u); load(); });
  else load();
})();
