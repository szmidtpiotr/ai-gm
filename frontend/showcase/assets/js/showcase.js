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

  // --- hero background (graceful: only apply if image loads) ---
  const hero = document.querySelector('.hero[data-bg]');
  if (hero) {
    const src = hero.getAttribute('data-bg');
    const img = new Image();
    img.onload = () => { hero.style.setProperty('--hero-img', `url('${src}')`); hero.classList.add('has-bg'); };
    img.src = src;
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

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
})();
