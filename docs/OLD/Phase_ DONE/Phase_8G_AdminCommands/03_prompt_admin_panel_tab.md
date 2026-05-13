<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 3 — Frontend: Zakładka „Admin Commands” w panelu admin

> **STATUS: DONE — zakładka wdrożona.**

> **REV 2 — Prompt implementacyjny.** Pytania blokujące odpowiedziane na podstawie
> analizy kodu przez Perplexity (2026-04-30).

> **Zależność:** Wymaga gotowego backendu (PROMPT 1 ✔) i `admin_commands_tree.js` (PROMPT 2 ✔).

---

## Phase 8H — uwagi do `parseCmd` w panelu

- Funkcja **`parseCmd`** w `admin_commands.js` dla **`add weapon`** / **`add consumable`** zwraca `{ cmd: "add item", key, kind: "weapon"|"consumable" }` — **bez** narzucania prefiksów `weapon_`/`consumable_` w polu `key`; rozstrzyganie robi backend (`_resolve_inventory_add_key`).
- Zachowanie jest **spójne z czatem** (`parseAdminCommand` w `admin_commands_tree.js`).

---

## Odpowiedzi na pytania blokujące (ustalone z kodu)

1. **Branch/status:** sprawdzić przed startem (`git branch --show-current`, `git status --short`)
2. **Plik sekcji:** `frontend/admin_panel/sections/admin_commands.js` — wdrożony.
3. **Wersja `?v=` importów:** `config.js` używa `?v=17`. Nowa sekcja używa **`?v=1`**
   (tak jak `voice.js` i `ui_settings.js` — nowe sekcje startują od v=1).
4. **Mechanizm lazy-load:** każda sekcja ma własną funkcję `maybeInitXxx(section)` w `index.html`.
   `wireSidebarNav()` woła wszystkie `maybeInitXxx` przy każdym kliknięciu sidebar.
   Wzorzec — skopiować z `maybeInitVoice`.
5. **`GET /api/admin/characters` format:**
   `{ items: [{ id, name, campaign_id, user_id, campaign_title }] }`
6. **Stan postaci do karty:** używamy `POST /api/admin/cheat/{id}` z `{ cmd: "show state" }`
   (zamiast osobnego debug endpointu). Odpowiedź: `{ ok, cmd, result: { current_hp, max_hp,
   gold_gp, level, location, stats, quests_active, quests_completed, inventory } }`.
7. **`adminFetch` obsługa tokenu:** tak, automatycznie dołącza Bearer z localStorage.
8. **CSS klasy** (z `config.js` i `layout.css`):
   - karty: `admin-card`, `admin-card-title`, `two-col-cards`
   - przyciski: `primary-btn`, `secondary-btn`, `danger-btn`
   - banner: `warning-banner warning-banner-orange`
   - tabela: `admin-table`, `muted`
9. **`adminFetch` import:** `import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";`
   (używamy ustalonej wersji v=17 jak inne sekcje, nie v=1 — to dotyczy tylko sekcji JS).
10. **Backend `/admin/cheat` działa:** tak (PROMPT 1 zaliczone, healthcheck OK).

---

## Cel

Nowa zakładka **🛠 Admin Cmd** w panelu admin z:
1. Selectorem postaci (`GET /api/admin/characters`)
2. Terminalem komend (input + przycisk + historia in-memory)
3. Quick-action buttons (+100 GP, Full Heal, Clear Inventory, End Combat)
4. Kartą stanu postaci (odświeżana po każdej komendzie przez `show state`)

---

## Kontekst techniczny

**Nowe pliki:**
- `frontend/admin_panel/sections/admin_commands.js`

**Modyfikowane pliki:**
- `frontend/admin_panel/index.html` — sidebar button + section panel + `maybeInitAdminCommands` + call w `wireSidebarNav`

**NIE ruszamy:**
- Istniejące sekcje, `backend/`, `docker-compose.yml`, `data/ai_gm.db`

**Importy (identyczne jak inne sekcje):**
```js
import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";
```

---

## Implementacja — kroki

### Krok 1 — `frontend/admin_panel/index.html`

#### 1a — Dodaj button w `<nav id="sidebar-nav">` (po `voice`, przed `</nav>`):

```html
<button type="button" data-section="admin-commands">
  <span class="nav-icon">🛠</span>
  <span class="nav-label">Admin Cmd</span>
</button>
```

#### 1b — Dodaj panel w `<section class="sections">` (po ostatnim `section-panel`):

```html
<div class="section-panel" data-section="admin-commands" aria-busy="true"></div>
```

#### 1c — Dodaj flagę i funkcję lazy-load (wzorzec z `maybeInitVoice`):

W bloku zmiennych na górze `<script type="module">` dodaj:
```js
let adminCommandsReady = false;
```

Dodaj funkcję (po `maybeInitVoice`, przed `wireSidebarNav`):
```js
async function maybeInitAdminCommands(section) {
  if (section !== "admin-commands" || adminCommandsReady) {
    return;
  }
  const el = document.querySelector('.section-panel[data-section="admin-commands"]');
  if (!el) {
    return;
  }
  adminCommandsReady = true;
  el.removeAttribute("aria-busy");
  try {
    const { init } = await import("/admin_panel/sections/admin_commands.js?v=1");
    await init(el);
  } catch (err) {
    adminCommandsReady = false;
    el.textContent = "B\u0142\u0105d \u0142adowania Admin Commands.";
    showToast(err.message || "Admin Commands nie za\u0142adowa\u0142o si\u0119.", "error");
  }
}
```

#### 1d — Dodaj wywołanie w `wireSidebarNav()` (w bloku forEach, po `maybeInitVoice`):
```js
void maybeInitAdminCommands(selected);
```

---

### Krok 2 — Utwórz `frontend/admin_panel/sections/admin_commands.js`

```js
import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body?.detail) {
    const d = err.body.detail;
    return Array.isArray(d) ? d.join("; ") : String(d);
  }
  return fallback;
}

/**
 * Parsuje "/admin add gold 100" lub "add gold 100" na body request.
 * Wersja uproszczona dla panelu (bez dynamic import).
 */
function parseCmd(raw) {
  const t = (raw || '').trim().replace(/^\/admin\s*/i, '');
  const parts = t.split(/\s+/);
  const p0 = (parts[0] || '').toLowerCase();
  const p1 = (parts[1] || '').toLowerCase();
  const rest = parts.slice(2).join(' ');

  if (p0 === 'add' && (p1 === 'gold' || p1 === 'health')) {
    const v = rest.toLowerCase() === 'max' ? 'max' : parseInt(rest, 10);
    return { cmd: `add ${p1}`, value: isNaN(v) ? rest : v };
  }
  if (p0 === 'add' && p1 === 'weapon') {
    const key = rest ? rest.trim() : undefined;
    return { cmd: 'add item', key, kind: 'weapon' };
  }
  if (p0 === 'add' && p1 === 'consumable') {
    const key = rest ? rest.trim() : undefined;
    return { cmd: 'add item', key, kind: 'consumable' };
  }
  if (p0 === 'add' && p1 === 'item')   return { cmd: 'add item',   key: rest || undefined };
  if (p0 === 'add' && p1 === 'stat') {
    const stat = (parts[2] || '').toUpperCase();
    const val  = parseInt(parts[3] || '1', 10);
    return { cmd: 'add stat', stat, value: isNaN(val) ? 1 : val };
  }
  if (p0 === 'set' && (p1 === 'gold' || p1 === 'level')) {
    const v = parseInt(rest, 10);
    return { cmd: `set ${p1}`, value: isNaN(v) ? 0 : v };
  }
  if (p0 === 'set' && p1 === 'health') {
    const v = rest.toLowerCase() === 'max' ? 'max' : parseInt(rest, 10);
    return { cmd: 'set health', value: isNaN(v) ? rest : v };
  }
  if (p0 === 'set' && p1 === 'location') return { cmd: 'set location', key: rest || undefined };
  if (p0 === 'remove' && p1 === 'item')  return { cmd: 'remove item',  key: rest || undefined };
  if (p0 === 'clear' && p1 === 'inventory') return { cmd: 'clear inventory' };
  if (p0 === 'combat' && p1 === 'end')   return { cmd: 'combat end' };
  if (p0 === 'quest' && (p1 === 'add' || p1 === 'complete'))
    return { cmd: `quest ${p1}`, key: rest || undefined };
  if (p0 === 'show' && p1 === 'state')   return { cmd: 'show state' };
  return null;
}

export async function init(container) {
  container.innerHTML = '';
  container.classList.add('admin-commands-section');

  // Warning banner
  const banner = el('div', 'warning-banner warning-banner-orange');
  banner.textContent = '\u26a0\ufe0f Komendy modyfikuj\u0105 baz\u0119 bezpo\u015brednio. U\u017cywaj tylko na DEV/TEST.';
  container.appendChild(banner);

  // --- Selektor postaci ---
  const charRow = el('div', 'field');
  charRow.appendChild(el('label', '', 'Posta\u0107'));
  const charSelect = document.createElement('select');
  charSelect.className = 'admin-cmd-char-select';
  charSelect.style.maxWidth = '360px';
  const defaultOpt = el('option', '', '\u2014 wybierz posta\u0107 \u2014');
  defaultOpt.value = '';
  charSelect.appendChild(defaultOpt);
  charRow.appendChild(charSelect);
  container.appendChild(charRow);

  // Ładuj listę postaci
  try {
    const data = await adminFetch('/api/admin/characters');
    (data.items || []).forEach(c => {
      const opt = el('option', '', `[${c.id}] ${c.name} (${c.campaign_title})`);
      opt.value = String(c.id);
      charSelect.appendChild(opt);
    });
  } catch (e) {
    showToast(parseApiError(e, 'Nie można załadować postaci.'), 'error');
  }

  // --- Terminal ---
  const termCard = el('div', 'admin-card');
  termCard.style.marginTop = '16px';
  termCard.appendChild(el('h3', 'admin-card-title', 'Terminal'));

  const cmdRow = el('div', 'field');
  cmdRow.style.display = 'flex'; cmdRow.style.gap = '8px';
  const cmdInput = document.createElement('input');
  cmdInput.type = 'text';
  cmdInput.className = 'admin-cmd-input';
  cmdInput.placeholder = 'np. add gold 100  lub  set health max';
  cmdInput.style.flex = '1';
  const execBtn = el('button', 'primary-btn', '\u25b6 Wykonaj');
  execBtn.type = 'button';
  cmdRow.appendChild(cmdInput);
  cmdRow.appendChild(execBtn);
  termCard.appendChild(cmdRow);

  const historyEl = el('div', 'admin-cmd-history');
  historyEl.style.cssText = 'margin-top:10px; font-family:monospace; font-size:12px; max-height:180px; overflow-y:auto;';
  termCard.appendChild(historyEl);
  container.appendChild(termCard);

  // --- Quick actions ---
  const qaCard = el('div', 'admin-card');
  qaCard.style.marginTop = '16px';
  qaCard.appendChild(el('h3', 'admin-card-title', 'Quick Actions'));
  const qaRow = el('div', '');
  qaRow.style.cssText = 'display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;';

  const QUICK_ACTIONS = [
    { label: '\ud83d\udc9b +100 GP',        body: { cmd: 'add gold',       value: 100 } },
    { label: '\u2764\ufe0f Full Heal',        body: { cmd: 'set health',     value: 'max' } },
    { label: '\ud83d\uddd1 Clear Inventory', body: { cmd: 'clear inventory' } },
    { label: '\u2694\ufe0f End Combat',       body: { cmd: 'combat end' } },
  ];

  QUICK_ACTIONS.forEach(({ label, body }) => {
    const btn = el('button', 'secondary-btn', label);
    btn.type = 'button';
    btn.addEventListener('click', () => executeRaw(body, label));
    qaRow.appendChild(btn);
  });
  qaCard.appendChild(qaRow);
  container.appendChild(qaCard);

  // --- Karta stanu ---
  const stateCard = el('div', 'admin-card');
  stateCard.style.marginTop = '16px';
  stateCard.appendChild(el('h3', 'admin-card-title', 'Stan postaci'));
  const statePre = el('pre', 'muted');
  statePre.style.cssText = 'white-space:pre-wrap; font-size:12px; margin-top:8px;';
  statePre.textContent = '\u2014 wybierz posta\u0107 i wykonaj komend\u0119 \u2014';
  stateCard.appendChild(stateCard.appendChild(statePre) && stateCard.lastChild || statePre);
  container.appendChild(stateCard);

  // --- Historia ---
  /** @type {{time:string, label:string, ok:boolean, result:unknown}[]} */
  let cmdHistory = [];

  function addHistory(label, result, ok) {
    const time = new Date().toLocaleTimeString();
    cmdHistory.unshift({ time, label, result, ok });
    if (cmdHistory.length > 20) cmdHistory.pop();
    renderHistory();
  }

  function renderHistory() {
    historyEl.innerHTML = '';
    cmdHistory.forEach(({ time, label, result, ok }) => {
      const row = el('div', '');
      row.style.color = ok ? '#4caf50' : '#f44336';
      row.style.borderBottom = '1px solid #333';
      row.style.padding = '2px 0';
      const arrow = ok ? '\u2705' : '\u274c';
      row.textContent = `[${time}] ${arrow} ${label} \u2192 ${JSON.stringify(result)}`;
      historyEl.appendChild(row);
    });
  }

  async function refreshState(charId) {
    try {
      const res = await adminFetch(`/api/admin/cheat/${charId}`, {
        method: 'POST',
        body: JSON.stringify({ cmd: 'show state' }),
      });
      const r = res.result || {};
      statePre.textContent = [
        `HP:       ${r.current_hp ?? '?'}/${r.max_hp ?? '?'}`,
        `GP:       ${r.gold_gp ?? '?'}`,
        `Level:    ${r.level ?? '?'}`,
        `Location: ${r.location || '?'}`,
        `Stats:    ${JSON.stringify(r.stats || {})}`,
        `Items:    ${(r.inventory || []).join(', ') || '(brak)'}`,
        `Quests:   ${(r.quests_active || []).join(', ') || '(brak)'}`,
      ].join('\n');
    } catch (_e) {
      /* ignoruj — stan może być niedostępny dla walczącej postaci */
    }
  }

  async function executeRaw(body, label) {
    const charId = charSelect.value;
    if (!charId) { showToast('Wybierz posta\u0107.', 'info'); return; }
    try {
      const res = await adminFetch(`/api/admin/cheat/${charId}`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      addHistory(label, res.result, true);
      await refreshState(charId);
      showToast(`\u2705 ${label}`, 'success');
    } catch (e) {
      const msg = parseApiError(e, e.message || 'B\u0142\u0105d');
      addHistory(label, msg, false);
      showToast(`\u274c ${msg}`, 'error');
    }
  }

  execBtn.addEventListener('click', async () => {
    const raw = cmdInput.value.trim();
    if (!raw) return;
    const body = parseCmd(raw);
    if (!body) {
      showToast(`Nieznana komenda: ${raw}`, 'error');
      return;
    }
    await executeRaw(body, raw);
    cmdInput.value = '';
    cmdInput.focus();
  });

  cmdInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); execBtn.click(); }
  });

  // Odśwież stan przy zmianie postaci
  charSelect.addEventListener('change', async () => {
    const charId = charSelect.value;
    if (charId) await refreshState(charId);
  });
}
```

---

### Krok 3 — Weryfikacja

```bash
# 1. Brak rebuildla — pliki statyczne
# Wystarczy hard-refresh panelu: Ctrl+Shift+R na /admin_panel/

# 2. Sprawdź że zakładka się pojawia i ładuje sekcję
# → Kliknij "Admin Cmd" w sidebar
# → Pojawia się banner, select z postaciami, terminal, quick actions, karta stanu

# 3. Test manualny:
# a) Wybierz postać z listy
# b) Kliknij "💛 +100 GP" → toast success, karta stanu aktualizuje GP
# c) Kliknij "❤️ Full Heal" → karta stanu aktualizuje HP
# d) Wpisz: add gold 50 + Enter → historia pokazuje wynik
# e) Wpisz: show state + Enter → karta stanu się odświeża
# f) Wpisz złą komendę: xyz → toast error "Nieznana komenda"
# g) Bez wybranej postaci kliknij quick action → toast "Wybierz postać"
```

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Pliki dodane/zmienione: zgodnie z sekcją „Implementacja — kroki” powyżej oraz stanem repo (`index.html`, `admin_commands.js`).
- Test manualny (zakładka Admin Cmd w panelu): wykonany przy zamykaniu fazy 8G.
- Commit: zgodnie z historią gałęzi roboczej / sync do develop.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

- Dokumentacja zaktualizowana pod **Phase 8H**: podkreślone pole **`kind`** i brak wymogu prefiksów w panelu dla weapon/consumable.
