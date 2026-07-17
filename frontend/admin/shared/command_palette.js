/**
 * command_palette.js — Wyszukiwarka funkcji admina.
 *
 * Cel: admin wpisuje nazwę funkcji ("tabele łupów", "presety LLM"), dostaje
 * listę wyników z krótkim opisem i po kliknięciu ląduje w odpowiedniej
 * zakładce (a jeśli funkcja siedzi w podzakładce — od razu w niej).
 *
 * Dwa wejścia, jeden UI wyników:
 *   • pole "🔍 Szukaj funkcji…" w sidebarze,
 *   • skrót Ctrl+K (Cmd+K) — otwiera ten sam overlay.
 *
 * Nawigacja: ustawia location.hash = '#<section>' albo '#<section>/<tab>'.
 * Router w index.html rozumie sufiks /<tab> i klika właściwy `.stab` (dowolny
 * atrybut data-*, bo sekcje używają różnych: data-tab/wtab/mtap/dtab/…).
 *
 * Dopasowanie odporne na brak polskich znaków (admini na telefonie piszą bez
 * ogonków). GOTCHA: NFD nie rozkłada "ł" — trzeba podmienić ręcznie.
 */
import { FEATURE_INDEX } from './feature_index.js?v=1';

// ── Normalizacja PL (mirror app/core/text_utils.strip_pl_diacritics) ──────────
function normPl(s) {
  return (s || '')
    .normalize('NFD').replace(/[̀-ͯ]/g, '')  // rozkłada ą ę ó ć ś ż ź ń
    .replace(/ł/g, 'l').replace(/Ł/g, 'l')   // NFD NIE rusza ł — ręcznie
    .toLowerCase()
    .trim();
}

// Prekomputowany "stóg siana" per wpis (title + opis + keywords + sekcja),
// plus rozbity na słowa — do dopasowania odpornego na fleksję PL.
const HAYSTACK = FEATURE_INDEX.map(e => {
  const hay = normPl([e.title, e.desc, e.keywords, e.sectionLabel].filter(Boolean).join(' '));
  return {
    entry: e,
    title: normPl(e.title),
    hay,
    words: hay.split(/[^a-z0-9]+/).filter(w => w.length >= 2),
  };
});

// Wspólny prefiks dwóch słów.
function commonPrefix(a, b) {
  const n = Math.min(a.length, b.length);
  let i = 0;
  while (i < n && a[i] === b[i]) i++;
  return i;
}

// Czy token pasuje do stogu? Krótki (<3) — czysty podciąg. Dłuższy — podciąg
// LUB wspólny rdzeń ze słowem stogu (łapie fleksję: "łupy"↔"łupów", "czar"↔"czary").
function tokenHits(token, h) {
  if (token.length < 3) return h.hay.includes(token);
  if (h.hay.includes(token)) return true;
  for (const w of h.words) {
    const cp = commonPrefix(token, w);
    if (cp >= 3 && cp >= Math.min(token.length, w.length) - 2) return true;
  }
  return false;
}

// Ranking: wszystkie tokeny zapytania muszą trafić w stóg. Punktacja premiuje
// dopasowanie na początku tytułu > w tytule > w opisie/keywords.
function search(query) {
  const q = normPl(query);
  if (!q) return [];
  const tokens = q.split(/\s+/).filter(Boolean);
  const out = [];
  for (const h of HAYSTACK) {
    if (!tokens.every(t => tokenHits(t, h))) continue;
    let score = 0;
    if (h.title.startsWith(q)) score += 100;
    else if (h.title.includes(q)) score += 60;
    if (tokens.every(t => h.title.includes(t))) score += 30;   // wszystkie tokeny dosłownie w tytule
    else if (tokens.every(t => h.words.some(w => commonPrefix(t, w) >= 3 && h.title.includes(w)))) score += 18;
    score -= h.title.length * 0.05;                             // krótszy tytuł = trafniejszy
    out.push({ entry: h.entry, title: h.title, score });
  }
  out.sort((a, b) => b.score - a.score);
  return out.slice(0, 12).map(x => x.entry);
}

function hashFor(entry) {
  return entry.tab ? `#${entry.section}/${entry.tab}` : `#${entry.section}`;
}

// ── Overlay UI ────────────────────────────────────────────────────────────────
let _els = null;      // { overlay, input, results }
let _matches = [];    // aktualne wyniki
let _active = 0;      // podświetlony indeks (klawiatura)

function buildOverlay() {
  if (_els) return _els;
  const overlay = document.createElement('div');
  overlay.className = 'cmdp-overlay';
  overlay.id = 'cmdp-overlay';
  overlay.innerHTML = `
    <div class="cmdp-box" role="dialog" aria-label="Wyszukiwarka funkcji">
      <div class="cmdp-input-row">
        <span class="cmdp-input-icon">🔍</span>
        <input class="cmdp-input" id="cmdp-input" type="text"
               placeholder="Szukaj funkcji… (np. tabele łupów, presety LLM)"
               autocomplete="off" spellcheck="false" aria-label="Szukaj funkcji">
        <kbd class="cmdp-esc">ESC</kbd>
      </div>
      <div class="cmdp-results" id="cmdp-results"></div>
      <div class="cmdp-foot"><kbd>↑</kbd><kbd>↓</kbd> nawigacja · <kbd>↵</kbd> otwórz · <kbd>ESC</kbd> zamknij</div>
    </div>`;
  document.body.appendChild(overlay);

  const input = overlay.querySelector('#cmdp-input');
  const results = overlay.querySelector('#cmdp-results');

  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  input.addEventListener('input', () => render(input.value));
  input.addEventListener('keydown', onKey);
  results.addEventListener('click', e => {
    const row = e.target.closest('.cmdp-row');
    if (row) go(Number(row.dataset.idx));
  });

  _els = { overlay, input, results };
  return _els;
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function render(query) {
  _matches = search(query);
  _active = 0;
  const { results } = _els;
  if (!query.trim()) {
    results.innerHTML = `<div class="cmdp-empty">Zacznij pisać, by znaleźć funkcję w panelu.</div>`;
    return;
  }
  if (!_matches.length) {
    results.innerHTML = `<div class="cmdp-empty">Brak wyników dla „${escapeHtml(query)}".</div>`;
    return;
  }
  results.innerHTML = _matches.map((m, i) => `
    <button class="cmdp-row${i === 0 ? ' active' : ''}" data-idx="${i}" type="button">
      <div class="cmdp-row-main">
        <span class="cmdp-row-title">${escapeHtml(m.title)}</span>
        <span class="cmdp-row-badge">${escapeHtml(m.sectionLabel || m.section)}</span>
      </div>
      <div class="cmdp-row-desc">${escapeHtml(m.desc || '')}</div>
    </button>`).join('');
}

function highlight() {
  const rows = _els.results.querySelectorAll('.cmdp-row');
  rows.forEach((r, i) => r.classList.toggle('active', i === _active));
  rows[_active]?.scrollIntoView({ block: 'nearest' });
}

function onKey(e) {
  if (e.key === 'Escape') { e.preventDefault(); close(); return; }
  if (e.key === 'ArrowDown') { e.preventDefault(); if (_matches.length) { _active = (_active + 1) % _matches.length; highlight(); } return; }
  if (e.key === 'ArrowUp')   { e.preventDefault(); if (_matches.length) { _active = (_active - 1 + _matches.length) % _matches.length; highlight(); } return; }
  if (e.key === 'Enter')     { e.preventDefault(); if (_matches.length) go(_active); return; }
}

function go(idx) {
  const entry = _matches[idx];
  if (!entry) return;
  close();
  const target = hashFor(entry);
  if (location.hash === target) {
    // Ten sam hash → hashchange nie odpali; ręcznie wywołaj router.
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else {
    location.hash = target;
  }
}

export function openPalette() {
  const { overlay, input } = buildOverlay();
  overlay.classList.add('open');
  input.value = '';
  render('');
  // focus po malowaniu — inaczej mobilna klawiatura bywa kapryśna
  requestAnimationFrame(() => input.focus());
}

function close() {
  _els?.overlay.classList.remove('open');
}

// ── Publiczny init — woła index.html ──────────────────────────────────────────
export function initCommandPalette() {
  // 1) Pole-trigger w sidebarze (nad nawigacją).
  const nav = document.getElementById('admin-nav');
  if (nav && !document.getElementById('cmdp-trigger')) {
    const trigger = document.createElement('button');
    trigger.id = 'cmdp-trigger';
    trigger.className = 'cmdp-trigger';
    trigger.type = 'button';
    trigger.innerHTML = `<span class="cmdp-trigger-icon">🔍</span><span class="cmdp-trigger-label">Szukaj funkcji…</span><kbd class="cmdp-trigger-kbd">Ctrl K</kbd>`;
    trigger.addEventListener('click', openPalette);
    nav.parentNode.insertBefore(trigger, nav);
  }

  // 2) Skrót Ctrl+K / Cmd+K — globalnie.
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      openPalette();
    }
  });
}
