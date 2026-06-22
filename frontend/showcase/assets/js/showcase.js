/* AI-GM wizytówka — interakcje + data-driven sekcje. Faza W #903/#914. */
(() => {
  'use strict';
  document.documentElement.classList.add('js'); // gate scroll-reveal; bez JS treść widoczna

  // --- mobile nav toggle ---
  const toggle = document.querySelector('.nav-toggle');
  const links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => links.classList.toggle('open'));
    links.querySelectorAll('a').forEach(a => a.addEventListener('click', () => links.classList.remove('open')));
  }

  // --- active nav link on scroll (scrollspy) ---
  const navMap = {};
  document.querySelectorAll('.nav-links a[href^="#"]').forEach(a => {
    navMap[a.getAttribute('href').slice(1)] = a;
  });
  const spy = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      const link = navMap[e.target.id];
      if (!link) return;
      if (e.isIntersecting) {
        Object.values(navMap).forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  document.querySelectorAll('section[id]').forEach(s => spy.observe(s));

  // --- scroll reveal ---
  const revealer = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); revealer.unobserve(e.target); } });
  }, { threshold: 0.12 });
  document.querySelectorAll('.reveal').forEach(el => revealer.observe(el));

  // --- backgrounds (graceful: apply only if image loads) ---
  const hero = document.querySelector('.hero[data-bg]');
  if (hero) applyBg(hero, hero.getAttribute('data-bg'), '--hero-img');
  document.querySelectorAll('.sect[data-sect-bg]').forEach(s => applyBg(s, s.getAttribute('data-sect-bg'), '--sect-img'));
  function applyBg(el, src, varName) {
    if (!src) return;
    // Ścieżka ABSOLUTNA — relatywny url() w CSS-var rozwiązuje się względem pliku CSS,
    // nie dokumentu, co dawało /assets/css/assets/img/... => 404.
    const abs = new URL(src, document.baseURI).href;
    const img = new Image();
    img.onload = () => { el.style.setProperty(varName, `url("${abs}")`); el.classList.add('has-bg'); };
    img.src = abs;
  }

  // --- data-driven changelog (W6 generator → data/changelog.json) ---
  const clRoot = document.getElementById('changelog-list');
  if (clRoot) {
    fetch('data/changelog.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        const items = (data.entries || []).slice(0, 12);
        if (!items.length) return;
        clRoot.innerHTML = items.map(e => `
          <div class="cl-item reveal">
            <div class="when">${escapeHtml(e.when || e.date || '')}</div>
            <h3>${escapeHtml(e.title || e.version || '')}</h3>
            <ul>${(e.highlights || []).map(h => `<li>${escapeHtml(h)}</li>`).join('')}</ul>
          </div>`).join('');
        clRoot.querySelectorAll('.reveal').forEach(el => revealer.observe(el));
      })
      .catch(() => { /* placeholder text stays */ });
  }

  // --- data-driven historia (W3 → data/historia.json) ---
  const hRoot = document.getElementById('historia-list');
  if (hRoot) {
    fetch('data/historia.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        const stages = data.stages || [];
        if (!stages.length) return;
        const intro = data.intro ? `<p class="hist-intro reveal">${escapeHtml(data.intro)}</p>` : '';
        hRoot.innerHTML = intro + stages.map(s => `
          <div class="tl-item reveal">
            <div class="when">${escapeHtml(s.when || '')}</div>
            <h3>${escapeHtml(s.title || '')}</h3>
            ${String(s.body || '').split(/\n\n+/).map(p => `<p>${escapeHtml(p.trim())}</p>`).join('')}
          </div>`).join('');
        hRoot.querySelectorAll('.reveal').forEach(el => revealer.observe(el));
      })
      .catch(() => { /* fallback stubs zostają */ });
  }

  // --- data-driven świat (W4 → data/swiat.json) ---
  const krainyRoot = document.getElementById('krainy-list');
  if (krainyRoot) {
    fetch('data/swiat.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        const intro = document.getElementById('swiat-intro');
        if (intro && data.intro) intro.textContent = data.intro;
        if (Array.isArray(data.krainy) && data.krainy.length) {
          krainyRoot.innerHTML = data.krainy.map(k => {
            const locked = k.available === false;
            const href = k.anchor ? `swiat.html#${k.anchor}` : 'swiat.html';
            return `
            <a class="kraina reveal${locked ? ' locked' : ''}" href="${escapeHtml(href)}">
              ${k.img ? `<div class="thumb"><img src="${escapeHtml(k.img)}" alt="${escapeHtml(k.name || '')}" onerror="this.closest('.thumb').remove()">${locked ? '<span class="lock-badge">wkrótce</span>' : '<span class="play-badge">grywalne</span>'}</div>` : ''}
              <div class="body"><h3>${escapeHtml(k.name || '')}</h3><span class="ktag">${escapeHtml(k.tag || '')}</span><p>${escapeHtml(k.desc || '')}</p></div>
            </a>`;
          }).join('');
        }
        const rdzen = document.getElementById('rdzen-block');
        if (rdzen && data.rdzen) rdzen.innerHTML = `<h3>${escapeHtml(data.rdzen.title || '')}</h3><p>${escapeHtml(data.rdzen.body || '')}</p>`;
        const nap = document.getElementById('napiecia-list');
        if (nap && Array.isArray(data.napiecia) && data.napiecia.length) {
          nap.innerHTML = data.napiecia.map(n => `<div class="napiecie reveal"><h4>${escapeHtml(n.title || '')}</h4><p>${escapeHtml(n.body || '')}</p></div>`).join('');
        }
        document.querySelectorAll('#swiat .reveal').forEach(el => revealer.observe(el));
      })
      .catch(() => { /* fallback statyczny zostaje */ });
  }

  // --- FAQ + roadmapa (W12 → data/faq.json, data/roadmap.json) ---
  const faqRoot = document.getElementById('faq-list');
  if (faqRoot) {
    faqRoot.addEventListener('click', e => {
      const q = e.target.closest('.faq-q');
      if (q) q.closest('.faq-item').classList.toggle('open');
    });
    fetch('data/faq.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => {
        if (Array.isArray(d.faq) && d.faq.length) {
          faqRoot.innerHTML = d.faq.map(f => `
            <div class="faq-item"><button class="faq-q">${escapeHtml(f.q)}<span class="chev">▾</span></button>
            <div class="faq-a"><p>${escapeHtml(f.a)}</p></div></div>`).join('');
        }
      }).catch(() => { /* fallback statyczny zostaje */ });
  }
  const roadRoot = document.getElementById('roadmap-list');
  if (roadRoot) {
    fetch('data/roadmap.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => {
        if (Array.isArray(d.kolumny) && d.kolumny.length) {
          roadRoot.innerHTML = d.kolumny.map((c, i) => `
            <div class="road-col s${i}"><h3>${escapeHtml(c.status)}</h3>
            <ul>${(c.items || []).map(it => `<li>${escapeHtml(it)}</li>`).join('')}</ul></div>`).join('');
        }
      }).catch(() => { /* fallback statyczny zostaje */ });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
})();
