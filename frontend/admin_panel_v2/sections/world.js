import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";
import { renderTable, showConfirm } from "/admin_panel_v2/shared/table.js?v=9";
import { openModal } from "/admin_panel_v2/shared/modal.js?v=1";
import { openSmartEntry } from "/admin_panel_v2/shared/smart_entry.js?v=5";

const LABELS = {
  locations:    "Lokacje",
  npcs:         "Postacie NPC",
  enemies:      "Wrogowie",
  key:          "Klucz",
  label:        "Nazwa",
  type:         "Typ",
  parentKey:    "Lokacja nadrzędna",
  description:  "Opis",
  isActive:     "Aktywny",
  isShop:       "Sklep",
  personality:  "Osobowość (JSON)",
  shopInv:      "Ekwipunek sklepu (JSON)",
  locationKeys: "Klucze lokacji (przecinki)",
  addLocation:  "Dodaj lokację",
  addNpc:       "Dodaj NPC",
  addEnemy:     "Dodaj wroga",
  npcType:      "Typ NPC",
  save:         "Zapisz",
  cancel:       "Anuluj",
  locked:       "Blokada",
  tiers: { weak: "Słaby", standard: "Standardowy", elite: "Elita", boss: "Boss" },
  damageTypes: { physical: "Fizyczne", fire: "Ogień", cold: "Zimno", poison: "Trucizna", magic: "Magia" },
};

const NPC_TYPES = [
  { value: "neutral",     label: "Neutralny" },
  { value: "merchant",    label: "Kupiec" },
  { value: "quest_giver", label: "Dawca zadań" },
  { value: "ally",        label: "Sojusznik" },
];

const LOC_TYPES = [
  { value: "macro", label: "Makro" },
  { value: "sub",   label: "Pod-lokacja" },
];

// Stage 2B-Schema: enums for provenance + reuse fields
const LOC_SUBTYPES = [
  { value: "",                label: "— nieokreślony —" },
  { value: "tavern",          label: "Karczma / Tawerna" },
  { value: "inn",             label: "Zajazd" },
  { value: "shop",            label: "Sklep" },
  { value: "temple",          label: "Świątynia" },
  { value: "guild",           label: "Cech / Gildia" },
  { value: "village",         label: "Wioska" },
  { value: "town",            label: "Miasteczko" },
  { value: "city",            label: "Miasto" },
  { value: "castle",          label: "Zamek / Twierdza" },
  { value: "ruin",            label: "Ruiny" },
  { value: "cave",            label: "Jaskinia" },
  { value: "dungeon",         label: "Loch" },
  { value: "tower",           label: "Wieża" },
  { value: "watchtower",      label: "Strażnica" },
  { value: "forest_clearing", label: "Polana leśna" },
  { value: "camp",            label: "Obóz" },
  { value: "road",            label: "Droga / Trakt" },
  { value: "bridge",          label: "Most" },
  { value: "crossroads",      label: "Rozdroże" },
  { value: "graveyard",       label: "Cmentarz" },
  { value: "swamp_hut",       label: "Chata na mokradłach" },
  { value: "mine",            label: "Kopalnia" },
  { value: "harbor",          label: "Port" },
  { value: "other",           label: "Inne" },
];

const LOC_BIOMES = [
  { value: "",         label: "— nieokreślony —" },
  { value: "forest",   label: "Las" },
  { value: "mountain", label: "Góry" },
  { value: "swamp",    label: "Bagna" },
  { value: "plains",   label: "Równiny" },
  { value: "coast",    label: "Wybrzeże" },
  { value: "desert",   label: "Pustynia" },
  { value: "tundra",   label: "Tundra" },
  { value: "urban",    label: "Tereny miejskie" },
  { value: "underground", label: "Podziemia" },
];

const LOC_TIERS = [
  { value: 1, label: "Tier 1 (lvl 1-2)" },
  { value: 2, label: "Tier 2 (lvl 3-4)" },
  { value: 3, label: "Tier 3 (lvl 5-6)" },
  { value: 4, label: "Tier 4 (lvl 7-8)" },
  { value: 5, label: "Tier 5 (lvl 9+)" },
];

const LOC_REVIEW_STATUS = {
  pending_review: { label: "⏳ Oczekuje",   class: "admin-badge-gold"   },
  permanent:      { label: "✓ Permanentna", class: "admin-badge-green"  },
  discarded:      { label: "✕ Odrzucona",   class: "admin-badge-muted"  },
};

const LOC_CREATED_BY = {
  seed:          { label: "Seed",     class: "admin-badge-gold" },
  admin_manual:  { label: "Admin",    class: "admin-badge-blue" },
  admin_kreator: { label: "Kreator",  class: "admin-badge-purple" },
  gm_runtime:    { label: "GM",       class: "admin-badge-orange" },
  import:        { label: "Import",   class: "admin-badge-muted" },
};

const LOCATION_RULES = [
  { key: "no_combat",        label: "No Combat",        type: "boolean", description: "Combat forbidden (temples, safe zones)" },
  { key: "no_loot",          label: "No Loot",          type: "boolean", description: "Enemies don't drop loot" },
  { key: "teleport_blocked", label: "Teleport Blocked", type: "boolean", description: "Teleportation spells don't work" },
  { key: "stealth_check",    label: "Stealth Check",    type: "boolean", description: "Entry requires successful stealth roll" },
  { key: "rest_bonus",       label: "Rest Bonus",       type: "number",  default: 2,         description: "HP regen multiplier (2 = 2× HP)" },
  { key: "mana_regen",       label: "Mana Regen",       type: "number",  default: 0,         description: "Natural mana regen (0 = none)" },
  { key: "required_item",    label: "Required Item",    type: "text",    default: "torch",   description: "Item key required to enter" },
  { key: "reason",           label: "Reason",           type: "text",    default: "Sacred ground", description: "Reason shown to player" },
];

const TABS = ["builder", "terrain", "locations", "npcs", "enemies", "loot-tables", "pending"];
const _rendered = new Set();
let _aiTrigger = null;

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-content">
      <div class="subtab-bar">
        <button class="subtab-btn active" data-tab="builder">🗺 Mapa Świata</button>
        <button class="subtab-btn" data-tab="terrain">🌿 Typy Terenu</button>
        <button class="subtab-btn" data-tab="locations">📍 Lokacje</button>
        <button class="subtab-btn" data-tab="npcs">${LABELS.npcs}</button>
        <button class="subtab-btn" data-tab="enemies">${LABELS.enemies}</button>
        <button class="subtab-btn" data-tab="loot-tables">💰 Tabele łupów</button>
        <button class="subtab-btn" data-tab="pending">⏳ Oczekujące <span id="pending-nav-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
      </div>
      <div class="subtab-panels">
        ${TABS.map((t) => `<div class="subtab-panel${t === "builder" ? " active" : ""}" data-tab="${t}"></div>`).join("")}
      </div>
    </div>`;

  _rendered.clear();
  _aiTrigger = null;

  panel.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      panel.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
      panel.querySelectorAll(".subtab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      panel.querySelector(`.subtab-panel[data-tab="${tab}"]`).classList.add("active");
      _aiTrigger = null;
      _activateTab(panel, tab);
    });
  });

  await _activateTab(panel, "builder");
}

async function _activateTab(panel, tab) {
  if (_rendered.has(tab)) return;
  _rendered.add(tab);
  const container = panel.querySelector(`.subtab-panel[data-tab="${tab}"]`);
  if (!container) return;
  if      (tab === "locations") await _renderLocations(container);
  else if (tab === "npcs")      await _renderNpcs(container);
  else if (tab === "enemies")   await _renderEnemies(container);
  else if (tab === "loot-tables") {
    const { _renderLootTables } = await import("/admin_panel_v2/sections/content.js?v=23");
    await _renderLootTables(container, panel);
  }
  else if (tab === "terrain")   await _renderTerrainConfig(container);
  else if (tab === "pending")   await _renderPendingReview(container, panel);
  else if (tab === "builder") {
    const { init: initBuilder } = await import("/admin_panel_v2/sections/world_builder.js?v=8");
    await initBuilder(container);
  }
}

// ── AI generation helper ──────────────────────────────────────────────────────

async function _openAiGenerateModal({ entityType, title, onFill }) {
  const { openModal } = await import("/admin_panel_v2/shared/modal.js?v=1");
  const { showToast } = await import("/admin_panel_v2/shared/toast.js?v=1");

  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="modal-form">
      <label class="modal-field">
        <span>Brief</span>
        <textarea name="brief" rows="4" placeholder="Opisz krótko postać/miejsce/wroga…" style="width:100%"></textarea>
      </label>
      <div id="ai-gen-result" style="display:none;margin-top:10px">
        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:6px">Podgląd (edytowalny po wstawieniu)</div>
        <pre id="ai-gen-json" style="font-size:0.75rem;background:var(--bg-elevated);padding:10px;border-radius:6px;overflow:auto;max-height:200px;white-space:pre-wrap"></pre>
      </div>
    </div>`;

  let generated = null;

  openModal({
    title,
    content: wrap,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (c) => c() },
      {
        label: "Generuj AI",
        class: "secondary-btn",
        onClick: async (_c, btn) => {
          const brief = wrap.querySelector('[name="brief"]').value.trim();
          if (brief.length < 3) { showToast("Podaj brief.", "info"); return; }
          btn.disabled = true; btn.textContent = "Generuję…";
          try {
            const data = await (await import("/admin_panel_v2/shared/api.js?v=3")).adminFetch(
              "/api/admin/campaign-designer/generate-entity",
              { method: "POST", body: JSON.stringify({ entity_type: entityType, brief }) }
            );
            generated = data.entity;
            wrap.querySelector("#ai-gen-result").style.display = "block";
            wrap.querySelector("#ai-gen-json").textContent = JSON.stringify(generated, null, 2);
            btn.textContent = "Generuj ponownie";
          } catch (e) {
            showToast(e.message || "Błąd generowania.", "error");
          } finally {
            btn.disabled = false;
          }
        },
      },
      {
        label: "Wstaw do formularza",
        class: "primary-btn",
        onClick: (c) => {
          if (!generated) { showToast("Najpierw wygeneruj.", "info"); return; }
          c();
          onFill(generated);
        },
      },
    ],
  });
}

// ── Location rules editor ─────────────────────────────────────────────────────

function _buildRulesEditor(currentRules) {
  const wrap = document.createElement("div");
  wrap.className = "rules-editor";

  // Predefined rules
  const presetSection = document.createElement("div");
  presetSection.className = "rules-preset-section";
  const checkboxes = [];
  const valueInputs = {};

  LOCATION_RULES.forEach(rule => {
    const isChecked = rule.key in currentRules;
    const row = document.createElement("div");
    row.className = "rule-row";

    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.name = `rule_${rule.key}`; cb.checked = isChecked;
    checkboxes.push({ rule, cb });

    const label = document.createElement("label");
    label.className = "rule-row-label";
    label.appendChild(cb);
    label.innerHTML += ` <strong>${rule.label}</strong> <span class="rule-desc">${rule.description}</span>`;
    row.appendChild(label);

    if (rule.type !== "boolean") {
      const inp = document.createElement("input");
      inp.type = rule.type === "number" ? "number" : "text";
      inp.className = "field-input rule-value-input";
      inp.placeholder = String(rule.default ?? "");
      inp.value = isChecked ? String(currentRules[rule.key] ?? rule.default ?? "") : "";
      inp.style.display = isChecked ? "block" : "none";
      inp.style.marginTop = "4px";
      inp.dataset.ruleKey = rule.key;
      valueInputs[rule.key] = inp;
      cb.addEventListener("change", () => { inp.style.display = cb.checked ? "block" : "none"; });
      row.appendChild(inp);
    }

    presetSection.appendChild(row);
  });
  wrap.appendChild(presetSection);

  // Custom rules
  const customSection = document.createElement("div");
  customSection.className = "rules-custom-section";

  const customHeader = document.createElement("div");
  customHeader.className = "rules-custom-header";
  customHeader.innerHTML = `<span style="font-size:0.78rem;font-weight:600;color:var(--text-muted)">Własne reguły</span>`;
  const addCustomBtn = document.createElement("button");
  addCustomBtn.type = "button"; addCustomBtn.className = "secondary-btn"; addCustomBtn.style.fontSize = "0.75rem";
  addCustomBtn.textContent = "+ Dodaj";
  const aiRuleBtn = document.createElement("button");
  aiRuleBtn.type = "button"; aiRuleBtn.className = "secondary-btn"; aiRuleBtn.style.fontSize = "0.75rem";
  aiRuleBtn.textContent = "✨ AI";
  aiRuleBtn.title = "Generuj regułę z AI";
  customHeader.appendChild(addCustomBtn);
  customHeader.appendChild(aiRuleBtn);
  customSection.appendChild(customHeader);

  const customList = document.createElement("div");
  customList.className = "rules-custom-list";
  customSection.appendChild(customList);
  wrap.appendChild(customSection);

  // Pre-populate custom rules (any keys not in LOCATION_RULES)
  const knownKeys = new Set(LOCATION_RULES.map(r => r.key));
  Object.entries(currentRules).forEach(([k, v]) => {
    if (!knownKeys.has(k)) _addCustomRuleRow(customList, k, String(v));
  });

  addCustomBtn.addEventListener("click", () => _addCustomRuleRow(customList, "", ""));

  aiRuleBtn.addEventListener("click", async () => {
    const brief = prompt("Opisz krótko efekt reguły (np. 'gracze tracą 1 HP co turę z powodu trucizny'):");
    if (!brief) return;
    aiRuleBtn.disabled = true; aiRuleBtn.textContent = "⏳";
    try {
      const data = await adminFetch("/api/admin/campaign-designer/generate-entity", {
        method: "POST",
        body: JSON.stringify({ entity_type: "rule", brief }),
      });
      const rule = data.entity || {};
      _addCustomRuleRow(customList, rule.key || "", rule.value !== undefined ? String(rule.value) : "");
      showToast("Reguła wygenerowana.", "success");
    } catch (e) {
      showToast(e.message || "Błąd generowania.", "error");
    } finally { aiRuleBtn.disabled = false; aiRuleBtn.textContent = "✨ AI"; }
  });

  // Store references for _getRulesFromEditor
  wrap._checkboxes   = checkboxes;
  wrap._valueInputs  = valueInputs;
  wrap._customList   = customList;
  return wrap;
}

function _addCustomRuleRow(list, key, value) {
  const row = document.createElement("div");
  row.className = "rule-custom-row";
  row.innerHTML = `
    <input type="text" class="field-input rule-custom-key" placeholder="klucz_reguły" value="${_esc(key)}" style="flex:1;min-width:80px" />
    <input type="text" class="field-input rule-custom-val" placeholder="wartość" value="${_esc(value)}" style="flex:1;min-width:80px" />
    <button type="button" class="icon-btn rule-custom-del" style="color:var(--accent-red)">✕</button>`;
  row.querySelector(".rule-custom-del").addEventListener("click", () => row.remove());
  list.appendChild(row);
}

function _getRulesFromEditor(wrap) {
  const result = {};
  (wrap._checkboxes || []).forEach(({ rule, cb }) => {
    if (!cb.checked) return;
    if (rule.type === "boolean") {
      result[rule.key] = true;
    } else {
      const inp = wrap._valueInputs[rule.key];
      const raw = inp ? inp.value.trim() : String(rule.default ?? "");
      result[rule.key] = rule.type === "number" ? Number(raw) : raw;
    }
  });
  (wrap._customList?.querySelectorAll(".rule-custom-row") || []).forEach(row => {
    const k = row.querySelector(".rule-custom-key").value.trim();
    const v = row.querySelector(".rule-custom-val").value.trim();
    if (k) {
      const n = Number(v);
      result[k] = (v === "true") ? true : (v === "false") ? false : (Number.isFinite(n) && v !== "") ? n : v;
    }
  });
  return result;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _tryJson(str, fallback) {
  if (!str || !String(str).trim()) return { ok: true, value: fallback };
  try { return { ok: true, value: JSON.parse(str) }; }
  catch { return { ok: false, value: null }; }
}

function _field(label, content) {
  const lbl = document.createElement("label");
  lbl.className = "modal-field";
  lbl.innerHTML = `<span>${label}</span>${content}`;
  return lbl;
}

function _checkbox(name, labelText, checked = false) {
  const lbl = document.createElement("label");
  lbl.className = "modal-checkbox-row";
  lbl.innerHTML = `<input type="checkbox" name="${name}" ${checked ? "checked" : ""}><span>${labelText}</span>`;
  return lbl;
}

// ── Locations ─────────────────────────────────────────────────────────────────

// Icon map for location subtypes used in the accordion tree view
const _LOC_ICONS = {
  tavern: "🍺", inn: "🏠", shop: "🏪", temple: "⛪", guild: "🏛", village: "🏡",
  town: "🏘", city: "🏙", castle: "🏰", ruin: "🏚", cave: "🗻", dungeon: "🕳",
  tower: "🗼", watchtower: "🛡", forest_clearing: "🌿", camp: "⛺", road: "🛣",
  bridge: "🌉", crossroads: "🔀", graveyard: "☠", swamp_hut: "🌫", mine: "⛏",
  harbor: "⚓", other: "•",
  // extended subtypes from seed
  "port-city": "⚓", "trade-city": "🏪", "port": "⚓", "pirate-haven": "🏴‍☠️",
  "religious-city": "⛪", "mining-village": "⛏", "burned-village": "🔥",
  "bridge-town": "🌉", "lumber-village": "🪓", hermitage: "🏡", "wayside-inn": "🏠",
  "haunted-forest": "👻", "undead-forest": "💀", "swamp-forest": "🌿",
  "elven-woods": "🌟", "mountain-range": "🏔", volcano: "🌋", "frozen-peaks": "❄️",
  "ruined-monastery": "🏚", "vampire-crypt": "🧛", "cursed-mine": "⛏",
  "haunted-fortress": "👹", "ancient-temple": "🌀", "misty-marsh": "🌫",
  "wolf-steppe": "🐺", "salt-desert": "🏜", "sorrow-coast": "🌊",
  "frozen-tundra": "❄️", garrison: "🛡", shrine: "🕯", library: "📚",
  smithy: "⚒️", arena: "⚔️", monastery: "⛩", slum: "🌆", "port-city": "⚓",
  wilderness: "🌄", river: "🌊", mountain: "⛰️", forest: "🌲", garden: "🌿",
  tomb: "⚰️", market: "🛒", fortress: "🏰",
};
const _locIcon = (loc) =>
  _LOC_ICONS[loc.location_subtype] || _LOC_ICONS[loc.biome] ||
  (loc.location_type === "macro" ? "📍" : "·");

async function _renderLocations(container) {
  // ── Toolbar ──────────────────────────────────────────────────────────
  const toolbar = document.createElement("div");
  toolbar.className = "tab-toolbar";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addLocation;
  toolbar.appendChild(addBtn);
  const kreatorBtn = document.createElement("button");
  kreatorBtn.className = "subtab-btn";
  kreatorBtn.id = "loc-smart-entry-btn";
  kreatorBtn.title = "AI asystent tworzenia lokacji";
  kreatorBtn.style.marginLeft = "auto";
  kreatorBtn.textContent = "🤖 Kreator AI";
  kreatorBtn.addEventListener("click", () => openSmartEntry("game_locations"));
  toolbar.appendChild(kreatorBtn);
  container.appendChild(toolbar);

  // ── Filters bar ──────────────────────────────────────────────────────
  const filtersBar = document.createElement("div");
  filtersBar.className = "loc-filters-bar";
  filtersBar.innerHTML = `
    <input class="loc-search" type="text" placeholder="Szukaj lokacji…" />
    <select class="loc-filter" data-filter="biome">
      <option value="">Wszystkie biomy</option>
      ${LOC_BIOMES.filter(b => b.value).map(b => `<option value="${b.value}">${b.label}</option>`).join("")}
    </select>
    <select class="loc-filter" data-filter="created_by">
      <option value="">Wszystkie źródła</option>
      ${Object.entries(LOC_CREATED_BY).map(([v, m]) => `<option value="${v}">${m.label}</option>`).join("")}
    </select>
    <select class="loc-filter" data-filter="review_status">
      <option value="">Wszystkie statusy</option>
      ${Object.entries(LOC_REVIEW_STATUS).map(([v, m]) => `<option value="${v}">${m.label}</option>`).join("")}
    </select>
    <button class="secondary-btn loc-expand-all" title="Rozwiń wszystkie makro-lokacje">+ Rozwiń</button>
    <button class="secondary-btn loc-collapse-all" title="Zwiń wszystkie makro-lokacje">− Zwiń</button>
  `;
  container.appendChild(filtersBar);

  // ── Tree host ─────────────────────────────────────────────────────────
  const treeHost = document.createElement("div");
  treeHost.className = "loc-tree";
  container.appendChild(treeHost);

  let locations = [];
  const expandedSet = new Set();
  const filterState = { search: "", biome: "", created_by: "", review_status: "" };

  // Cleanup listeners when container leaves DOM
  const _onSmartSave = (e) => { if (e?.detail?.table === "game_locations") load(); };
  window.addEventListener("smart-entry-saved", _onSmartSave);
  const _obs = new MutationObserver(() => {
    if (!document.contains(container)) {
      window.removeEventListener("smart-entry-saved", _onSmartSave);
      _obs.disconnect();
    }
  });
  _obs.observe(document.body, { childList: true, subtree: true });

  // ── Helpers ───────────────────────────────────────────────────────────
  const _byLabel = (a, b) => String(a.label || "").localeCompare(String(b.label || ""), "pl");
  const _esc = (s) => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

  const _matchesFilter = (loc) => {
    const s = filterState.search.toLowerCase();
    if (s && !loc.label?.toLowerCase().includes(s) && !loc.key?.toLowerCase().includes(s)) return false;
    if (filterState.biome && loc.biome !== filterState.biome) return false;
    if (filterState.created_by && loc.created_by !== filterState.created_by) return false;
    if (filterState.review_status && loc.review_status !== filterState.review_status) return false;
    return true;
  };

  const _tierBadge = (loc) => {
    if (!loc.tier) return "";
    const cls = ["","admin-badge-green","admin-badge-gold","admin-badge-orange","admin-badge-red","admin-badge-red"][Math.min(loc.tier,5)] || "admin-badge-muted";
    return `<span class="admin-badge ${cls} loc-badge">T${loc.tier}</span>`;
  };
  const _biomeBadge = (loc) => {
    if (!loc.biome) return "";
    const m = LOC_BIOMES.find(b => b.value === loc.biome);
    return `<span class="admin-badge admin-badge-muted loc-badge">${m ? m.label : loc.biome}</span>`;
  };
  const _sourceBadge = (loc) => {
    const info = LOC_CREATED_BY[loc.created_by] || LOC_CREATED_BY.admin_manual;
    return `<span class="admin-badge ${info.class} loc-badge">${info.label}</span>`;
  };
  const _safeBadge = (loc) =>
    loc.safe_for_rest ? `<span class="admin-badge admin-badge-green loc-badge" title="Bezpieczny odpoczynek">🛏</span>` : "";

  const _attachRowActions = (actionsEl, loc) => {
    const editBtn = document.createElement("button");
    editBtn.className = "secondary-btn loc-action-btn";
    editBtn.textContent = "Edytuj";
    editBtn.addEventListener("click", () => {
      const orig = locations.find(l => l.key === loc.key) || loc;
      _openLocationModal(orig, locations, load);
    });
    actionsEl.appendChild(editBtn);

    if ((loc.review_status || "permanent") === "permanent") {
      const revertBtn = document.createElement("button");
      revertBtn.className = "secondary-btn loc-action-btn";
      revertBtn.textContent = "↩ Review";
      revertBtn.title = "Cofnij do oczekujących";
      revertBtn.addEventListener("click", async () => {
        try {
          await adminFetch(`/api/locations/admin/locations/${loc.key}`, {
            method: "PATCH",
            body: JSON.stringify({ review_status: "pending_review", approved: 0 }),
          });
          showToast("Cofnięto do review.", "success");
          await load();
        } catch (e) {
          showToast("Błąd: " + (e.message || "?"), "error");
        }
      });
      actionsEl.appendChild(revertBtn);
    }

    const delBtn = document.createElement("button");
    delBtn.className = "secondary-btn loc-action-btn loc-action-btn--danger";
    delBtn.textContent = "Usuń";
    delBtn.addEventListener("click", async () => {
      if (!confirm(`Usunąć lokację "${loc.label}"?`)) return;
      try {
        await adminFetch(`/api/locations/${loc.key}`, { method: "DELETE" });
        showToast("Usunięto.", "success");
        await load();
      } catch (e) {
        if (e?.status === 404) { showToast("Już usunięte.", "info"); await load(); return; }
        if (e?.status === 422) {
          const msg = e?.body?.detail || "Ma aktywne podlokalizacje.";
          if (confirm(`${msg}\n\nCzy usunąć lokację razem z wszystkimi podlokalizacjami?`)) {
            try {
              await adminFetch(`/api/locations/${loc.key}?force=true`, { method: "DELETE" });
              showToast("Usunięto (z podlokalizacjami).", "success");
              await load();
            } catch (e2) {
              showToast("Błąd: " + (e2.message || "?"), "error");
            }
          }
          return;
        }
        showToast("Błąd: " + (e.message || "?"), "error");
      }
    });
    actionsEl.appendChild(delBtn);
  };

  // ── Hover tooltip (singleton per _renderLocations call) ──────────────
  const tip = document.createElement("div");
  tip.className = "loc-tooltip";
  tip.hidden = true;
  document.body.appendChild(tip);
  let _tipTimer = null;

  const _showTip = (loc, anchorEl) => {
    const biomeLabel  = LOC_BIOMES.find(b => b.value === loc.biome)?.label || loc.biome || "—";
    const subtypeLabel = LOC_SUBTYPES.find(s => s.value === loc.location_subtype)?.label || loc.location_subtype || "—";
    const sourceInfo  = LOC_CREATED_BY[loc.created_by] || LOC_CREATED_BY.admin_manual;
    const enemyCount  = Array.isArray(loc.enemy_keys) ? loc.enemy_keys.length : 0;
    const desc = loc.description ? _esc(loc.description) : "<em style='color:var(--text-muted)'>Brak opisu.</em>";

    tip.innerHTML = `
      <div class="loc-tip-header">
        <span class="loc-tip-icon">${_locIcon(loc)}</span>
        <span class="loc-tip-name">${_esc(loc.label || loc.key)}</span>
        ${loc.canonical ? `<span class="loc-tip-canon" title="Kanoniczne">⭐</span>` : ""}
      </div>
      <div class="loc-tip-key">${_esc(loc.key)}</div>
      <div class="loc-tip-divider"></div>
      <div class="loc-tip-desc">${desc}</div>
      <div class="loc-tip-divider"></div>
      <div class="loc-tip-meta">
        <span class="loc-tip-meta-item"><b>Biom</b> ${biomeLabel}</span>
        <span class="loc-tip-meta-item"><b>Tier</b> ${loc.tier ?? "—"}</span>
        <span class="loc-tip-meta-item"><b>Podtyp</b> ${subtypeLabel}</span>
        <span class="loc-tip-meta-item"><b>Odpoczynek</b> ${loc.safe_for_rest ? "✓" : "✗"}</span>
        <span class="loc-tip-meta-item"><b>Wrogowie</b> ${enemyCount}</span>
        <span class="loc-tip-meta-item"><b>Wizyt</b> ${loc.usage_count ?? 0}</span>
        <span class="loc-tip-meta-item"><b>Źródło</b> ${sourceInfo.label}</span>
      </div>
    `;

    tip.hidden = false;

    // Position: below the row, flip up if near bottom of viewport
    const rect = anchorEl.getBoundingClientRect();
    const tipH = 200; // estimated, corrected below after paint
    const spaceBelow = window.innerHeight - rect.bottom;
    const top = spaceBelow > tipH + 8
      ? rect.bottom + 6
      : rect.top - tipH - 6;
    const left = Math.min(rect.left, window.innerWidth - 340);
    tip.style.top  = `${top + window.scrollY}px`;
    tip.style.left = `${Math.max(8, left)}px`;

    // Re-adjust vertically after real paint
    requestAnimationFrame(() => {
      const realH = tip.offsetHeight;
      const adjustedTop = spaceBelow > realH + 8
        ? rect.bottom + 6
        : rect.top - realH - 6;
      tip.style.top = `${adjustedTop + window.scrollY}px`;
    });
  };

  const _hideTip = () => {
    clearTimeout(_tipTimer);
    tip.hidden = true;
  };

  const _attachHover = (row, loc) => {
    row.addEventListener("mouseenter", () => {
      clearTimeout(_tipTimer);
      _tipTimer = setTimeout(() => _showTip(loc, row), 1500);
    });
    row.addEventListener("mouseleave", _hideTip);
    // Also hide immediately if user starts clicking
    row.addEventListener("mousedown", _hideTip);
  };

  // Cleanup tooltip when container leaves DOM
  const _tipObs = new MutationObserver(() => {
    if (!document.contains(container)) {
      _hideTip();
      tip.remove();
      _tipObs.disconnect();
    }
  });
  _tipObs.observe(document.body, { childList: true, subtree: true });

  // ── Row builders ──────────────────────────────────────────────────────
  const _makeMacroRow = (loc, subCount, isExpanded, onToggle) => {
    const row = document.createElement("div");
    row.className = `loc-row loc-row--macro${isExpanded ? " loc-row--expanded" : ""}`;

    const toggleBtn = document.createElement("button");
    toggleBtn.className = "loc-toggle";
    toggleBtn.title = isExpanded ? "Zwiń pod-lokacje" : "Rozwiń pod-lokacje";
    toggleBtn.textContent = isExpanded ? "−" : "+";
    toggleBtn.addEventListener("click", (e) => { e.stopPropagation(); onToggle(); });
    row.appendChild(toggleBtn);

    row.insertAdjacentHTML("beforeend", `
      <span class="loc-icon">${_locIcon(loc)}</span>
      <span class="loc-label">${_esc(loc.label || loc.key)}</span>
      <span class="loc-key">${_esc(loc.key)}</span>
      <span class="loc-sub-count">${subCount} pod-lok.</span>
      ${_biomeBadge(loc)}${_tierBadge(loc)}${_safeBadge(loc)}${_sourceBadge(loc)}
    `);

    const actionsEl = document.createElement("span");
    actionsEl.className = "loc-actions";
    _attachRowActions(actionsEl, loc);
    row.appendChild(actionsEl);
    _attachHover(row, loc);
    return row;
  };

  const _makeSubRow = (loc, orphan = false) => {
    const row = document.createElement("div");
    row.className = `loc-row loc-row--sub${orphan ? " loc-row--orphan" : ""}`;
    row.insertAdjacentHTML("beforeend", `
      <span class="loc-sub-indent"><span class="loc-sub-glyph">└</span></span>
      <span class="loc-icon">${_locIcon(loc)}</span>
      <span class="loc-label">${_esc(loc.label || loc.key)}</span>
      <span class="loc-key">${_esc(loc.key)}</span>
      ${_biomeBadge(loc)}${_tierBadge(loc)}${_safeBadge(loc)}${_sourceBadge(loc)}
    `);
    const actionsEl = document.createElement("span");
    actionsEl.className = "loc-actions";
    _attachRowActions(actionsEl, loc);
    row.appendChild(actionsEl);
    _attachHover(row, loc);
    return row;
  };

  // ── Render tree ───────────────────────────────────────────────────────
  const render = () => {
    treeHost.innerHTML = "";

    const locById = new Map(locations.map(l => [l.id, l]));
    const macros = locations.filter(l => l.location_type === "macro").sort(_byLabel);
    const subsByParent = new Map();
    const orphanSubs = [];

    for (const l of locations) {
      if (l.location_type === "macro") continue;
      const parent = l.parent_id != null ? locById.get(l.parent_id) : null;
      if (parent?.location_type === "macro") {
        if (!subsByParent.has(parent.id)) subsByParent.set(parent.id, []);
        subsByParent.get(parent.id).push(l);
      } else {
        orphanSubs.push(l);
      }
    }

    const hasFilter = Object.values(filterState).some(Boolean);
    let count = 0;

    for (const macro of macros) {
      const subs = (subsByParent.get(macro.id) || []).sort(_byLabel);
      const macroMatch = _matchesFilter(macro);
      const matchingSubs = subs.filter(_matchesFilter);

      if (hasFilter && !macroMatch && matchingSubs.length === 0) continue;

      // Auto-expand when filter has matching subs
      const isExpanded = expandedSet.has(macro.id) || (hasFilter && matchingSubs.length > 0);

      treeHost.appendChild(
        _makeMacroRow(macro, subs.length, isExpanded, () => {
          if (expandedSet.has(macro.id)) expandedSet.delete(macro.id);
          else expandedSet.add(macro.id);
          render();
        })
      );
      count++;

      if (isExpanded) {
        const visibleSubs = hasFilter ? matchingSubs : subs;
        for (const sub of visibleSubs) {
          treeHost.appendChild(_makeSubRow(sub));
          count++;
        }
      }
    }

    for (const sub of orphanSubs.sort(_byLabel)) {
      if (hasFilter && !_matchesFilter(sub)) continue;
      treeHost.appendChild(_makeSubRow(sub, true));
      count++;
    }

    if (count === 0) {
      treeHost.innerHTML = `<div class="loc-empty">Brak lokacji spełniających kryteria.</div>`;
    }
  };

  // ── Load data ─────────────────────────────────────────────────────────
  const load = async () => {
    treeHost.innerHTML = `<div class="loc-loading">Ładowanie lokacji…</div>`;
    try {
      locations = await adminFetch("/api/locations/admin/locations?active_only=1");
    } catch (e) {
      showToast("Błąd ładowania lokacji: " + (e.message || "?"), "error");
      treeHost.innerHTML = `<div class="loc-empty">Błąd ładowania danych.</div>`;
      return;
    }
    render();
  };

  // ── Filter events ─────────────────────────────────────────────────────
  filtersBar.querySelector(".loc-search").addEventListener("input", function() {
    filterState.search = this.value;
    render();
  });
  filtersBar.querySelectorAll(".loc-filter").forEach(sel => {
    sel.addEventListener("change", function() {
      filterState[this.dataset.filter] = this.value;
      render();
    });
  });
  filtersBar.querySelector(".loc-expand-all").addEventListener("click", () => {
    locations.filter(l => l.location_type === "macro").forEach(m => expandedSet.add(m.id));
    render();
  });
  filtersBar.querySelector(".loc-collapse-all").addEventListener("click", () => {
    expandedSet.clear();
    render();
  });

  addBtn.addEventListener("click", () => _openLocationModal(null, locations, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "location",
    title: "Generuj lokację z AI",
    onFill: (e) => _openLocationModal(e, locations, load),
  });

  await load();
}

function _openLocationModal(row, allLocations, onDone) {
  const isEdit = !!row;
  const macros = allLocations.filter((l) => l.location_type === "macro");

  const form = document.createElement("div");
  form.className = "modal-form";

  form.appendChild(_field(`${LABELS.key} *`,
    `<input type="text" name="key" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. tavern_main" autocomplete="off" />`));
  form.appendChild(_field(`${LABELS.label} *`,
    `<input type="text" name="label" value="${_esc(row?.label ?? "")}" placeholder="np. Tawerna" autocomplete="off" />`));

  form.appendChild(_field(LABELS.type,
    `<select name="location_type">
      ${LOC_TYPES.map((t) => `<option value="${t.value}" ${(row?.location_type ?? "macro") === t.value ? "selected" : ""}>${t.label}</option>`).join("")}
    </select>`));

  form.appendChild(_field(LABELS.parentKey,
    `<select name="parent_key">
      <option value="">— brak —</option>
      ${macros.map((m) => `<option value="${_esc(m.key)}" ${row?.parent_key === m.key ? "selected" : ""}>${_esc(m.label)} (${_esc(m.key)})</option>`).join("")}
    </select>`));

  form.appendChild(_field(LABELS.description,
    `<textarea name="description" rows="3">${_esc(row?.description ?? "")}</textarea>`));

  // ── Rules editor ──
  const rulesDiv = _buildRulesEditor(row?.rules || {});
  const rulesLabel = document.createElement("div");
  rulesLabel.innerHTML = `<span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary);display:block;margin-bottom:6px">Reguły lokacji</span>`;
  rulesLabel.appendChild(rulesDiv);
  form.appendChild(rulesLabel);

  // ── Stage 2B-Schema provenance & reuse fields ──
  form.appendChild(_field("Podtyp",
    `<select name="location_subtype">
      ${LOC_SUBTYPES.map((s) => `<option value="${_esc(s.value)}" ${(row?.location_subtype ?? "") === s.value ? "selected" : ""}>${_esc(s.label)}</option>`).join("")}
    </select>`));

  form.appendChild(_field("Biom",
    `<select name="biome">
      ${LOC_BIOMES.map((b) => `<option value="${_esc(b.value)}" ${(row?.biome ?? "") === b.value ? "selected" : ""}>${_esc(b.label)}</option>`).join("")}
    </select>`));

  form.appendChild(_field("Tier (1-5)",
    `<select name="tier">
      ${LOC_TIERS.map((t) => `<option value="${t.value}" ${Number(row?.tier ?? 1) === t.value ? "selected" : ""}>${_esc(t.label)}</option>`).join("")}
    </select>`));

  form.appendChild(_checkbox("canonical", "⭐ Kanoniczna (preferowana przez GM)", row?.canonical ?? !isEdit));
  form.appendChild(_checkbox("safe_for_rest", "🛏 Bezpieczne miejsce odpoczynku (Stage 2B)", !!row?.safe_for_rest));
  form.appendChild(_checkbox("is_active", LABELS.isActive, row?.is_active ?? true));

  // Read-only provenance footer (when editing)
  if (isEdit && row?.created_by) {
    const meta = LOC_CREATED_BY[row.created_by] || LOC_CREATED_BY.admin_manual;
    const provInfo = document.createElement("div");
    provInfo.style.cssText = "margin-top:8px;padding:6px 10px;background:var(--bg-elevated);border-radius:4px;font-size:0.8rem;color:var(--text-secondary)";
    const usageTxt = (row.usage_count ?? 0) > 0 ? ` · wizyt: <strong>${row.usage_count}</strong>` : "";
    const srcCampaign = row.source_campaign_id ? ` · z kampanii #${row.source_campaign_id}` : "";
    provInfo.innerHTML = `Źródło: <span class="admin-badge ${meta.class}">${meta.label}</span>${srcCampaign}${usageTxt}`;
    form.appendChild(provInfo);
  }

  const { close } = openModal({
    title:   isEdit ? `Edytuj lokację: ${row.key}` : LABELS.addLocation,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : "Dodaj",
        class: "primary-btn",
        onClick: async (c) => {
          const key         = form.querySelector('[name="key"]').value.trim();
          const label       = form.querySelector('[name="label"]').value.trim();
          const loc_type    = form.querySelector('[name="location_type"]').value;
          const parent_key  = form.querySelector('[name="parent_key"]').value || null;
          const description = form.querySelector('[name="description"]').value.trim();
          const is_active   = form.querySelector('[name="is_active"]').checked;
          const safe_for_rest = form.querySelector('[name="safe_for_rest"]').checked;
          const canonical   = form.querySelector('[name="canonical"]').checked;
          const location_subtype = form.querySelector('[name="location_subtype"]').value || null;
          const biome       = form.querySelector('[name="biome"]').value || null;
          const tier        = parseInt(form.querySelector('[name="tier"]').value, 10) || 1;
          const rules_json  = _getRulesFromEditor(rulesDiv);  // sent as "rules" to API

          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }

          const body = {
            key, label, location_type: loc_type, parent_key, description,
            rules: rules_json, is_active, safe_for_rest,
            location_subtype, biome, tier, canonical,
          };

          try {
            if (isEdit) {
              // PATCH /admin/locations/{key} handles partial updates incl. all new fields.
              await adminFetch(`/api/locations/admin/locations/${row.key}`, {
                method: "PATCH", body: JSON.stringify(body),
              });
            } else {
              // POST canonical create endpoint (NOT /admin/locations — that's GET/PATCH only).
              await adminFetch("/api/locations", {
                method: "POST", body: JSON.stringify(body),
              });
            }
            showToast(isEdit ? "Zapisano." : "Dodano lokację.", "success");
            c();
            await onDone();
          } catch (e) {
            showToast((e.message || "Błąd zapisu"), "error");
          }
        },
      },
    ],
  });
}

// ── NPCs ──────────────────────────────────────────────────────────────────────

async function _renderNpcs(container) {
  const toolbar = document.createElement("div");
  toolbar.className = "tab-toolbar";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addNpc;
  toolbar.appendChild(addBtn);
  container.appendChild(toolbar);

  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try {
      const data = await adminFetch("/api/admin/npcs");
      rows = (data.data || data.items || []).map(r => ({
        ...r,
        _location_keys_text: Array.isArray(r.location_keys)
          ? r.location_keys.join(", ")
          : (r.location_keys_json ? JSON.stringify(r.location_keys_json) : ""),
      }));
    } catch (e) {
      showToast("Błąd ładowania NPC: " + (e.message || "?"), "error");
      return;
    }

    // Compute a per-row "roles" summary for display ("🪙 📜 🤝" or "neutralny")
    rows = rows.map(r => {
      const tokens = [];
      if (Number(r.is_shop))        tokens.push("🪙");
      if (Number(r.is_quest_giver)) tokens.push("📜");
      if (Number(r.is_ally))        tokens.push("🤝");
      return { ...r, _roles_display: tokens.length ? tokens.join(" ") : "neutralny" };
    });

    const columns = [
      { key: "id",       label: "ID",          editable: false },
      { key: "key",      label: LABELS.key,    editable: false },
      { key: "label",    label: LABELS.label,  editable: true },
      {
        key: "_roles_display", label: "Role", editable: false,
        // Tooltip listing each role spelled out
        formatDisplay: (r) => {
          const ts = [];
          if (Number(r.is_shop))        ts.push("🪙 Kupiec");
          if (Number(r.is_quest_giver)) ts.push("📜 Dawca zadań");
          if (Number(r.is_ally))        ts.push("🤝 Sojusznik");
          return ts.length ? ts.join(" · ") : "neutralny";
        },
      },
      { key: "_location_keys_text", label: "Lokacje",            editable: false, popup: true },
      { key: "is_shop",             label: "🪙 Kupiec",          type: "boolean", editable: true },
      { key: "is_quest_giver",      label: "📜 Quest",           type: "boolean", editable: true },
      { key: "is_ally",             label: "🤝 Sojusznik",       type: "boolean", editable: true },
      { key: "is_active",           label: LABELS.isActive,      type: "boolean", editable: true },
      { key: "description",         label: LABELS.description,   editable: true, popup: true },
      { key: "personality_json",    label: "Osobowość JSON",     editable: true, popup: true },
      { key: "shop_inventory_json", label: "Ekwipunek sklepu",   editable: true, popup: true },
      { key: "locked_at",           label: LABELS.locked,        type: "locked",  editable: false },
    ];

    renderTable(tableHost, columns, rows, {
      tableId:           "npcs",
      selectable:        true,
      showTextSearch:    true,
      searchPlaceholder: "Szukaj NPC…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        let apiVal = newVal;
        // personality_json and shop_inventory_json must be sent as strings
        if (colKey === "personality_json" || colKey === "shop_inventory_json") {
          const p = _tryJson(String(newVal), null);
          if (!p.ok) { showToast("Nieprawidłowy JSON.", "error"); throw new Error("bad json"); }
          apiVal = JSON.stringify(p.value);
        }
        try {
          await adminFetch(`/api/npcs/${row.id}`, {
            method: "PATCH",
            body:   JSON.stringify({ [colKey]: apiVal, ...(force ? { force: true } : {}) }),
          });
          showToast("Zapisano.", "success");
          await load();
        } catch (e) {
          showToast("Błąd zapisu: " + (e.message || "?"), "error");
          throw e;
        }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/npcs/${row.id}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success");
          await load();
        } catch (e) {
          showToast("Błąd usuwania: " + (e.message || "?"), "error");
          throw e;
        }
      },
      extraActions: (row) => [
        {
          label: "Edytuj",
          class: "secondary-btn",
          onClick: () => _openNpcModal(row, load),
        },
      ],
    });
  };

  addBtn.addEventListener("click", () => _openNpcModal(null, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "npc",
    title: "Generuj NPC z AI",
    onFill: (e) => _openNpcModal(e, load),
  });
  await load();
}

async function _openNpcModal(row, onDone) {
  const isEdit = !!row;
  const persJson = row?.personality_json
    ? (typeof row.personality_json === "string" ? row.personality_json : JSON.stringify(row.personality_json, null, 2))
    : "{}";
  const shopJson = row?.shop_inventory_json
    ? (typeof row.shop_inventory_json === "string" ? row.shop_inventory_json : JSON.stringify(row.shop_inventory_json, null, 2))
    : "[]";
  const currentLocKeys = new Set(Array.isArray(row?.location_keys) ? row.location_keys : []);

  const form = document.createElement("div");
  form.className = "modal-form";

  form.appendChild(_field(`${LABELS.key} *`,
    `<input type="text" name="key" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. innkeeper" autocomplete="off" />`));
  form.appendChild(_field(`${LABELS.label} *`,
    `<input type="text" name="label" value="${_esc(row?.label ?? "")}" placeholder="np. Karczmarz" autocomplete="off" />`));

  // Multi-role checkboxes (mirror AP1 pending modal). Backend re-derives the
  // single-value `npc_type` column from these flags. For legacy rows where
  // booleans weren't set (raw INSERTs), pre-fill the matching flag from
  // npc_type so the modal shows a sensible starting state.
  const flagsSum = Number(row?.is_shop || 0) + Number(row?.is_quest_giver || 0) + Number(row?.is_ally || 0);
  const legacyType = flagsSum === 0 ? (row?.npc_type || "neutral") : null;
  const roleField = document.createElement("div");
  roleField.className = "ea-field";
  roleField.innerHTML = `
    <label>Role (możesz zaznaczyć więcej niż jedną)</label>
    <div class="ea-role-group">
      <label class="ea-role-check">
        <input type="checkbox" name="is_shop"        ${Number(row?.is_shop) || legacyType === "merchant"    ? "checked" : ""}>
        <span class="ea-role-label">🪙 Kupiec</span><span class="ea-role-hint">handluje przedmiotami</span>
      </label>
      <label class="ea-role-check">
        <input type="checkbox" name="is_quest_giver" ${Number(row?.is_quest_giver) || legacyType === "quest_giver" ? "checked" : ""}>
        <span class="ea-role-label">📜 Dawca zadań</span><span class="ea-role-hint">oferuje questy / haki fabularne</span>
      </label>
      <label class="ea-role-check">
        <input type="checkbox" name="is_ally"        ${Number(row?.is_ally) || legacyType === "ally"        ? "checked" : ""}>
        <span class="ea-role-label">🤝 Sojusznik</span><span class="ea-role-hint">może dołączyć do drużyny</span>
      </label>
    </div>
    <div class="ea-field-hint">Wszystkie odznaczone = neutralny (tylko rozmowa).</div>`;
  form.appendChild(roleField);

  form.appendChild(_field(LABELS.description,
    `<textarea name="description" rows="3">${_esc(row?.description ?? "")}</textarea>`));
  form.appendChild(_field(LABELS.personality,
    `<textarea name="personality_json" rows="4">${_esc(persJson)}</textarea>`));

  // ── Location checkbox list ──
  const locFieldWrap = document.createElement("div");
  const locLabel = document.createElement("span");
  locLabel.style.cssText = "font-size:0.8rem;font-weight:600;color:var(--text-secondary);display:block;margin-bottom:6px";
  locLabel.textContent = LABELS.locationKeys;
  locFieldWrap.appendChild(locLabel);

  const locListWrap = document.createElement("div");
  locListWrap.className = "npc-location-list";
  locListWrap.innerHTML = `<p style="font-size:0.78rem;color:var(--text-muted);padding:8px">Ładowanie lokacji…</p>`;
  locFieldWrap.appendChild(locListWrap);
  form.appendChild(locFieldWrap);

  // Load locations async and render checkboxes
  adminFetch("/api/locations/admin/locations").then(data => {
    const locs = Array.isArray(data) ? data : (data.locations ?? data.items ?? []);
    if (!locs.length) {
      locListWrap.innerHTML = `<p style="font-size:0.78rem;color:var(--text-muted);padding:8px">Brak lokacji.</p>`;
      return;
    }
    locListWrap.innerHTML = "";
    locs.forEach(l => {
      const item = document.createElement("label");
      item.className = "npc-location-item";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.name = "location_key_cb";
      cb.value = l.key;
      cb.checked = currentLocKeys.has(l.key);
      item.appendChild(cb);
      const txt = document.createElement("span");
      txt.innerHTML = `<strong>${_esc(l.label)}</strong> <code style="font-size:0.72rem;color:var(--text-muted)">${_esc(l.key)}</code>`;
      item.appendChild(txt);
      locListWrap.appendChild(item);
    });
  }).catch(() => {
    locListWrap.innerHTML = `<p style="font-size:0.78rem;color:var(--accent-red);padding:8px">Błąd ładowania lokacji.</p>`;
  });

  // Shop inventory JSON shown only when the 🪙 Kupiec role is ticked (in the
  // role-group above). is_shop standalone checkbox removed — the role group
  // is the single source of truth for that flag.
  const isShopInitial = Number(row?.is_shop) || legacyType === "merchant";
  const shopInvWrap = document.createElement("div");
  shopInvWrap.id = "shop-inv-wrap";
  shopInvWrap.style.display = isShopInitial ? "" : "none";
  shopInvWrap.appendChild(_field(LABELS.shopInv,
    `<textarea name="shop_inventory_json" rows="4">${_esc(shopJson)}</textarea>`));
  form.appendChild(shopInvWrap);

  form.appendChild(_checkbox("is_active", LABELS.isActive, row?.is_active ?? true));

  // Reactively show/hide shop inventory when the merchant role checkbox flips.
  roleField.querySelector('[name="is_shop"]').addEventListener("change", (e) => {
    shopInvWrap.style.display = e.target.checked ? "" : "none";
  });

  openModal({
    title:   isEdit ? `Edytuj NPC: ${row.label}` : LABELS.addNpc,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : "Dodaj",
        class: "primary-btn",
        onClick: async (c) => {
          const key            = form.querySelector('[name="key"]').value.trim();
          const label          = form.querySelector('[name="label"]').value.trim();
          const description    = form.querySelector('[name="description"]').value.trim();
          const is_shop        = form.querySelector('[name="is_shop"]').checked;
          const is_quest_giver = form.querySelector('[name="is_quest_giver"]').checked;
          const is_ally        = form.querySelector('[name="is_ally"]').checked;
          const is_active      = form.querySelector('[name="is_active"]').checked;
          const location_keys  = Array.from(
            form.querySelectorAll('[name="location_key_cb"]:checked')
          ).map(cb => cb.value);

          if (!key)   { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }

          const persRaw = form.querySelector('[name="personality_json"]').value.trim() || "{}";
          const pJSON = _tryJson(persRaw, {});
          if (!pJSON.ok) { showToast("Osobowość musi być poprawnym JSON.", "error"); return; }

          // Backend derives npc_type from the role flags. No need to send it.
          const body = {
            key, label, description,
            is_shop:        is_shop        ? 1 : 0,
            is_quest_giver: is_quest_giver ? 1 : 0,
            is_ally:        is_ally        ? 1 : 0,
            is_active:      is_active      ? 1 : 0,
            personality_json: JSON.stringify(pJSON.value),
            location_keys,
          };

          if (is_shop) {
            const shopRaw = form.querySelector('[name="shop_inventory_json"]').value.trim() || "[]";
            const sJSON = _tryJson(shopRaw, []);
            if (!sJSON.ok) { showToast("Ekwipunek sklepu musi być poprawnym JSON.", "error"); return; }
            body.shop_inventory_json = JSON.stringify(sJSON.value);
          }

          try {
            if (isEdit) {
              await adminFetch(`/api/npcs/${row.id}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/npcs", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano NPC.", "success");
            c();
            await onDone();
          } catch (e) {
            showToast((e.message || "Błąd zapisu"), "error");
          }
        },
      },
    ],
  });
}

// ── Enemies ───────────────────────────────────────────────────────────────────

async function _renderEnemies(container) {
  const toolbar = document.createElement("div");
  toolbar.className = "tab-toolbar";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ " + LABELS.addEnemy;
  toolbar.appendChild(addBtn);
  container.appendChild(toolbar);

  const tableHost = document.createElement("div");
  container.appendChild(tableHost);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows, lootOpts = [];
    try {
      const [enemyData, lootData] = await Promise.all([
        adminFetch("/api/admin/enemies"),
        adminFetch("/api/admin/loot-tables").catch(() => ({ items: [] })),
      ]);
      rows = (enemyData.items || []).map(r => ({
        ...r,
        _skills: r.skills_json ? JSON.stringify(r.skills_json) : "{}",
        _ci:     Array.isArray(r.conditions_immune) ? JSON.stringify(r.conditions_immune) : "[]",
        _drop_pct: r.drop_chance != null ? Math.round(Number(r.drop_chance) * 100) : 0,
      }));
      lootOpts = (lootData.items || []).map(t => ({ value: t.key, label: t.label || t.key }));
    } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",              label: LABELS.key,   editable: false },
      { key: "label",            label: LABELS.label, editable: true },
      { key: "tier",             label: "Poziom",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.tiers),
        formatDisplay: (r) => LABELS.tiers[r.tier] || r.tier,
        badgeClass: (r) => ({ weak: "admin-badge-muted", standard: "admin-badge-blue", elite: "admin-badge-gold", boss: "admin-badge-red" }[r.tier] ?? "admin-badge-muted"),
        filterOptions: Object.entries(LABELS.tiers).map(([v,l])=>({value:v,label:l})),
      },
      { key: "hp_base",          label: "HP",          type: "number", editable: true },
      { key: "ac_base",          label: "AC",          type: "number", editable: true },
      { key: "attack_bonus",     label: "Atk+",        type: "number", editable: true },
      { key: "damage_die",       label: "Kość",        editable: true },
      { key: "damage_bonus",     label: "Dmg+",        type: "number", editable: true },
      { key: "attacks_per_turn", label: "Atk/turę",    type: "number", editable: true },
      { key: "damage_type",      label: "Typ dmg",
        type: "badge", editType: "select",
        editOptions: Object.keys(LABELS.damageTypes),
        badgeClass: (r) => ({ fire:"admin-badge-red", magic:"admin-badge-blue", poison:"admin-badge-green", cold:"admin-badge-muted" }[r.damage_type] ?? "admin-badge-muted"),
        filterOptions: Object.entries(LABELS.damageTypes).map(([v,l])=>({value:v,label:l})),
      },
      { key: "xp_award",         label: "XP",          type: "number", editable: true },
      { key: "loot_table_key",   label: "Loot",        type: "select-dropdown", editable: true, editOptions: [{ value: "", label: "— brak —" }, ...lootOpts] },
      { key: "_drop_pct",        label: "Drop %",      type: "number", editable: true,
        formatDisplay: (r) => r.drop_chance != null ? Math.round(Number(r.drop_chance) * 100) + "%" : "—" },
      { key: "_skills",          label: "Skills JSON", editable: true, popup: true },
      { key: "_ci",              label: "Immune JSON", editable: true, popup: true },
      { key: "note",             label: "Notatka",     editable: true, popup: true },
      { key: "description",      label: "Opis",        editable: true, popup: true },
      { key: "is_active",        label: LABELS.isActive, type: "boolean", editable: true },
      { key: "locked_at",        label: LABELS.locked,   type: "locked",  editable: false },
    ];

    renderTable(tableHost, cols, rows, {
      tableId: "enemies",
      selectable: true,
      showTextSearch: true, searchPlaceholder: "Szukaj wrogów…",
      async onEdit(row, colKey, newVal, { force } = {}) {
        // Map computed display keys back to actual API fields
        const apiKey = colKey === "_skills" ? "skills_json"
                     : colKey === "_ci"     ? "conditions_immune"
                     : colKey === "_drop_pct" ? "drop_chance"
                     : colKey;
        let apiVal = newVal;
        if (colKey === "_skills" || colKey === "_ci") {
          try { apiVal = JSON.parse(newVal); } catch { showToast("Nieprawidłowy JSON.", "error"); throw new Error("bad json"); }
        }
        if (colKey === "_drop_pct") apiVal = Number(newVal) / 100;
        try {
          await adminFetch(`/api/admin/enemies/${row.key}`, { method: "PATCH", body: JSON.stringify({ [apiKey]: apiVal, ...(force ? { force: true } : {}) }) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row, { force } = {}) {
        try {
          await adminFetch(`/api/admin/enemies/${row.key}${force ? "?force=true" : ""}`, { method: "DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openEnemyModal(row, load) }],
    });
  };

  addBtn.addEventListener("click", () => _openEnemyModal(null, load));
  _aiTrigger = () => _openAiGenerateModal({
    entityType: "enemy",
    title: "Generuj wroga z AI",
    onFill: (e) => _openEnemyModal(e, load),
  });
  await load();
}

// ── Rules library ─────────────────────────────────────────────────────────────

const RULES_STORAGE_KEY = "aigm_admin2_rule_presets";

function _loadRulePresets() {
  try { return JSON.parse(localStorage.getItem(RULES_STORAGE_KEY) || "[]"); } catch { return []; }
}
function _saveRulePresets(list) {
  try { localStorage.setItem(RULES_STORAGE_KEY, JSON.stringify(list)); } catch {}
}

async function _renderRules(container) {
  container.innerHTML = "";

  // ── Section 1: Predefined rules reference ──
  const refSection = document.createElement("div");
  refSection.className = "rules-section-wrap";
  refSection.innerHTML = `
    <div class="rules-section-header">
      <span class="system-section-title" style="font-size:0.72rem">Wbudowane reguły lokacji</span>
      <span class="system-help-text">Gotowe do użycia w każdej lokacji. Zaznacz w edytorze lokacji.</span>
    </div>
    <table class="sys-table" style="margin-bottom:20px">
      <thead><tr><th>Klucz</th><th>Nazwa</th><th>Typ</th><th>Domyślnie</th><th>Opis</th></tr></thead>
      <tbody>
        ${LOCATION_RULES.map(r => `
          <tr>
            <td><code style="font-size:0.72rem;color:var(--text-link)">${_esc(r.key)}</code></td>
            <td><strong>${_esc(r.label)}</strong></td>
            <td><span class="admin-badge ${r.type === "boolean" ? "admin-badge-blue" : r.type === "number" ? "admin-badge-gold" : "admin-badge-muted"}">${_esc(r.type)}</span></td>
            <td>${r.default !== undefined ? _esc(String(r.default)) : "—"}</td>
            <td style="color:var(--text-muted);font-size:0.78rem">${_esc(r.description)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  container.appendChild(refSection);

  // ── Section 2: Custom rule presets ──
  const presetsSection = document.createElement("div");
  presetsSection.className = "rules-section-wrap";

  const presetsHeader = document.createElement("div");
  presetsHeader.className = "rules-section-header";
  presetsHeader.innerHTML = `
    <span class="system-section-title" style="font-size:0.72rem">Szablony reguł (własne zestawy)</span>
    <span class="system-help-text">Zapisz zestaw reguł pod nazwą, by szybko stosować go do lokacji.</span>`;

  const addPresetBtn = document.createElement("button");
  addPresetBtn.className = "primary-btn";
  addPresetBtn.style.marginLeft = "auto";
  addPresetBtn.textContent = "+ Nowy szablon";
  presetsHeader.appendChild(addPresetBtn);
  presetsSection.appendChild(presetsHeader);

  const presetsList = document.createElement("div");
  presetsList.className = "rules-presets-list";
  presetsSection.appendChild(presetsList);
  container.appendChild(presetsSection);

  const renderPresets = () => {
    const presets = _loadRulePresets();
    presetsList.innerHTML = "";
    if (!presets.length) {
      presetsList.innerHTML = `<p class="system-help-text" style="padding:12px">Brak szablonów. Utwórz pierwszy zestaw reguł.</p>`;
      return;
    }
    presets.forEach((preset, idx) => {
      const card = document.createElement("div");
      card.className = "rule-preset-card";
      const ruleKeys = Object.keys(preset.rules || {});
      card.innerHTML = `
        <div class="rule-preset-card-header">
          <strong class="rule-preset-name">${_esc(preset.name)}</strong>
          <span class="system-help-text">${_esc(ruleKeys.join(", ") || "brak reguł")}</span>
        </div>
        <div class="rule-preset-card-actions">
          <button class="secondary-btn preset-edit-btn" style="font-size:0.75rem">Edytuj</button>
          <button class="secondary-btn danger-outline preset-delete-btn" style="font-size:0.75rem">Usuń</button>
        </div>`;
      card.querySelector(".preset-edit-btn").addEventListener("click", () => _openPresetModal(preset, idx, renderPresets));
      card.querySelector(".preset-delete-btn").addEventListener("click", () => {
        if (!confirm(`Usunąć szablon "${preset.name}"?`)) return;
        const list = _loadRulePresets();
        list.splice(idx, 1);
        _saveRulePresets(list);
        renderPresets();
      });
      presetsList.appendChild(card);
    });
  };

  addPresetBtn.addEventListener("click", () => _openPresetModal(null, -1, renderPresets));
  renderPresets();
}

function _openPresetModal(preset, idx, onDone) {
  const isEdit = !!preset;
  const form = document.createElement("div");
  form.className = "modal-form";

  const nameField = document.createElement("label");
  nameField.className = "modal-field";
  nameField.innerHTML = `<span>Nazwa szablonu *</span><input type="text" name="preset_name" value="${_esc(preset?.name ?? "")}" placeholder="np. Strefa bezpieczna, Loch śmierci" />`;
  form.appendChild(nameField);

  const rulesLabel = document.createElement("div");
  rulesLabel.innerHTML = `<span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary);display:block;margin:12px 0 6px">Reguły zestawu</span>`;
  const rulesDiv = _buildRulesEditor(preset?.rules || {});
  rulesLabel.appendChild(rulesDiv);
  form.appendChild(rulesLabel);

  openModal({
    title: isEdit ? `Edytuj szablon: ${preset.name}` : "Nowy szablon reguł",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: c => c() },
      {
        label: isEdit ? "Zapisz" : "Utwórz",
        class: "primary-btn",
        onClick: async c => {
          const name = form.querySelector('[name="preset_name"]').value.trim();
          if (!name) { showToast("Podaj nazwę szablonu.", "error"); return; }
          const rules = _getRulesFromEditor(rulesDiv);
          const list = _loadRulePresets();
          if (isEdit && idx >= 0) list[idx] = { name, rules };
          else list.push({ name, rules });
          _saveRulePresets(list);
          showToast(isEdit ? "Szablon zaktualizowany." : "Szablon utworzony.", "success");
          c();
          onDone();
        },
      },
    ],
  });
}

async function _openEnemyModal(row, onDone) {
  const isEdit = !!row;
  let lootTables = [];
  try { lootTables = (await adminFetch("/api/admin/loot-tables")).items || []; } catch {}

  const lootTableOpts = `<option value="">— brak —</option>` +
    lootTables.map((t) => `<option value="${t.key}"${row?.loot_table_key === t.key ? " selected" : ""}>${_esc(t.label || t.key)}</option>`).join("");
  const dropChancePct = Math.round((row?.drop_chance ?? 1.0) * 100);

  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span><input name="key" type="text" value="${_esc(row?.key??"")}" ${isEdit?"readonly":""} placeholder="np. goblin_scout" autocomplete="off"/></label>
    <label class="modal-field"><span>Nazwa *</span><input name="label" type="text" value="${_esc(row?.label??"")}" placeholder="np. Goblin zwiadowca" autocomplete="off"/></label>
    <label class="modal-field"><span>Poziom</span><select name="tier">${Object.entries(LABELS.tiers).map(([v,l])=>`<option value="${v}"${(row?.tier??"standard")===v?" selected":""}>${l}</option>`).join("")}</select></label>
    <label class="modal-field"><span>HP bazowe *</span><input name="hp_base" type="number" value="${row?.hp_base??10}" min="1"/></label>
    <label class="modal-field"><span>AC bazowe</span><input name="ac_base" type="number" value="${row?.ac_base??10}" min="0"/></label>
    <label class="modal-field"><span>Bonus do ataku</span><input name="attack_bonus" type="number" value="${row?.attack_bonus??0}"/></label>
    <label class="modal-field"><span>Bonus obrażeń</span><input name="damage_bonus" type="number" value="${row?.damage_bonus??0}"/></label>
    <label class="modal-field"><span>Kość obrażeń *</span><input name="damage_die" type="text" value="${_esc(row?.damage_die??"d6")}" placeholder="d6"/></label>
    <label class="modal-field"><span>Ataki/turę</span><input name="attacks_per_turn" type="number" value="${row?.attacks_per_turn??1}" min="1"/></label>
    <label class="modal-field"><span>Typ obrażeń</span><select name="damage_type">${Object.entries(LABELS.damageTypes).map(([v,l])=>`<option value="${v}"${(row?.damage_type??"physical")===v?" selected":""}>${l}</option>`).join("")}</select></label>
    <label class="modal-field"><span>Nagroda XP</span><input name="xp_award" type="number" value="${row?.xp_award??10}" min="0"/></label>
    <div class="modal-field-divider"></div>
    <label class="modal-field"><span>Tabela łupów</span><select name="loot_table_key">${lootTableOpts}</select></label>
    <label class="modal-field"><span>Szansa na łup (%)</span><input name="drop_chance_pct" type="number" value="${dropChancePct}" min="0" max="100" title="0 = nigdy, 100 = zawsze"/></label>
    <div class="modal-field-divider"></div>
    <label class="modal-field"><span>Opis</span><textarea name="description" rows="3">${_esc(row?.description??"")}</textarea></label>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>${LABELS.isActive}</span></label>`;

  openModal({
    title: isEdit ? `Edytuj wroga: ${row.key}` : LABELS.addEnemy,
    content: form,
    footer: [
      { label: LABELS.cancel, class: "secondary-btn", onClick: (c) => c() },
      {
        label: isEdit ? LABELS.save : "Dodaj",
        class: "primary-btn",
        onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key) { showToast("Klucz jest wymagany.", "error"); return; }
          if (!label) { showToast("Nazwa jest wymagana.", "error"); return; }
          const lootKey = g("loot_table_key").value.trim() || null;
          const dropPct = Number(g("drop_chance_pct").value);
          const body = {
            key, label,
            tier: g("tier").value,
            hp_base: Number(g("hp_base").value),
            ac_base: Number(g("ac_base").value),
            attack_bonus: Number(g("attack_bonus").value),
            damage_bonus: Number(g("damage_bonus").value),
            damage_die: g("damage_die").value.trim(),
            attacks_per_turn: Number(g("attacks_per_turn").value),
            damage_type: g("damage_type").value,
            xp_award: Number(g("xp_award").value),
            description: g("description").value.trim(),
            is_active: g("is_active").checked,
            loot_table_key: lootKey,
            drop_chance: Math.min(1, Math.max(0, dropPct / 100)),
          };
          try {
            if (isEdit) {
              await adminFetch(`/api/admin/enemies/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            } else {
              await adminFetch("/api/admin/enemies", { method: "POST", body: JSON.stringify(body) });
            }
            showToast(isEdit ? "Zapisano." : "Dodano wroga.", "success");
            c(); await onDone();
          } catch (e) { showToast((e.message || "Błąd"), "error"); }
        },
      },
    ],
  });
}

// ── Pending Review Queue (Task 32) ────────────────────────────────────────

// AP1 — inline "Edytuj i Zatwierdź" modal for pending NPCs/enemies.
// Pre-fills full row, lets admin tweak fields, PATCHes changes, then approves
// in one flow. Used by _loadPendingType.
const _EA_FIELDS = {
  npc: [
    { key: "label",              label: "Nazwa",          type: "text",     required: true },
    { type: "role_group",        label: "Role (możesz zaznaczyć więcej niż jedną)", roles: [
        { key: "is_shop",        l: "🪙 Kupiec",     hint: "handluje przedmiotami" },
        { key: "is_quest_giver", l: "📜 Dawca zadań", hint: "oferuje questy / haki fabularne" },
        { key: "is_ally",        l: "🤝 Sojusznik",   hint: "może dołączyć do drużyny" },
    ], hint: "Wszystkie odznaczone = neutralny (tylko rozmowa)." },
    { key: "description",        label: "Opis",           type: "textarea" },
    { key: "personality_prompt", label: "Osobowość (prompt do GM)", type: "textarea" },
    { key: "is_active",          label: "Aktywny",        type: "checkbox" },
  ],
  enemy: [
    { key: "label",        label: "Nazwa",         type: "text",     required: true },
    { key: "tier",         label: "Tier",          type: "select",   options: [
        { v: "weak", l: "Słaby" }, { v: "standard", l: "Standardowy" },
        { v: "elite", l: "Elita" }, { v: "boss", l: "Boss" },
    ]},
    { key: "hp_base",      label: "HP",            type: "number", min: 1 },
    { key: "ac_base",      label: "AC",            type: "number", min: 1 },
    { key: "attack_bonus", label: "Atak +",        type: "number", min: 0 },
    { key: "damage_die",   label: "Kość obrażeń (np. d6, 2d8)", type: "text" },
    { key: "damage_type",  label: "Typ obrażeń",   type: "select",   options: [
        { v: "physical", l: "Fizyczne" }, { v: "fire", l: "Ogień" },
        { v: "poison", l: "Trucizna" },   { v: "magic", l: "Magia" },
        { v: "misc", l: "Inny" },
    ]},
    { key: "xp_award",     label: "XP za zabójstwo", type: "number", min: 0 },
    { key: "description",  label: "Opis",          type: "textarea" },
    { key: "note",         label: "Notatka (zdolności specjalne — informacyjne)", type: "textarea" },
  ],
};

async function _openEditApproveModal({ item, entityType, onDone }) {
  // Fetch the full row so we have every field — the list response only returns
  // summary columns (label / tier / hp_base for enemies, etc.).
  const detailUrl = entityType === "npc"
    ? `/api/admin/world/pending/npc/${item.key}`
    : `/api/admin/world/pending/enemy/${item.key}`;
  let detail;
  try {
    const resp = await adminFetch(detailUrl);
    detail = resp.item || {};
  } catch (e) {
    showToast("Nie udało się pobrać szczegółów: " + (e.message || "?"), "error");
    return;
  }

  const fields = _EA_FIELDS[entityType] || [];
  const form = document.createElement("div");
  form.className = "edit-approve-form";

  fields.forEach((f) => {
    const field = document.createElement("div");
    field.className = "ea-field";

    if (f.type === "role_group") {
      // Multi-role checkbox group — each role is its own DB column (is_shop /
      // is_quest_giver / is_ally). npc_type is derived server-side from these.
      const checks = f.roles.map(r => `
        <label class="ea-role-check">
          <input type="checkbox" name="${r.key}"${Number(detail[r.key]) ? " checked" : ""}>
          <span class="ea-role-label">${_esc(r.l)}</span>
          <span class="ea-role-hint">${_esc(r.hint || "")}</span>
        </label>`).join("");
      field.innerHTML = `<label>${_esc(f.label)}</label><div class="ea-role-group">${checks}</div>${
        f.hint ? `<div class="ea-field-hint">${_esc(f.hint)}</div>` : ""
      }`;
      form.appendChild(field);
      return;
    }

    const cur = detail[f.key];
    const reqMark = f.required ? " <span class='ea-req'>*</span>" : "";
    let inputHtml;
    if (f.type === "select") {
      inputHtml = `<select name="${f.key}">
        ${f.options.map(o => `<option value="${_esc(o.v)}"${String(cur ?? "") === o.v ? " selected" : ""}>${_esc(o.l)}</option>`).join("")}
      </select>`;
    } else if (f.type === "textarea") {
      inputHtml = `<textarea name="${f.key}" rows="3">${_esc(cur ?? "")}</textarea>`;
    } else if (f.type === "checkbox") {
      inputHtml = `<input type="checkbox" name="${f.key}"${Number(cur) ? " checked" : ""}>`;
    } else if (f.type === "number") {
      inputHtml = `<input type="number" name="${f.key}" value="${_esc(cur ?? "")}"${f.min !== undefined ? ` min="${f.min}"` : ""}>`;
    } else {
      inputHtml = `<input type="text" name="${f.key}" value="${_esc(cur ?? "")}">`;
    }
    field.innerHTML = `<label>${_esc(f.label)}${reqMark}</label>${inputHtml}`;
    form.appendChild(field);
  });

  const patchUrl = entityType === "npc"
    ? `/api/admin/world/pending/npcs/${item.key}`
    : `/api/admin/world/pending/enemies/${item.key}`;
  const approveUrl = `/api/admin/world/review/${entityType}/${item.key}`;

  // Enemy-only: append a loot preview section (rolled tier-based, editable).
  // State lives in a closure object so reroll/add/remove can mutate it and
  // the same object is read on save.
  let lootState = null;
  if (entityType === "enemy") {
    lootState = await _attachLootPreviewSection(form, item);
  }

  openModal({
    title: `✎ Edytuj i Zatwierdź — ${item.label || item.key}`,
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (cls) => cls() },
      { label: "Zapisz i Zatwierdź", class: "primary-btn", onClick: async (cls) => {
          const patch = {};
          for (const f of fields) {
            if (f.type === "role_group") {
              // Collect each role checkbox individually; backend re-derives npc_type.
              for (const r of f.roles) {
                const el = form.querySelector(`[name="${r.key}"]`);
                if (!el) continue;
                const v = el.checked ? 1 : 0;
                const orig = Number(detail[r.key] || 0);
                if (v !== orig) patch[r.key] = v;
              }
              continue;
            }
            const el = form.querySelector(`[name="${f.key}"]`);
            if (!el) continue;
            let v;
            if (f.type === "checkbox") v = el.checked ? 1 : 0;
            else if (f.type === "number") v = el.value === "" ? null : Number(el.value);
            else v = String(el.value);
            if (f.required && (v === null || v === "")) {
              showToast(`Pole „${f.label}" jest wymagane.`, "error");
              return;
            }
            // Only send fields that actually changed (skip nulls when DB had null/empty).
            const orig = detail[f.key];
            const origNorm = orig == null ? (f.type === "checkbox" ? 0 : "") : (f.type === "checkbox" ? Number(orig) : orig);
            if (v !== origNorm) patch[f.key] = v;
          }
          try {
            if (Object.keys(patch).length > 0) {
              await adminFetch(patchUrl, { method: "PATCH", body: JSON.stringify(patch) });
            }
            // Enemy: collect the (possibly edited) loot entries and PUT before
            // approve. Backend's auto-gen skips because loot_table_key is set.
            if (entityType === "enemy" && lootState) {
              const entries = lootState.collect();
              await adminFetch(`/api/admin/world/pending/enemies/${item.key}/loot`, {
                method: "PUT",
                body: JSON.stringify({
                  tier: lootState.tier,
                  gold_min: lootState.gold_min,
                  gold_max: lootState.gold_max,
                  entries,
                }),
              });
            }
            await adminFetch(approveUrl, { method: "POST", body: JSON.stringify({ action: "approve" }) });
            showToast("Zapisane i zatwierdzone.", "success");
            cls();
            onDone?.();
          } catch (e) {
            showToast("Błąd: " + (e.message || "?"), "error");
          }
        }},
    ],
  });
}

// AP1 v2 — render the loot preview/edit section inside the pending-enemy modal.
// Returns a state object with .collect() to read current entries on save +
// .tier / .gold_min / .gold_max for the PUT body.
async function _attachLootPreviewSection(form, item) {
  const wrap = document.createElement("div");
  wrap.className = "ea-loot-section";
  wrap.innerHTML = `
    <div class="ea-loot-header">
      <label>🎲 Tabela łupów (auto-roll na podstawie tieru)</label>
      <div class="ea-loot-actions">
        <button type="button" class="secondary-btn ea-loot-reroll" style="font-size:0.75rem;padding:3px 10px">🔄 Przeloseuj</button>
        <button type="button" class="secondary-btn ea-loot-add"    style="font-size:0.75rem;padding:3px 10px">＋ Dodaj wpis</button>
      </div>
    </div>
    <div class="ea-loot-gold">
      <label>Złoto:</label>
      <input type="number" class="ea-loot-gmin" min="0" style="width:80px">
      <span>–</span>
      <input type="number" class="ea-loot-gmax" min="0" style="width:80px">
    </div>
    <div class="ea-loot-rows"><div class="ea-loot-loading">Ładowanie podglądu łupu…</div></div>
    <div class="ea-field-hint">Edytuj wpisy przed zapisem. Pusta lista = brak losowych przedmiotów (tylko złoto, jeśli &gt; 0).</div>
  `;
  form.appendChild(wrap);

  const rowsEl = wrap.querySelector(".ea-loot-rows");
  const gMinEl = wrap.querySelector(".ea-loot-gmin");
  const gMaxEl = wrap.querySelector(".ea-loot-gmax");

  // State shared with the save handler
  const state = {
    tier: null,
    gold_min: 0,
    gold_max: 0,
    entries: [],
    collect() {
      // Read current values from the DOM so admin edits flow through.
      const out = [];
      rowsEl.querySelectorAll(".ea-loot-row").forEach(r => {
        const kind = r.querySelector(".ea-loot-kind").value;
        const key  = r.querySelector(".ea-loot-key").value.trim();
        const w    = Number(r.querySelector(".ea-loot-weight").value);
        const qm   = Number(r.querySelector(".ea-loot-qmax").value);
        if (!key) return;
        out.push({ kind, key, weight: Math.max(1, w || 30), qty_min: 1, qty_max: Math.max(1, qm || 1) });
      });
      state.gold_min = Math.max(0, Number(gMinEl.value) || 0);
      state.gold_max = Math.max(0, Number(gMaxEl.value) || 0);
      return out;
    },
  };

  const renderRows = (entries) => {
    if (!entries.length) {
      rowsEl.innerHTML = `<div class="ea-loot-empty">Brak wpisów — kliknij „＋ Dodaj wpis" lub „🔄 Przeloseuj".</div>`;
      return;
    }
    rowsEl.innerHTML = entries.map(e => _lootRowHtml(e)).join("");
    rowsEl.querySelectorAll(".ea-loot-remove").forEach(b => {
      b.addEventListener("click", () => { b.closest(".ea-loot-row").remove(); });
    });
  };

  const loadPreview = async () => {
    rowsEl.innerHTML = `<div class="ea-loot-loading">Ładowanie podglądu łupu…</div>`;
    try {
      const data = await adminFetch(`/api/admin/world/pending/enemy/${item.key}/loot-preview`);
      state.tier = data.tier;
      state.gold_min = data.gold_min;
      state.gold_max = data.gold_max;
      state.entries = data.entries || [];
      gMinEl.value = state.gold_min;
      gMaxEl.value = state.gold_max;
      renderRows(state.entries);
    } catch (e) {
      rowsEl.innerHTML = `<div class="ea-loot-empty" style="color:var(--accent-red)">${_esc(e.message || "Błąd")}</div>`;
    }
  };

  wrap.querySelector(".ea-loot-reroll").addEventListener("click", loadPreview);
  wrap.querySelector(".ea-loot-add").addEventListener("click", () => {
    // Add an empty row admin can fill in
    const blank = { kind: "consumable", key: "", weight: 30, qty_min: 1, qty_max: 1 };
    const cur = (rowsEl.querySelector(".ea-loot-empty")) ? [] : state.collect();
    cur.push(blank);
    state.entries = cur;
    renderRows(cur);
  });

  await loadPreview();
  return state;
}

function _lootRowHtml(e) {
  return `
    <div class="ea-loot-row">
      <select class="ea-loot-kind">
        <option value="consumable"${e.kind === "consumable" ? " selected" : ""}>🧪 consumable</option>
        <option value="item"${e.kind === "item" ? " selected" : ""}>📦 item</option>
        <option value="weapon"${e.kind === "weapon" ? " selected" : ""}>⚔ weapon</option>
      </select>
      <input type="text"   class="ea-loot-key"    value="${_esc(e.key || "")}" placeholder="key (np. potion_healing_minor)">
      <input type="number" class="ea-loot-weight" value="${Number(e.weight) || 30}" min="1" max="100" title="Weight 1-100">
      <input type="number" class="ea-loot-qmax"   value="${Number(e.qty_max) || 1}" min="1" title="Qty max">
      <button type="button" class="ea-loot-remove" title="Usuń">✕</button>
    </div>`;
}

async function _renderPendingReview(container, panel) {
  container.innerHTML = `
    <div class="pending-review-layout">
      <h2 class="section-heading">⏳ Oczekujące na weryfikację</h2>
      <p class="section-note">Encje stworzone przez GM podczas sesji. Zatwierdź aby stały się permanentne.</p>
      <div class="subtab-bar" style="margin-bottom:12px">
        <button class="subtab-btn active" data-ptab="locations">Lokacje <span id="pr-loc-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
        <button class="subtab-btn" data-ptab="npcs">NPC <span id="pr-npc-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
        <button class="subtab-btn" data-ptab="enemies">Wrogowie <span id="pr-enemy-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
        <button class="subtab-btn" data-ptab="weapons">⚔ Broń <span id="pr-weapon-badge" class="admin-badge admin-badge-gold" style="display:none"></span></button>
      </div>
      <div id="pr-loc-panel" class="pr-panel active"></div>
      <div id="pr-npc-panel" class="pr-panel"></div>
      <div id="pr-enemy-panel" class="pr-panel"></div>
      <div id="pr-weapon-panel" class="pr-panel"></div>
    </div>`;

  container.querySelectorAll("[data-ptab]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll("[data-ptab]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      // Toggle .active class on panels — CSS rules .pr-panel { display:none }
      // and .pr-panel.active { display:block } make this the only working hook.
      container.querySelectorAll(".pr-panel").forEach(p => {
        p.classList.remove("active");
        p.style.removeProperty("display");
      });
      const map = { locations: "pr-loc-panel", npcs: "pr-npc-panel", enemies: "pr-enemy-panel", weapons: "pr-weapon-panel" };
      const target = container.querySelector(`#${map[btn.dataset.ptab]}`);
      if (target) target.classList.add("active");
    });
  });

  await Promise.all([
    _loadPendingLocations(container, panel),
    _loadPendingType(container, "npcs", "pr-npc-panel", "pr-npc-badge", panel),
    _loadPendingType(container, "enemies", "pr-enemy-panel", "pr-enemy-badge", panel),
    _loadPendingWeapons(container, panel),
  ]);
}

// Locations: full table view so admin sees subtype/biome/tier before approving.
async function _loadPendingLocations(container, panel) {
  const panelEl = container.querySelector("#pr-loc-panel");
  const badge   = container.querySelector("#pr-loc-badge");
  const navBadge = panel.querySelector("#pending-nav-badge");
  panelEl.innerHTML = `<div class="camp-loading">Ładowanie…</div>`;

  const updateBadges = (count) => {
    badge.textContent = String(count);
    badge.style.display = count ? "" : "none";
    const total = ["pr-loc-badge","pr-npc-badge","pr-enemy-badge","pr-weapon-badge"]
      .reduce((s, id) => s + (parseInt(container.querySelector(`#${id}`)?.textContent) || 0), 0);
    if (navBadge) { navBadge.textContent = String(total); navBadge.style.display = total ? "" : "none"; }
  };

  const reload = async () => {
    try {
      const data = await adminFetch(`/api/admin/world/pending/locations`);
      const items = data.items || [];
      updateBadges(items.length);

      if (!items.length) {
        panelEl.innerHTML = `<p class="section-note">Brak oczekujących lokacji.</p>`;
        return;
      }

      const columns = [
        { key: "key",   label: LABELS.key,   editable: false },
        { key: "label", label: LABELS.label, editable: true,
          formatDisplay: (r) => r.location_type === "sub" ? `↳ ${r.label ?? ""}` : (r.label ?? "") },
        {
          key: "location_type", label: LABELS.type,
          type: "badge", editType: "select",
          editOptions: LOC_TYPES.map((t) => t.value),
          editable: true,
          badgeClass: (row) => row.location_type === "macro" ? "admin-badge-gold" : "admin-badge-muted",
          filterOptions: LOC_TYPES,
        },
        { key: "parent_key", label: "Nadrzędna", editable: false },
        {
          key: "created_by", label: "Źródło",
          type: "badge", editable: false,
          badgeClass: (row) => (LOC_CREATED_BY[row.created_by] || LOC_CREATED_BY.admin_manual).class,
          formatDisplay: (r) => (LOC_CREATED_BY[r.created_by] || LOC_CREATED_BY.admin_manual).label,
        },
        {
          key: "location_subtype", label: "Podtyp",
          editType: "select", editOptions: LOC_SUBTYPES.map((s) => s.value), editable: true,
          formatDisplay: (r) => {
            const m = LOC_SUBTYPES.find((s) => s.value === (r.location_subtype || ""));
            return m ? m.label : (r.location_subtype || "—");
          },
        },
        {
          key: "biome", label: "Biom",
          editType: "select", editOptions: LOC_BIOMES.map((b) => b.value), editable: true,
          formatDisplay: (r) => {
            const m = LOC_BIOMES.find((b) => b.value === (r.biome || ""));
            return m ? m.label : (r.biome || "—");
          },
        },
        { key: "tier",          label: "Tier", type: "number", editable: true },
        { key: "safe_for_rest", label: "🛏 Odpoczynek", type: "boolean", editable: true },
        { key: "description",   label: LABELS.description, editable: true, popup: true },
        { key: "source_campaign_id", label: "Kampania", editable: false },
      ];

      renderTable(panelEl, columns, items, {
        tableId: "pending-locations",
        showTextSearch: true,
        searchPlaceholder: "Szukaj…",
        async onEdit(row, colKey, newVal) {
          try {
            await adminFetch(`/api/locations/admin/locations/${row.key}`, {
              method: "PATCH",
              body: JSON.stringify({ [colKey]: newVal }),
            });
            showToast("Zapisano.", "success");
          } catch (e) {
            showToast("Błąd zapisu: " + (e.message || "?"), "error");
            throw e;
          }
        },
        extraActions: (row) => [
          {
            label: "✓ Zatwierdź",
            class: "primary-btn",
            onClick: async () => {
              try {
                await adminFetch(`/api/admin/world/review/location/${row.key}`, {
                  method: "POST", body: JSON.stringify({ action: "approve" }),
                });
                showToast("Zatwierdzone.", "success");
                await reload();
              } catch (e) { showToast(e.message, "error"); }
            },
          },
          {
            label: row.canonical ? "⭐ Kanon" : "☆ Kanon",
            class: row.canonical ? "secondary-btn" : "secondary-btn",
            style: row.canonical ? "opacity:0.5;cursor:default" : "",
            onClick: async () => {
              if (row.canonical) return;
              try {
                await adminFetch(`/api/admin/world/locations/${row.key}/promote-canonical`, {
                  method: "PATCH",
                });
                showToast("Oznaczono jako kanoniczną.", "success");
                await reload();
              } catch (e) { showToast(e.message, "error"); }
            },
          },
          {
            label: "✕ Odrzuć",
            class: "secondary-btn danger-outline",
            onClick: async () => {
              if (!confirm(`Odrzucić "${row.label || row.key}"?`)) return;
              try {
                await adminFetch(`/api/admin/world/review/location/${row.key}`, {
                  method: "POST", body: JSON.stringify({ action: "discard" }),
                });
                showToast("Odrzucone.", "success");
                await reload();
              } catch (e) { showToast(e.message, "error"); }
            },
          },
        ],
      });
    } catch (e) {
      panelEl.innerHTML = `<p style="color:var(--accent-red);font-size:0.82rem">${_esc(e.message)}</p>`;
    }
  };

  await reload();
}

async function _loadPendingType(container, type, panelId, badgeId, panel) {
  const panelEl = container.querySelector(`#${panelId}`);
  const badge = container.querySelector(`#${badgeId}`);
  const navBadge = panel.querySelector("#pending-nav-badge");
  panelEl.innerHTML = `<div class="camp-loading">Ładowanie…</div>`;

  try {
    const data = await adminFetch(`/api/admin/world/pending/${type}`);
    const items = data.items || [];

    badge.textContent = String(items.length);
    badge.style.display = items.length ? "" : "none";

    // Update nav tab badge total
    const total = (parseInt(panel.querySelector("#pr-loc-badge")?.textContent || 0) || 0) +
                  (parseInt(panel.querySelector("#pr-npc-badge")?.textContent || 0) || 0) +
                  (parseInt(panel.querySelector("#pr-enemy-badge")?.textContent || 0) || 0);
    if (navBadge) { navBadge.textContent = String(total); navBadge.style.display = total ? "" : "none"; }

    if (!items.length) {
      panelEl.innerHTML = `<p class="section-note">Brak oczekujących pozycji.</p>`;
      return;
    }

    panelEl.innerHTML = "";
    const entityType = type === "locations" ? "location" : type === "npcs" ? "npc" : "enemy";

    // AP2 — bulk-select state shared between toolbar + rows
    const selected = new Set();
    const rowByKey = new Map();

    const toolbar = document.createElement("div");
    toolbar.className = "bulk-toolbar";
    toolbar.innerHTML = `
      <label class="bulk-select-all-label">
        <input type="checkbox" class="bulk-select-all">
        <span>Zaznacz wszystko</span>
      </label>
      <span class="bulk-count" data-count="0">0 zaznaczonych</span>
      <div class="bulk-actions">
        <button class="primary-btn bulk-approve-btn" disabled style="font-size:0.78rem;padding:4px 12px">✓ Zatwierdź zaznaczone</button>
        <button class="secondary-btn danger-outline bulk-reject-btn" disabled style="font-size:0.78rem;padding:4px 12px">✕ Odrzuć zaznaczone</button>
      </div>
    `;
    panelEl.appendChild(toolbar);

    const bulkApproveBtn = toolbar.querySelector(".bulk-approve-btn");
    const bulkRejectBtn  = toolbar.querySelector(".bulk-reject-btn");
    const bulkCount      = toolbar.querySelector(".bulk-count");
    const selectAllBox   = toolbar.querySelector(".bulk-select-all");

    const decBadgeOnce = () => {
      badge.textContent = String(Math.max(0, (parseInt(badge.textContent) || 1) - 1));
      if (badge.textContent === "0") badge.style.display = "none";
    };

    const refreshToolbar = () => {
      const n = selected.size;
      bulkCount.textContent = `${n} zaznaczonych`;
      bulkCount.dataset.count = String(n);
      bulkApproveBtn.disabled = n === 0;
      bulkRejectBtn.disabled  = n === 0;
      // Select-all reflects current state (no event loop — we set .checked manually)
      const total = rowByKey.size;
      selectAllBox.checked = total > 0 && n === total;
      selectAllBox.indeterminate = n > 0 && n < total;
    };

    const removeRow = (key) => {
      const r = rowByKey.get(key);
      if (r) { r.remove(); rowByKey.delete(key); }
      selected.delete(key);
      decBadgeOnce();
      refreshToolbar();
    };

    const runBulk = async (action) => {
      const keys = Array.from(selected);
      if (!keys.length) return;
      if (action === "discard" && !confirm(`Odrzucić ${keys.length} oczekujących pozycji? Tej operacji nie można cofnąć.`)) return;
      bulkApproveBtn.disabled = true;
      bulkRejectBtn.disabled  = true;
      let ok = 0, fail = 0;
      const results = await Promise.allSettled(keys.map(k =>
        adminFetch(`/api/admin/world/review/${entityType}/${k}`, {
          method: "POST", body: JSON.stringify({ action }),
        }).then(() => ({ k, ok: true }))
      ));
      results.forEach((r, i) => {
        if (r.status === "fulfilled") { ok++; removeRow(keys[i]); }
        else { fail++; }
      });
      if (ok)   showToast(`${ok} ${action === "approve" ? "zatwierdzonych" : "odrzuconych"}.`, "success");
      if (fail) showToast(`${fail} nie udało się.`, "error");
      refreshToolbar();
    };

    bulkApproveBtn.addEventListener("click", () => runBulk("approve"));
    bulkRejectBtn .addEventListener("click", () => runBulk("discard"));

    selectAllBox.addEventListener("change", () => {
      const check = selectAllBox.checked;
      rowByKey.forEach((row, key) => {
        const cb = row.querySelector(".pending-row-check");
        if (!cb) return;
        cb.checked = check;
        if (check) selected.add(key); else selected.delete(key);
      });
      refreshToolbar();
    });

    items.forEach(item => {
      const row = document.createElement("div");
      row.className = "pending-row";
      row.innerHTML = `
        <input type="checkbox" class="pending-row-check" title="Zaznacz do operacji zbiorczej">
        <div class="pending-row-info">
          <strong>${_esc(item.label || item.name || item.key)}</strong>
          <code>${_esc(item.key)}</code>
          ${item.description ? `<span style="color:var(--text-muted);font-size:0.76rem">${_esc(item.description.slice(0, 80))}${item.description.length > 80 ? "…" : ""}</span>` : ""}
        </div>
        <div class="pending-row-actions">
          <button class="secondary-btn pending-edit-approve-btn" style="font-size:0.78rem;padding:4px 10px" title="Otwórz formularz edycji">✎ Edytuj i Zatwierdź</button>
          <button class="primary-btn pending-approve-btn" style="font-size:0.78rem;padding:4px 10px" title="Zatwierdź bez zmian">✓ Zatwierdź</button>
          <button class="secondary-btn danger-outline pending-reject-btn" style="font-size:0.78rem;padding:4px 8px">✕ Odrzuć</button>
        </div>`;

      rowByKey.set(item.key, row);

      row.querySelector(".pending-row-check").addEventListener("change", (e) => {
        if (e.target.checked) selected.add(item.key); else selected.delete(item.key);
        refreshToolbar();
      });

      row.querySelector(".pending-edit-approve-btn").addEventListener("click", () => {
        _openEditApproveModal({ item, entityType, onDone: () => removeRow(item.key) });
      });

      row.querySelector(".pending-approve-btn").addEventListener("click", async () => {
        try {
          await adminFetch(`/api/admin/world/review/${entityType}/${item.key}`, {
            method: "POST", body: JSON.stringify({ action: "approve" }),
          });
          showToast("Zatwierdzone.", "success");
          removeRow(item.key);
        } catch (e) { showToast(e.message, "error"); }
      });

      row.querySelector(".pending-reject-btn").addEventListener("click", async () => {
        if (!confirm(`Odrzucić "${item.label || item.key}"?`)) return;
        try {
          await adminFetch(`/api/admin/world/review/${entityType}/${item.key}`, {
            method: "POST", body: JSON.stringify({ action: "discard" }),
          });
          showToast("Odrzucone.", "success");
          removeRow(item.key);
        } catch (e) { showToast(e.message, "error"); }
      });

      panelEl.appendChild(row);
    });

    refreshToolbar();
  } catch (e) {
    panelEl.innerHTML = `<p style="color:var(--accent-red);font-size:0.82rem">${_esc(e.message)}</p>`;
  }
}

async function _loadPendingWeapons(container, panel) {
  const panelEl = container.querySelector("#pr-weapon-panel");
  const badge = container.querySelector("#pr-weapon-badge");
  const navBadge = panel.querySelector("#pending-nav-badge");
  panelEl.innerHTML = `<div class="camp-loading">Ładowanie…</div>`;

  const updateBadges = (count) => {
    badge.textContent = String(count);
    badge.style.display = count ? "" : "none";
    if (navBadge) {
      const total = ["pr-loc-badge","pr-npc-badge","pr-enemy-badge","pr-weapon-badge"]
        .reduce((s, id) => s + (parseInt(container.querySelector(`#${id}`)?.textContent)||0), 0);
      navBadge.textContent = String(total); navBadge.style.display = total ? "" : "none";
    }
  };

  const reload = async () => {
    try {
      const data = await adminFetch("/api/admin/world/pending/weapons");
      const items = data.items || [];
      updateBadges(items.length);
      if (!items.length) {
        panelEl.innerHTML = `<p class="section-note">Brak oczekującej broni.</p>`;
        return;
      }

      const columns = [
        { key: "label",       label: "Nazwa",     editable: true },
        { key: "key",         label: "Klucz",     editable: false },
        { key: "weapon_type", label: "Typ",       type: "badge", editType: "select",
          editOptions: ["melee","ranged","spell"], editable: true,
          badgeClass: (r) => r.weapon_type === "ranged" ? "admin-badge-blue"
                            : r.weapon_type === "spell" ? "admin-badge-gold"
                            : "admin-badge-muted" },
        { key: "damage_die",  label: "Kość",      editable: true },
        { key: "linked_stat", label: "Stat",      type: "badge", editType: "select",
          editOptions: ["STR","DEX","INT","WIS","CHA"], editable: true,
          badgeClass: () => "admin-badge-muted" },
        { key: "campaign_id", label: "Kampania",  editable: false,
          formatDisplay: (r) => r.campaign_id ? `#${r.campaign_id}` : "—" },
        { key: "description", label: "Opis",      editable: true, popup: true,
          formatDisplay: (r) => r.description ? `${String(r.description).slice(0,60)}${r.description.length>60?"…":""}` : "—" },
        { key: "ai_generated", label: "Autor",    type: "badge", editable: false,
          formatDisplay: (r) => r.ai_generated ? "🎲 GM (sesja LLM)" : "🛠 Admin",
          badgeClass:   (r) => r.ai_generated ? "admin-badge-gold" : "admin-badge-blue" },
      ];

      panelEl.innerHTML = "";
      const tableHost = document.createElement("div");
      panelEl.appendChild(tableHost);

      renderTable(tableHost, columns, items, {
        tableId: "pending-weapons",
        showTextSearch: true,
        searchPlaceholder: "Szukaj oczekującej broni…",
        async onEdit(row, colKey, newVal) {
          try {
            await adminFetch(`/api/admin/world/pending/weapons/${row.key}`, {
              method: "PATCH", body: JSON.stringify({ [colKey]: newVal }),
            });
            showToast("Zapisano.", "success");
            await reload();
          } catch (e) { showToast(e.message, "error"); throw e; }
        },
        extraActions: (row) => [
          { label: "✓ Globalna", class: "primary-btn", onClick: async () => {
              try {
                await adminFetch(`/api/admin/world/review/weapon/${row.key}`, {
                  method: "POST", body: JSON.stringify({ action: "approve" }),
                });
                showToast("Broń dodana do globalnego katalogu.", "success");
                await reload();
              } catch (e) { showToast(e.message, "error"); }
            }},
          { label: "📌 Tylko kampania", class: "secondary-btn", onClick: async () => {
              try {
                await adminFetch(`/api/admin/weapons/${row.key}`, {
                  method: "PATCH", body: JSON.stringify({ review_status: "permanent" }),
                });
                showToast("Broń zachowana — widoczna tylko w kampanii.", "success");
                await reload();
              } catch (e) { showToast(e.message, "error"); }
            }},
          { label: "✕ Odrzuć", class: "danger-outline", onClick: async () => {
              if (!confirm(`Odrzucić broń "${row.label||row.key}"?`)) return;
              try {
                await adminFetch(`/api/admin/world/review/weapon/${row.key}`, {
                  method: "POST", body: JSON.stringify({ action: "discard" }),
                });
                showToast("Odrzucone.", "success");
                await reload();
              } catch (e) { showToast(e.message, "error"); }
            }},
        ],
      });
    } catch (e) {
      panelEl.innerHTML = `<p style="color:var(--accent-red);font-size:0.82rem">${_esc(e.message)}</p>`;
    }
  };

  await reload();
}

// ── Dungeons ──────────────────────────────────────────────────────────────────

export async function _renderDungeons(container) {
  container.innerHTML = `
    <div class="dungeon-list-panel" style="display:flex;flex-direction:column;height:100%;overflow:hidden">
      <div class="dungeon-list-toolbar">
        <button class="primary-btn" id="dungeon-add-btn">+ Dodaj loch</button>
      </div>
      <div id="dungeon-table-host" style="flex:1;overflow-y:auto;padding:12px 16px"></div>
    </div>
    <!-- Floating AI bubble -->
    <button class="dungeon-ai-fab" id="dungeon-ai-fab" title="AI Kreator Lochu">🤖</button>
    <div class="dungeon-ai-chat" id="dungeon-ai-chat" hidden>
      <div class="dungeon-ai-chat-header">
        <span>🤖 Kreator Lochu</span>
        <button class="dungeon-ai-chat-close" id="dungeon-ai-close">✕</button>
      </div>
      <div class="dungeon-ai-messages" id="dungeon-ai-msgs"></div>
      <div class="dungeon-ai-input-row">
        <textarea id="dungeon-ai-prompt" class="dungeon-ai-textarea" rows="3"
          placeholder="Opisz loch… (Ctrl+Enter = wyślij)"></textarea>
        <button class="primary-btn small-btn" id="dungeon-ai-btn">Generuj</button>
      </div>
    </div>`;

  const tableHost = container.querySelector("#dungeon-table-host");
  const msgsEl = container.querySelector("#dungeon-ai-msgs");
  let aiHistory = [];
  let aiDraft = null;

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows = [];
    try { rows = (await adminFetch("/api/admin/dungeons")).items || []; }
    catch (e) { showToast("Błąd ładowania lochów: " + (e.message || "?"), "error"); return; }

    const cols = [
      { key: "key",           label: "Klucz",     editable: false },
      { key: "label",         label: "Nazwa",      editable: true },
      { key: "rooms",         label: "Pokoje",     type: "number", editable: true },
      { key: "cooldown_hours",label: "Cooldown(h)",type: "number", editable: true },
      { key: "min_level",     label: "Poziom",     type: "number", editable: true },
      { key: "loot_tier",     label: "Łupy",
        type: "badge", editType: "select",
        editOptions: ["poor","standard","rich"],
        badgeClass: (r) => ({poor:"admin-badge-blue",standard:"admin-badge-green",rich:"admin-badge-gold"}[r.loot_tier]||"admin-badge-blue"),
        formatDisplay: (r) => ({poor:"Słabe",standard:"Standardowe",rich:"Bogate"}[r.loot_tier]||r.loot_tier),
      },
      { key: "boss_enemy",   label: "Boss",       editable: true },
      { key: "is_active",    label: "Aktywny",    type: "boolean", editable: true },
    ];

    renderTable(tableHost, cols, rows, {
      tableId: "dungeons", showTextSearch: true, searchPlaceholder: "Szukaj lochów…",
      async onEdit(row, colKey, newVal) {
        try {
          await adminFetch(`/api/admin/dungeons/${row.key}`, { method:"PATCH", body:JSON.stringify({[colKey]:newVal}) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message||"?"), "error"); throw e; }
      },
      async onDelete(row) {
        try {
          await adminFetch(`/api/admin/dungeons/${row.key}`, { method:"DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message||"?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label:"Edytuj", class:"secondary-btn", onClick:() => _openDungeonModal(row, load) }],
    });
  };

  container.querySelector("#dungeon-add-btn").addEventListener("click", () => _openDungeonModal(null, load));

  // FAB toggle
  const fab = container.querySelector("#dungeon-ai-fab");
  const chat = container.querySelector("#dungeon-ai-chat");
  fab.addEventListener("click", () => { chat.hidden = !chat.hidden; if (!chat.hidden) container.querySelector("#dungeon-ai-prompt")?.focus(); });
  container.querySelector("#dungeon-ai-close").addEventListener("click", () => { chat.hidden = true; });

  // AI generator
  const renderAiMsgs = () => {
    msgsEl.innerHTML = aiHistory.map(m => `
      <div class="dungeon-ai-msg dungeon-ai-msg--${m.role}">
        <span class="dungeon-ai-msg-role">${m.role === "user" ? "Ty" : "AI"}</span>
        <span>${m.content}</span>
      </div>`).join("") +
      (aiDraft ? `<div class="dungeon-ai-draft">
        <div class="dungeon-ai-draft-title">Gotowy szkic: <strong>${aiDraft.label || aiDraft.key}</strong></div>
        <div class="dungeon-ai-draft-info">${aiDraft.rooms || "?"} pokoi · Boss: ${aiDraft.boss_enemy || "brak"} · ${aiDraft.atmosphere?.slice(0,60)||""}…</div>
        <div class="dungeon-ai-draft-btns">
          <button class="primary-btn small-btn" id="dungeon-ai-open-modal">Edytuj i dodaj</button>
          <button class="secondary-btn small-btn" id="dungeon-ai-save-direct">Zapisz od razu</button>
        </div>
      </div>` : "");
    msgsEl.scrollTop = msgsEl.scrollHeight;

    if (aiDraft) {
      container.querySelector("#dungeon-ai-open-modal")?.addEventListener("click", () => {
        _openDungeonModal(aiDraft, load);
      });
      container.querySelector("#dungeon-ai-save-direct")?.addEventListener("click", async () => {
        try {
          await adminFetch("/api/admin/dungeons", { method:"POST", body:JSON.stringify(aiDraft) });
          showToast("Loch dodany!", "success"); aiDraft = null; aiHistory = []; renderAiMsgs(); await load();
        } catch (e) { showToast(e.message||"Błąd", "error"); }
      });
    }
  };

  const genBtn = container.querySelector("#dungeon-ai-btn");
  const promptEl = container.querySelector("#dungeon-ai-prompt");

  genBtn.addEventListener("click", async () => {
    const msg = promptEl.value.trim();
    if (!msg) { showToast("Opisz loch.", "info"); return; }
    genBtn.disabled = true; genBtn.textContent = "Generuję…";
    try {
      const res = await adminFetch("/api/admin/assistant/draft", {
        method:"POST",
        body: JSON.stringify({ resource:"game_dungeons", message:msg, history:aiHistory }),
      });
      aiHistory.push({ role:"user", content:msg });
      aiHistory.push({ role:"assistant", content: res.assistant_reply || "Gotowe." });
      aiDraft = res.draft || null;
      promptEl.value = "";
      renderAiMsgs();
    } catch (e) {
      showToast("Błąd AI: " + (e.message||"?"), "error");
    } finally {
      genBtn.disabled = false; genBtn.textContent = "Generuj";
    }
  });
  promptEl.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) genBtn.click();
  });

  await load();
}

function _openDungeonModal(row, onDone) {
  const isEdit = !!row;
  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span>
      <input name="key" type="text" value="${_esc(row?.key ?? "")}" ${isEdit ? "readonly" : ""} placeholder="np. goblin_warren" autocomplete="off"/>
    </label>
    <label class="modal-field"><span>Nazwa *</span>
      <input name="label" type="text" value="${_esc(row?.label ?? "")}" placeholder="Nora Goblinów"/>
    </label>
    <label class="modal-field"><span>Klucz lokacji</span>
      <input name="location_key" type="text" value="${_esc(row?.location_key ?? "")}" placeholder="Zostaw puste = jak klucz lochu"/>
    </label>
    <label class="modal-field"><span>Pokoje (1–20)</span>
      <input name="rooms" type="number" value="${row?.rooms ?? 5}" min="1" max="20"/>
    </label>
    <label class="modal-field"><span>Pula wrogów (JSON array)</span>
      <input name="enemy_pool" type="text" value="${_esc(row?.enemy_pool ?? '[]')}" placeholder='["goblin","goblin_archer"]'/>
    </label>
    <label class="modal-field"><span>Boss (klucz wroga, opcjonalnie)</span>
      <input name="boss_enemy" type="text" value="${_esc(row?.boss_enemy ?? "")}" placeholder="goblin_shaman"/>
    </label>
    <label class="modal-field"><span>Jakość łupów</span>
      <select name="loot_tier">
        ${["poor","standard","rich"].map(t => `<option value="${t}" ${(row?.loot_tier ?? "standard") === t ? "selected" : ""}>${{ poor:"Słabe", standard:"Standardowe", rich:"Bogate" }[t]}</option>`).join("")}
      </select>
    </label>
    <label class="modal-field"><span>Cooldown (godziny)</span>
      <input name="cooldown_hours" type="number" value="${row?.cooldown_hours ?? 72}" min="1" max="720"/>
    </label>
    <label class="modal-field"><span>Minimalny poziom</span>
      <input name="min_level" type="number" value="${row?.min_level ?? 1}" min="1" max="20"/>
    </label>
    <label class="modal-field"><span>Atmosfera (opis klimatu)</span>
      <textarea name="atmosphere" rows="3" placeholder="Ciasne tunele, smród gnijącego mięsa…">${_esc(row?.atmosphere ?? "")}</textarea>
    </label>
    <div class="modal-field-divider"></div>
    <label class="modal-field"><span>Tabela łupów — skrzynie</span>
      <input name="chest_loot_table_key" type="text" value="${_esc(row?.chest_loot_table_key ?? "")}" placeholder="np. chest_goblin_warren"/>
    </label>
    <label class="modal-field"><span>Tabela łupów — boss</span>
      <input name="boss_loot_table_key" type="text" value="${_esc(row?.boss_loot_table_key ?? "")}" placeholder="np. chest_goblin_warren"/>
    </label>
    <label class="modal-field"><span>Szansa na łup z komnaty (0.0–1.0)</span>
      <input name="room_loot_chance" type="number" value="${row?.room_loot_chance ?? 0.15}" min="0" max="1" step="0.05"/>
    </label>
    <div class="modal-field-divider"></div>
    <label class="modal-field"><span>Źródło zagadek</span>
      <select name="riddle_source">
        ${["database","llm","mixed"].map(s=>`<option value="${s}" ${(row?.riddle_source??"database")===s?"selected":""}>${{database:"Baza danych (bezpieczne)",llm:"LLM (eksperymentalne)",mixed:"Mieszane"}[s]}</option>`).join("")}
      </select>
    </label>
    <label class="modal-field"><span>Maks. podpowiedzi do zagadki</span>
      <input name="riddle_max_hints" type="number" value="${row?.riddle_max_hints ?? 2}" min="0" max="5"/>
    </label>
    <label class="modal-checkbox-row">
      <input name="is_active" type="checkbox" ${(row?.is_active ?? 1) ? "checked" : ""}>
      <span>Aktywny</span>
    </label>
  `;

  openModal({
    title: isEdit ? `Edytuj loch: ${row.key}` : "Nowy loch",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (c) => c() },
      { label: isEdit ? "Zapisz" : "Dodaj", class: "primary-btn", onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const key = g("key").value.trim();
          const label = g("label").value.trim();
          if (!key || !label) { showToast("Klucz i nazwa są wymagane.", "error"); return; }
          const body = {
            key, label,
            location_key:         g("location_key").value.trim() || key,
            rooms:                parseInt(g("rooms").value) || 5,
            enemy_pool:           g("enemy_pool").value.trim() || "[]",
            boss_enemy:           g("boss_enemy").value.trim() || null,
            loot_tier:            g("loot_tier").value,
            cooldown_hours:       parseInt(g("cooldown_hours").value) || 72,
            min_level:            parseInt(g("min_level").value) || 1,
            atmosphere:           g("atmosphere").value.trim() || null,
            chest_loot_table_key: g("chest_loot_table_key").value.trim() || null,
            boss_loot_table_key:  g("boss_loot_table_key").value.trim() || null,
            room_loot_chance:     parseFloat(g("room_loot_chance").value) || 0.15,
            riddle_source:        g("riddle_source").value,
            riddle_max_hints:     parseInt(g("riddle_max_hints").value) || 2,
            is_active:            g("is_active").checked ? 1 : 0,
          };
          try {
            if (isEdit) await adminFetch(`/api/admin/dungeons/${row.key}`, { method: "PATCH", body: JSON.stringify(body) });
            else        await adminFetch("/api/admin/dungeons",              { method: "POST",  body: JSON.stringify(body) });
            showToast(isEdit ? "Zapisano." : "Dodano loch.", "success");
            c(); await onDone();
          } catch (e) { showToast(e.message || "Błąd zapisu", "error"); }
        }},
    ],
  });
}

// ── Riddle Bank ───────────────────────────────────────────────────────────────

export async function _renderRiddles(container) {
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ Dodaj zagadkę";
  container.appendChild(addBtn);
  const tableHost = document.createElement("div");
  tableHost.style.marginTop = "12px";
  container.appendChild(tableHost);

  const DIFF_LABELS = {1:"Łatwa",2:"Średnia",3:"Trudna"};
  const THEMES = ["general","dungeon","magic","nature","death"];

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows;
    try { rows = (await adminFetch("/api/admin/riddles")).items || []; }
    catch (e) { showToast("Błąd: " + (e.message||"?"), "error"); return; }

    const cols = [
      { key: "key",        label: "Klucz",      editable: false },
      { key: "text",       label: "Treść zagadki", editable: false,
        formatDisplay: (r) => r.text?.slice(0,60) + (r.text?.length > 60 ? "…" : "") },
      { key: "answer",     label: "Odpowiedź",  editable: true },
      { key: "difficulty", label: "Trudność",
        type: "badge", editType: "select", editOptions: [1,2,3],
        badgeClass: (r) => ({1:"admin-badge-green",2:"admin-badge-gold",3:"admin-badge-red"}[r.difficulty]||"admin-badge-muted"),
        formatDisplay: (r) => DIFF_LABELS[r.difficulty] || r.difficulty,
      },
      { key: "theme",      label: "Motyw",      editable: true, type: "select-dropdown",
        editOptions: THEMES.map(t => ({value:t,label:t})) },
      { key: "is_active",  label: "Aktywna",    type: "boolean", editable: true },
    ];

    renderTable(tableHost, cols, rows, {
      showTextSearch: true, searchPlaceholder: "Szukaj zagadek…",
      async onEdit(row, colKey, newVal) {
        const updated = {...row, [colKey]: newVal,
          answer_alts: Array.isArray(row.answer_alts) ? row.answer_alts : [],
          hints: Array.isArray(row.hints) ? row.hints : [] };
        try {
          await adminFetch(`/api/admin/riddles/${row.key}`, { method:"PATCH", body: JSON.stringify(updated) });
          showToast("Zapisano.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message||"?"), "error"); throw e; }
      },
      async onDelete(row) {
        try {
          await adminFetch(`/api/admin/riddles/${row.key}`, { method:"DELETE" });
          showToast("Usunięto.", "success"); await load();
        } catch (e) { showToast("Błąd: " + (e.message||"?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openRiddleModal(row, load) }],
    });
  };

  addBtn.addEventListener("click", () => _openRiddleModal(null, load));
  await load();
}

function _openRiddleModal(row, onDone) {
  const isEdit = !!row;
  const THEMES = ["general","dungeon","magic","nature","death"];
  const form = document.createElement("div");
  form.className = "modal-form";
  const alts = Array.isArray(row?.answer_alts) ? row.answer_alts.join("\n") : "";
  const hints = Array.isArray(row?.hints) ? row.hints.join("\n") : "";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz</span><input name="key" type="text" value="${_esc(row?.key??'')}" ${isEdit?"readonly":""} placeholder="np. riddle_shadow" autocomplete="off"/></label>
    <label class="modal-field"><span>Treść zagadki *</span><textarea name="text" rows="3" placeholder="Podążam za tobą w dzień, znikam w nocy. Czym jestem?">${_esc(row?.text??"")}</textarea></label>
    <label class="modal-field"><span>Poprawna odpowiedź *</span><input name="answer" type="text" value="${_esc(row?.answer??"")}" placeholder="np. cień"/></label>
    <label class="modal-field"><span>Alternatywne odpowiedzi (jedna per linia)</span><textarea name="answer_alts" rows="3" placeholder="shadow\ntwój cień\nmój cień">${_esc(alts)}</textarea></label>
    <label class="modal-field"><span>Podpowiedzi (jedna per linia, od najogólniejszej)</span><textarea name="hints" rows="4" placeholder="Jestem czarny\nZnikam gdy nie ma słońca\nTo twój...">${_esc(hints)}</textarea></label>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <label class="modal-field"><span>Trudność (1–3)</span><input name="difficulty" type="number" value="${row?.difficulty??1}" min="1" max="3"/></label>
      <label class="modal-field"><span>Motyw</span>
        <select name="theme">${THEMES.map(t=>`<option value="${t}"${(row?.theme??'general')===t?' selected':''}>${t}</option>`).join('')}</select>
      </label>
    </div>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>Aktywna</span></label>`;

  openModal({
    title: isEdit ? `Edytuj zagadkę: ${row.key}` : "Nowa zagadka",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: c => c() },
      { label: isEdit ? "Zapisz" : "Dodaj", class: "primary-btn", onClick: async c => {
        const g = n => form.querySelector(`[name="${n}"]`);
        const text = g("text").value.trim();
        const answer = g("answer").value.trim();
        if (!text || !answer) { showToast("Treść i odpowiedź są wymagane.", "error"); return; }
        const alts = g("answer_alts").value.trim().split("\n").map(s=>s.trim()).filter(Boolean);
        const hintsList = g("hints").value.trim().split("\n").map(s=>s.trim()).filter(Boolean);
        const body = {
          key: isEdit ? row.key : g("key").value.trim() || undefined,
          text, answer, answer_alts: alts, hints: hintsList,
          difficulty: parseInt(g("difficulty").value)||1,
          theme: g("theme").value,
          is_active: g("is_active").checked,
        };
        try {
          if (isEdit) await adminFetch(`/api/admin/riddles/${row.key}`, { method:"PATCH", body:JSON.stringify(body) });
          else        await adminFetch("/api/admin/riddles",             { method:"POST",  body:JSON.stringify(body) });
          showToast(isEdit?"Zapisano.":"Dodano zagadkę.", "success");
          c(); await onDone();
        } catch (e) { showToast(e.message||"Błąd", "error"); }
      }},
    ],
  });
}

// ── Terrain Config ─────────────────────────────────────────────────────────────

async function _renderTerrainConfig(container) {
  container.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
    <h3 style="margin:0">🌿 Typy Terenu</h3>
    <button class="primary-btn" id="terrain-add-btn">+ Nowy typ</button>
  </div>
  <p style="color:var(--text-muted);font-size:13px;margin-bottom:20px">
    Parametry generowania terenu świata. <strong>Waga spawnu</strong> określa częstotliwość — wyższe = częstsze.
    Typy z wagą 0 nie są generowane automatycznie.
  </p>
  <div id="terrain-table-wrap"><div class="loading">Ładowanie…</div></div>`;

  container.querySelector("#terrain-add-btn").addEventListener("click", () => _openTerrainModal(null, () => _renderTerrainConfig(container)));

  await _loadTerrainTable(container.querySelector("#terrain-table-wrap"));
}

async function _loadTerrainTable(wrap) {
  wrap.innerHTML = `<div class="loading">Ładowanie…</div>`;
  let rows;
  try {
    rows = await adminFetch("/api/admin/hex-terrain-config");
  } catch (e) {
    wrap.innerHTML = `<div class="error-msg">Błąd: ${_esc(e.message)}</div>`;
    return;
  }

  const totalWeight = rows.reduce((s, r) => s + (r.spawn_weight || 0), 0);

  wrap.innerHTML = `
  <table class="admin-table" style="width:100%">
    <colgroup>
      <col style="width:44px">
      <col style="width:80px">
      <col>
      <col style="width:90px">
      <col style="width:120px">
      <col style="width:100px">
      <col style="width:80px">
      <col style="width:56px">
    </colgroup>
    <thead><tr>
      <th>Ikona</th>
      <th>Klucz</th>
      <th>Etykieta</th>
      <th>Waga</th>
      <th>Szansa spawnu</th>
      <th>Czas podróży</th>
      <th>Enc. %</th>
      <th></th>
    </tr></thead>
    <tbody>
    ${rows.map(r => {
      const pct = totalWeight > 0 && r.spawn_weight > 0
        ? ((r.spawn_weight / totalWeight) * 100).toFixed(1)
        : "0";
      const barW = totalWeight > 0 ? Math.round((r.spawn_weight / totalWeight) * 100) : 0;
      return `<tr data-key="${_esc(r.hex_type)}" style="${r.is_active ? '' : 'opacity:0.45'}">
        <td style="text-align:center;font-size:22px">${_esc(r.map_icon || "")}</td>
        <td><code style="font-size:12px">${_esc(r.hex_type)}</code></td>
        <td>${_esc(r.label || "")}</td>
        <td>
          <input type="number" class="terrain-weight-input" data-key="${_esc(r.hex_type)}"
            value="${r.spawn_weight}" min="0" max="999"
            style="width:60px;padding:3px 6px;background:var(--input-bg,#1e2030);border:1px solid var(--border,#333);
                   border-radius:4px;color:var(--text-primary,#e2e8f0);text-align:center">
        </td>
        <td>
          <div style="display:flex;align-items:center;gap:6px">
            <div style="flex:1;height:8px;background:var(--border,#333);border-radius:4px;overflow:hidden">
              <div style="height:100%;width:${barW}%;background:${r.map_color||'#4ade80'};border-radius:4px;transition:width .3s"></div>
            </div>
            <span style="font-size:12px;color:var(--text-muted);min-width:36px;text-align:right">${pct}%</span>
          </div>
        </td>
        <td style="text-align:center">
          <input type="number" class="terrain-hours-input" data-key="${_esc(r.hex_type)}"
            value="${r.travel_hours}" min="1" max="48" step="0.5"
            style="width:64px;padding:3px 6px;background:var(--input-bg,#1e2030);border:1px solid var(--border,#333);
                   border-radius:4px;color:var(--text-primary,#e2e8f0);text-align:center"> h
        </td>
        <td style="text-align:center">
          <input type="number" class="terrain-enc-input" data-key="${_esc(r.hex_type)}"
            value="${Math.round((r.encounter_base_chance||0)*100)}" min="0" max="100"
            style="width:52px;padding:3px 6px;background:var(--input-bg,#1e2030);border:1px solid var(--border,#333);
                   border-radius:4px;color:var(--text-primary,#e2e8f0);text-align:center"> %
        </td>
        <td>
          <button class="icon-btn terrain-edit-btn" data-key="${_esc(r.hex_type)}" title="Edytuj">✏️</button>
        </td>
      </tr>`;
    }).join("")}
    </tbody>
  </table>
  <p style="font-size:12px;color:var(--text-muted);margin-top:10px">
    Suma wag: <strong>${totalWeight}</strong>. Zmiany wagi/godzin/% — naciśnij Enter lub kliknij poza polem.
  </p>`;

  // Inline save on blur/Enter for weight, hours, encounter
  const _saveField = async (key, field, rawValue) => {
    let value;
    if (field === "spawn_weight" || field === "travel_hours") {
      value = parseFloat(rawValue);
      if (isNaN(value) || value < 0) return;
    } else if (field === "encounter_base_chance") {
      value = Math.min(100, Math.max(0, parseInt(rawValue, 10))) / 100;
      if (isNaN(value)) return;
    }
    try {
      await adminFetch(`/api/admin/hex-terrain-config/${key}`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value }),
      });
      showToast(`Zapisano ${field} dla ${key}.`, "success");
      await _loadTerrainTable(wrap);
    } catch (e) { showToast(e.message || "Błąd zapisu", "error"); }
  };

  wrap.querySelectorAll(".terrain-weight-input").forEach(inp => {
    inp.addEventListener("change", () => _saveField(inp.dataset.key, "spawn_weight", inp.value));
    inp.addEventListener("keydown", e => { if (e.key === "Enter") inp.blur(); });
  });
  wrap.querySelectorAll(".terrain-hours-input").forEach(inp => {
    inp.addEventListener("change", () => _saveField(inp.dataset.key, "travel_hours", inp.value));
    inp.addEventListener("keydown", e => { if (e.key === "Enter") inp.blur(); });
  });
  wrap.querySelectorAll(".terrain-enc-input").forEach(inp => {
    inp.addEventListener("change", () => _saveField(inp.dataset.key, "encounter_base_chance", inp.value));
    inp.addEventListener("keydown", e => { if (e.key === "Enter") inp.blur(); });
  });

  wrap.querySelectorAll(".terrain-edit-btn").forEach(btn => {
    const key = btn.dataset.key;
    const row = rows.find(r => r.hex_type === key);
    btn.addEventListener("click", () => _openTerrainModal(row, () => _loadTerrainTable(wrap)));
  });
}

// Grouped emoji suggestions for terrain/map icons
const _TERRAIN_EMOJI_GROUPS = [
  { label: "Roślinność", emojis: ["🌾","🌱","🌿","🍀","🍁","🍂","🍃","🌺","🌸","🌼","🌻","🪷","🪴","🌵","🎋","🎍","🪨","🪵","🌰","🍄","🪸","🌾"] },
  { label: "Krajobraz", emojis: ["⛰️","🏔️","🗻","🌋","🏝️","🏜️","🌊","🏞️","🌅","🌄","🌁","🌃","🌌","🌬️","💧","🌀","❄️","🌨️","⛅","🌧️","⛈️","🌈"] },
  { label: "Drzewa i lasy", emojis: ["🌲","🌳","🌴","🎄","🌿","🍂","🌾","🎑","🌳","🌲","🌴","🪵","🍄","🌱","🌿","🍀","🎋"] },
  { label: "Woda", emojis: ["🌊","💧","💦","🌧️","❄️","🏔️","🏞️","⛵","🚣","⚓","🐟","🐠","🦈","🐬","🐳","🦦","🌀","🌁"] },
  { label: "Miejsca", emojis: ["🏘️","🏰","🏯","⛪","🕌","🛕","🏛️","🏚️","🗼","⛺","🕳️","🚪","🌉","🛤️","🛣️","⚓","🏗️","🏠","🏡","🏟️","🗽"] },
  { label: "Symbole", emojis: ["⚔️","🗡️","🛡️","🏹","🪄","💀","👁️","🔮","🌙","☀️","⭐","💎","🪙","🗺️","📜","🔑","⚗️","🧿","🕯️","🪬","🔥","⚡"] },
  { label: "Stworzenia", emojis: ["🐉","🦁","🐺","🐻","🦅","🦇","🐍","🦎","🐊","🕷️","🦂","🐗","🦊","🦋","🦌","🐘","🦏","🐆","🐅","🦬","🦉","🦅","🐦‍⬛"] },
];

function _openTerrainModal(row, onDone) {
  const isEdit = !!row;
  const form = document.createElement("div");
  form.style.cssText = "display:flex;flex-direction:column;gap:12px";
  form.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <label class="modal-field"><span>Klucz hex_type *</span>
        <input name="hex_type" type="text" value="${_esc(row?.hex_type??'')}" ${isEdit?"readonly":""}
          placeholder="np. volcano" autocomplete="off" style="font-family:monospace"/>
      </label>
      <label class="modal-field"><span>Etykieta (PL) *</span>
        <input name="label" type="text" value="${_esc(row?.label??'')}" placeholder="np. Wulkan"/>
      </label>
    </div>
    <div style="display:grid;grid-template-columns:80px 1fr;gap:12px">
      <label class="modal-field"><span>Ikona</span>
        <div style="display:flex;flex-direction:column;gap:6px">
          <input name="map_icon" type="text" value="${_esc(row?.map_icon??'')}" placeholder="🌋"
            style="font-size:22px;text-align:center;width:56px;padding:4px"/>
          <button type="button" id="icon-picker-toggle"
            style="font-size:11px;padding:3px 6px;background:var(--border,#333);border:none;border-radius:4px;color:var(--text-muted);cursor:pointer">
            🎨 wybierz
          </button>
        </div>
      </label>
      <label class="modal-field"><span>Kolor mapy</span>
        <div style="display:flex;gap:8px;align-items:center">
          <input name="map_color" type="color" value="${row?.map_color??'#888888'}" style="width:48px;height:36px;padding:2px;border:1px solid var(--border,#333);border-radius:4px;background:none;cursor:pointer"/>
          <input name="map_color_hex" type="text" value="${_esc(row?.map_color??'#888888')}" placeholder="#888888"
            style="width:100px;font-family:monospace"/>
          <span style="font-size:12px;color:var(--text-muted)">Kolor hexagonu na mapie świata</span>
        </div>
      </label>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
      <label class="modal-field"><span>Waga spawnu</span>
        <input name="spawn_weight" type="number" value="${row?.spawn_weight??5}" min="0" max="999"/>
        <small style="color:var(--text-muted)">0 = nie generowany</small>
      </label>
      <label class="modal-field"><span>Czas podróży (h)</span>
        <input name="travel_hours" type="number" value="${row?.travel_hours??4}" min="0.5" max="48" step="0.5"/>
      </label>
      <label class="modal-field"><span>Bazowa szansa enc. (%)</span>
        <input name="encounter_base_chance" type="number" value="${Math.round((row?.encounter_base_chance??0.2)*100)}" min="0" max="100"/>
      </label>
    </div>
    <label class="modal-checkbox-row"><input name="is_active" type="checkbox" ${(row?.is_active??true)?"checked":""}><span>Aktywny (widoczny na mapie i generowany)</span></label>
    <div id="icon-picker-panel" style="display:none;border:1px solid var(--border,#333);border-radius:6px;padding:10px;background:var(--surface-2,#1a1d2e)">
      ${_TERRAIN_EMOJI_GROUPS.map(g => `
        <div style="margin-bottom:8px">
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em">${g.label}</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            ${g.emojis.map(e => `<button type="button" class="emoji-pick-btn"
              style="font-size:20px;width:36px;height:36px;border:1px solid var(--border,#333);border-radius:4px;
                     background:var(--surface,#13152a);cursor:pointer;transition:background .15s"
              data-emoji="${e}">${e}</button>`).join("")}
          </div>
        </div>`).join("")}
    </div>`;

  // Sync color picker ↔ text input
  const syncColor = (src, dst) => {
    form.querySelector(`[name="${src}"]`).addEventListener("input", e => {
      form.querySelector(`[name="${dst}"]`).value = e.target.value;
    });
  };
  // Defer until form is in DOM (openModal attaches it)
  setTimeout(() => {
    syncColor("map_color", "map_color_hex");
    syncColor("map_color_hex", "map_color");

    // Icon picker toggle
    const pickerPanel = form.querySelector("#icon-picker-panel");
    const iconInput = form.querySelector("[name='map_icon']");
    form.querySelector("#icon-picker-toggle").addEventListener("click", () => {
      pickerPanel.style.display = pickerPanel.style.display === "none" ? "block" : "none";
    });
    form.querySelectorAll(".emoji-pick-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        iconInput.value = btn.dataset.emoji;
        pickerPanel.style.display = "none";
      });
      btn.addEventListener("mouseenter", () => { btn.style.background = "var(--primary-dim,#2a3060)"; });
      btn.addEventListener("mouseleave", () => { btn.style.background = "var(--surface,#13152a)"; });
    });
  }, 0);

  openModal({
    title: isEdit ? `Edytuj teren: ${row.hex_type}` : "Nowy typ terenu",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: c => c() },
      { label: isEdit ? "Zapisz" : "Dodaj", class: "primary-btn", onClick: async c => {
        const g = n => form.querySelector(`[name="${n}"]`);
        const hex_type = isEdit ? row.hex_type : g("hex_type").value.trim().toLowerCase().replace(/\s+/g,"_");
        const label = g("label").value.trim();
        if (!hex_type || !label) { showToast("Klucz i etykieta są wymagane.", "error"); return; }
        const body = {
          label,
          map_icon: g("map_icon").value.trim() || null,
          map_color: g("map_color_hex").value.trim() || g("map_color").value,
          spawn_weight: parseInt(g("spawn_weight").value) || 0,
          travel_hours: parseFloat(g("travel_hours").value) || 4,
          encounter_base_chance: Math.min(100, Math.max(0, parseInt(g("encounter_base_chance").value))) / 100,
          is_active: g("is_active").checked,
        };
        if (!isEdit) body.hex_type = hex_type;
        try {
          if (isEdit) await adminFetch(`/api/admin/hex-terrain-config/${hex_type}`, { method:"PATCH", body:JSON.stringify(body) });
          else        await adminFetch("/api/admin/hex-terrain-config",              { method:"POST",  body:JSON.stringify(body) });
          showToast(isEdit?"Zapisano.":"Dodano typ terenu.", "success");
          c(); await onDone();
        } catch (e) { showToast(e.message || "Błąd", "error"); }
      }},
    ],
  });
}
