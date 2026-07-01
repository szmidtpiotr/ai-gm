/**
 * FADM-P14 (#450) — sekcja Kuźnia (Forge): Agent AI, haki, szablony, spotkania.
 * Port 1:1 z admin_panel_v3/index.html. Backend BEZ ZMIAN — tylko UI.
 *
 * Klastry przeniesione:
 *  - główny blok forge (_loadForge … forgeGeneratePlanConfirm/_doForgeGeneratePlan)
 *  - inline effect-builder (_ej*) + EFFECT_JSON_SCHEMA
 *  - współdzielony modalny effect-builder (openEffectBuilder + _ejModal*) — forge ma własną kopię
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── Aliasy zgodne z monolitem ────────────────────────────────────────────────
const _showToast = (msg, type) => showToast(msg, type);
const _esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const _buildUrl = p => { p = String(p); return p.startsWith('http') ? p : (p.startsWith('/') ? p : '/'+p); };
const _ADMIN_TOKEN_KEY = 'aigm_admin_token';

// ── Stan modułu ──────────────────────────────────────────────────────────────
const _sectionLoaded = new Set();       // używane przez inline onclick (invalidacja kart)
let _forgeSessionId = 'forge-' + Date.now();
let _forgeDraft = null;
let _forgeScenarioDirty = false;
let _forgeHooksFilter = { status: '', type: '' };
let _forgeCurrentIdeaId = null;
let _currentEncounter = null;           // {hook_id, encounter}
let _hookModalData = null;
let _forgePlanIdeaId = null;            // set when creating template from idea
let _tplEditorData = null;
let _tplEditorPlan = null;
let _forgeTemplatesCache = [];
let _tplDifficulty = 2;
let _sublocEditCtx = null;              // { locIdx, subIdx }
let _tplEntityCtx = null;               // { listKey, idx, type }
let _forgeEjData = null;
let _forgePlanTemplateId = null;

const _HOOK_TYPE_LABELS = {
  weapon:'⚔ Broń', armor:'🛡 Zbroja', item:'🎒 Przedmiot', consumable:'🧪 Mikstura',
  enemy:'💀 Wróg', npc:'👤 NPC', location:'🗺 Lokacja', event:'📜 Wydarzenie', theme:'💡 Motyw',
};

// ── Inline effect-builder schema (_ej*) ──────────────────────────────────────
const EFFECT_JSON_SCHEMA = {
  categories: {
    gear_bonus: {
      label: 'Bonus wyposażenia',
      allowed_types: ['static_stat_modifier']
    },
    character_condition: {
      label: 'Stan postaci',
      allowed_types: ['periodic_save', 'static_stat_modifier', 'block_action', 'dot', 'stacking_levels', 'escalating_dot', 'reroll', 'extra_action', 'on_expire_apply', 'on_zero_hp_save', 'condition_immunity', 'behavior_override', 'untargetable', 'ambush_bonus']
    },
    aura: {
      label: 'Aura',
      allowed_types: ['periodic_save', 'static_stat_modifier', 'apply_condition', 'remove_condition', 'block_action']
    }
  },
  effect_types: {
    static_stat_modifier: {
      label: 'Modyfikator statystyki (+stat)',
      fields: [
        { id: 'stat', label: 'Statystyka', type: 'select', options: ['STR','DEX','CON','INT','WIS','CHA'] },
        { id: 'value', label: 'Wartość', type: 'text', placeholder: '1 lub 1d4' },
        { id: 'tick', label: 'Tick', type: 'select', options: ['on_use','start_turn','each_round'] }
      ]
    },
    periodic_save: {
      label: 'Rzut obronny (co rundę)',
      fields: [
        { id: 'dc_key', label: 'Klucz DC', type: 'text', placeholder: 'np. dc_medium' },
        { id: 'condition_key', label: 'Stan przy fail', type: 'text', placeholder: 'np. frightened' },
        { id: 'tick', label: 'Tick', type: 'select', options: ['start_turn','each_round'] },
        { id: 'expires', label: 'Rundy (0=stały)', type: 'number' }
      ]
    },
    apply_condition: {
      label: 'Nałóż stan',
      fields: [
        { id: 'condition_key', label: 'Klucz stanu', type: 'text', placeholder: 'np. frightened' },
        { id: 'tick', label: 'Tick', type: 'select', options: ['on_use','start_turn','each_round'] },
        { id: 'expires', label: 'Rundy (0=stały)', type: 'number' }
      ]
    },
    remove_condition: {
      label: 'Usuń stan',
      fields: [
        { id: 'condition_key', label: 'Klucz stanu', type: 'text', placeholder: 'np. frightened' },
        { id: 'tick', label: 'Tick', type: 'select', options: ['on_use','start_turn','each_round'] }
      ]
    },
    block_action: {
      label: 'Zablokuj akcję',
      fields: [
        { id: 'tick', label: 'Tick', type: 'select', options: ['start_turn','each_round'] },
        { id: 'expires', label: 'Rundy (0=stały)', type: 'number' }
      ]
    },
    // S8 (#603): damage-over-time po kości (np. on_fire 2d6/turę).
    dot: {
      label: 'Obrażenia co turę (DOT)',
      fields: [
        { id: 'value', label: 'Obrażenia', type: 'text', placeholder: 'np. 2d6 lub 7' },
        { id: 'damage_type', label: 'Typ obrażeń', type: 'select', options: ['physical','magic','fire','poison','misc'] },
        { id: 'tick', label: 'Tick', type: 'select', options: ['start_turn','each_round'] }
      ]
    },
    // S9 (#604): kondycja z poziomami (np. exhausted). per_level_effects/threshold_effects
    // to struktury zagnieżdżone — autorowane przez seed/Smart Entry/JSON, nie płaskie pole.
    stacking_levels: {
      label: 'Poziomy stackowania (np. wyczerpanie)',
      fields: [
        { id: 'max_level', label: 'Maks. poziom', type: 'number', placeholder: '2' }
      ]
    },
    // S10 (#605): narastajacy DOT (np. hemorrhage 1d4/ture, +1d4 co 3 tury).
    escalating_dot: {
      label: 'Narastajacy DOT (np. krwotok)',
      fields: [
        { id: 'value', label: 'Kosc startowa', type: 'text', placeholder: 'np. 1d4' },
        { id: 'escalate_every_rounds', label: 'Co ile tur rosnie', type: 'number', placeholder: '3' },
        { id: 'escalate_dice', label: 'Przyrost (kosc)', type: 'text', placeholder: 'np. 1d4' },
        { id: 'damage_type', label: 'Typ obrazen', type: 'select', options: ['physical','magic','fire','poison','misc'] },
        { id: 'tick', label: 'Tick', type: 'select', options: ['start_turn','each_round'] }
      ]
    },
    // S12 (#607): dodatkowa akcja w turze (np. hasted — darmowa zmiana strefy).
    extra_action: {
      label: 'Dodatkowa akcja (np. przyśpieszenie)',
      fields: [
        { id: 'action_kind', label: 'Rodzaj akcji', type: 'select', options: ['move_only'] },
        { id: 'expires', label: 'Wygasa', type: 'text', placeholder: 'duration_rounds:3' }
      ]
    },
    // S12 (#607): przy wygaśnięciu kondycji nałóż inną (np. hasted → exhausted).
    on_expire_apply: {
      label: 'Po wygaśnięciu nałóż stan (np. wyczerpanie)',
      fields: [
        { id: 'condition_key', label: 'Stan do nałożenia', type: 'text', placeholder: 'np. exhausted' },
        { id: 'value', label: 'Poziom', type: 'number', placeholder: '1' }
      ]
    },
    // S13 (#608): rzut ratunkowy przy 0 HP (np. blessed CON DC 12 → 1 HP zamiast nieprzytomności).
    on_zero_hp_save: {
      label: 'Rzut ratunkowy przy 0 HP (np. błogosławieństwo)',
      fields: [
        { id: 'stat', label: 'Statystyka rzutu', type: 'select', options: ['STR','DEX','CON','INT','WIS','CHA'] },
        { id: 'value', label: 'DC', type: 'number', placeholder: '12' },
        { id: 'result', label: 'Skutek', type: 'select', options: ['stay_at_1hp'] },
        { id: 'uses', label: 'Użycia (na scenę)', type: 'number', placeholder: '1' }
      ]
    },
    // S14 (#609): odporność na kondycje (np. rage immune na slowed/weakened). immune_to =
    // lista kluczy kondycji (po przecinku). broken_by (top-level) autorowane przez seed/JSON.
    condition_immunity: {
      label: 'Odporność na kondycje (np. furia)',
      fields: [
        { id: 'immune_to', label: 'Odporność na (klucze po przecinku)', type: 'text', placeholder: 'slowed, weakened' },
        { id: 'expires', label: 'Wygasa', type: 'text', placeholder: 'duration_rounds:6' }
      ]
    },
    // S18 (#613): kondycja steruje turą aktora (confused/berserk/panicked). behavior:
    // random_table_k4 (k4: stoi/atak losowy/ucieczka/normalnie) / attack_nearest (atak
    // najbliższego niezależnie od frakcji) / flee (ucieczka, zmiana strefy).
    behavior_override: {
      label: 'Wymuszone zachowanie (np. szał, dezorientacja)',
      fields: [
        { id: 'behavior', label: 'Zachowanie', type: 'select', options: ['random_table_k4','attack_nearest','flee'] },
        { id: 'expires', label: 'Wygasa', type: 'text', placeholder: 'duration_rounds:6' }
      ]
    },
    // S19 (#614): hidden — untargetable (wróg pomija ukrytego) + ambush_bonus (+Nk6 pierwszy atak).
    untargetable: {
      label: 'Nietykalny (ukrycie — wróg pomija cel)',
      fields: []
    },
    ambush_bonus: {
      label: 'Zasadzka (+Nk6 pierwszy atak z ukrycia)',
      fields: [
        { id: 'value', label: 'Kość zasadzki', type: 'text', placeholder: '2d6' }
      ]
    }
  }
};

// ── Współdzielony modalny effect-builder — stałe + stan ──────────────────────
const _EJ_WEAPON_TYPES = {
  extra_damage: {
    label: 'Dodatkowe obrażenia (on hit)',
    fields: [
      { id: 'dice',        label: 'Kość',         type: 'text',   placeholder: '1d6' },
      { id: 'damage_type', label: 'Typ obrażeń',  type: 'select', options: ['physical','fire','poison','cold','lightning','necrotic','radiant','magic'] }
    ]
  },
  on_hit_save: {
    label: 'Rzut obronny przy trafieniu',
    fields: [
      { id: 'stat',            label: 'Save stat',    type: 'select',           options: ['STR','DEX','CON','INT','WIS','CHA'] },
      { id: 'dc',              label: 'DC',            type: 'number' },
      { id: '_on_fail_type',   label: 'Efekt (fail)', type: 'select',           options: ['apply_condition','extra_damage'] },
      { id: 'condition_key',   label: 'Stan (fail)',  type: 'condition_select' },
      { id: 'duration_rounds', label: 'Rundy',        type: 'number' }
    ]
  },
  remove_condition: {
    label: 'Usuń stan (on hit)',
    fields: [
      { id: 'condition_key', label: 'Stan', type: 'condition_select' }
    ]
  },
  skill_modifier: {
    label: 'Modyfikator umiejętności',
    fields: [
      { id: 'skill_key', label: 'Umiejętność', type: 'skill_select' },
      { id: 'value',     label: 'Wartość',     type: 'text', placeholder: '+1 lub -1' },
      { id: 'tick',      label: 'Kiedy',       type: 'select', options: ['on_use','start_turn','each_round'] }
    ]
  }
};

const _EJ_STANDARD_CATS = {
  gear_bonus:          { label: 'Bonus wyposażenia (pasywny)',   allowed_types: ['static_stat_modifier','skill_modifier','narrative_only'] },
  character_condition: { label: 'Stan postaci',                  allowed_types: ['periodic_save','static_stat_modifier','skill_modifier','block_action','heal_hp','restore_mana','narrative_only','dot','stacking_levels','escalating_dot','reroll','extra_action','on_expire_apply','on_zero_hp_save','behavior_override','untargetable','ambush_bonus'] },
  consumable_immediate:{ label: 'Efekt jednorazowy (eliksir)',   allowed_types: ['heal_hp','restore_mana','apply_condition','remove_condition','damage_enemy','skill_modifier','narrative_only'] },
  aura:                { label: 'Aura',                          allowed_types: ['periodic_save','static_stat_modifier','skill_modifier','apply_condition','remove_condition','block_action','narrative_only'] }
};

const _EJ_STANDARD_TYPES = {
  static_stat_modifier: { label: 'Modyfikator statystyki', fields: [
    { id: 'stat',  label: 'Stat',    type: 'select', options: ['STR','DEX','CON','INT','WIS','CHA'] },
    { id: 'value', label: 'Wartość', type: 'text',   placeholder: '2 lub -1' },
    { id: 'tick',  label: 'Kiedy',   type: 'select', options: ['on_use','start_turn','each_round'] }
  ]},
  skill_modifier: { label: 'Modyfikator umiejętności', fields: [
    { id: 'skill_key', label: 'Umiejętność', type: 'skill_select' },
    { id: 'value',     label: 'Wartość',     type: 'text', placeholder: '+1 lub -1' },
    { id: 'tick',      label: 'Kiedy',       type: 'select', options: ['on_use','start_turn','each_round'] }
  ]},
  periodic_save: { label: 'Rzut obronny (co rundę)', fields: [
    { id: 'stat',   label: 'Stat',     type: 'select', options: ['STR','DEX','CON','INT','WIS','CHA'] },
    { id: 'dc_key', label: 'Klucz DC', type: 'text',   placeholder: 'dc_medium' },
    { id: 'tick',   label: 'Kiedy',    type: 'select', options: ['start_turn','each_round'] },
    { id: 'expires',label: 'Wygasa',   type: 'text',   placeholder: 'save_success / duration_rounds:3' }
  ]},
  heal_hp:       { label: 'Leczenie HP',         fields: [{ id: 'value', label: 'Kość/wartość', type: 'text', placeholder: '2d6+2' }] },
  restore_mana:  { label: 'Przywrócenie many',   fields: [{ id: 'value', label: 'Kość/wartość', type: 'text', placeholder: '1d4'   }] },
  apply_condition: { label: 'Nałóż stan', fields: [
    { id: 'condition_key', label: 'Stan',   type: 'condition_select' },
    { id: 'expires',       label: 'Wygasa', type: 'text', placeholder: 'duration_rounds:3' }
  ]},
  remove_condition: { label: 'Usuń stan', fields: [
    { id: 'condition_key', label: 'Stan', type: 'condition_select' }
  ]},
  block_action: { label: 'Zablokuj akcję', fields: [
    { id: 'tick',   label: 'Kiedy',  type: 'select', options: ['start_turn','each_round'] },
    { id: 'expires',label: 'Wygasa', type: 'text',   placeholder: 'duration_rounds:2' }
  ]},
  narrative_only: { label: 'Tylko narracyjny', fields: [
    { id: 'value', label: 'Opis', type: 'text', placeholder: 'Opis efektu narracyjnego' }
  ]},
  // S9 (#604): poziomy stackowania (np. exhausted); per_level/threshold = seed/JSON.
  stacking_levels: { label: 'Poziomy stackowania', fields: [
    { id: 'max_level', label: 'Maks. poziom', type: 'number', placeholder: '2' }
  ]},
  // S10 (#605): narastajacy DOT (np. hemorrhage).
  escalating_dot: { label: 'Narastajacy DOT (np. krwotok)', fields: [
    { id: 'value',                label: 'Kosc startowa',     type: 'text',   placeholder: '1d4' },
    { id: 'escalate_every_rounds',label: 'Co ile tur rosnie', type: 'number', placeholder: '3'   },
    { id: 'escalate_dice',        label: 'Przyrost (kosc)',   type: 'text',   placeholder: '1d4' },
    { id: 'damage_type',          label: 'Typ obrazen',       type: 'select', options: ['physical','magic','fire','poison','misc'] },
    { id: 'tick',                 label: 'Tick',              type: 'select', options: ['start_turn','each_round'] }
  ]},
  // S11 (#606): przerzut testu (np. inspired/cursed). mode wymagany, uses/scope opcjonalne.
  reroll: { label: 'Przerzut testu (np. natchnienie/klatwa)', fields: [
    { id: 'mode',  label: 'Tryb',   type: 'select', options: ['player_keep_best','forced_keep_worst'] },
    { id: 'uses',  label: 'Uzycia', type: 'number', placeholder: '1' },
    { id: 'scope', label: 'Zakres', type: 'select', options: ['skill_test','attack','all'] }
  ]},
  // S12 (#607): dodatkowa akcja w turze (np. hasted — darmowa zmiana strefy).
  extra_action: { label: 'Dodatkowa akcja (np. przyspieszenie)', fields: [
    { id: 'action_kind', label: 'Rodzaj akcji', type: 'select', options: ['move_only'] },
    { id: 'expires',     label: 'Wygasa',       type: 'text',   placeholder: 'duration_rounds:3' }
  ]},
  // S12 (#607): po wygasnieciu kondycji nalozy inna (np. hasted -> exhausted).
  on_expire_apply: { label: 'Po wygasnieciu naloz stan (np. wyczerpanie)', fields: [
    { id: 'condition_key', label: 'Stan do nalozenia', type: 'condition_select' },
    { id: 'value',         label: 'Poziom',            type: 'number', placeholder: '1' }
  ]},
  // S13 (#608): rzut ratunkowy przy 0 HP (np. blessed CON DC 12 -> 1 HP).
  on_zero_hp_save: { label: 'Rzut ratunkowy przy 0 HP (np. blogoslawienstwo)', fields: [
    { id: 'stat',   label: 'Statystyka', type: 'select', options: ['STR','DEX','CON','INT','WIS','CHA'] },
    { id: 'value',  label: 'DC',         type: 'number', placeholder: '12' },
    { id: 'result', label: 'Skutek',     type: 'select', options: ['stay_at_1hp'] },
    { id: 'uses',   label: 'Uzycia',     type: 'number', placeholder: '1' }
  ]},
  // S18 (#613): kondycja steruje turą aktora (confused/berserk/panicked).
  behavior_override: { label: 'Wymuszone zachowanie (szal/dezorientacja/panika)', fields: [
    { id: 'behavior', label: 'Zachowanie', type: 'select', options: ['random_table_k4','attack_nearest','flee'] },
    { id: 'expires',  label: 'Wygasa',     type: 'text',   placeholder: 'duration_rounds:6' }
  ]},
  // S19 (#614): hidden — untargetable (wrog pomija ukrytego) + ambush_bonus (+Nk6 pierwszy atak).
  untargetable: { label: 'Nietykalny (ukrycie — wrog pomija cel)', fields: [] },
  ambush_bonus: { label: 'Zasadzka (+Nk6 pierwszy atak z ukrycia)', fields: [
    { id: 'value', label: 'Kosc zasadzki', type: 'text', placeholder: '2d6' }
  ]}
};

let _ejMode = 'weapon';
let _ejOnSave = null;
let _ejConditions = [];
let _ejSkills = [];
let _ejDataLoaded = false;

// ── Inline effect builder — gear on-equip types (weapons/armor/items) ────────
const _FORGE_EFFECT_TYPES = [
  { value: 'damage_bonus',        label: 'Bonus obrażeń',          fields: ['value'],
    tooltip: 'Stały bonus do obrażeń (int). NIE podwaja się przy krytycznym.' },
  { value: 'heal_on_hit',         label: 'Leczenie przy trafieniu', fields: ['value'],
    tooltip: 'HP przywrócone atakującemu przy każdym trafieniu (int).' },
  { value: 'ac_bonus',            label: 'Bonus AC',                fields: ['value'],
    tooltip: 'Bonus do AC na start walki (int).' },
  { value: 'static_stat_modifier',label: 'Modyfikator statystyki',  fields: ['stat', 'value'],
    tooltip: 'Modyfikator statystyki na start walki (int, może być ujemny).' },
  { value: 'apply_condition',     label: 'Aplikuj kondycję',        fields: ['condition_key', 'duration_rounds'],
    tooltip: 'Aplikuje kondycję na cel przy trafieniu.' },
  { value: 'narrative_only',      label: 'Tylko narracja',          fields: [],
    tooltip: 'Brak efektu mechanicznego.' },
];

// On-use effect types dla konsumabli (#771)
const _FORGE_CONSUMABLE_EFFECT_TYPES = [
  { value: 'heal_hp',        label: 'Leczenie HP',           fields: ['value'],
    tooltip: 'Leczy HP gracza. Wartość: kostka (np. 2d4) lub int.' },
  { value: 'restore_mana',   label: 'Przywróć manę',         fields: ['value'],
    tooltip: 'Przywraca manę (Scholar). Wartość: kostka lub int.' },
  { value: 'remove_condition',label: 'Zdejmij kondycję',     fields: ['condition_key'],
    tooltip: 'Usuwa kondycję z gracza.' },
  { value: 'apply_condition', label: 'Aplikuj kondycję',     fields: ['condition_key', 'target', 'duration_rounds'],
    tooltip: 'Aplikuje kondycję na gracza (self) lub wroga (enemy).' },
  { value: 'damage_enemy',   label: 'Obrażenia wrogowi ⭐', fields: ['value', 'target'],
    tooltip: 'Obrażenia wrogowi w walce. Poza walką → narracja. Wartość: kostka (np. 2d6).' },
  { value: 'narrative_only', label: 'Tylko narracja',        fields: [],
    tooltip: 'Brak efektu mechanicznego.' },
];
const _FORGE_STATS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

function _forgeGetEffectTypes() {
  return (_tplEntityCtx?.type === 'consumable') ? _FORGE_CONSUMABLE_EFFECT_TYPES : _FORGE_EFFECT_TYPES;
}

function _forgeEffectBuilderHtml(effects) {
  const rows = (effects || []).map((e, i) => _forgeEffectRowHtml(e, i)).join('');
  return `<div class="effect-builder" id="forge-effect-builder">
    <div id="forge-effect-rows">${rows}</div>
    <button type="button" class="btn btn-sm btn-secondary" id="forge-add-effect-btn" style="margin-top:6px">+ Efekt</button>
  </div>`;
}

function _forgeEffectRowHtml(e, i) {
  const types = _forgeGetEffectTypes();
  const defaultType = types[0]?.value || 'damage_bonus';
  const tdef = types.find(t => t.value === (e.type || defaultType)) || types[0];
  const typeSel = `<select class="form-input effect-type-sel forge-effect-type" style="min-width:170px" data-idx="${i}">
    ${types.map(t => `<option value="${t.value}"${e.type===t.value?' selected':''}>${_esc(t.label)}</option>`).join('')}
  </select>`;
  const extras = _forgeBuildExtraFields(tdef, e);
  return `<div class="effect-row" data-idx="${i}" style="display:flex;gap:6px;align-items:flex-end;margin-bottom:6px;flex-wrap:wrap">
    ${typeSel}
    <div class="effect-extra forge-effect-extra" style="display:flex;gap:6px;align-items:flex-end;flex-wrap:wrap">${extras}</div>
    <button type="button" class="btn-icon danger forge-effect-del" data-idx="${i}" title="Usuń efekt">✕</button>
  </div>`;
}

function _forgeBuildExtraFields(tdef, e) {
  return (tdef.fields || []).map(f => {
    if (f === 'value') {
      const tip = tdef.tooltip ? ` title="${_esc(tdef.tooltip)}"` : '';
      return `<input class="form-input forge-effect-value" type="number" placeholder="Wartość" value="${e.value??''}" style="width:90px"${tip}>`;
    }
    if (f === 'stat') {
      return `<select class="form-input forge-effect-stat" style="width:80px">
        ${_FORGE_STATS.map(s => `<option${e.stat===s?' selected':''}>${s}</option>`).join('')}
      </select>`;
    }
    if (f === 'condition_key') {
      const conds = _ejConditions || [];
      if (conds.length) {
        const opts = conds.map(c => `<option value="${_esc(c.v)}"${e.condition_key===c.v?' selected':''}>${_esc(c.l)}</option>`).join('');
        return `<select class="form-input forge-effect-cond" style="width:160px"><option value="">— kondycja —</option>${opts}</select>`;
      }
      return `<input class="form-input forge-effect-cond" type="text" placeholder="klucz kondycji" value="${_esc(e.condition_key||'')}" style="width:130px">`;
    }
    if (f === 'duration_rounds') return `<input class="form-input forge-effect-duration" type="number" placeholder="Rundy" value="${e.duration_rounds??3}" style="width:70px">`;
    if (f === 'target') {
      const cur = e.target || 'self';
      return `<select class="form-input forge-effect-target" style="width:100px">
        <option value="self"${cur==='self'?' selected':''}>self</option>
        <option value="enemy"${cur==='enemy'?' selected':''}>enemy</option>
        <option value="area"${cur==='area'?' selected':''}>area</option>
      </select>`;
    }
    return '';
  }).join('');
}

function _forgeReadEffects() {
  const rowsEl = document.getElementById('forge-effect-rows');
  if (!rowsEl) return [];
  const types = _forgeGetEffectTypes();
  const defaultType = types[0]?.value || 'damage_bonus';
  return Array.from(rowsEl.querySelectorAll('.effect-row')).map(row => {
    const type = row.querySelector('.forge-effect-type')?.value || defaultType;
    const tdef = types.find(t => t.value === type) || types[0];
    const e = { type };
    if (tdef.fields.includes('value')) {
      const raw = row.querySelector('.forge-effect-value')?.value ?? '';
      const v = parseFloat(raw);
      e.value = isNaN(v) ? (raw.trim() || 0) : v;
    }
    if (tdef.fields.includes('stat'))           { e.stat = row.querySelector('.forge-effect-stat')?.value || 'STR'; }
    if (tdef.fields.includes('condition_key'))  { e.condition_key = (row.querySelector('.forge-effect-cond')?.value || '').trim(); }
    if (tdef.fields.includes('duration_rounds')){ const d = parseInt(row.querySelector('.forge-effect-duration')?.value ?? '3'); e.duration_rounds = isNaN(d) ? 3 : d; }
    if (tdef.fields.includes('target'))         { e.target = row.querySelector('.forge-effect-target')?.value || 'self'; }
    return e;
  });
}

function _forgeSyncEjData() {
  const effects = _forgeReadEffects();
  const isConsumable = _tplEntityCtx?.type === 'consumable';
  const category = isConsumable ? 'consumable_immediate' : 'gear_bonus';
  _forgeEjData = effects.length > 0
    ? { schema_version: 1, effect_category: category, effects }
    : null;
}

function _forgeWireEffectBuilder() {
  const rowsEl = document.getElementById('forge-effect-rows');
  const addBtn = document.getElementById('forge-add-effect-btn');
  if (!rowsEl || !addBtn) return;

  const _wireRows = () => {
    rowsEl.querySelectorAll('.forge-effect-type').forEach(sel => {
      sel.addEventListener('change', () => {
        const i = parseInt(sel.dataset.idx);
        const effects = _forgeReadEffects();
        effects[i] = { type: sel.value };
        rowsEl.innerHTML = effects.map((e, j) => _forgeEffectRowHtml(e, j)).join('');
        _wireRows();
        _forgeSyncEjData();
      });
    });
    rowsEl.querySelectorAll('.forge-effect-del').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = parseInt(btn.dataset.idx);
        const effects = _forgeReadEffects();
        effects.splice(i, 1);
        rowsEl.innerHTML = effects.map((e, j) => _forgeEffectRowHtml(e, j)).join('');
        _wireRows();
        _forgeSyncEjData();
      });
    });
    rowsEl.querySelectorAll('.forge-effect-value,.forge-effect-stat,.forge-effect-duration,.forge-effect-cond').forEach(inp => {
      inp.addEventListener('input', _forgeSyncEjData);
      inp.addEventListener('change', _forgeSyncEjData);
    });
  };

  addBtn.addEventListener('click', () => {
    const effects = _forgeReadEffects();
    const types = _forgeGetEffectTypes();
    effects.push({ type: types[0]?.value || 'damage_bonus', value: 1 });
    rowsEl.innerHTML = effects.map((e, i) => _forgeEffectRowHtml(e, i)).join('');
    _wireRows();
    _forgeSyncEjData();
  });

  _wireRows();
  _forgeSyncEjData();
}

// openSmartEntryForDbItem żyje w content/smart-entry (nieportowane tu) — graceful fallback.
function openSmartEntryForDbItem(entryType, key) {
  if (typeof window !== 'undefined' && typeof window.openSmartEntryForDbItem === 'function' && window.openSmartEntryForDbItem !== openSmartEntryForDbItem) {
    return window.openSmartEntryForDbItem(entryType, key);
  }
  _showToast('Edycja rekordu DB dostępna w sekcji Przedmioty (Smart Entry).', 'info');
}

// ── Agent AI / pomysły ───────────────────────────────────────────────────────
async function _loadForge() {
  _forgeSessionId = 'forge-' + Date.now();
  // Wire forge tabs
  document.getElementById('forge-tabs')?.querySelectorAll('.stab[data-forgetab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#forge-tabs .stab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.forgetab;
      document.querySelectorAll('[id^="forge-tab-"]').forEach(p => p.style.display = 'none');
      const panel = document.getElementById(`forge-tab-${tab}`);
      if (panel) panel.style.display = '';
      if (tab === 'hooks') _loadForgeHooks();
      if (tab === 'templates') _loadForgeTemplates();
      if (tab === 'encounters') _loadForgeEncounters();
    });
  });
  // Wire hooks status filter
  document.getElementById('forge-hooks-status-bar')?.querySelectorAll('.stab[data-hookstatus]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#forge-hooks-status-bar .stab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _forgeHooksFilter.status = btn.dataset.hookstatus;
      _loadForgeHooks();
    });
  });
  // Wire hooks type filter
  document.getElementById('forge-hooks-type-filter')?.querySelectorAll('.chip[data-hooktype]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#forge-hooks-type-filter .chip').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      _forgeHooksFilter.type = btn.dataset.hooktype;
      _loadForgeHooks();
    });
  });
  await _refreshForgeIdeas();
}

async function _refreshForgeIdeas() {
  try {
    const d = await apiFetch('/api/admin/forge/ideas');
    const items = d.items || [];
    const list = document.getElementById('forge-ideas-list');
    const count = document.getElementById('forge-ideas-count');
    if (count) count.textContent = `${items.length} pomysłów`;
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<div style="color:var(--t3);font-size:0.78rem;padding:6px 0">Brak zapisanych pomysłów.</div>';
      return;
    }
    list.innerHTML = items.map(idea => `
      <div class="forge-idea-chip" onclick="forgeOpenIdea(${idea.id})" title="${_esc(idea.premise||'')}">
        <div class="forge-idea-chip-title">${_esc(idea.title)}</div>
        <div class="forge-idea-chip-sub">${_esc(idea.difficulty||'?')} · ${idea.created_at?.substring(0,10)||''}</div>
        <div style="display:flex;gap:4px;margin-top:5px">
          <button class="btn btn-sm btn-secondary" style="font-size:0.7rem;padding:2px 6px" onclick="event.stopPropagation();forgeExtractHooks(${idea.id},this)">Haki ⚓</button>
          <button class="btn btn-sm" style="font-size:0.7rem;padding:2px 6px;color:var(--red)" onclick="event.stopPropagation();if(confirm('Usunąć?'))apiFetch('/api/admin/forge/ideas/${idea.id}',{method:'DELETE'}).then(()=>{_sectionLoaded.delete('forge');_loadForge()})">🗑</button>
        </div>
      </div>`).join('');
  } catch(e) { console.warn('forge ideas', e.message); }
}

function forgeOpenIdea(id) {
  _forgeCurrentIdeaId = id;
  apiFetch(`/api/admin/forge/ideas/${id}`).then(idea => {
    // Switch to agent tab
    const agentTab = document.querySelector('#forge-tabs .stab[data-forgetab="agent"]');
    if (agentTab && !agentTab.classList.contains('active')) agentTab.click();
    // Build draft and load into editable scenario panel
    const sd = idea.structured_data || {};
    const draftFromIdea = {
      title: idea.title,
      premise: idea.premise,
      tone: idea.tone || [],
      themes: idea.themes || [],
      difficulty: idea.difficulty,
      arcs: sd.arcs || [],
      hooks: sd.hooks || [],
      player_hook: sd.player_hook,
      gm_private: sd.gm_private,
    };
    _forgeDraft = draftFromIdea;
    _forgeRenderScenario(draftFromIdea);
    // Action buttons in scenario body
    const actionsEl = document.getElementById('fsc-actions');
    if (actionsEl) {
      actionsEl.style.display = 'flex';
      actionsEl.innerHTML =
        `<button class="btn btn-sm btn-secondary" onclick="forgeReloadIdeaInChat(${id})">↩ Kontynuuj w Warsztacie</button>` +
        `<button class="btn btn-sm btn-primary" onclick="forgeExtractHooks(${id},this)">⚡ Wyodrębnij haki → DB</button>` +
        `<button class="btn btn-sm btn-secondary" onclick="forgeCreateTemplateFromIdea(${id},${JSON.stringify(idea.title).replace(/"/g,'&quot;')},${sd.arcs?.length||0})">📖 Utwórz szablon</button>`;
    }
    // Inject context into chat
    const hist = document.getElementById('forge-chat-history');
    if (hist) {
      hist.querySelectorAll('.forge-bubble--hint').forEach(el => el.remove());
      _forgeAppendBubble(hist, 'forge-bubble forge-bubble--context',
        `<strong>↩ Załadowano: ${_esc(idea.title)}</strong><br><span style="font-size:0.74rem;color:var(--t2)">${_esc(idea.premise?.substring(0,120)||'')}</span>`);
    }
  }).catch(e => console.warn('forge open idea', e.message));
}

async function forgeReloadIdeaInChat(id) {
  try {
    const idea = await apiFetch(`/api/admin/forge/ideas/${id}`);
    const sd = idea.structured_data || {};

    // Reset session so we start fresh context
    _forgeSessionId = 'forge-idea-' + id + '-' + Date.now();

    // Switch to the Agent AI tab so the chat is visible
    const agentTab = document.querySelector('#forge-tabs .stab[data-forgetab="agent"]');
    if (agentTab) agentTab.click();

    const chatContainer = document.getElementById('forge-chat-history');
    if (!chatContainer) return;

    // Inject context into chat display
    const summary = [
      idea.title,
      idea.premise ? 'Premisa: ' + idea.premise.substring(0, 120) : '',
      sd.arcs?.length ? 'Akty: ' + sd.arcs.map(a => a.title).join(', ') : '',
      sd.player_hook ? 'Wciągacz: ' + sd.player_hook.substring(0, 100) : '',
    ].filter(Boolean).join('\n');

    chatContainer.querySelectorAll('.forge-bubble--hint').forEach(el => el.remove());
    _forgeAppendBubble(chatContainer, 'forge-bubble forge-bubble--context',
      '<strong>↩ Załadowano szkic: ' + _esc(idea.title) + '</strong><br>' +
      '<span style="font-size:0.75rem;white-space:pre-wrap">' + _esc(summary) + '</span>');

    // Pre-fill input with a continuation prompt
    const input = document.getElementById('forge-input');
    if (input) {
      input.value = 'Chcę dopracować ten szkic. Co możemy poprawić lub rozbudować?';
      input.focus();
    }
  } catch(e) { _showToast('Błąd ładowania szkicu.', 'error'); }
}

function _formatForgeText(text) {
  // HTML-escape first, then apply lightweight markdown-ish formatting
  let s = _esc(text);
  // Paragraphs: double newline
  s = s.replace(/\n\n+/g, '</p><p>');
  // Single newline → br
  s = s.replace(/\n/g, '<br>');
  // Bold: **text**
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text*
  s = s.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
  // Bullet lines (- item or • item at line start — already split by <br>)
  s = s.replace(/(^|<br>)[-•] (.+?)(?=<br>|<\/p>|$)/g, '$1<span style="display:inline-block;padding-left:10px">• $2</span>');
  return `<p>${s}</p>`;
}

function _fscAutoResize(el) {
  el.style.height = 'auto';
  el.style.height = (el.scrollHeight + 2) + 'px';
}

function _fscAutoResizeAll() {
  document.querySelectorAll('.fsc-textarea').forEach(el => _fscAutoResize(el));
}

function _forgeToggleChat() {
  const fc = document.getElementById('forge-float-chat');
  if (!fc) return;
  const isHidden = fc.classList.contains('ffc-hidden');
  fc.classList.toggle('ffc-hidden', !isHidden);
  if (isHidden) {
    // just opened — focus input
    const inp = document.getElementById('forge-input');
    if (inp) setTimeout(() => inp.focus(), 150);
  }
}

function _forgeIdeasShelfToggle() {
  const shelf = document.getElementById('forge-ideas-shelf');
  if (shelf) shelf.classList.toggle('open');
}

// Draggable float chat
function _forgeDragInit() {
  let dragging = false, ox = 0, oy = 0;
  const handle = document.getElementById('forge-float-drag-handle');
  const chat = document.getElementById('forge-float-chat');
  if (!handle || !chat || handle._dragWired) return;
  handle._dragWired = true;
  handle.addEventListener('mousedown', e => {
    if (e.target.tagName === 'BUTTON') return;
    dragging = true;
    const rect = chat.getBoundingClientRect();
    ox = e.clientX - rect.left;
    oy = e.clientY - rect.top;
    chat.style.transition = 'none';
    e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    let x = e.clientX - ox;
    let y = e.clientY - oy;
    const maxX = window.innerWidth - chat.offsetWidth;
    const maxY = window.innerHeight - chat.offsetHeight;
    x = Math.max(0, Math.min(x, maxX));
    y = Math.max(0, Math.min(y, maxY));
    chat.style.left = x + 'px';
    chat.style.right = 'auto';
    chat.style.top = y + 'px';
    chat.style.bottom = 'auto';
  });
  document.addEventListener('mouseup', () => {
    dragging = false;
    if (chat) chat.style.transition = '';
  });
}

function _forgeInputKey(e) {
  if (e.key === 'Enter' && e.ctrlKey) {
    e.preventDefault();
    sendForgeMsg();
  }
  // plain Enter = default (newline) — no interception needed
}

function _forgeSidebarToggle() {
  // legacy noop
}

function _forgeNewSession() {
  _forgeDraft = null;
  _forgeScenarioDirty = false;
  _forgeSessionId = 'forge-' + Date.now();
  const hist = document.getElementById('forge-chat-history');
  if (hist) hist.innerHTML = '<div class="forge-bubble forge-bubble--hint">Opisz swój pomysł na przygodę — Agent dopyta i zbuduje strukturę.<br><span style="font-size:0.74rem;opacity:0.65">Ctrl+Enter wysyła · Enter = nowa linia</span></div>';
  const input = document.getElementById('forge-input');
  if (input) { input.value = ''; input.focus(); }
  // Reset scenario panel
  const empty = document.getElementById('forge-scenario-empty');
  if (empty) empty.style.display = '';
  const panel = document.getElementById('forge-scenario-panel');
  if (panel) panel.style.display = 'none';
  const actionsEl = document.getElementById('fsc-actions');
  if (actionsEl) { actionsEl.style.display = 'none'; actionsEl.innerHTML = ''; }
}

function _forgeMarkDirty() {
  _forgeScenarioDirty = true;
  const badge = document.getElementById('fsc-dirty-badge');
  if (badge) badge.style.display = '';
}

function _forgeRenderScenario(draft) {
  if (!draft) return;
  const empty = document.getElementById('forge-scenario-empty');
  const panel = document.getElementById('forge-scenario-panel');
  if (empty) empty.style.display = 'none';
  if (panel) panel.style.display = 'block';

  // Title + premise
  const titleEl = document.getElementById('fsc-title');
  if (titleEl) titleEl.value = draft.title || '';
  const premiseEl = document.getElementById('fsc-premise');
  if (premiseEl) premiseEl.value = draft.premise || '';

  // Meta chips
  const chipsEl = document.getElementById('fsc-chips');
  const metaRow = document.getElementById('fsc-meta-row');
  if (chipsEl) {
    const chips = [];
    if (draft.difficulty) chips.push(`⚔ ${draft.difficulty}`);
    (draft.tone || []).forEach(t => chips.push(`🎭 ${t}`));
    (draft.themes || []).forEach(t => chips.push(`◈ ${t}`));
    if (chips.length) {
      chipsEl.innerHTML = chips.map(c => `<span class="fsc-chip">${_esc(c)}</span>`).join('');
      if (metaRow) metaRow.style.display = '';
    }
  }

  // Arcs
  const arcsEl = document.getElementById('fsc-arcs');
  const arcsSection = document.getElementById('fsc-arcs-section');
  const arcsCount = document.getElementById('fsc-arcs-count');
  const arcs = draft.arcs || [];
  if (arcsEl && arcs.length) {
    if (arcsCount) arcsCount.textContent = `(${arcs.length})`;
    arcsEl.innerHTML = arcs.map((arc, i) => {
      const goalsVal = (arc.scene_goals || []).join('\n');
      return `<div class="fsc-arc-card">
        <button class="fsc-arc-head" onclick="this.nextElementSibling.classList.toggle('hidden')">
          <span style="color:var(--t3);font-size:0.72rem">Akt ${i+1}</span>
          <span style="flex:1">${_esc(arc.title || '')}</span>
          <span style="font-size:0.7rem;color:var(--t3)">▾</span>
        </button>
        <div class="fsc-arc-body">
          <textarea class="fsc-textarea" data-arc="${i}" data-field="description"
            oninput="_forgeMarkDirty();_fscAutoResize(this)">${_esc(arc.description || '')}</textarea>
          <div style="font-size:0.75rem;color:var(--t3);margin-top:4px">Cele scen <span style="opacity:0.6">(jedna na linię)</span></div>
          <textarea class="fsc-textarea" data-arc="${i}" data-field="scene_goals"
            placeholder="Cel sceny 1&#10;Cel sceny 2&#10;…"
            oninput="_forgeMarkDirty();_fscAutoResize(this)">${_esc(goalsVal)}</textarea>
          ${arc.private_twist ? `<div style="font-size:0.75rem;color:var(--amber,#c9a227);font-style:italic;margin-top:2px">🔒 ${_esc(arc.private_twist)}</div>` : ''}
        </div>
      </div>`;
    }).join('');
    if (arcsSection) arcsSection.style.display = '';
  }

  // Hooks
  const hooksSection = document.getElementById('fsc-hooks-section');
  const hooksList = document.getElementById('fsc-hooks-list');
  const hooksCount = document.getElementById('fsc-hooks-count');
  const hooks = draft.hooks || [];
  if (hooksList && hooks.length) {
    if (hooksCount) hooksCount.textContent = `(${hooks.length})`;
    const _typeColor = { weapon:'var(--red)', enemy:'var(--orange,#e07040)', npc:'var(--blue)', location:'var(--green)', item:'var(--purple,#8a5af0)' };
    hooksList.innerHTML = hooks.map(h =>
      `<span class="fsc-chip" style="border-color:${_typeColor[h.hook_type||h.type]||'var(--border)'};color:${_typeColor[h.hook_type||h.type]||'var(--t2)'}">${_esc(h.title||h.label||'')}</span>`
    ).join('');
    if (hooksSection) hooksSection.style.display = '';
  }

  // Player hook + GM private
  const ph = draft.player_hook;
  const phSection = document.getElementById('fsc-player-hook-section');
  const phEl = document.getElementById('fsc-player-hook');
  if (ph && phEl) { phEl.value = ph; if (phSection) phSection.style.display = ''; }

  const gm = draft.gm_private;
  const gmSection = document.getElementById('fsc-gm-section');
  const gmEl = document.getElementById('fsc-gm-private');
  if (gm && gmEl) { gmEl.value = gm; if (gmSection) gmSection.style.display = ''; }

  // Reset dirty state after render
  _forgeScenarioDirty = false;
  const badge = document.getElementById('fsc-dirty-badge');
  if (badge) badge.style.display = 'none';
  // Auto-resize all textareas after content set
  setTimeout(_fscAutoResizeAll, 0);
}

function _forgeCollectScenario() {
  // Collect current scenario panel values back into draft object
  const draft = JSON.parse(JSON.stringify(_forgeDraft || {}));
  const titleEl = document.getElementById('fsc-title');
  if (titleEl) draft.title = titleEl.value;
  const premiseEl = document.getElementById('fsc-premise');
  if (premiseEl) draft.premise = premiseEl.value;
  const phEl = document.getElementById('fsc-player-hook');
  if (phEl) draft.player_hook = phEl.value;
  const gmEl = document.getElementById('fsc-gm-private');
  if (gmEl) draft.gm_private = gmEl.value;
  // Arc descriptions + scene_goals
  document.querySelectorAll('[data-arc][data-field="description"]').forEach(ta => {
    const i = parseInt(ta.dataset.arc);
    if (draft.arcs && draft.arcs[i]) draft.arcs[i].description = ta.value;
  });
  document.querySelectorAll('[data-arc][data-field="scene_goals"]').forEach(ta => {
    const i = parseInt(ta.dataset.arc);
    if (draft.arcs && draft.arcs[i]) {
      draft.arcs[i].scene_goals = ta.value.split('\n').map(s => s.trim()).filter(Boolean);
    }
  });
  return draft;
}

async function _forgeSendEditsToAgent() {
  const collected = _forgeCollectScenario();
  _forgeDraft = collected;
  const input = document.getElementById('forge-input');
  const currentMsg = input?.value?.trim() || 'Zaktualizowałem szkic. Kontynuuj na podstawie tych zmian.';
  if (input) input.value = '';
  // Open floating chat so user sees the agent's response
  const fc = document.getElementById('forge-float-chat');
  if (fc && fc.classList.contains('ffc-hidden')) fc.classList.remove('ffc-hidden');
  await _forgeSendMessage(currentMsg, collected);
}

function _forgeAppendBubble(hist, cls, html) {
  const div = document.createElement('div');
  div.className = `forge-bubble ${cls}`;
  div.innerHTML = html;
  hist.appendChild(div);
  hist.scrollTop = hist.scrollHeight;
}

async function sendForgeMsg() {
  const input = document.getElementById('forge-input');
  const btn = document.getElementById('forge-send-btn');
  if (!input || !btn) return;
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  // Always pass current scenario so LLM knows full state (collect latest edits too)
  const draftOverride = _forgeDraft ? _forgeCollectScenario() : null;
  if (draftOverride) _forgeDraft = draftOverride;
  await _forgeSendMessage(msg, draftOverride);
  btn.disabled = false;
  input.focus();
}

async function _forgeSendMessage(msg, draftOverride) {
  const btn = document.getElementById('forge-send-btn');
  if (btn) btn.disabled = true;
  const hist = document.getElementById('forge-chat-history');
  hist.querySelectorAll('.forge-bubble--hint').forEach(el => el.remove());
  _forgeAppendBubble(hist, 'forge-bubble--user', _esc(msg).replace(/\n/g, '<br>'));
  // Typing indicator
  const thinking = document.createElement('div');
  thinking.className = 'forge-bubble forge-bubble--ai forge-bubble--thinking';
  thinking.innerHTML = '<span class="forge-typing-dots"><span></span><span></span><span></span></span>';
  hist.appendChild(thinking);
  hist.scrollTop = hist.scrollHeight;
  try {
    const body = { session_id: _forgeSessionId, message: msg };
    if (draftOverride) body.draft_override = draftOverride;
    const d = await apiFetch('/api/admin/forge/chat/message', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    thinking.remove();
    _forgeAppendBubble(hist, 'forge-bubble--ai', _formatForgeText(d.reply));
    if (d.draft) {
      _forgeDraft = d.draft;
      _forgeRenderScenario(d.draft);
    }
  } catch(e) {
    thinking.remove();
    _forgeAppendBubble(hist, 'forge-bubble--error', _esc(e.message));
  }
  if (btn) btn.disabled = false;
}

async function saveForgeIdea() {
  if (!_forgeDraft) { _showToast('Brak szkicu do zapisania.', 'warning'); return; }
  try {
    const arcCount = (_forgeDraft?.arcs || []).length;
    const d = await apiFetch('/api/admin/forge/chat/save', {
      method: 'POST',
      body: JSON.stringify({ session_id: _forgeSessionId, idea_data: _forgeDraft }),
    });
    _showToast(`Zapisano: ${d.idea?.title||'pomysł'}`, 'success');
    const ideaId = d.idea?.id;
    const ideaTitle = d.idea?.title || '';
    _forgeDraft = null;
    _forgeSessionId = 'forge-' + Date.now();
    const saveRow = document.getElementById('forge-save-row');
    if (saveRow) saveRow.style.display = 'none';
    // Show next-step actions immediately after save
    const actionsEl = document.getElementById('fsc-actions');
    if (actionsEl && ideaId) {
      actionsEl.style.display = 'flex';
      actionsEl.innerHTML =
        `<button class="btn btn-sm btn-secondary" onclick="forgeReloadIdeaInChat(${ideaId})">↩ Kontynuuj w Warsztacie</button>` +
        `<button class="btn btn-sm btn-primary" onclick="forgeExtractHooks(${ideaId},this)">⚡ Wyodrębnij haki → DB</button>` +
        `<button class="btn btn-sm btn-secondary" onclick="forgeCreateTemplateFromIdea(${ideaId},${JSON.stringify(ideaTitle).replace(/"/g,'&quot;')},${arcCount})">📖 Utwórz szablon</button>`;
    }
    await _refreshForgeIdeas();
  } catch(e) { _showToast(e.message||'Błąd zapisu.', 'error'); }
}

async function forgeExtractHooks(ideaId, btn) {
  const orig = btn?.textContent || 'Wyodrębnij haki';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Ekstrahuję…'; }
  try {
    const d = await apiFetch(`/api/admin/forge/ideas/${ideaId}/extract-hooks`, { method: 'POST' });
    _showToast(`Wyodrębniono ${d.hooks_created} hooków → zakładka Haki`, 'success');
    // Switch to hooks tab
    document.querySelectorAll('#forge-tabs .stab').forEach(b => b.classList.remove('active'));
    const hookTab = document.querySelector('#forge-tabs .stab[data-forgetab="hooks"]');
    if (hookTab) hookTab.classList.add('active');
    document.querySelectorAll('[id^="forge-tab-"]').forEach(p => p.style.display = 'none');
    const panel = document.getElementById('forge-tab-hooks');
    if (panel) panel.style.display = '';
    _forgeHooksFilter.status = 'pending';
    document.querySelectorAll('#forge-hooks-status-bar .stab').forEach(b => {
      b.classList.toggle('active', b.dataset.hookstatus === 'pending');
    });
    await _loadForgeHooks();
  } catch(e) { _showToast(e.message||'Błąd ekstrakcji.', 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = orig; } }
}

// ── Spotkania tab ──────────────────────────────────────────────────────────
async function _loadForgeEncounters() {
  const grid = document.getElementById('forge-encounters-grid');
  if (!grid) return;
  grid.innerHTML = '<em style="color:var(--t3);font-size:0.82rem">Ładowanie…</em>';
  try {
    const d = await apiFetch('/api/admin/forge/encounters');
    if (!d.encounters || d.encounters.length === 0) {
      grid.innerHTML = '<em style="color:var(--t3);font-size:0.82rem">Brak spotkań. Zatwierdź hak i kliknij "Utwórz spotkanie" w modalnym.</em>';
      return;
    }
    grid.innerHTML = d.encounters.map(e => {
      const enc = e.encounter || {};
      const typeLabel = _HOOK_TYPE_LABELS[e.hook_type] || e.hook_type;
      const enemies = (enc.enemies || []).map(en => `${en.name} ×${en.count||1}`).join(', ');
      return `<div class="card" style="cursor:pointer;border:1px solid var(--border)" onclick="openEncounterModal(${e.hook_id})">
        <div class="card-header" style="padding-bottom:6px">
          <span class="badge" style="font-size:0.7rem;background:var(--surface3)">${typeLabel}</span>
          <span style="font-size:0.78rem;color:var(--t3);margin-left:6px">#${e.hook_id} ${_esc(e.hook_title)}</span>
        </div>
        <div style="padding:0 12px 12px">
          <div style="font-weight:600;font-size:0.9rem;margin-bottom:4px">${_esc(enc.title||'')}</div>
          ${enc.trigger_condition?`<div style="font-size:0.75rem;color:var(--yellow);margin-bottom:6px">⚡ ${_esc(enc.trigger_condition)}</div>`:''}
          ${enc.scene_setup?`<div style="font-size:0.78rem;color:var(--t2);margin-bottom:8px">${_esc(enc.scene_setup.substring(0,120))}${enc.scene_setup.length>120?'…':''}</div>`:''}
          ${enemies?`<div style="font-size:0.75rem;color:var(--red)">💀 ${_esc(enemies)}</div>`:''}
        </div>
      </div>`;
    }).join('');
  } catch(e) { grid.innerHTML = `<span style="color:var(--red)">${e.message}</span>`; }
}

async function openEncounterModal(hookId) {
  try {
    const d = await apiFetch('/api/admin/forge/encounters');
    const item = (d.encounters || []).find(e => e.hook_id === hookId);
    if (!item) { _showToast('Nie znaleziono spotkania', 'error'); return; }
    _currentEncounter = item;
    const enc = item.encounter || {};

    document.getElementById('em-hook-badge').textContent = (_HOOK_TYPE_LABELS[item.hook_type]||item.hook_type) + ' · hak #' + hookId;
    document.getElementById('em-hook-title').textContent = item.hook_title;
    document.getElementById('em-title').value = enc.title || '';
    document.getElementById('em-trigger').value = enc.trigger_condition || '';
    document.getElementById('em-scene').value = enc.scene_setup || '';
    document.getElementById('em-enemies').value = (enc.enemies||[]).map(e=>`${e.name} ×${e.count||1}${e.notes?' — '+e.notes:''}`).join('\n');
    document.getElementById('em-objectives').value = (enc.objectives||[]).join('\n');
    const rew = enc.rewards || {};
    document.getElementById('em-xp').value = rew.xp_estimate || '';
    document.getElementById('em-loot').value = rew.loot_notes || '';
    document.getElementById('em-gm-notes').value = enc.gm_notes || '';

    // Trigger config
    const trigTypes = enc.trigger_types || [];
    document.getElementById('em-trig-hex').checked = trigTypes.includes('hex_enter');
    document.getElementById('em-trig-nturns').checked = trigTypes.includes('n_turns');
    document.getElementById('em-trig-combat').checked = trigTypes.includes('combat_end');
    const nturnsInterval = enc.n_turns_interval || 5;
    document.getElementById('em-nturns-interval').value = nturnsInterval;
    document.getElementById('em-nturns-row').style.display = trigTypes.includes('n_turns') ? 'flex' : 'none';
    const prob = enc.trigger_probability !== undefined ? enc.trigger_probability : 0.25;
    document.getElementById('em-probability').value = prob;
    document.getElementById('em-prob-val').textContent = Math.round(prob * 100) + '%';
    document.getElementById('em-biomes').value = (enc.biomes || []).join(', ');
    document.getElementById('em-tags').value = (enc.tags || []).join(', ');

    // Show modal first, then populate picker (don't block modal on picker error)
    document.getElementById('encounter-modal').classList.add('open');
    ['em-scene','em-enemies','em-objectives','em-gm-notes'].forEach(id => {
      const el = document.getElementById(id); if (el) _fscAutoResize(el);
    });
    _previewEncounterFromForm();
    _populateEncounterCampaignPicker(); // async, fire-and-forget
  } catch(e) { _showToast(e.message, 'error'); }
}

async function _populateEncounterCampaignPicker() {
  const sel = document.getElementById('em-campaign-picker');
  if (!sel) return;
  try {
    const d = await apiFetch('/api/admin/campaigns/live');
    const campaigns = d.items || [];
    sel.innerHTML = campaigns.length
      ? campaigns.map(c => `<option value="${c.id}">${_esc(c.title||('Kampania #'+c.id))}</option>`).join('')
      : '<option value="">Brak aktywnych kampanii</option>';
  } catch(e) { sel.innerHTML = '<option value="">Błąd ładowania</option>'; }
}

function _readEncounterFromForm() {
  // Parse enemies from text block
  const enemiesRaw = document.getElementById('em-enemies').value.trim();
  const enemies = enemiesRaw ? enemiesRaw.split('\n').filter(Boolean).map(line => {
    const m = line.match(/^(.+?)\s*×(\d+)\s*(?:—\s*(.+))?$/);
    if (m) return { name: m[1].trim(), count: parseInt(m[2]), notes: m[3]||'' };
    return { name: line.trim(), count: 1, notes: '' };
  }) : [];
  const objectives = document.getElementById('em-objectives').value.trim().split('\n').filter(Boolean);
  const trigTypes = [];
  if (document.getElementById('em-trig-hex').checked) trigTypes.push('hex_enter');
  if (document.getElementById('em-trig-nturns').checked) trigTypes.push('n_turns');
  if (document.getElementById('em-trig-combat').checked) trigTypes.push('combat_end');
  const biomes = document.getElementById('em-biomes').value.split(',').map(s=>s.trim()).filter(Boolean);
  const tags = document.getElementById('em-tags').value.split(',').map(s=>s.trim()).filter(Boolean);
  return {
    title: document.getElementById('em-title').value.trim(),
    trigger_condition: document.getElementById('em-trigger').value.trim(),
    trigger_types: trigTypes,
    trigger_probability: parseFloat(document.getElementById('em-probability').value) || 0.25,
    n_turns_interval: parseInt(document.getElementById('em-nturns-interval').value) || 5,
    biomes,
    tags,
    scene_setup: document.getElementById('em-scene').value.trim(),
    enemies,
    objectives,
    rewards: {
      xp_estimate: parseInt(document.getElementById('em-xp').value) || 0,
      loot_notes: document.getElementById('em-loot').value.trim(),
    },
    gm_notes: document.getElementById('em-gm-notes').value.trim(),
  };
}

async function _saveEncounterEdits() {
  if (!_currentEncounter) return;
  const encounter = _readEncounterFromForm();
  try {
    await apiFetch(`/api/admin/forge/encounters/${_currentEncounter.hook_id}`, {
      method: 'PATCH',
      body: JSON.stringify({ encounter }),
    });
    _showToast('Spotkanie zapisane!', 'success');
    document.getElementById('encounter-modal').classList.remove('open');
    _loadForgeEncounters();
  } catch(e) { _showToast(e.message, 'error'); }
}

async function _injectEncounterFromModal() {
  if (!_currentEncounter) return;
  const campaignId = parseInt(document.getElementById('em-campaign-picker')?.value);
  if (!campaignId) { _showToast('Wybierz kampanię', 'error'); return;  }
  const btn = document.getElementById('em-inject-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    await apiFetch('/api/admin/forge/debug/inject-encounter', {
      method: 'POST',
      body: JSON.stringify({ campaign_id: campaignId, hook_id: _currentEncounter.hook_id }),
    });
    _showToast('Spotkanie wstrzyknięte do kampanii! Następna tura gracza je użyje.', 'success');
    document.getElementById('encounter-modal').classList.remove('open');
  } catch(e) { _showToast(e.message, 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = '⚡ Wstrzyknij do kampanii'; } }
}

// ── Haki tab ─────────────────────────────────────────────────────────────────
async function _loadForgeHooks() {
  const grid = document.getElementById('forge-hooks-grid');
  if (!grid) return;
  grid.innerHTML = '<div style="color:var(--t3);font-size:0.8rem;padding:8px">Ładowanie…</div>';
  try {
    const params = new URLSearchParams();
    if (_forgeHooksFilter.status) params.set('status', _forgeHooksFilter.status);
    if (_forgeHooksFilter.type) params.set('hook_type', _forgeHooksFilter.type);
    const d = await apiFetch('/api/admin/forge/hooks?' + params.toString());
    const hooks = d.items || [];
    if (!hooks.length) {
      grid.innerHTML = '<div style="color:var(--t3);font-size:0.8rem;padding:8px;grid-column:1/-1">Brak hooków.</div>';
      return;
    }
    grid.innerHTML = hooks.map(h => {
      const statusColor = {pending:'var(--amber)',approved:'var(--green)',promoted:'var(--blue)',rejected:'var(--red)',draft:'var(--t3)'}[h.status]||'var(--t3)';
      const dd = h.draft_data || {};
      const canPromote = ['weapon','armor','item','consumable','enemy','npc','location'].includes(h.hook_type);
      return '<div class="card" style="padding:10px 12px;cursor:pointer" onclick="openHookModal(' + h.id + ')">' +
        '<div style="display:flex;justify-content:space-between;margin-bottom:6px">' +
          '<span style="font-size:0.75rem;font-weight:600;color:var(--t3)">' + (_HOOK_TYPE_LABELS[h.hook_type]||h.hook_type) + '</span>' +
          '<span style="font-size:0.7rem;color:' + statusColor + ';font-weight:600">' + h.status + '</span>' +
        '</div>' +
        '<div style="font-weight:600;font-size:0.85rem;margin-bottom:4px">' + _esc(h.title) + '</div>' +
        '<div style="font-size:0.75rem;color:var(--t2);margin-bottom:8px">' + _esc((h.description||'').substring(0,100)) + ((h.description||'').length>100?'…':'') + '</div>' +
        (dd.key ? '<div style="font-size:0.7rem;color:var(--t3);font-family:monospace;margin-bottom:6px">key: ' + _esc(dd.key) + '</div>' : '') +
        '<div style="display:flex;gap:4px;flex-wrap:wrap">' +
          (h.status === 'pending' ? '<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();forgeApproveHook(' + h.id + ').then(()=>_loadForgeHooks())">✓ Zatwierdź</button>' : '') +
          (canPromote && h.status === 'approved' ? '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();forgePromoteHook(' + h.id + ',this)">⬆ Promuj do DB</button>' : '') +
          (h.promoted_table ? '<span style="font-size:0.7rem;color:var(--green);padding:2px 6px">✓ ' + _esc(h.promoted_table) + '</span>' : '') +
          '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();forgeRejectHook(' + h.id + ')" style="margin-left:auto">✕</button>' +
        '</div>' +
      '</div>';
    }).join('');
  } catch(e) { grid.innerHTML = '<div style="color:var(--red);font-size:0.8rem;padding:8px">' + _esc(e.message) + '</div>'; }
}

async function forgeApproveHook(id) {
  try {
    await apiFetch(`/api/admin/forge/hooks/${id}`, { method:'PATCH', body:JSON.stringify({status:'approved'}) });
    _showToast('Hak zatwierdzony.', 'success');
    await _loadForgeHooks();
  } catch(e) { _showToast(e.message||'Błąd.','error'); }
}

async function forgeRejectHook(id) {
  if (!confirm('Usunąć hak?')) return;
  try {
    await apiFetch(`/api/admin/forge/hooks/${id}`, { method:'DELETE' });
    _showToast('Hak usunięty.', 'success');
    await _loadForgeHooks();
  } catch(e) { _showToast(e.message||'Błąd.','error'); }
}

async function forgePromoteHook(id, btn) {
  const orig = btn?.textContent || '⬆ Promuj';
  if (btn) { btn.disabled = true; btn.textContent = '⏳…'; }
  try {
    const d = await apiFetch(`/api/admin/forge/hooks/${id}/promote`, { method:'POST' });
    _showToast(`Promowano do ${d.promoted_table} (#${d.promoted_record_id})`, 'success');
    await _loadForgeHooks();
  } catch(e) { _showToast(e.message||'Błąd promocji.','error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = orig; } }
}

async function forgeGenerateEncounter(id, btn) {
  const orig = btn?.textContent || '🗡 Utwórz spotkanie';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Generuję…'; }
  try {
    const d = await apiFetch(`/api/admin/forge/hooks/${id}/generate-encounter`, { method: 'POST' });
    if (!d.encounter) { _showToast('Brak wyników.', 'warn'); return; }
    // Update local data and show
    if (_hookModalData) _hookModalData.draft_data = { ...(_hookModalData.draft_data || {}), encounter: d.encounter };
    const encEl = document.getElementById('hm-encounter-panel');
    if (encEl) { encEl.style.display = ''; encEl.innerHTML = _renderEncounterCard(d.encounter); }
    _showToast('Spotkanie wygenerowane!', 'success');
  } catch(e) { _showToast(e.message || 'Błąd generowania.', 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = orig; } }
}

function _renderEncounterCard(enc) {
  if (!enc) return '';
  const li = arr => Array.isArray(arr) ? arr.map(x => '<li style="font-size:0.78rem;margin-bottom:2px">' + _esc(typeof x === 'object' ? (x.name||'') + (x.count>1?' ×'+x.count:'') + (x.notes?' — '+x.notes:'') : x) + '</li>').join('') : '';
  return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">🗡 SPOTKANIE</div>' +
    '<div style="font-size:0.88rem;font-weight:600;margin-bottom:6px">' + _esc(enc.title||'') + '</div>' +
    (enc.trigger_condition ? '<div style="font-size:0.75rem;color:var(--t3);margin-bottom:8px">⚡ Wyzwalacz: ' + _esc(enc.trigger_condition) + '</div>' : '') +
    (enc.scene_setup ? '<p style="font-size:0.8rem;color:var(--t2);margin:0 0 10px">' + _esc(enc.scene_setup) + '</p>' : '') +
    (enc.enemies?.length ? '<div style="margin-bottom:8px"><div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:4px">WROGOWIE</div><ul style="margin:0;padding-left:16px">' + li(enc.enemies) + '</ul></div>' : '') +
    (enc.objectives?.length ? '<div style="margin-bottom:8px"><div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:4px">CELE</div><ul style="margin:0;padding-left:16px">' + li(enc.objectives) + '</ul></div>' : '') +
    (enc.rewards ? '<div style="margin-bottom:8px;font-size:0.78rem;color:var(--t2)">🏆 XP ~' + (enc.rewards.xp_estimate||0) + ' · ' + _esc(enc.rewards.loot_notes||'') + '</div>' : '') +
    (enc.gm_notes ? '<div style="padding:6px 8px;background:var(--amber-light);border:1px solid var(--amber-border);border-radius:var(--r);font-size:0.78rem;color:var(--t1)">🔒 GM: ' + _esc(enc.gm_notes) + '</div>' : '');
}

function _previewEncounterFromForm() {
  const g = id => document.getElementById(id);
  const parseEnemiesTxt = txt => (txt || '').split('\n').filter(Boolean).map(line => {
    const m = line.match(/^(.+?)\s*[×x](\d+)\s*(?:[—-]\s*(.+))?$/);
    return m ? { name: m[1].trim(), count: parseInt(m[2]), notes: m[3]?.trim() } : { name: line.trim(), count: 1 };
  });
  const enc = {
    title: g('em-title')?.value || '',
    trigger_condition: g('em-trigger')?.value || '',
    scene_setup: g('em-scene')?.value || '',
    enemies: parseEnemiesTxt(g('em-enemies')?.value || ''),
    objectives: (g('em-objectives')?.value || '').split('\n').filter(Boolean),
    rewards: { xp_estimate: parseInt(g('em-xp')?.value) || 0, loot_notes: g('em-loot')?.value || '' },
    gm_notes: g('em-gm-notes')?.value || '',
  };
  const preview = g('em-preview');
  if (!preview) return;
  const html = _renderEncounterCard(enc);
  preview.innerHTML = html || '<div style="color:var(--t3);font-size:0.8rem;text-align:center;padding:20px">Wypełnij pola aby zobaczyć podgląd.</div>';
}

async function openHookModal(id) {
  const modal = document.getElementById('hook-modal');
  if (!modal) return;
  try {
    const params = new URLSearchParams();
    const d = await apiFetch('/api/admin/forge/hooks?' + params.toString());
    const all = d.items || [];
    let h = all.find(x => x.id === id);
    // If not found in default list, try fetching with no status filter
    if (!h) {
      const d2 = await apiFetch('/api/admin/forge/hooks?status=');
      h = (d2.items || []).find(x => x.id === id);
    }
    if (!h) { _showToast('Nie znaleziono haka.', 'error'); return; }
    _hookModalData = h;
    document.getElementById('hm-title').value = h.title || '';
    document.getElementById('hm-description').value = h.description || '';
    const titleEl = document.getElementById('hook-modal-title');
    const typeEl = document.getElementById('hook-modal-type');
    if (titleEl) titleEl.textContent = h.title || 'Hak';
    if (typeEl) typeEl.textContent = (_HOOK_TYPE_LABELS[h.hook_type] || h.hook_type) + ' · ' + (h.significance || '');
    const statusColors = {pending:'var(--amber)',approved:'var(--green)',promoted:'var(--blue-light)',rejected:'var(--red)',draft:'var(--t3)'};
    const statusBadge = document.getElementById('hm-status-badge');
    if (statusBadge) { statusBadge.textContent = h.status; statusBadge.style.color = statusColors[h.status] || 'var(--t3)'; }
    const sigBadge = document.getElementById('hm-significance-badge');
    if (sigBadge) sigBadge.textContent = 'Znaczenie: ' + (h.significance || '—');
    const ratingEl = document.getElementById('hm-rating');
    if (ratingEl) ratingEl.textContent = '⭐ ' + (h.quality_rating||0).toFixed(1) + ' · użyte: ' + (h.times_used||0) + '×';
    const formEl = document.getElementById('hm-draft-form');
    if (formEl) formEl.innerHTML = _renderHookForm(h);
    // Show encounter card if already generated
    const encEl = document.getElementById('hm-encounter-panel');
    if (encEl) {
      const enc = (h.draft_data || {}).encounter;
      if (enc) {
        encEl.style.display = '';
        encEl.innerHTML = _renderEncounterCard(enc);
      } else {
        encEl.style.display = 'none';
        encEl.innerHTML = '';
      }
    }
    const actEl = document.getElementById('hm-actions');
    if (actEl) {
      const canPromote = ['weapon','armor','item','consumable','enemy','npc','location'].includes(h.hook_type);
      actEl.innerHTML =
        (h.status === 'pending' ? '<button class="btn btn-sm btn-primary" onclick="forgeApproveHook(' + h.id + ').then(()=>document.getElementById(\'hook-modal\').classList.remove(\'open\'))">✓ Zatwierdź</button>' : '') +
        (canPromote && h.status === 'approved' ? '<button class="btn btn-sm btn-secondary" onclick="forgePromoteHook(' + h.id + ',this).then(()=>document.getElementById(\'hook-modal\').classList.remove(\'open\'))">⬆ Promuj do DB</button>' : '') +
        (h.promoted_table ? '<span style="font-size:0.72rem;color:var(--green)">✓ ' + _esc(h.promoted_table) + ' #' + (h.promoted_record_id||'') + '</span>' : '') +
        (h.status === 'approved' ? '<button class="btn btn-sm btn-secondary" id="hm-encounter-btn" onclick="forgeGenerateEncounter(' + h.id + ',this)">🗡 Utwórz spotkanie</button>' : '') +
        '<button class="btn btn-sm btn-secondary" onclick="forgeRejectHook(' + h.id + ').then(()=>document.getElementById(\'hook-modal\').classList.remove(\'open\'))" style="color:var(--red)">✕ Odrzuć</button>';
    }
    modal.classList.add('open');
  } catch(e) { _showToast(e.message || 'Błąd.', 'error'); }
}

function _renderHookForm(h) {
  const dd = h.draft_data || {};
  const field = (fid, label, val, type, opts) => {
    if (opts) {
      return '<div class="form-row"><label class="form-label">' + label + '</label><select class="form-input" id="hm-dd-' + fid + '">' + opts.map(o => '<option value="' + _esc(o) + '"' + (o==val?' selected':'') + '>' + _esc(o) + '</option>').join('') + '</select></div>';
    }
    return '<div class="form-row"><label class="form-label">' + label + '</label><input class="form-input" id="hm-dd-' + fid + '" type="' + (type||'text') + '" value="' + _esc(String(val??'')) + '"></div>';
  };
  const textarea = (fid, label, val) =>
    '<div class="form-row"><label class="form-label">' + label + '</label><textarea class="form-input" id="hm-dd-' + fid + '" rows="3" style="resize:vertical">' + _esc(String(val??'')) + '</textarea></div>';
  switch(h.hook_type) {
    case 'weapon': case 'armor': return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data — Broń/Zbroja</div>' +
      field('key','Klucz (slug)',dd.key) + field('label','Etykieta',dd.label) + field('damage_die','Kości obrażeń',dd.damage_die) +
      field('linked_stat','Statystyka',dd.linked_stat,'text',['STR','DEX','INT','WIS','CHA','CON']) +
      field('weapon_type','Typ',dd.weapon_type,'text',['melee','ranged','armor']) +
      field('rarity','Rzadkość',dd.rarity,'number') + textarea('description','Opis',dd.description);
    case 'enemy': return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data — Wróg</div>' +
      field('key','Klucz (slug)',dd.key) + field('label','Etykieta',dd.label) + field('hp_base','HP',dd.hp_base,'number') +
      field('ac_base','AC',dd.ac_base,'number') + field('attack_bonus','Bonus ataku',dd.attack_bonus,'number') +
      field('damage_die','Kości obrażeń',dd.damage_die) + field('tier','Tier',dd.tier,'text',['weak','standard','elite','boss']) +
      field('damage_type','Typ obrażeń',dd.damage_type,'text',['physical','fire','poison','cold','lightning']) +
      textarea('description','Opis',dd.description);
    case 'npc': return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data — NPC</div>' +
      field('key','Klucz (slug)',dd.key) + field('label','Imię/Etykieta',dd.label) +
      field('npc_type','Typ NPC',dd.npc_type,'text',['neutral','merchant','quest_giver','ally','antagonist']) +
      textarea('personality_prompt','Osobowość',dd.personality_prompt) + textarea('description','Opis',dd.description);
    case 'location': return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data — Lokacja</div>' +
      field('key','Klucz (slug)',dd.key) + field('label','Nazwa',dd.label) +
      field('location_type','Typ',dd.location_type,'text',['macro','micro','dungeon','settlement']) +
      field('biome','Biom',dd.biome,'text',['forest','city','dungeon','ruin','plains','swamp','mountain','cave']) +
      textarea('description','Opis',dd.description);
    case 'item': return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data — Przedmiot</div>' +
      field('key','Klucz (slug)',dd.key) + field('label','Etykieta',dd.label) +
      field('item_type','Typ',dd.item_type,'text',['misc','tool','key','quest','armor']) +
      field('value_gp','Wartość (GP)',dd.value_gp,'number') + field('rarity','Rzadkość',dd.rarity,'number') +
      textarea('description','Opis',dd.description);
    case 'consumable': return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data — Konsumpcja</div>' +
      field('key','Klucz (slug)',dd.key) + field('label','Etykieta',dd.label) +
      field('effect_type','Efekt',dd.effect_type,'text',['heal','buff','misc','damage','utility']) +
      field('base_price','Cena bazowa',dd.base_price,'number') + field('rarity','Rzadkość',dd.rarity,'number') +
      textarea('description','Opis',dd.description);
    default: return '<div style="font-size:0.75rem;font-weight:600;color:var(--t3);margin-bottom:8px">Draft Data</div>' +
      '<textarea class="form-input" id="hm-dd-raw" rows="8" style="font-family:monospace;font-size:0.75rem;resize:vertical">' + _esc(JSON.stringify(h.draft_data||{},null,2)) + '</textarea>';
  }
}

async function saveHookEdits() {
  if (!_hookModalData) return;
  const h = _hookModalData;
  const title = document.getElementById('hm-title')?.value?.trim() || h.title;
  const description = document.getElementById('hm-description')?.value?.trim() || h.description;
  const dd = { ...(h.draft_data || {}) };
  const ddFields = {
    weapon: ['key','label','damage_die','linked_stat','weapon_type','description'],
    armor:  ['key','label','damage_die','linked_stat','weapon_type','description'],
    enemy:  ['key','label','hp_base','ac_base','attack_bonus','damage_die','tier','damage_type','description'],
    npc:    ['key','label','npc_type','personality_prompt','description'],
    location: ['key','label','location_type','biome','description'],
    item:   ['key','label','item_type','value_gp','rarity','description'],
    consumable: ['key','label','effect_type','base_price','rarity','description'],
  };
  const numFields = ['hp_base','ac_base','attack_bonus','value_gp','base_price','rarity'];
  for (const f of (ddFields[h.hook_type] || [])) {
    const el = document.getElementById('hm-dd-' + f);
    if (el) dd[f] = numFields.includes(f) ? (parseFloat(el.value)||0) : el.value;
  }
  const rawEl = document.getElementById('hm-dd-raw');
  if (rawEl) { try { Object.assign(dd, JSON.parse(rawEl.value)); } catch {} }
  try {
    await apiFetch('/api/admin/forge/hooks/' + h.id, {
      method: 'PATCH',
      body: JSON.stringify({ title, description, draft_data: dd }),
    });
    _showToast('Hak zapisany.', 'success');
    document.getElementById('hook-modal')?.classList.remove('open');
    await _loadForgeHooks();
  } catch(e) { _showToast(e.message || 'Błąd zapisu.', 'error'); }
}

// ── Szablony tab ─────────────────────────────────────────────────────────────
async function _loadForgeTemplates() {
  const grid = document.getElementById('forge-templates-grid');
  const count = document.getElementById('forge-templates-count');
  if (!grid) return;
  grid.innerHTML = '<div style="color:var(--t3);font-size:0.8rem">Ładowanie…</div>';
  try {
    const d = await apiFetch('/api/admin/forge/templates');
    const templates = d.items || [];
    _forgeTemplatesCache = templates;
    if (count) count.textContent = templates.length + ' szablonów';
    if (!templates.length) {
      grid.innerHTML = '<div style="color:var(--t3);font-size:0.8rem">Brak szablonów. Utwórz pierwszy z zapisanego pomysłu.</div>';
      return;
    }
    grid.innerHTML = templates.map(t => {
      const statusColor = {published:'var(--green)', review:'var(--amber,#f59e0b)', draft:'var(--t3)'}[t.status] || 'var(--t3)';
      const statusLabel = {published:'Opublikowany', review:'W recenzji', draft:'Szkic'}[t.status] || t.status;
      return '<div class="card" style="padding:12px;cursor:pointer" onclick="openTemplateEditor(' + t.id + ')">' +
        '<div style="display:flex;justify-content:space-between;margin-bottom:6px">' +
          '<span style="font-weight:600;font-size:0.88rem">' + _esc(t.title) + '</span>' +
          '<span style="font-size:0.7rem;color:' + statusColor + ';font-weight:600">' + statusLabel + '</span>' +
        '</div>' +
        '<div style="font-size:0.78rem;color:var(--t2);margin-bottom:8px">' + _esc((t.description||'').substring(0,120)) + ((t.description||'').length>120?'…':'') + '</div>' +
        '<div style="font-size:0.72rem;color:var(--t3);margin-bottom:8px">⭐ ' + t.difficulty_rating + '/5 · 🎮 ' + t.play_count + ' rozegrań · ' + (t.hook_ids||[]).length + ' hooków</div>' +
        (t.start_hex_q != null ? '<div style="font-size:0.72rem;color:var(--amber,#c9a227);margin-bottom:6px">📍 Start: (' + t.start_hex_q + ', ' + t.start_hex_r + ')</div>' : '<div style="font-size:0.72rem;color:var(--t3);margin-bottom:6px">📍 Brak przydzielonego terenu</div>') +
        '<div style="display:flex;gap:4px;flex-wrap:wrap">' +
          (t.status === 'draft' ? '<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();forgeSetTemplateStatus(' + t.id + ',\'review\')">→ Recenzja</button>' : '') +
          (t.status === 'review' ? '<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();forgePublishTemplate(' + t.id + ')">Opublikuj</button>' : '') +
          (t.status !== 'draft' ? '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();forgeUnpublishTemplate(' + t.id + ')">↩ Szkic</button>' : '') +
          '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();openTemplateEditor(' + t.id + ')">Edytuj</button>' +
          '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();forgeAllocateHex(' + t.id + ')">🗺 Przydziel teren</button>' +
          (t.status === 'published' ? '<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();forgeLaunchCampaignFromTemplate(' + t.id + ')" style="background:var(--green);border-color:var(--green)">🚀 Uruchom kampanię</button>' : '') +
          '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();if(confirm(\'Usunąć szablon?\'))apiFetch(\'/api/admin/forge/templates/' + t.id + '\',{method:\'DELETE\'}).then(()=>{_sectionLoaded.delete(\'forge\');_loadForgeTemplates()})" style="margin-left:auto">🗑</button>' +
        '</div>' +
      '</div>';
    }).join('');
  } catch(e) { grid.innerHTML = '<div style="color:var(--red);font-size:0.8rem">' + _esc(e.message) + '</div>'; }
}

// E12 (#427) — card quick-action: change template status, surfacing 422 detail.
async function forgeSetTemplateStatus(id, status) {
  try {
    const token = localStorage.getItem(_ADMIN_TOKEN_KEY);
    const r = await fetch(_buildUrl('/api/admin/forge/templates/' + id), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
      body: JSON.stringify({ status }),
    });
    if (r.status === 422) {
      const det = (await r.json().catch(() => ({}))).detail || {};
      const parts = [];
      if ((det.missing_npcs || []).length) parts.push('Brak NPC: ' + det.missing_npcs.join(', '));
      if ((det.missing_beats || []).length) parts.push('Brak beatów: ' + det.missing_beats.join(', '));
      _showToast((det.message || 'Nie można zmienić statusu') + (parts.length ? ' — ' + parts.join(' · ') : ''), 'error', 6000);
      return;
    }
    if (!r.ok) { _showToast('Błąd (HTTP ' + r.status + ')', 'error'); return; }
    const MSG = { review: 'Wysłano do recenzji.', published: 'Szablon opublikowany.', draft: 'Cofnięto do szkicu.' };
    _showToast(MSG[status] || 'Status zmieniony.', 'success');
    await _loadForgeTemplates();
  } catch(e) { _showToast(e.message || 'Błąd.', 'error'); }
}

// #1060 — Pre-publish validator: shows red/yellow issue cards, blocks if errors.
async function forgePublishTemplate(id) {
  const tpl = _forgeTemplatesCache.find(t => t.id === id);
  const plan = tpl ? (tpl.gm_plan_json || {}) : {};
  let vres;
  try {
    vres = await apiFetch('/api/admin/forge/validate-plan', {
      method: 'POST',
      body: JSON.stringify({ gm_plan_json: plan }),
    });
  } catch(e) {
    // Validation call failed — proceed with normal publish (backend gate still blocks)
    return forgeSetTemplateStatus(id, 'published');
  }
  if (!vres.issues || !vres.issues.length) {
    return forgeSetTemplateStatus(id, 'published');
  }
  // Build modal with issue cards
  const cards = vres.issues.map(i => {
    const bg = i.type === 'error' ? 'var(--red,#dc2626)' : 'var(--amber,#d97706)';
    const icon = i.type === 'error' ? '🔴' : '🟡';
    return '<div style="background:' + bg + '18;border:1px solid ' + bg + ';border-radius:6px;padding:8px 10px;margin-bottom:6px">' +
      '<div style="font-weight:600;font-size:0.82rem;color:' + bg + '">' + icon + ' ' + (i.type === 'error' ? 'BLAD' : 'OSTRZEZENIE') + ' — ' + _esc(i.code) + '</div>' +
      '<div style="font-size:0.8rem;margin-top:3px;color:#e2e8f0">' + _esc(i.message) + '</div>' +
    '</div>';
  }).join('');
  const hasErrors = vres.issues.some(i => i.type === 'error');
  const publishBtn = hasErrors
    ? '<button class="btn btn-sm" disabled style="opacity:0.4;cursor:not-allowed">Publikuj (zablokowane — napraw bledy)</button>'
    : '<button class="btn btn-sm btn-primary" id="_forge-publish-anyway">Publikuj mimo ostrzezen</button>';
  const html = '<div style="max-height:60vh;overflow-y:auto;margin-bottom:12px">' + cards + '</div>' + publishBtn;
  const { openModal, closeModal } = await import('../shared/modal.js');
  openModal('Walidacja planu GM', html, { width: 560 });
  if (!hasErrors) {
    document.getElementById('_forge-publish-anyway')?.addEventListener('click', () => {
      closeModal();
      forgeSetTemplateStatus(id, 'published');
    });
  }
}

async function forgeAllocateHex(id) {
  try {
    const r = await apiFetch(`/api/admin/forge/templates/${id}/allocate-hex`, { method: 'POST' });
    const h = r.start_hex || {};
    _showToast(`Przydzielono teren: ${h.label || ''}(${h.q}, ${h.r})`, 'success');
    await _loadForgeTemplates();
  } catch(e) { _showToast(e.message || 'Błąd przydziału terenu.', 'error'); }
}

async function forgeLaunchCampaignFromTemplate(templateId) {
  const templateTitle = (_forgeTemplatesCache.find(t => t.id === templateId) || {}).title || '';
  // Fetch user list first
  let users = [];
  try {
    const d = await apiFetch('/api/admin/accounts');
    users = (d.items || []).filter(u => !u.is_admin);
  } catch(e) {
    _showToast('Nie można załadować graczy: ' + (e.message||'błąd'), 'error');
    return;
  }
  if (!users.length) {
    _showToast('Brak graczy — najpierw utwórz konto gracza.', 'warn');
    return;
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `
    <div class="modal" style="max-width:420px">
      <div class="modal-head">
        <span class="modal-title">🚀 Uruchom kampanię z szablonu</span>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div class="modal-body" style="display:flex;flex-direction:column;gap:14px;padding:16px">
        <div style="font-size:0.78rem;color:var(--t2)">Szablon: <strong>${_esc(templateTitle)}</strong></div>
        ${((_forgeTemplatesCache.find(t=>t.id===templateId)||{}).start_hex_q!=null) ? `<div style="font-size:0.72rem;color:var(--amber,#c9a227)">📍 Start na mapie: (${(_forgeTemplatesCache.find(t=>t.id===templateId)||{}).start_hex_q}, ${(_forgeTemplatesCache.find(t=>t.id===templateId)||{}).start_hex_r})</div>` : ''}
        <div>
          <label class="form-label">Tytuł kampanii</label>
          <input id="launch-camp-title" class="form-input" value="${_esc(templateTitle)}" placeholder="Tytuł kampanii">
        </div>
        <div>
          <label class="form-label">Gracz</label>
          <select id="launch-camp-user" class="form-input">
            ${users.map(u => `<option value="${u.id}">${_esc(u.display_name || u.username)} (${_esc(u.username)})</option>`).join('')}
          </select>
        </div>
      </div>
      <div class="modal-foot" style="display:flex;gap:8px;justify-content:flex-end;padding:12px 16px;border-top:1px solid var(--border)">
        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
        <button class="btn btn-primary" id="launch-camp-confirm">🚀 Uruchom</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

  document.getElementById('launch-camp-confirm').addEventListener('click', async function() {
    const title = document.getElementById('launch-camp-title').value.trim();
    const userId = parseInt(document.getElementById('launch-camp-user').value, 10);
    if (!title) { _showToast('Podaj tytuł kampanii.', 'warn'); return; }
    this.disabled = true; this.textContent = '⏳';
    try {
      const r = await apiFetch('/api/campaigns', {
        method: 'POST',
        body: JSON.stringify({
          title,
          system_id: 'fantasy',
          model_id: 'default',
          owner_user_id: userId,
          language: 'pl',
          mode: 'pre_built',
          status: 'active',
          template_id: templateId,
          selected_hook_ids: []
        })
      });
      overlay.remove();
      _showToast(`Kampania „${_esc(title)}" uruchomiona!`, 'success');
      // Refresh template grid (play_count may have changed) + invalidate campaigns tab
      _sectionLoaded.delete('campaigns');
      _loadForgeTemplates();
    } catch(e) {
      _showToast('Błąd: ' + (e.message||'nieznany'), 'error');
      this.disabled = false; this.textContent = '🚀 Uruchom';
    }
  });
}

async function forgeGenerateTplDescription(evt) {
  if (!_tplEditorData?.id) return;
  const btn = evt ? evt.target : null;
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    const title = document.getElementById('tpl-title')?.value || _tplEditorData.title || '';
    const atmosphere = document.getElementById('tpl-atmosphere')?.value || '';
    const r = await apiFetch(`/api/admin/forge/templates/${_tplEditorData.id}/generate-description`, {
      method: 'POST',
      body: JSON.stringify({ title, atmosphere, gm_plan: _tplEditorPlan || {} })
    });
    const ta = document.getElementById('tpl-description');
    if (ta && r.description) {
      ta.value = r.description;
      ta.dispatchEvent(new Event('input'));
    }
  } catch(e) {
    _showToast('Błąd generowania opisu: ' + (e.message || 'nieznany błąd'), 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🤖 Generuj opis'; }
  }
}

async function forgeUnpublishTemplate(id) {
  return forgeSetTemplateStatus(id, 'draft');
}

function forgeCreateTemplateFromIdea(ideaId, defaultTitle, arcCount) {
  _forgePlanIdeaId = ideaId;
  _forgePlanTemplateId = null;
  const titleInput = document.getElementById('fpd-title');
  if (titleInput) titleInput.value = defaultTitle || '';
  // Pre-set acts select based on idea arc count
  const actsSelect = document.getElementById('fpd-acts');
  if (actsSelect && arcCount > 0) {
    const clamp = Math.min(Math.max(arcCount, 3), 9);
    const opt = actsSelect.querySelector(`option[value="${clamp}"]`);
    if (opt) actsSelect.value = String(clamp);
  }
  document.getElementById('fpd-title-row').style.display = '';
  document.getElementById('fpd-heading').textContent = 'Stwórz szablon i generuj plan';
  document.getElementById('fpd-confirm-btn').textContent = 'Stwórz i generuj';
  const dlg = document.getElementById('forge-plan-dialog');
  if (dlg) dlg.style.display = 'flex';
}

async function openCreateTemplate() {
  const title = prompt('Tytuł nowego szablonu:');
  if (!title) return;
  try {
    const t = await apiFetch('/api/admin/forge/templates', {
      method:'POST',
      body:JSON.stringify({ title }),
    });
    _showToast('Szablon "' + t.title + '" utworzony.', 'success');
    await _loadForgeTemplates();
    // Open in editor immediately
    if (t.id) openTemplateEditor(t.id);
  } catch(e) { _showToast(e.message||'Błąd.','error'); }
}

// ── Template Full Editor ─────────────────────────────────
async function openTemplateEditor(id) {
  try {
    const d = await apiFetch('/api/admin/forge/templates/' + id);
    _tplEditorData = d;
    _tplEditorPlan = d.gm_plan_json || {};

    // Translate old arcs-keyed format → V2 acts array if acts are missing or unpopulated
    if (_tplEditorPlan.arcs) {
      const hasRealActs = (_tplEditorPlan.acts || []).some(a => a.title);
      if (!hasRealActs) {
        const arcsObj = _tplEditorPlan.arcs;
        _tplEditorPlan.acts = Object.keys(arcsObj).sort().map(k => {
          const a = arcsObj[k];
          return { title: a.title || '', summary: a.roadmap || '', key_beats: a.scene_goals || [], completed: a.status === 'done' };
        });
      }
    }

    // Show editor, hide grid
    document.getElementById('forge-templates-grid').style.display = 'none';
    const createBtn = document.querySelector('[onclick="openCreateTemplate()"]');
    if (createBtn) createBtn.style.display = 'none';
    document.getElementById('forge-template-editor').style.display = '';

    // Populate fields
    document.getElementById('tpl-title').value = d.title || '';
    document.getElementById('tpl-description').value = d.description || '';
    document.getElementById('tpl-atmosphere').value = d.atmosphere || '';
    _setTplDifficulty(d.difficulty_rating || 2);
    // E7 (#422) — required NPCs/beats + player visibility
    if (document.getElementById('tpl-required-npcs')) document.getElementById('tpl-required-npcs').value = (d.required_npc_keys || []).join(', ');
    if (document.getElementById('tpl-required-beats')) document.getElementById('tpl-required-beats').value = (d.required_beats || []).join(', ');
    if (document.getElementById('tpl-player-visible')) document.getElementById('tpl-player-visible').checked = (d.player_visible ?? 1) ? true : false;
    _renderTplWorkflow(d.status);

    // Wire editor tabs
    document.getElementById('tpl-editor-tabs')?.querySelectorAll('.stab[data-tpltab]').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('#tpl-editor-tabs .stab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        ['overview','acts','characters','endings','items'].forEach(t => {
          const el = document.getElementById('tpl-tab-' + t);
          if (el) el.style.display = btn.dataset.tpltab === t ? '' : 'none';
        });
      };
    });

    // Render all tabs
    _renderTplHooksList(d.hook_ids || []);
    _renderTplActs(_tplEditorPlan.acts || []);
    _renderTplNPCs(_tplEditorPlan.key_npcs || []);
    _renderTplEnemies(_tplEditorPlan.key_enemies || []);
    _renderTplLocations(_tplEditorPlan.key_locations || []);
    _renderTplEndings(_tplEditorPlan.endings || []);
    _renderTplItems(_tplEditorPlan.key_items || []);
    _loadTplDbItems();
    const ep = _tplEditorPlan.engine_private || {};
    if (document.getElementById('tpl-gm-hint')) document.getElementById('tpl-gm-hint').value = ep.secret_predisposition_hint || '';
    if (document.getElementById('tpl-gm-twist')) document.getElementById('tpl-gm-twist').value = ep.hidden_twist || '';
    if (document.getElementById('tpl-gm-contingency')) document.getElementById('tpl-gm-contingency').value = ep.contingency || '';
    ['tpl-gm-hint','tpl-gm-twist','tpl-gm-contingency'].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px'; el.addEventListener('input', function(){ this.style.height='auto'; this.style.height=this.scrollHeight+'px'; }, {once:false}); }
    });
  } catch(e) { _showToast(e.message || 'Błąd ładowania szablonu.', 'error'); }
}

function _closeTemplateEditor() {
  document.getElementById('forge-template-editor').style.display = 'none';
  document.getElementById('forge-templates-grid').style.display = '';
  const createBtn = document.querySelector('[onclick="openCreateTemplate()"]');
  if (createBtn) createBtn.style.display = '';
  _tplEditorData = null;
  _tplEditorPlan = null;
  // Reset to overview tab
  document.querySelectorAll('#tpl-editor-tabs .stab').forEach((b,i) => b.classList.toggle('active', i===0));
  ['acts','characters','endings','items'].forEach(t => {
    const el = document.getElementById('tpl-tab-' + t);
    if (el) el.style.display = 'none';
  });
  if (document.getElementById('tpl-tab-overview')) document.getElementById('tpl-tab-overview').style.display = '';
}

function _setTplDifficulty(n) {
  _tplDifficulty = n;
  const container = document.getElementById('tpl-difficulty-stars');
  if (!container) return;
  // Populate stars if empty
  if (!container.querySelector('button')) {
    container.innerHTML = [1,2,3,4,5].map(i => '<button type="button" onclick="_setTplDifficulty(' + i + ')" id="tpl-star-' + i + '" style="font-size:1.2rem;background:none;border:none;cursor:pointer;padding:0">☆</button>').join('');
  }
  for (let i = 1; i <= 5; i++) {
    const star = document.getElementById('tpl-star-' + i);
    if (star) star.textContent = i <= n ? '★' : '☆';
  }
}

function _renderTplHooksList(hookIds) {
  const el = document.getElementById('tpl-hooks-list');
  if (!el) return;
  if (!hookIds.length) { el.innerHTML = '<span style="font-size:0.78rem;color:var(--t3)">Brak powiązanych haków.</span>'; return; }
  apiFetch('/api/admin/forge/hooks?status=approved').then(d => {
    const all = d.items || [];
    const linked = all.filter(h => hookIds.includes(h.id));
    if (!linked.length) { el.innerHTML = '<span style="font-size:0.78rem;color:var(--t3)">Brak powiązanych haków (hook_ids: ' + hookIds.join(',') + ').</span>'; return; }
    el.innerHTML = linked.map(h =>
      '<span style="display:inline-flex;align-items:center;gap:4px;font-size:0.75rem;padding:3px 8px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)">' +
        (_esc(_HOOK_TYPE_LABELS[h.hook_type]||h.hook_type)) + ' ' + _esc(h.title) +
        '<button type="button" onclick="_removeTplHook(' + h.id + ')" style="background:none;border:none;cursor:pointer;color:var(--t3);padding:0;line-height:1">✕</button>' +
      '</span>'
    ).join('');
  }).catch(() => { el.innerHTML = '<span style="font-size:0.75rem;color:var(--t3)">hook_ids: ' + hookIds.join(',') + '</span>'; });
}

function _removeTplHook(hookId) {
  if (!_tplEditorData) return;
  _tplEditorData.hook_ids = (_tplEditorData.hook_ids || []).filter(id => id !== hookId);
  _renderTplHooksList(_tplEditorData.hook_ids);
}

async function _openHookLinkPicker() {
  try {
    const d = await apiFetch('/api/admin/forge/hooks?status=approved');
    const all = d.items || [];
    const current = _tplEditorData?.hook_ids || [];
    if (!all.length) { _showToast('Brak zatwierdzonych haków.', 'error'); return; }
    const selection = prompt('Zatwierdzone haki:\n' + all.map(h => h.id + ': [' + h.hook_type + '] ' + h.title).join('\n') + '\n\nWpisz ID haka do dodania:');
    const hookId = parseInt(selection);
    if (!hookId || isNaN(hookId)) return;
    if (!current.includes(hookId)) {
      _tplEditorData.hook_ids = [...current, hookId];
      _renderTplHooksList(_tplEditorData.hook_ids);
    }
  } catch(e) { _showToast(e.message, 'error'); }
}

function _renderTplActs(acts) {
  const el = document.getElementById('tpl-acts-list');
  if (!el) return;
  while (acts.length < 3) acts.push({ number: acts.length+1, title:'', summary:'', key_beats:[], completed:false });
  el.innerHTML = acts.map((act, i) =>
    '<details open style="border:1px solid var(--border);border-radius:var(--r);overflow:hidden">' +
      '<summary style="padding:10px 14px;background:var(--surface);cursor:pointer;font-weight:600;font-size:0.85rem;color:var(--t1)">Akt ' + (i+1) + ': <span id="tpl-act-title-label-' + i + '">' + _esc(act.title||'(bez tytułu)') + '</span></summary>' +
      '<div style="padding:14px">' +
        '<div class="form-row"><label class="form-label">Tytuł aktu</label>' +
          '<input class="form-input" id="tpl-act-title-' + i + '" type="text" value="' + _esc(act.title||'') + '" oninput="document.getElementById(\'tpl-act-title-label-' + i + '\').textContent=this.value||\'(bez tytułu)\'"></div>' +
        '<div class="form-row"><label class="form-label">Streszczenie</label>' +
          '<textarea class="form-input" id="tpl-act-summary-' + i + '" rows="3" style="resize:vertical">' + _esc(act.summary||'') + '</textarea></div>' +
        '<div class="form-row"><label class="form-label">Kluczowe zdarzenia (key_beats)</label>' +
          '<div id="tpl-act-beats-' + i + '" style="display:flex;flex-direction:column;gap:4px;margin-bottom:6px"></div>' +
          '<div style="display:flex;gap:6px">' +
            '<input class="form-input" id="tpl-act-beats-input-' + i + '" type="text" placeholder="Dodaj zdarzenie…" style="flex:1" onkeydown="if(event.key===\'Enter\'){event.preventDefault();_addTplBeat(' + i + ')}">' +
            '<button class="btn btn-sm btn-secondary" onclick="_addTplBeat(' + i + ')">+ Dodaj</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</details>'
  ).join('');
  // #1014 — render beat rows (with optional checkbox) after the act shells exist.
  acts.forEach((_, i) => _renderTplBeatChips(i));
}

// #1014 — beats may be bare strings (legacy) or {beat_key, summary, optional} objects.
function _tplBeatText(b) { return (b && typeof b === 'object') ? (b.summary || b.beat_key || '') : (b || ''); }
function _tplBeatOptional(b) { return !!(b && typeof b === 'object' && b.optional === true); }

// Normalize an act's beats to objects in place so `optional` can be toggled + persisted.
function _normalizeTplActBeats(actIdx) {
  const act = _tplEditorPlan?.acts?.[actIdx];
  if (!act) return [];
  act.key_beats = (act.key_beats || []).map(b =>
    (b && typeof b === 'object') ? { ...b, optional: b.optional === true }
                                 : { summary: String(b || ''), optional: false });
  return act.key_beats;
}

function _renderTplBeatChips(actIdx) {
  const el = document.getElementById('tpl-act-beats-' + actIdx);
  if (!el) return;
  const beats = _normalizeTplActBeats(actIdx);
  el.innerHTML = beats.map((b, bi) =>
    '<div data-beat-row="' + bi + '" style="display:flex;align-items:center;gap:8px;font-size:0.78rem;padding:4px 8px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)">' +
      '<span style="flex:1">' + _esc(_tplBeatText(b)) + '</span>' +
      '<label style="display:inline-flex;align-items:center;gap:4px;color:var(--t3);cursor:pointer;white-space:nowrap;font-size:0.72rem" title="Scena opcjonalna — pomijalna, nie blokuje zakończenia aktu (#1014)">' +
        '<input type="checkbox" class="tpl-beat-optional" ' + (_tplBeatOptional(b) ? 'checked' : '') +
          ' onchange="_toggleTplBeatOptional(' + actIdx + ',' + bi + ',this.checked)">opcjonalna</label>' +
      '<button type="button" onclick="_removeTplBeat(' + actIdx + ',' + bi + ')" style="background:none;border:none;cursor:pointer;color:var(--t3);padding:0">✕</button>' +
    '</div>'
  ).join('');
}

function _toggleTplBeatOptional(actIdx, beatIdx, checked) {
  const beats = _normalizeTplActBeats(actIdx);
  if (beats[beatIdx]) beats[beatIdx].optional = !!checked;
}

function _addTplBeat(actIdx) {
  const input = document.getElementById('tpl-act-beats-input-' + actIdx);
  if (!input || !input.value.trim()) return;
  const text = input.value.trim();
  input.value = '';
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan.acts) _tplEditorPlan.acts = [];
  if (!_tplEditorPlan.acts[actIdx]) _tplEditorPlan.acts[actIdx] = {};
  if (!_tplEditorPlan.acts[actIdx].key_beats) _tplEditorPlan.acts[actIdx].key_beats = [];
  _tplEditorPlan.acts[actIdx].key_beats.push({ summary: text, optional: false });
  _renderTplBeatChips(actIdx);
}

function _removeTplBeat(actIdx, beatIdx) {
  if (_tplEditorPlan?.acts?.[actIdx]?.key_beats) {
    _tplEditorPlan.acts[actIdx].key_beats.splice(beatIdx, 1);
    _renderTplBeatChips(actIdx);
  }
}

function _renderTplNPCs(npcs) {
  const el = document.getElementById('tpl-npcs-list');
  if (!el) return;
  if (!npcs.length) { el.innerHTML = '<div style="font-size:0.78rem;color:var(--t3)">Brak NPC. Kliknij + Dodaj lub wygeneruj plan AI.</div>'; return; }
  el.innerHTML = npcs.map((n, i) => {
    const importanceColor = n.importance==='critical'?'var(--red)':n.importance==='supporting'?'var(--amber)':'var(--t3)';
    const importanceBg   = n.importance==='critical'?'var(--red-light)':n.importance==='supporting'?'var(--amber-light)':'var(--surface)';
    const csTag = n.campaign_specific ? '<span style="font-size:0.65rem;padding:1px 5px;background:var(--blue-light,#dbeafe);color:var(--blue);border-radius:var(--r);margin-left:4px">kampania</span>' : '';
    return '<div style="padding:8px 10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);font-size:0.78rem;cursor:pointer;transition:border-color .15s" onmouseenter="this.style.borderColor=\'var(--accent)\'" onmouseleave="this.style.borderColor=\'var(--border)\'" onclick="openTplEntityModal(\'key_npcs\',' + i + ',\'npc\',' + JSON.stringify(n).replace(/"/g,'&quot;') + ')">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">' +
        '<div><strong>' + _esc(n.name||n.key||'NPC') + '</strong>' + csTag + '</div>' +
        '<span style="font-size:0.7rem;padding:1px 6px;border-radius:var(--r);background:' + importanceBg + ';color:' + importanceColor + '">' + (n.importance||'?') + '</span>' +
      '</div>' +
      '<div style="color:var(--t3)">' + _esc(n.role||'') + '</div>' +
    '</div>';
  }).join('');
}

function _addTplNPC() {
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan.key_npcs) _tplEditorPlan.key_npcs = [];
  openTplEntityModal('key_npcs', -1, 'npc', {});
}

function _renderTplLocations(locations) {
  const el = document.getElementById('tpl-locations-list');
  if (!el) return;
  if (!locations.length) { el.innerHTML = '<div style="font-size:0.78rem;color:var(--t3)">Brak lokacji. Kliknij + Dodaj lub wygeneruj plan AI.</div>'; return; }
  el.innerHTML = locations.map((l, i) => {
    const csTag = l.campaign_specific ? '<span style="font-size:0.65rem;padding:1px 5px;background:var(--blue-light,#dbeafe);color:var(--blue);border-radius:var(--r);margin-left:4px">kampania</span>' : '';
    const subs = (l.sub_locations||[]).length;
    return '<div style="padding:8px 10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);font-size:0.78rem;cursor:pointer;transition:border-color .15s" onmouseenter="this.style.borderColor=\'var(--accent)\'" onmouseleave="this.style.borderColor=\'var(--border)\'" onclick="openTplEntityModal(\'key_locations\',' + i + ',\'location\',' + JSON.stringify(l).replace(/"/g,'&quot;') + ')">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">' +
        '<div>' +
          '<strong>' + _esc(l.name||l.key||'Lokacja') + '</strong>' + csTag +
        '</div>' +
        '<div style="display:flex;gap:4px">' +
          (subs ? '<span style="font-size:0.7rem;color:var(--t3)">' + subs + ' sublok.</span>' : '') +
          '<button class="btn btn-sm btn-secondary" style="padding:1px 6px;font-size:0.7rem" onclick="event.stopPropagation();openGenerateSublocations(' + i + ',event)" title="Generuj sublokacje">+ sublok.</button>' +
        '</div>' +
      '</div>' +
      '<div style="color:var(--t3)">' + _esc(l.role||'') + '</div>' +
      (subs ? '<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:4px">' + (l.sub_locations||[]).map((s,si)=>'<span title="' + _esc(s.description||'brak opisu') + '" style="font-size:0.68rem;padding:1px 6px;background:var(--canvas);border:1px solid var(--border);border-radius:var(--r);cursor:pointer" onclick="event.stopPropagation();openSublocEdit(' + i + ',' + si + ')">' + _esc(s.name) + (s.description?'':' ⚠') + '</span>').join('') + '</div>' : '') +
    '</div>';
  }).join('');
}

function _addTplLocation() {
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan.key_locations) _tplEditorPlan.key_locations = [];
  openTplEntityModal('key_locations', -1, 'location', {});
}

async function openGenerateSublocations(locIdx, event) {
  if (!_tplEditorData?.id) return;
  const loc = _tplEditorPlan?.key_locations?.[locIdx];
  if (!loc) return;
  const btn = event.currentTarget;
  const origText = btn.textContent;
  btn.textContent = '⏳'; btn.disabled = true;
  try {
    const result = await apiFetch('/api/admin/forge/templates/' + _tplEditorData.id + '/generate-sublocations', {
      method: 'POST',
      body: JSON.stringify({ location_key: loc.key, location_name: loc.name || loc.key, location_description: (loc.overrides||{}).description || '' })
    });
    if (!result.sub_locations?.length) { _showToast('Brak sugestii.', 'warn'); return; }
    if (!_tplEditorPlan.key_locations[locIdx].sub_locations) _tplEditorPlan.key_locations[locIdx].sub_locations = [];
    _tplEditorPlan.key_locations[locIdx].sub_locations.push(...result.sub_locations);
    _renderTplLocations(_tplEditorPlan.key_locations);
    _showToast('Dodano ' + result.sub_locations.length + ' sublokacji.', 'success');
  } catch(e) { _showToast(e.message||'Błąd generowania.', 'error'); }
  finally { btn.textContent = origText; btn.disabled = false; }
}

function openSublocEdit(locIdx, subIdx) {
  const loc = _tplEditorPlan?.key_locations?.[locIdx];
  if (!loc) return;
  const sub = (loc.sub_locations || [])[subIdx];
  if (!sub) return;
  _sublocEditCtx = { locIdx, subIdx };
  document.getElementById('sled-key').value = sub.key || '';
  document.getElementById('sled-name').value = sub.name || '';
  document.getElementById('sled-description').value = sub.description || '';
  document.getElementById('subloc-edit-dialog').style.display = 'flex';
}

function saveSublocEdit() {
  if (!_sublocEditCtx) return;
  const { locIdx, subIdx } = _sublocEditCtx;
  const subs = _tplEditorPlan?.key_locations?.[locIdx]?.sub_locations;
  if (!subs) return;
  subs[subIdx] = {
    ...subs[subIdx],
    key: document.getElementById('sled-key').value.trim() || subs[subIdx].key,
    name: document.getElementById('sled-name').value.trim() || subs[subIdx].name,
    description: document.getElementById('sled-description').value.trim(),
  };
  document.getElementById('subloc-edit-dialog').style.display = 'none';
  _sublocEditCtx = null;
  _renderTplLocations(_tplEditorPlan.key_locations);
  _showToast('Sublokacja zapisana.', 'success');
}

function _renderTplEnemies(enemies) {
  const el = document.getElementById('tpl-enemies-list');
  if (!el) return;
  if (!enemies.length) { el.innerHTML = '<div style="font-size:0.78rem;color:var(--t3)">Brak wrogów. Kliknij + Dodaj.</div>'; return; }
  const tierColor = { weak:'var(--t3)', standard:'var(--green)', elite:'var(--amber)', boss:'var(--red)' };
  el.innerHTML = enemies.map((e, i) => {
    const csTag = e.campaign_specific ? '<span style="font-size:0.65rem;padding:1px 5px;background:var(--blue-light,#dbeafe);color:var(--blue);border-radius:var(--r);margin-left:4px">kampania</span>' : '';
    const tier = (e.overrides||e).tier || 'standard';
    return '<div style="padding:8px 10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);font-size:0.78rem;cursor:pointer;transition:border-color .15s" onmouseenter="this.style.borderColor=\'var(--accent)\'" onmouseleave="this.style.borderColor=\'var(--border)\'" onclick="openTplEntityModal(\'key_enemies\',' + i + ',\'enemy\',' + JSON.stringify(e).replace(/"/g,'&quot;') + ')">' +
      '<div style="display:flex;justify-content:space-between;align-items:center">' +
        '<div><strong>' + _esc(e.label||e.key||'Wróg') + '</strong>' + csTag + '</div>' +
        '<span style="font-size:0.7rem;color:' + (tierColor[tier]||'var(--t3)') + '">' + tier + '</span>' +
      '</div>' +
      '<div style="color:var(--t3);font-size:0.72rem">HP ' + ((e.overrides||e).hp_base||'?') + ' · AC ' + ((e.overrides||e).ac_base||'?') + ' · ' + ((e.overrides||e).damage_die||'?') + '</div>' +
    '</div>';
  }).join('');
}

function _addTplEnemy() {
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan.key_enemies) _tplEditorPlan.key_enemies = [];
  openTplEntityModal('key_enemies', -1, 'enemy', {});
}

function _renderTplItems(items, dbItemsByType) {
  const weaponEl = document.getElementById('tpl-items-weapon-list');
  const itemEl   = document.getElementById('tpl-items-item-list');
  const consEl   = document.getElementById('tpl-items-consumable-list');
  const empty = '<div style="font-size:0.78rem;color:var(--t3)">Brak. Kliknij + Dodaj lub 🤖 Generuj AI.</div>';
  if (!weaponEl) return;
  const db = dbItemsByType || window._tplDbItemsByType || {};
  const RARITY = {1:'C',2:'U',3:'R',4:'L'};

  const renderDbCard = (it) => {
    const rarityLabel = RARITY[it.rarity] || it.rarity || '';
    const summary = [it.weapon_type, it.damage_die, it.effect_type, it.item_type, rarityLabel].filter(Boolean).join(' · ');
    return '<div style="padding:8px 10px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);font-size:0.78rem;cursor:pointer;display:flex;align-items:center;gap:6px;transition:border-color .15s" onmouseenter="this.style.borderColor=\'var(--accent)\'" onmouseleave="this.style.borderColor=\'var(--border)\'" onclick="openSmartEntryForDbItem(\'' + _esc(it.entry_type) + '\',\'' + _esc(it.key) + '\')">' +
      '<span style="font-size:0.6rem;padding:1px 4px;background:#d1fae5;color:#065f46;border-radius:3px;font-weight:700;white-space:nowrap">🔌 DB</span>' +
      '<strong style="flex:1">' + _esc(it.label||it.key) + '</strong>' +
      (summary ? '<span style="color:var(--t3);font-size:0.68rem">' + _esc(summary) + '</span>' : '') +
      '<span style="font-size:0.65rem;color:var(--t3)" title="Promuj do globalnej bazy" onclick="event.stopPropagation();_promoteTplDbItem(\'' + _esc(it.entry_type) + '\',\'' + _esc(it.key) + '\',this)" style="cursor:pointer">⬆</span>' +
    '</div>';
  };

  const renderList = (planList, dbList, elRef) => {
    if (!elRef) return;
    const planHtml = planList.map((it) => {
      const realIdx = items.indexOf(it);
      const csTag = it.campaign_specific ? '<span style="font-size:0.65rem;padding:1px 5px;background:var(--blue-light,#dbeafe);color:var(--blue);border-radius:var(--r);margin-left:4px">kampania</span>' : '';
      const hiddenTag = it.hidden ? '<span style="font-size:0.65rem;padding:1px 5px;background:var(--surface);color:var(--t3);border-radius:var(--r);margin-left:4px">ukryty</span>' : '';
      return '<div style="padding:8px 10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);font-size:0.78rem;cursor:pointer;transition:border-color .15s" onmouseenter="this.style.borderColor=\'var(--accent)\'" onmouseleave="this.style.borderColor=\'var(--border)\'" onclick="openTplEntityModal(\'key_items\',' + realIdx + ',\'' + it.entity_type + '\',' + JSON.stringify(it).replace(/"/g,'&quot;') + ')">' +
        '<div><strong>' + _esc(it.label||it.key||'?') + '</strong>' + csTag + hiddenTag + '</div>' +
        (it.location_hint ? '<div style="color:var(--t3);font-size:0.7rem">📍 ' + _esc(it.location_hint) + '</div>' : '') +
      '</div>';
    });
    const dbHtml = (dbList||[]).map(renderDbCard);
    const allHtml = [...planHtml, ...dbHtml];
    elRef.innerHTML = allHtml.length ? allHtml.join('') : empty;
  };

  const weapons = items.filter(x => x.entity_type === 'weapon');
  const itemsArr = items.filter(x => x.entity_type === 'item');
  const cons   = items.filter(x => x.entity_type === 'consumable');
  renderList(weapons,  [...(db.weapon||[]), ...(db.armor||[])], weaponEl);
  renderList(itemsArr, db.item||[], itemEl);
  renderList(cons,     db.consumable||[], consEl);
}

async function _loadTplDbItems() {
  if (!_tplEditorData?.id) return;
  try {
    const d = await apiFetch('/api/admin/forge/templates/' + _tplEditorData.id + '/db-items');
    window._tplDbItemsByType = {
      weapon: (d.weapons||[]).map(x=>({...x,entry_type:'weapon'})),
      armor:  (d.armors||[]).map(x=>({...x,entry_type:'armor'})),
      item:   (d.items||[]).map(x=>({...x,entry_type:'item'})),
      consumable: (d.consumables||[]).map(x=>({...x,entry_type:'consumable'})),
    };
    _renderTplItems(_tplEditorPlan?.key_items || [], window._tplDbItemsByType);
  } catch(e) { console.warn('DB items load failed:', e.message); }
}

async function _promoteTplDbItem(entryType, key, btn) {
  if (!_tplEditorData?.id) return;
  if (!confirm('Promować ' + key + ' do globalnej bazy? Przedmiot przestanie być powiązany tylko z tym szablonem.')) return;
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    await apiFetch('/api/admin/forge/templates/' + _tplEditorData.id + '/db-items/' + entryType + '/' + encodeURIComponent(key) + '/promote', { method: 'POST' });
    _showToast(key + ' → globalna baza ✓', 'success');
    _loadTplDbItems();
  } catch(e) {
    _showToast('Błąd promocji: ' + (e.message||'nieznany'), 'error');
    if (btn) { btn.disabled = false; btn.textContent = '⬆ Promuj do globalnej bazy'; }
  }
}

function _addTplItem(entityType) {
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan.key_items) _tplEditorPlan.key_items = [];
  openTplEntityModal('key_items', -1, entityType, { entity_type: entityType });
}

async function forgeGeneratePlanItem(entityType, evt) {
  if (!_tplEditorData?.id) return;
  const btn = evt ? evt.target : null;
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    const r = await apiFetch(`/api/admin/forge/templates/${_tplEditorData.id}/generate-item`, {
      method: 'POST',
      body: JSON.stringify({ entity_type: entityType })
    });
    if (!_tplEditorPlan) _tplEditorPlan = {};
    if (!_tplEditorPlan.key_items) _tplEditorPlan.key_items = [];
    openTplEntityModal('key_items', -1, entityType, Object.assign({ entity_type: entityType }, r.item || {}));
  } catch(e) {
    _showToast('Błąd generowania: ' + (e.message || 'nieznany błąd'), 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🤖 Generuj AI'; }
  }
}

// ─── Template Entity Modal ───────────────────────────────────────────────────
async function openTplEntityModal(listKey, idx, type, data) {
  _tplEntityCtx = { listKey, idx, type };
  const modal = document.getElementById('tpl-entity-modal');
  const typeLabels = {
    npc:'NPC', enemy:'Wróg', weapon:'Broń', item:'Przedmiot',
    consumable:'Mikstura', location:'Lokacja'
  };
  document.getElementById('tpl-entity-modal-type-badge').textContent = typeLabels[type] || type;
  document.getElementById('tpl-entity-modal-title').textContent =
    data.name || data.label || data.key || '(nowy)';
  document.getElementById('tpl-entity-campaign-specific').checked = !!data.campaign_specific;
  if (['weapon','item','consumable'].includes(type)) await _ejLoadDynamicData();
  _forgeEjData = null;
  document.getElementById('tpl-entity-form').innerHTML = _renderEntityForm(type, data.overrides || data);
  if (['weapon','item','consumable'].includes(type)) _forgeWireEffectBuilder();
  document.getElementById('tpl-entity-delete-btn').style.display = idx < 0 ? 'none' : '';
  // #1085 — show enemy pool swap section for existing enemies
  const swapSection = document.getElementById('tpl-enemy-swap-section');
  if (swapSection) swapSection.style.display = (type === 'enemy' && idx >= 0) ? '' : 'none';
  modal.style.display = 'flex';
}

function closeTplEntityModal() {
  document.getElementById('tpl-entity-modal').style.display = 'none';
  const csRow = document.getElementById('tpl-entity-campaign-specific')?.parentElement;
  if (csRow) csRow.style.display = '';
  const delBtn = document.getElementById('tpl-entity-delete-btn');
  if (delBtn) delBtn.style.display = '';
  _tplEntityCtx = null;
}

function _deleteTplEntity() {
  if (!_tplEntityCtx || _tplEntityCtx.idx < 0) return;
  const { listKey, idx } = _tplEntityCtx;
  if (!_tplEditorPlan?.[listKey]) return;
  _tplEditorPlan[listKey].splice(idx, 1);
  _refreshTplEntityList(listKey);
  closeTplEntityModal();
}

function _refreshTplEntityList(listKey) {
  if (listKey === 'key_npcs') _renderTplNPCs(_tplEditorPlan.key_npcs || []);
  else if (listKey === 'key_locations') _renderTplLocations(_tplEditorPlan.key_locations || []);
  else if (listKey === 'key_enemies' && typeof _renderTplEnemies === 'function') _renderTplEnemies(_tplEditorPlan.key_enemies || []);
  else if (listKey === 'key_items' && typeof _renderTplItems === 'function') _renderTplItems(_tplEditorPlan.key_items || []);
}

// #1085 — enemy pool swap helpers
async function _loadEnemyPoolIntoSelect() {
  const sel = document.getElementById('tpl-enemy-pool-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">Ładowanie…</option>';
  try {
    const data = await apiFetch('/api/admin/enemies');
    const enemies = (data.items || []).filter(e => e.review_status !== 'pending');
    if (!enemies.length) { sel.innerHTML = '<option value="">Brak wrogów w puli</option>'; return; }
    sel.innerHTML = '<option value="">— wybierz wroga —</option>' +
      enemies.map(e => `<option value="${_esc(e.key)}" data-label="${_esc(e.label)}" data-hp="${e.hp_base||20}" data-ac="${e.ac_base||12}" data-dmg="${_esc(e.damage_die||'1d6')}" data-tier="${_esc(e.tier||'standard')}">${_esc(e.label)} (${e.tier||'standard'}, HP ${e.hp_base||'?'})</option>`).join('');
  } catch(err) {
    sel.innerHTML = '<option value="">Błąd wczytywania: ' + _esc(String(err.message||err)) + '</option>';
  }
}

function _swapTplEnemyFromPool() {
  if (!_tplEntityCtx || _tplEntityCtx.type !== 'enemy') return;
  const { listKey, idx } = _tplEntityCtx;
  const sel = document.getElementById('tpl-enemy-pool-select');
  if (!sel || !sel.value) { _showToast('Wybierz wroga z listy', 'warning'); return; }
  const opt = sel.selectedOptions[0];
  const swapped = {
    key: sel.value,
    label: opt.dataset.label || sel.value,
    tier: opt.dataset.tier || 'standard',
    campaign_specific: false,
    overrides: {
      key: sel.value,
      label: opt.dataset.label || sel.value,
      hp_base: parseInt(opt.dataset.hp) || 20,
      ac_base: parseInt(opt.dataset.ac) || 12,
      damage_die: opt.dataset.dmg || '1d6',
      tier: opt.dataset.tier || 'standard',
    },
  };
  if (!_tplEditorPlan[listKey]) _tplEditorPlan[listKey] = [];
  if (idx >= 0) _tplEditorPlan[listKey][idx] = swapped;
  _refreshTplEntityList(listKey);
  closeTplEntityModal();
  _showToast('Wróg zamieniony ✓', 'success');
}

function saveTplEntityEdits() {
  if (!_tplEntityCtx) return;
  const { listKey, idx, type } = _tplEntityCtx;
  // DB item: PATCH game_config_* record directly, then refresh lists
  if (listKey === 'db_item') {
    const { dbKey, dbEntryType } = _tplEntityCtx;
    const tableMap = { weapon:'game_config_weapons', armor:'game_config_items', item:'game_config_items', consumable:'game_config_consumables' };
    const table = tableMap[dbEntryType] || 'game_config_weapons';
    const formData = _collectEntityForm(type);
    apiFetch('/api/admin/smart-entry/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: 'tpl-entity-db', table, target_key: dbKey, draft: formData }),
    }).then(() => {
      _showToast('Zapisano ✓', 'success');
      _loadTplDbItems();
    }).catch(e => _showToast('Błąd zapisu: ' + e.message, 'error'));
    closeTplEntityModal();
    return;
  }
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan[listKey]) _tplEditorPlan[listKey] = [];

  const campaignSpecific = document.getElementById('tpl-entity-campaign-specific').checked;
  const formData = _collectEntityForm(type);
  const existing = idx >= 0 ? (_tplEditorPlan[listKey][idx] || {}) : {};

  const slug = (formData.key || formData.name || formData.label || '')
    .toLowerCase().replace(/\s+/g,'_').replace(/[^a-z0-9_]/g,'');

  const updated = {
    ...existing,
    key: formData.key || slug,
    campaign_specific: campaignSpecific,
    overrides: formData,
  };
  if (type === 'npc') { updated.name = formData.name || formData.key; updated.role = existing.role || ''; updated.importance = existing.importance || 'supporting'; updated.deviation_consequence = existing.deviation_consequence || 'steer'; updated.alive = existing.alive !== false; }
  if (type === 'enemy') { updated.label = formData.label || formData.key; }
  if (['weapon','item','consumable'].includes(type)) { updated.label = formData.label || formData.key; updated.entity_type = type; updated.hidden = formData.hidden || false; updated.location_hint = formData.location_hint || ''; }
  if (type === 'location') { updated.name = formData.name || formData.key; updated.role = existing.role || ''; updated.visited = existing.visited || false; updated.sub_locations = existing.sub_locations || []; }

  if (idx >= 0) {
    _tplEditorPlan[listKey][idx] = updated;
  } else {
    _tplEditorPlan[listKey].push(updated);
  }
  _refreshTplEntityList(listKey);
  closeTplEntityModal();
}

// ─── Inline effect-builder (_ej*) ────────────────────────────────────────────
function _forgeEjOpen(mode) {
  openEffectBuilder(_forgeEjData, mode, 'Effect JSON', function(data) {
    _forgeEjData = data;
    const p = document.getElementById('ef-ej-preview');
    if (p) p.textContent = data ? JSON.stringify(data, null, 2) : '— brak efektu —';
  });
}

function _ejCategoryChange() {
  _ejRenderEffects([]);
  _ejUpdatePreview();
  const cat = (document.getElementById('ef-ej-category')||{}).value;
  const addBtn = document.getElementById('ef-ej-add-btn');
  if (addBtn) addBtn.style.display = cat ? 'inline-block' : 'none';
}

function _ejGetAllowedTypes() {
  const cat = (document.getElementById('ef-ej-category')||{}).value;
  return cat ? (EFFECT_JSON_SCHEMA.categories[cat]||{}).allowed_types || [] : [];
}

function _ejRenderEffectRow(idx, effectData) {
  const allowedTypes = _ejGetAllowedTypes();
  const typeOpts = allowedTypes.map(t =>
    `<option value="${t}" ${(effectData.type||''===t)?'selected':''}>${EFFECT_JSON_SCHEMA.effect_types[t]?.label||t}</option>`
  ).join('');

  const selectedType = effectData.type || allowedTypes[0] || '';
  const typeDef = EFFECT_JSON_SCHEMA.effect_types[selectedType] || { fields: [] };

  const fieldHtml = typeDef.fields.map(f => {
    const val = effectData[f.id] !== undefined ? effectData[f.id] : '';
    if (f.type === 'select') {
      const opts = f.options.map(o => `<option value="${o}" ${val===o?'selected':''}>${o}</option>`).join('');
      return `<select class="form-input ej-field" data-field="${f.id}" style="max-width:110px" onchange="_ejUpdatePreview()"><option value="">— ${f.label} —</option>${opts}</select>`;
    } else if (f.type === 'number') {
      return `<input class="form-input ej-field" data-field="${f.id}" type="number" value="${val||0}" placeholder="${f.label}" style="max-width:70px" oninput="_ejUpdatePreview()">`;
    } else {
      return `<input class="form-input ej-field" data-field="${f.id}" type="text" value="${_esc(String(val||''))}" placeholder="${f.placeholder||f.label}" style="max-width:120px" oninput="_ejUpdatePreview()">`;
    }
  }).join('');

  return `<div class="ej-effect-row" data-idx="${idx}" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:6px;background:#1a1a1a;border-radius:4px;margin-bottom:4px">
  <select class="form-input ej-type-sel" style="max-width:190px" onchange="_ejTypeChange(this,${idx})">${typeOpts}</select>
  <span class="ej-fields" style="display:flex;gap:6px;flex-wrap:wrap">${fieldHtml}</span>
  <button type="button" style="background:#c0392b;color:#fff;border:none;border-radius:3px;padding:2px 7px;cursor:pointer" onclick="_ejRemoveEffect(${idx})">×</button>
</div>`;
}

function _ejTypeChange(sel, idx) {
  const row = sel.closest('.ej-effect-row');
  if (!row) return;
  const newType = sel.value;
  const typeDef = EFFECT_JSON_SCHEMA.effect_types[newType] || { fields: [] };
  const fieldsSpan = row.querySelector('.ej-fields');
  if (fieldsSpan) {
    fieldsSpan.innerHTML = typeDef.fields.map(f => {
      if (f.type === 'select') {
        const opts = f.options.map(o => `<option value="${o}">${o}</option>`).join('');
        return `<select class="form-input ej-field" data-field="${f.id}" style="max-width:110px" onchange="_ejUpdatePreview()"><option value="">— ${f.label} —</option>${opts}</select>`;
      } else if (f.type === 'number') {
        return `<input class="form-input ej-field" data-field="${f.id}" type="number" value="0" placeholder="${f.label}" style="max-width:70px" oninput="_ejUpdatePreview()">`;
      } else {
        return `<input class="form-input ej-field" data-field="${f.id}" type="text" value="" placeholder="${f.placeholder||f.label}" style="max-width:120px" oninput="_ejUpdatePreview()">`;
      }
    }).join('');
  }
  _ejUpdatePreview();
}

function _ejRenderEffects(effectsData) {
  const list = document.getElementById('ef-ej-effects-list');
  if (!list) return;
  list.innerHTML = effectsData.map((e, i) => _ejRenderEffectRow(i, e)).join('');
}

function _ejAddEffect() {
  const list = document.getElementById('ef-ej-effects-list');
  if (!list) return;
  const allowedTypes = _ejGetAllowedTypes();
  if (!allowedTypes.length) return;
  const idx = list.children.length;
  const div = document.createElement('div');
  div.innerHTML = _ejRenderEffectRow(idx, { type: allowedTypes[0] });
  list.appendChild(div.firstElementChild);
  _ejUpdatePreview();
}

function _ejRemoveEffect(idx) {
  const list = document.getElementById('ef-ej-effects-list');
  if (!list) return;
  const rows = list.querySelectorAll('.ej-effect-row');
  if (rows[idx]) rows[idx].remove();
  list.querySelectorAll('.ej-effect-row').forEach((row, i) => {
    row.dataset.idx = i;
    const btn = row.querySelector('button[onclick^="_ejRemove"]');
    if (btn) btn.setAttribute('onclick', `_ejRemoveEffect(${i})`);
    const typeSel = row.querySelector('.ej-type-sel');
    if (typeSel) typeSel.setAttribute('onchange', `_ejTypeChange(this,${i})`);
  });
  _ejUpdatePreview();
}

function _ejSerialize() {
  const cat = (document.getElementById('ef-ej-category')||{}).value;
  if (!cat) return null;
  const list = document.getElementById('ef-ej-effects-list');
  if (!list) return null;
  const effects = [];
  list.querySelectorAll('.ej-effect-row').forEach(row => {
    const type = (row.querySelector('.ej-type-sel')||{}).value;
    if (!type) return;
    const effect = { type };
    row.querySelectorAll('.ej-field').forEach(el => {
      const field = el.dataset.field;
      if (!field) return;
      const val = el.value;
      if (val === '' || val === null) return;
      if (el.type === 'number') effect[field] = parseFloat(val) || 0;
      else effect[field] = val;
    });
    effects.push(effect);
  });
  if (!effects.length) return null;
  return { schema_version: 1, effect_category: cat, effects };
}

function _ejUpdatePreview() {
  const preview = document.getElementById('ef-ej-preview');
  if (!preview) return;
  const data = _ejSerialize();
  preview.textContent = data ? JSON.stringify(data) : '— brak efektu —';
}

function _ejPopulate(effectJson) {
  let parsed = effectJson;
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed); } catch(e) { parsed = null; }
  }
  _forgeEjData = (parsed && typeof parsed === 'object') ? parsed : null;
  const preview = document.getElementById('ef-ej-preview');
  if (preview) preview.textContent = _forgeEjData ? JSON.stringify(_forgeEjData, null, 2) : '— brak efektu —';
}

function _renderEntityForm(type, d) {
  d = d || {};
  const sel = (id, label, opts, val) =>
    '<div class="form-row"><label class="form-label">' + label + '</label><select class="form-input" id="ef-' + id + '">' + opts.map(o => '<option value="' + (o.v||o) + '" ' + ((val||'')===(o.v||o)?'selected':'') + '>' + (o.l||o) + '</option>').join('') + '</select></div>';
  const txt = (id, label, val, placeholder) =>
    '<div class="form-row"><label class="form-label">' + label + '</label><input class="form-input" id="ef-' + id + '" type="text" value="' + _esc(val||'') + '" placeholder="' + (placeholder||'') + '"></div>';
  const num = (id, label, val) =>
    '<div class="form-row"><label class="form-label">' + label + '</label><input class="form-input" id="ef-' + id + '" type="number" value="' + (val||0) + '" style="max-width:100px"></div>';
  const ta  = (id, label, val, rows) =>
    '<div class="form-row" style="grid-column:1/-1"><label class="form-label">' + label + '</label><textarea class="form-input" id="ef-' + id + '" rows="' + (rows||2) + '" style="resize:vertical">' + _esc(val||'') + '</textarea></div>';
  const chk = (id, label, val) =>
    '<div class="form-row" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="ef-' + id + '" ' + (val?'checked':'') + '><label for="ef-' + id + '" class="form-label" style="margin:0">' + label + '</label></div>';
  const G = (cols, ...fields) =>
    '<div style="display:grid;grid-template-columns:' + cols + ';gap:10px;margin-bottom:4px">' + fields.join('') + '</div>';
  const rarity = [{v:'1',l:'Pospolity'},{v:'2',l:'Niepospolity'},{v:'3',l:'Rzadki'},{v:'4',l:'Epicki'},{v:'5',l:'Legendarny'}];

  if (type === 'npc') return G('1fr 1fr',
    txt('key','Klucz (slug)',d.key),
    txt('name','Imię / Nazwa',d.name||d.label),
    sel('npc_type','Typ NPC',[{v:'neutral',l:'Neutralny'},{v:'friendly',l:'Przyjazny'},{v:'hostile',l:'Wrogi'},{v:'merchant',l:'Kupiec'},{v:'quest_giver',l:'Dawca zadań'},{v:'ally',l:'Sojusznik'}],d.npc_type),
    chk('is_quest_giver','Dawca zadań',d.is_quest_giver),
    chk('is_ally','Sojusznik',d.is_ally),
    ta('personality_prompt','Osobowość / ton głosu',d.personality_prompt,2),
    ta('description','Opis',d.description,3),
    txt('keyword_triggers','Słowa kluczowe (przecinki)',Array.isArray(d.keyword_triggers)?d.keyword_triggers.join(', '):d.keyword_triggers||'')
  );

  if (type === 'enemy') return G('1fr 1fr',
    txt('key','Klucz (slug)',d.key),
    txt('label','Nazwa',d.label),
    num('hp_base','HP bazowe',d.hp_base||10),
    num('ac_base','AC bazowe',d.ac_base||10),
    num('attack_bonus','Bonus do ataku',d.attack_bonus||0),
    num('damage_bonus','Bonus do obrażeń',d.damage_bonus||0),
    txt('damage_die','Kość obrażeń',d.damage_die||'1d6','np. 1d8+2'),
    sel('damage_type','Typ obrażeń',[{v:'physical',l:'Fizyczne'},{v:'magic',l:'Magiczne'},{v:'poison',l:'Trucizna'}],d.damage_type||'physical'),
    sel('tier','Tier',[{v:'weak',l:'Słaby'},{v:'standard',l:'Standardowy'},{v:'elite',l:'Elita'},{v:'boss',l:'Boss'}],d.tier||'standard'),
    num('attacks_per_turn','Ataki/tura',d.attacks_per_turn||1),
    num('xp_award','Nagroda XP',d.xp_award||0),
    chk('fear_aura','Aura strachu',d.fear_aura),
    num('fear_dc','DC strachu',d.fear_dc||12),
    txt('conditions_immune','Odporności (przecinki)',d.conditions_immune||''),
    ta('description','Opis',d.description,2),
    ta('note','Notatka GM (zdolności)',d.note,2)
  );

  if (type === 'weapon') return G('1fr 1fr',
    txt('key','Klucz (slug)',d.key),
    txt('label','Nazwa',d.label),
    txt('damage_die','Kość obrażeń',d.damage_die||'1d6','np. 1d8+2'),
    sel('linked_stat','Statystyka',[{v:'STR',l:'STR'},{v:'DEX',l:'DEX'},{v:'INT',l:'INT'}],d.linked_stat||'STR'),
    sel('weapon_type','Typ broni',[{v:'melee',l:'Biała'},{v:'ranged',l:'Dystansowa'},{v:'thrown',l:'Miotana'}],d.weapon_type||'melee'),
    sel('weapon_slot','Slot',[{v:'main_hand',l:'Prawa ręka'},{v:'off_hand',l:'Lewa ręka'},{v:'two_handed',l:'Oburącz'},{v:'ranged',l:'Dystansowy'}],d.weapon_slot||'main_hand'),
    sel('targeting','Cel',[{v:'single',l:'Pojedynczy'},{v:'aoe',l:'AOE'},{v:'self',l:'Własny'}],d.targeting||'single'),
    chk('two_handed','Dwuręczna',d.two_handed),
    chk('finesse','Finezja (DEX)',d.finesse),
    num('range_m','Zasięg (m)',d.range_m||0),
    num('value_gp','Wartość (zł)',d.value_gp||0),
    sel('rarity','Rzadkość',rarity,String(d.rarity||1)),
    txt('magic_school','Szkoła magii',d.magic_school||'','np. necromancy'),
    ta('description','Opis',d.description,2),
    ta('note','Notatka GM (efekty)',d.note,2),
    (() => {
      const existing = (() => { try { const e = typeof d.effect_json==='string'?JSON.parse(d.effect_json):(d.effect_json||null); return Array.isArray(e)?e:(e?.effects||[]); } catch{return[];} })();
      return `<div class="form-row" style="grid-column:1/-1"><label class="form-label" style="margin-bottom:4px">Efekty broni (on-equip)</label>${_forgeEffectBuilderHtml(existing)}</div>`;
    })()
    + chk('hidden','Ukryty (GM musi odkryć)',d.hidden||false)
    + txt('location_hint','Wskazówka lokalizacji',d.location_hint||'','np. "Zbrojownia na 2. piętrze"')
  );

  if (type === 'item') return G('1fr 1fr',
    txt('key','Klucz (slug)',d.key),
    txt('label','Nazwa',d.label),
    sel('item_type','Typ',[{v:'misc',l:'Różne'},{v:'armor',l:'Zbroja'},{v:'gear',l:'Ekwipunek'},{v:'tool',l:'Narzędzie'},{v:'container',l:'Pojemnik'},{v:'lore',l:'Wiedza'},{v:'magic',l:'Magiczne'},{v:'quest',l:'Zadanie'}],d.item_type||'misc'),
    sel('armor_coverage','Zasięg zbroi',[{v:'torso',l:'Tors'},{v:'head',l:'Głowa'},{v:'legs',l:'Nogi'},{v:'full',l:'Pełna'}],d.armor_coverage||'torso'),
    num('ac_bonus','Bonus AC',d.ac_bonus||0),
    num('value_gp','Wartość (zł)',d.value_gp||0),
    num('weight_kg','Waga (kg)',d.weight_kg||0),
    sel('rarity','Rzadkość',rarity,String(d.rarity||1)),
    sel('effect_target','Cel efektu',[{v:'self',l:'Własny'},{v:'target',l:'Cel'},{v:'aoe',l:'AOE'}],d.effect_target||'self'),
    txt('effect_type','Typ efektu',d.effect_type||'','np. ac_bonus'),
    txt('effect_dice','Kość efektu',d.effect_dice||'','np. 1d4'),
    num('effect_bonus','Bonus efektu',d.effect_bonus||0),
    num('charges','Ładunki',d.charges||1),
    ta('description','Opis',d.description,2),
    ta('note','Notatka GM',d.note,2),
    (() => {
      const existing = (() => { try { const e = typeof d.effect_json==='string'?JSON.parse(d.effect_json):(d.effect_json||null); return Array.isArray(e)?e:(e?.effects||[]); } catch{return[];} })();
      return `<div class="form-row" style="grid-column:1/-1"><label class="form-label" style="margin-bottom:4px">Efekty przedmiotu (on-equip)</label>${_forgeEffectBuilderHtml(existing)}</div>`;
    })()
    + chk('hidden','Ukryty (GM musi odkryć)',d.hidden||false)
    + txt('location_hint','Wskazówka lokalizacji',d.location_hint||'','np. "Zbrojownia na 2. piętrze"')
  );

  if (type === 'consumable') return G('1fr 1fr',
    txt('key','Klucz (slug)',d.key),
    txt('label','Nazwa',d.label),
    sel('effect_type','Typ efektu',[{v:'heal_hp',l:'Leczenie HP'},{v:'restore_mana',l:'Przywróć manę'},{v:'remove_condition',l:'Usuń stan'},{v:'stat_buff',l:'Bufor statystyki'},{v:'add_condition',l:'Dodaj stan'},{v:'misc',l:'Różne'}],d.effect_type||'misc'),
    sel('effect_target','Cel',[{v:'self',l:'Własny'},{v:'target',l:'Cel'}],d.effect_target||'self'),
    txt('effect_dice','Kość efektu',d.effect_dice||'','np. 2d4+2'),
    num('effect_bonus','Bonus efektu',d.effect_bonus||0),
    num('charges','Ładunki',d.charges||1),
    num('base_price','Cena bazowa (zł)',d.base_price||0),
    num('weight_kg','Waga (kg)',d.weight_kg||0),
    sel('rarity','Rzadkość',rarity,String(d.rarity||1)),
    ta('description','Opis',d.description,2),
    ta('note','Notatka GM',d.note,2),
    (() => {
      const existing = (() => { try { const e = typeof d.effect_json==='string'?JSON.parse(d.effect_json):(d.effect_json||null); return Array.isArray(e)?e:(e?.effects||[]); } catch{return[];} })();
      return `<div class="form-row" style="grid-column:1/-1"><label class="form-label" style="margin-bottom:4px">Efekty konsumablu (on-use)</label>${_forgeEffectBuilderHtml(existing)}</div>`;
    })()
    + chk('hidden','Ukryty (GM musi odkryć)',d.hidden||false)
    + txt('location_hint','Wskazówka lokalizacji',d.location_hint||'','np. "Zbrojownia na 2. piętrze"')
  );

  if (type === 'location') return G('1fr 1fr',
    txt('key','Klucz (slug)',d.key),
    txt('name','Nazwa',d.name||d.label),
    sel('location_type','Typ',[{v:'dungeon',l:'Loch'},{v:'town',l:'Miasto'},{v:'wilderness',l:'Dzikie tereny'},{v:'building',l:'Budynek'},{v:'cave',l:'Jaskinia'},{v:'camp',l:'Obóz'},{v:'ruins',l:'Ruiny'}],d.location_type||'dungeon'),
    sel('biome','Biom',[{v:'ruin',l:'Ruiny'},{v:'forest',l:'Las'},{v:'mountain',l:'Góry'},{v:'urban',l:'Miejski'},{v:'underground',l:'Podziemia'},{v:'coast',l:'Wybrzeże'},{v:'swamp',l:'Bagna'}],d.biome||'ruin'),
    ta('description','Opis',d.description,3),
    ta('role','Rola w kampanii',d.role,2)
  );

  return '<pre style="font-size:0.75rem;overflow:auto">' + _esc(JSON.stringify(d,null,2)) + '</pre>';
}

function _collectEntityForm(type) {
  const v  = id => (document.getElementById('ef-'+id)||{}).value || '';
  const n  = id => parseFloat((document.getElementById('ef-'+id)||{}).value) || 0;
  const b  = id => !!(document.getElementById('ef-'+id)||{}).checked;
  if (type === 'npc') return { key:v('key'), name:v('name'), npc_type:v('npc_type'), personality_prompt:v('personality_prompt'), description:v('description'), is_quest_giver:b('is_quest_giver'), is_ally:b('is_ally'), keyword_triggers: v('keyword_triggers').split(',').map(s=>s.trim()).filter(Boolean) };
  if (type === 'enemy') return { key:v('key'), label:v('label'), hp_base:n('hp_base'), ac_base:n('ac_base'), attack_bonus:n('attack_bonus'), damage_bonus:n('damage_bonus'), damage_die:v('damage_die'), damage_type:v('damage_type'), tier:v('tier'), attacks_per_turn:n('attacks_per_turn'), xp_award:n('xp_award'), fear_aura:b('fear_aura'), fear_dc:n('fear_dc'), conditions_immune:v('conditions_immune'), description:v('description'), note:v('note') };
  if (type === 'weapon') return { key:v('key'), label:v('label'), damage_die:v('damage_die'), linked_stat:v('linked_stat'), weapon_type:v('weapon_type'), weapon_slot:v('weapon_slot'), targeting:v('targeting'), two_handed:b('two_handed'), finesse:b('finesse'), range_m:n('range_m'), value_gp:n('value_gp'), rarity:n('rarity'), magic_school:v('magic_school'), description:v('description'), note:v('note'), effect_json:_forgeEjData ? JSON.stringify(_forgeEjData) : null, hidden:b('hidden'), location_hint:v('location_hint') };
  if (type === 'item') return { key:v('key'), label:v('label'), item_type:v('item_type'), armor_coverage:v('armor_coverage'), ac_bonus:n('ac_bonus'), value_gp:n('value_gp'), weight_kg:n('weight_kg'), rarity:n('rarity'), effect_target:v('effect_target'), effect_type:v('effect_type'), effect_dice:v('effect_dice'), effect_bonus:n('effect_bonus'), charges:n('charges'), description:v('description'), note:v('note'), effect_json:_forgeEjData ? JSON.stringify(_forgeEjData) : null, hidden:b('hidden'), location_hint:v('location_hint') };
  if (type === 'consumable') return { key:v('key'), label:v('label'), effect_type:v('effect_type'), effect_target:v('effect_target'), effect_dice:v('effect_dice'), effect_bonus:n('effect_bonus'), charges:n('charges'), base_price:n('base_price'), weight_kg:n('weight_kg'), rarity:n('rarity'), description:v('description'), note:v('note'), effect_json:_forgeEjData ? JSON.stringify(_forgeEjData) : null, hidden:b('hidden'), location_hint:v('location_hint') };
  if (type === 'location') return { key:v('key'), name:v('name'), location_type:v('location_type'), biome:v('biome'), description:v('description'), role:v('role') };
  return {};
}

function _renderTplEndings(endings) {
  const el = document.getElementById('tpl-endings-list');
  if (!el) return;
  if (!endings.length) {
    endings = [
      { id:'ending_primary', title:'', type:'primary', description:'', requirements:[] },
      { id:'ending_alternate', title:'', type:'alternate', description:'', requirements:[] },
    ];
  }
  el.innerHTML = endings.slice(0,2).map((end, i) =>
    '<div class="card" style="padding:14px">' +
      '<div style="font-size:0.72rem;font-weight:600;color:' + (end.type==='primary'?'var(--blue)':'var(--amber)') + ';margin-bottom:8px">' + (end.type==='primary'?'★ ZAKOŃCZENIE GŁÓWNE':'◆ ZAKOŃCZENIE ALTERNATYWNE') + '</div>' +
      '<div class="form-row"><label class="form-label">Tytuł</label><input class="form-input" id="tpl-end-title-' + i + '" type="text" value="' + _esc(end.title||'') + '"></div>' +
      '<div class="form-row"><label class="form-label">Opis</label><textarea class="form-input" id="tpl-end-desc-' + i + '" rows="3" style="resize:vertical">' + _esc(end.description||'') + '</textarea></div>' +
      '<div class="form-row"><label class="form-label" style="margin-bottom:4px">Warunki</label>' +
        '<div id="tpl-end-reqs-' + i + '" style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">' +
          (end.requirements||[]).map((r,ri) => '<span style="display:inline-flex;align-items:center;gap:4px;font-size:0.75rem;padding:2px 8px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)">' + _esc(r) + '<button type="button" onclick="_removeTplReq(' + i + ',' + ri + ')" style="background:none;border:none;cursor:pointer;color:var(--t3);padding:0">✕</button></span>').join('') +
        '</div>' +
        '<div style="display:flex;gap:6px">' +
          '<input class="form-input" id="tpl-end-req-input-' + i + '" type="text" placeholder="Dodaj warunek…" style="flex:1" onkeydown="if(event.key===\'Enter\'){event.preventDefault();_addTplReq(' + i + ')}">' +
          '<button class="btn btn-sm btn-secondary" onclick="_addTplReq(' + i + ')">+</button>' +
        '</div>' +
      '</div>' +
    '</div>'
  ).join('');
}

function _addTplReq(endIdx) {
  const input = document.getElementById('tpl-end-req-input-' + endIdx);
  if (!input || !input.value.trim()) return;
  const req = input.value.trim(); input.value = '';
  if (!_tplEditorPlan) _tplEditorPlan = {};
  if (!_tplEditorPlan.endings) _tplEditorPlan.endings = [{requirements:[]},{requirements:[]}];
  if (!_tplEditorPlan.endings[endIdx]) _tplEditorPlan.endings[endIdx] = {requirements:[]};
  if (!_tplEditorPlan.endings[endIdx].requirements) _tplEditorPlan.endings[endIdx].requirements = [];
  _tplEditorPlan.endings[endIdx].requirements.push(req);
  _renderTplEndings(_tplEditorPlan.endings);
}

function _removeTplReq(endIdx, reqIdx) {
  if (_tplEditorPlan?.endings?.[endIdx]?.requirements) {
    _tplEditorPlan.endings[endIdx].requirements.splice(reqIdx, 1);
    _renderTplEndings(_tplEditorPlan.endings);
  }
}

function _collectTplPlan() {
  const plan = { ...(_tplEditorPlan || {}) };
  const actCount = (plan.acts || []).length || 3;
  plan.acts = Array.from({length: actCount}, (_, i) => ({
    number: i+1,
    title: document.getElementById('tpl-act-title-' + i)?.value || '',
    summary: document.getElementById('tpl-act-summary-' + i)?.value || '',
    key_beats: (plan.acts?.[i]?.key_beats || []),
    completed: false,
  }));
  plan.endings = [0,1].map(i => ({
    id: i===0?'ending_primary':'ending_alternate',
    title: document.getElementById('tpl-end-title-' + i)?.value || '',
    type: i===0?'primary':'alternate',
    description: document.getElementById('tpl-end-desc-' + i)?.value || '',
    requirements: plan.endings?.[i]?.requirements || [],
  }));
  plan.engine_private = {
    secret_predisposition_hint: document.getElementById('tpl-gm-hint')?.value || '',
    hidden_twist: document.getElementById('tpl-gm-twist')?.value || '',
    contingency: document.getElementById('tpl-gm-contingency')?.value || '',
  };
  plan.title = document.getElementById('tpl-title')?.value || plan.title || '';
  plan.premise = plan.premise || '';
  if (!plan.active_act) plan.active_act = 1;
  if (!plan.scene_log) plan.scene_log = [];
  if (!plan.deviations) plan.deviations = [];
  if (!plan.branches) plan.branches = [];
  plan.key_enemies = _tplEditorPlan.key_enemies || [];
  plan.key_items   = _tplEditorPlan.key_items || [];
  return plan;
}

// E7 (#422) — split a comma/newline separated key list into a clean array.
function _splitKeys(s) {
  return (s || '').split(/[,\n]/).map(x => x.trim()).filter(Boolean);
}

async function saveTemplateEdits() {
  if (!_tplEditorData) { _showToast('Brak danych szablonu.', 'error'); return; }
  const plan = _collectTplPlan();
  const payload = {
    title: document.getElementById('tpl-title')?.value?.trim() || _tplEditorData.title,
    description: document.getElementById('tpl-description')?.value?.trim(),
    atmosphere: document.getElementById('tpl-atmosphere')?.value?.trim(),
    difficulty_rating: _tplDifficulty,
    gm_plan_json: plan,
    hook_ids: _tplEditorData.hook_ids || [],
    // E7 (#422)
    required_npc_keys: _splitKeys(document.getElementById('tpl-required-npcs')?.value),
    required_beats: _splitKeys(document.getElementById('tpl-required-beats')?.value),
    player_visible: document.getElementById('tpl-player-visible')?.checked ?? true,
  };
  try {
    await apiFetch('/api/admin/forge/templates/' + _tplEditorData.id, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    _showToast('Szablon zapisany.', 'success');
    _tplEditorPlan = plan;
  } catch(e) { _showToast(e.message || 'Błąd zapisu.', 'error'); }
}

// E12 (#427) — render the 3-state workflow buttons for the current status.
function _renderTplWorkflow(status) {
  const badge = document.getElementById('tpl-status-badge');
  const LABELS = { draft: 'Szkic', review: 'W recenzji', published: 'Opublikowany' };
  const COLORS = { draft: 'var(--t3)', review: 'var(--amber, #f59e0b)', published: 'var(--green)' };
  if (badge) { badge.textContent = LABELS[status] || status; badge.style.color = COLORS[status] || 'var(--t3)'; }
  const fwd = document.getElementById('tpl-publish-btn');
  const rev = document.getElementById('tpl-revert-btn');
  // Forward button: draft → Wyślij do recenzji; review → Opublikuj; published → (none, use revert)
  if (fwd) {
    if (status === 'draft') { fwd.textContent = '→ Do recenzji'; fwd.style.display = ''; }
    else if (status === 'review') { fwd.textContent = '✓ Opublikuj'; fwd.style.display = ''; }
    else { fwd.style.display = 'none'; }
  }
  // Revert button: review → Cofnij do szkicu; published → Wycofaj do szkicu
  if (rev) {
    if (status === 'review' || status === 'published') { rev.textContent = '↩ Cofnij do szkicu'; rev.style.display = ''; }
    else { rev.style.display = 'none'; }
  }
}

async function _patchTplStatus(newStatus, okMsg) {
  if (!_tplEditorData) return;
  // E10/E12 — publish can be rejected (422) with a structured detail; raw fetch reads it.
  try {
    const token = localStorage.getItem(_ADMIN_TOKEN_KEY);
    const r = await fetch(_buildUrl('/api/admin/forge/templates/' + _tplEditorData.id), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
      body: JSON.stringify({ status: newStatus }),
    });
    if (r.status === 422) {
      const body = await r.json().catch(() => ({}));
      const det = body.detail || {};
      const parts = [];
      if ((det.missing_npcs || []).length) parts.push('Brak NPC: ' + det.missing_npcs.join(', '));
      if ((det.missing_beats || []).length) parts.push('Brak beatów: ' + det.missing_beats.join(', '));
      _showToast((det.message || 'Nie można zmienić statusu') + (parts.length ? ' — ' + parts.join(' · ') : ''), 'error', 6000);
      return;
    }
    if (!r.ok) { _showToast('Błąd zmiany statusu (HTTP ' + r.status + ')', 'error'); return; }
    _tplEditorData.status = newStatus;
    _renderTplWorkflow(newStatus);
    _showToast(okMsg, 'success');
  } catch(e) { _showToast(e.message, 'error'); }
}

// Forward transition: draft → review → published.
async function _toggleTemplatePublish() {
  if (!_tplEditorData) return;
  if (_tplEditorData.status === 'draft') return _patchTplStatus('review', 'Szablon wysłany do recenzji.');
  if (_tplEditorData.status === 'review') return _patchTplStatus('published', 'Szablon opublikowany.');
}

// Revert: review/published → draft.
async function _revertTemplate() {
  return _patchTplStatus('draft', 'Szablon cofnięty do szkicu.');
}

function forgeGeneratePlan() {
  if (!_tplEditorData) return;
  _forgePlanIdeaId = null;
  _forgePlanTemplateId = _tplEditorData.id;
  // Pre-set acts count based on existing plan (or idea arc count if linked)
  const existingActs = (_tplEditorPlan?.acts || []).length;
  const actsSelect = document.getElementById('fpd-acts');
  if (actsSelect && existingActs > 0) {
    // Try to set the select to the matching option; default 5 if not found
    const opt = actsSelect.querySelector(`option[value="${existingActs}"]`);
    if (opt) actsSelect.value = String(existingActs);
  }
  document.getElementById('fpd-title-row').style.display = 'none';
  document.getElementById('fpd-heading').textContent = 'Generuj Plan GM';
  document.getElementById('fpd-confirm-btn').textContent = 'Generuj';
  const dlg = document.getElementById('forge-plan-dialog');
  if (dlg) dlg.style.display = 'flex';
}

async function forgeGeneratePlanConfirm() {
  const dlg = document.getElementById('forge-plan-dialog');
  if (dlg) dlg.style.display = 'none';
  const difficulty = document.getElementById('fpd-difficulty')?.value || 'medium';
  const suggestedActs = parseInt(document.getElementById('fpd-acts')?.value || '5', 10);

  if (_forgePlanIdeaId && !_forgePlanTemplateId) {
    // Creating new template from idea
    const title = document.getElementById('fpd-title')?.value?.trim();
    if (!title) { _showToast('Podaj tytuł szablonu.', 'error'); return; }
    const btn = document.getElementById('fpd-confirm-btn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
    try {
      const t = await apiFetch('/api/admin/forge/templates', {
        method: 'POST',
        body: JSON.stringify({ title, adventure_idea_id: _forgePlanIdeaId }),
      });
      _showToast(`Szablon "${t.title}" utworzony — generuję plan…`, 'success');
      // Switch to template editor immediately, then generate plan
      await _loadForgeTemplates();
      openTemplateEditor(t.id);
      // Small delay to let editor render, then run generate
      setTimeout(() => _doForgeGeneratePlan(t.id, difficulty, suggestedActs), 400);
    } catch(e) {
      _showToast(e.message || 'Błąd tworzenia szablonu.', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Stwórz i generuj'; }
    }
  } else {
    await _doForgeGeneratePlan(_forgePlanTemplateId, difficulty, suggestedActs);
  }
}

async function _doForgeGeneratePlan(templateId, difficulty, suggestedActs) {
  if (!templateId) return;
  const btn = document.getElementById('tpl-generate-btn');
  if (btn) { btn.disabled = true; btn.textContent = `⏳ Generuję ${suggestedActs} aktów…`; }
  try {
    const payload = {};
    if (_tplEditorData?.adventure_idea_id) payload.adventure_idea_id = _tplEditorData.adventure_idea_id;
    payload.difficulty = difficulty || 'medium';
    payload.suggested_act_count = suggestedActs || 5;
    const d = await apiFetch('/api/admin/forge/templates/' + templateId + '/generate-plan', {
      method: 'POST', body: JSON.stringify(payload),
    });
    _tplEditorPlan = d.gm_plan_json || {};
    _renderTplActs(_tplEditorPlan.acts || []);
    _renderTplNPCs(_tplEditorPlan.key_npcs || []);
    _renderTplEnemies(_tplEditorPlan.key_enemies || []);
    _renderTplLocations(_tplEditorPlan.key_locations || []);
    _renderTplEndings(_tplEditorPlan.endings || []);
    await _loadTplDbItems();  // #1084 — reload DB items after generate-plan (auto-assigned rewards)
    const ep = _tplEditorPlan.engine_private || {};
    if (document.getElementById('tpl-gm-hint')) document.getElementById('tpl-gm-hint').value = ep.secret_predisposition_hint || '';
    if (document.getElementById('tpl-gm-twist')) document.getElementById('tpl-gm-twist').value = ep.hidden_twist || '';
    if (document.getElementById('tpl-gm-contingency')) document.getElementById('tpl-gm-contingency').value = ep.contingency || '';
    ['tpl-gm-hint','tpl-gm-twist','tpl-gm-contingency'].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px'; el.addEventListener('input', function(){ this.style.height='auto'; this.style.height=this.scrollHeight+'px'; }, {once:false}); }
    });
    if (d.gm_plan_json?.title && document.getElementById('tpl-title')) {
      document.getElementById('tpl-title').value = d.gm_plan_json.title;
    }
    _showToast('Plan kampanii wygenerowany!', 'success');
    try {
      const vres = await apiFetch('/api/admin/forge/validate-plan', {method:'POST', body:JSON.stringify({gm_plan_json:_tplEditorPlan})});
      if (vres.issues && vres.issues.length) {
        const ec = vres.errors ? vres.errors.length : 0;
        const wc = vres.warnings ? vres.warnings.length : 0;
        const parts = [];
        if (ec) parts.push(ec + (ec===1?' błąd':' błędy'));
        if (wc) parts.push(wc + (wc===1?' ostrzeżenie':' ostrzeżenia'));
        _showToast('⚠ Plan ma ' + parts.join(', ') + ' — sprawdź przed publikacją', 'warning');
      }
    } catch(_) { /* walidacja opcjonalna */ }
  } catch(e) { _showToast(e.message || 'Błąd generowania planu.', 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = '⚡ Generuj plan AI'; } }
}

// ─── Shared Effect JSON Builder (modal) ──────────────────────────────────────
async function _ejLoadDynamicData() {
  if (_ejDataLoaded) return;
  try {
    const [cRes, sRes] = await Promise.all([
      apiFetch('/api/admin/conditions'),
      apiFetch('/api/admin/skills')
    ]);
    _ejConditions = (cRes.items || []).map(c => ({ v: c.key, l: c.label || c.key }));
    _ejSkills     = (sRes.items || []).map(s => ({ v: s.key, l: s.label || s.key }));
    _ejDataLoaded = true;
  } catch(e) { console.warn('EJ builder: failed to load conditions/skills', e); }
}

async function openEffectBuilder(currentJson, mode, title, onSave) {
  _ejMode = mode || 'weapon';
  _ejOnSave = onSave || null;
  document.getElementById('ej-builder-subtitle').textContent = title || '';
  const catRow = document.getElementById('ej-category-row');
  const catSel = document.getElementById('ej-modal-category');
  const addBtn = document.getElementById('ej-modal-add-btn');
  if (_ejMode === 'standard') {
    catRow.style.display = '';
    catSel.innerHTML = '<option value="">— brak efektu mechanicznego —</option>' +
      Object.entries(_EJ_STANDARD_CATS).map(([k,v]) => `<option value="${k}">${v.label}</option>`).join('');
    addBtn.style.display = 'none';
  } else {
    catRow.style.display = 'none';
    addBtn.style.display = 'inline-block';
  }
  await _ejLoadDynamicData();
  _ejModalPopulate(currentJson);
  document.getElementById('ej-builder-overlay').classList.add('open');
}

function closeEffectBuilder() {
  document.getElementById('ej-builder-overlay').classList.remove('open');
}

function _ejModalConfirm() {
  const data = _ejModalSerialize();
  if (_ejOnSave) _ejOnSave(data);
  closeEffectBuilder();
}

function _ejModalCatChange() {
  document.getElementById('ej-modal-effects-list').innerHTML = '';
  const cat = document.getElementById('ej-modal-category').value;
  document.getElementById('ej-modal-add-btn').style.display = cat ? 'inline-block' : 'none';
  _ejModalUpdatePreview();
}

function _ejModalGetTypes() {
  if (_ejMode === 'weapon') return _EJ_WEAPON_TYPES;
  const cat = document.getElementById('ej-modal-category')?.value;
  if (!cat || !_EJ_STANDARD_CATS[cat]) return {};
  return Object.fromEntries(
    (_EJ_STANDARD_CATS[cat].allowed_types || []).map(k => [k, _EJ_STANDARD_TYPES[k]]).filter(([,v]) => v)
  );
}

function _ejModalRenderField(f, val) {
  const v = val !== undefined && val !== null ? val : '';
  const lbl = `<span style="font-size:0.68rem;color:#888;display:block;margin-bottom:2px">${f.label}</span>`;
  const wrap = inner => `<label style="display:flex;flex-direction:column">${lbl}${inner}</label>`;
  if (f.type === 'select') {
    const opts = (f.options || []).map(o => `<option value="${o}" ${v===o?'selected':''}>${o}</option>`).join('');
    return wrap(`<select class="form-input ej-modal-field" data-field="${f.id}" style="max-width:140px" onchange="_ejModalUpdatePreview()"><option value="">—</option>${opts}</select>`);
  } else if (f.type === 'condition_select') {
    const opts = _ejConditions.map(o => `<option value="${o.v}" ${v===o.v?'selected':''}>${o.l}</option>`).join('');
    return wrap(`<select class="form-input ej-modal-field" data-field="${f.id}" style="max-width:180px" onchange="_ejModalUpdatePreview()"><option value="">— wybierz stan —</option>${opts}</select>`);
  } else if (f.type === 'skill_select') {
    const opts = _ejSkills.map(o => `<option value="${o.v}" ${v===o.v?'selected':''}>${o.l}</option>`).join('');
    return wrap(`<select class="form-input ej-modal-field" data-field="${f.id}" style="max-width:200px" onchange="_ejModalUpdatePreview()"><option value="">— wybierz umiejętność —</option>${opts}</select>`);
  } else if (f.type === 'number') {
    return wrap(`<input class="form-input ej-modal-field" data-field="${f.id}" type="number" value="${v||0}" style="max-width:80px" oninput="_ejModalUpdatePreview()">`);
  } else {
    return wrap(`<input class="form-input ej-modal-field" data-field="${f.id}" type="text" value="${_esc(String(v))}" placeholder="${f.placeholder||f.label}" style="max-width:150px" oninput="_ejModalUpdatePreview()">`);
  }
}

function _ejModalRenderEffectRow(idx, effectData) {
  const types = _ejModalGetTypes();
  const typeKeys = Object.keys(types);
  // Flatten on_fail for on_hit_save
  const flat = { ...effectData };
  if (effectData.on_fail) {
    flat._on_fail_type   = effectData.on_fail.type || 'apply_condition';
    flat.condition_key   = flat.condition_key   || effectData.on_fail.condition_key   || '';
    flat.duration_rounds = flat.duration_rounds || effectData.on_fail.duration_rounds || 2;
  }
  const selectedType = flat.type || typeKeys[0] || '';
  const typeOpts = typeKeys.map(t =>
    `<option value="${t}" ${t===selectedType?'selected':''}>${types[t]?.label||t}</option>`
  ).join('');
  const typeDef = types[selectedType] || { fields: [] };
  const fieldHtml = typeDef.fields.map(f => _ejModalRenderField(f, flat[f.id])).join('');
  return `<div class="effect-row ej-modal-row" data-idx="${idx}" style="display:flex;gap:6px;align-items:flex-end;margin-bottom:6px;flex-wrap:wrap">
    <select class="form-input effect-type-sel ej-modal-type" style="min-width:170px" onchange="_ejModalTypeChange(this,${idx})">${typeOpts}</select>
    <div class="effect-extra ej-modal-fields" style="display:flex;gap:6px;align-items:flex-end;flex-wrap:wrap">${fieldHtml}</div>
    <button type="button" class="btn-icon danger" title="Usuń efekt" onclick="_ejModalRemove(${idx})">✕</button>
  </div>`;
}

function _ejModalTypeChange(sel, idx) {
  const row = sel.closest('.ej-modal-row');
  if (!row) return;
  const types = _ejModalGetTypes();
  const typeDef = types[sel.value] || { fields: [] };
  const span = row.querySelector('.ej-modal-fields');
  if (span) span.innerHTML = typeDef.fields.map(f => _ejModalRenderField(f, '')).join('');
  _ejModalUpdatePreview();
}

function _ejModalAddEffect() {
  const list = document.getElementById('ej-modal-effects-list');
  if (!list) return;
  const types = _ejModalGetTypes();
  const firstType = Object.keys(types)[0];
  if (!firstType) return;
  const idx = list.children.length;
  const div = document.createElement('div');
  div.innerHTML = _ejModalRenderEffectRow(idx, { type: firstType });
  list.appendChild(div.firstElementChild);
  _ejModalUpdatePreview();
}

function _ejModalRemove(idx) {
  const list = document.getElementById('ej-modal-effects-list');
  if (!list) return;
  list.querySelectorAll('.ej-modal-row')[idx]?.remove();
  list.querySelectorAll('.ej-modal-row').forEach((row, i) => {
    row.dataset.idx = i;
    row.querySelector('.ej-modal-type')?.setAttribute('onchange', `_ejModalTypeChange(this,${i})`);
    row.querySelector('button[onclick^="_ejModalRemove"]')?.setAttribute('onclick', `_ejModalRemove(${i})`);
  });
  _ejModalUpdatePreview();
}

function _ejModalCollectRow(row) {
  const type = row.querySelector('.ej-modal-type')?.value;
  if (!type) return null;
  const effect = { type };
  row.querySelectorAll('.ej-modal-field').forEach(el => {
    const field = el.dataset.field;
    if (!field || field.startsWith('_')) return;
    const val = el.value;
    if (val === '' || val === null || val === undefined) return;
    effect[field] = el.type === 'number' ? (parseFloat(val) || 0) : val;
  });
  if (type === 'on_hit_save') {
    const failTypeSel = row.querySelector('[data-field="_on_fail_type"]');
    const failType = failTypeSel?.value || 'apply_condition';
    const onFail = { type: failType };
    if (failType === 'apply_condition') {
      const ck = row.querySelector('[data-field="condition_key"]')?.value;
      const dr = row.querySelector('[data-field="duration_rounds"]')?.value;
      if (ck) onFail.condition_key = ck;
      onFail.duration_rounds = parseInt(dr) || 2;
    }
    effect.on_fail = onFail;
    delete effect.condition_key;
    delete effect.duration_rounds;
  }
  return effect;
}

function _ejModalSerialize() {
  const list = document.getElementById('ej-modal-effects-list');
  if (!list) return null;
  const effects = [];
  list.querySelectorAll('.ej-modal-row').forEach(row => {
    const e = _ejModalCollectRow(row);
    if (e) effects.push(e);
  });
  if (!effects.length) return null;
  if (_ejMode === 'weapon') return { effects };
  const cat = document.getElementById('ej-modal-category')?.value;
  if (!cat) return null;
  return { schema_version: 1, effect_category: cat, effects };
}

function _ejModalPopulate(json) {
  let parsed = json;
  if (typeof parsed === 'string') { try { parsed = JSON.parse(parsed); } catch(e) { parsed = null; } }
  const list = document.getElementById('ej-modal-effects-list');
  if (!list) return;
  if (_ejMode === 'standard') {
    const catSel = document.getElementById('ej-modal-category');
    const addBtn = document.getElementById('ej-modal-add-btn');
    if (parsed?.effect_category && _EJ_STANDARD_CATS[parsed.effect_category]) {
      catSel.value = parsed.effect_category;
      addBtn.style.display = 'inline-block';
    } else {
      catSel.value = '';
      addBtn.style.display = 'none';
      list.innerHTML = '';
      _ejModalUpdatePreview();
      return;
    }
  }
  const effects = parsed?.effects || [];
  list.innerHTML = effects.map((e, i) => _ejModalRenderEffectRow(i, e)).join('');
  _ejModalUpdatePreview();
}

function _ejModalUpdatePreview() {
  const preview = document.getElementById('ej-modal-preview');
  if (!preview) return;
  const data = _ejModalSerialize();
  preview.textContent = data ? JSON.stringify(data, null, 2) : '— brak efektu —';
}

// ── Sekcja HTML (inner #section-forge) ───────────────────────────────────────
function _sectionHtml() {
  return `
    <div class="section-header">
      <div>
        <div class="section-heading">Kuźnia Kampanii</div>
        <div class="section-sub">AI-assisted adventure design → hooks → DB records → campaign templates</div>
      </div>
    </div>

    <div class="stab-bar" id="forge-tabs" style="margin-bottom:14px">
      <button class="stab active" data-forgetab="agent">⚡ Agent AI</button>
      <button class="stab" data-forgetab="hooks">⚓ Haki</button>
      <button class="stab" data-forgetab="templates">📖 Szablony</button>
      <button class="stab" data-forgetab="encounters">⚔ Spotkania</button>
    </div>

    <!-- Tab: Agent AI -->
    <div id="forge-tab-agent">

      <!-- Collapsible saved ideas shelf (above scenario editor) -->
      <div class="forge-ideas-shelf" id="forge-ideas-shelf">
        <div class="forge-ideas-shelf-header" onclick="_forgeIdeasShelfToggle()">
          <span style="font-size:0.8rem;font-weight:600;color:var(--t2)">📚 Zapisane pomysły</span>
          <span id="forge-ideas-count" style="font-size:0.72rem;color:var(--t3);margin-right:auto"></span>
          <span class="forge-ideas-shelf-toggle">▼</span>
        </div>
        <div class="forge-ideas-shelf-body">
          <div id="forge-ideas-list" class="forge-ideas-chips"></div>
        </div>
      </div>

      <!-- Full-width scenario editor -->
      <div class="forge-scenario-col" id="forge-scenario-col">

        <!-- Empty state -->
        <div id="forge-scenario-empty" class="forge-scenario-empty">
          <div style="font-size:1.8rem;margin-bottom:8px">📋</div>
          <div style="font-size:0.82rem;color:var(--t3)">Szkic pojawi się tutaj gdy Agent wygeneruje strukturę.</div>
          <div style="margin-top:12px">
            <button class="btn btn-sm btn-secondary" onclick="_forgeToggleChat()">⚡ Otwórz Agenta AI</button>
          </div>
        </div>

        <!-- Scenario panel (shown when draft exists) -->
        <div id="forge-scenario-panel" style="display:none">
          <!-- Scenario header -->
          <div class="forge-scenario-header">
            <input id="fsc-title" class="forge-scenario-title-input" placeholder="Tytuł przygody"
              oninput="_forgeMarkDirty()">
            <div style="display:flex;gap:6px;align-items:center;flex-shrink:0">
              <span id="fsc-dirty-badge" class="forge-dirty-badge" style="display:none">● niezapisane</span>
              <button class="btn btn-sm btn-secondary" onclick="_forgeToggleChat()" title="Otwórz/zamknij okno czatu">⚡ Agent</button>
              <button class="btn btn-sm btn-secondary" id="fsc-send-btn" onclick="_forgeSendEditsToAgent()"
                title="Wyślij zmiany do Agenta aby kontynuował na podstawie edycji">📤 Wyślij</button>
              <button class="btn btn-sm btn-primary" onclick="saveForgeIdea()">💾 Zapisz</button>
            </div>
          </div>

          <!-- Scenario body -->
          <div class="forge-scenario-body" id="forge-scenario-body">

            <div class="fsc-section">
              <div class="fsc-label">Premisa</div>
              <textarea id="fsc-premise" class="fsc-textarea"
                placeholder="Główna premisa przygody…" oninput="_forgeMarkDirty();_fscAutoResize(this)"></textarea>
            </div>

            <div class="fsc-section" id="fsc-meta-row" style="display:none">
              <div style="display:flex;gap:8px;flex-wrap:wrap" id="fsc-chips"></div>
            </div>

            <div class="fsc-section" id="fsc-arcs-section" style="display:none">
              <div class="fsc-label">Akty <span id="fsc-arcs-count" style="font-size:0.72rem;color:var(--t3)"></span></div>
              <div id="fsc-arcs" style="display:flex;flex-direction:column;gap:8px"></div>
            </div>

            <div class="fsc-section" id="fsc-hooks-section" style="display:none">
              <div class="fsc-label">Hooki <span id="fsc-hooks-count" style="font-size:0.72rem;color:var(--t3)"></span></div>
              <div id="fsc-hooks-list" style="display:flex;flex-wrap:wrap;gap:6px"></div>
            </div>

            <div class="fsc-section" id="fsc-player-hook-section" style="display:none">
              <div class="fsc-label">⚡ Wciągacz gracza</div>
              <textarea id="fsc-player-hook" class="fsc-textarea"
                oninput="_forgeMarkDirty();_fscAutoResize(this)"></textarea>
            </div>

            <div class="fsc-section" id="fsc-gm-section" style="display:none">
              <div class="fsc-label" style="color:var(--amber,#c9a227)">🔒 GM prywatne</div>
              <textarea id="fsc-gm-private" class="fsc-textarea fsc-textarea--amber"
                oninput="_forgeMarkDirty();_fscAutoResize(this)"></textarea>
            </div>

            <div id="fsc-actions" style="display:none;gap:6px;padding-top:12px;border-top:1px solid var(--border);flex-wrap:wrap"></div>

          </div>
        </div>
      </div>

      <!-- hidden forge-draft-card kept for compat -->
      <div id="forge-draft-card" style="display:none"><div id="forge-draft-preview"></div></div>

    </div>

    <!-- Floating draggable Agent chat (rendered outside tab, fixed to viewport) -->
    <div class="forge-float-chat ffc-hidden" id="forge-float-chat">
      <div class="forge-float-drag-handle" id="forge-float-drag-handle">
        <div class="forge-float-drag-dots"><span></span><span></span><span></span></div>
        <span style="font-size:0.82rem;font-weight:600;color:var(--t1);flex:1">⚡ Agent AI</span>
        <span style="font-size:0.7rem;color:var(--t3)">Ctrl+Enter = wyślij</span>
        <button class="btn btn-ghost btn-sm" onclick="_forgeNewSession()" style="padding:2px 6px">↺</button>
        <button onclick="_forgeToggleChat()" style="background:none;border:none;color:var(--t3);cursor:pointer;font-size:1rem;padding:0 2px;line-height:1">✕</button>
      </div>
      <div id="forge-chat-history" class="forge-chat-history" style="flex:1;min-height:0">
        <div class="forge-bubble forge-bubble--hint">
          Opisz swój pomysł na przygodę — Agent dopyta i zbuduje strukturę.<br>
          <span style="font-size:0.74rem;opacity:0.65">Ctrl+Enter wysyła · Enter = nowa linia</span>
        </div>
      </div>
      <div class="forge-input-row" style="flex-shrink:0">
        <textarea class="form-input forge-textarea" id="forge-input" rows="3"
          placeholder="Napisz do agenta…"
          onkeydown="_forgeInputKey(event)"></textarea>
        <button class="btn btn-primary forge-send-btn" id="forge-send-btn" onclick="sendForgeMsg()">➤</button>
      </div>
    </div>

    <!-- Tab: Spotkania -->
    <div id="forge-tab-encounters" style="display:none">
      <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
        <span style="font-size:0.82rem;color:var(--t3)">Spotkania wygenerowane z haków. Kliknij kartę, aby edytować. Przycisk ⚡ wstrzykuje spotkanie do aktywnej kampanii.</span>
        <button class="btn btn-sm btn-secondary" onclick="_loadForgeEncounters()" style="margin-left:auto">↺ Odśwież</button>
      </div>
      <div id="forge-encounters-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px"></div>
    </div>

    <!-- Encounter edit modal -->
    <div id="encounter-modal" class="modal-overlay" onclick="if(event.target===this)this.classList.remove('open')">
      <div class="modal" style="max-width:860px">
        <div class="modal-header">
          <div>
            <div class="modal-title" id="em-hook-title">Spotkanie</div>
            <div class="modal-subtitle" id="em-hook-badge"></div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="document.getElementById('encounter-modal').classList.remove('open')">✕</button>
        </div>
        <div class="modal-body forge-encounter-modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <!-- Left column: form fields -->
          <div style="display:flex;flex-direction:column;gap:10px">
            <div class="form-row">
              <label class="form-label">Tytuł spotkania</label>
              <input id="em-title" class="form-input" type="text" oninput="_previewEncounterFromForm()">
            </div>
            <div class="form-row">
              <label class="form-label">Wyzwalacz</label>
              <input id="em-trigger" class="form-input" type="text" oninput="_previewEncounterFromForm()">
            </div>
            <div class="form-row">
              <label class="form-label">Opis sceny</label>
              <textarea id="em-scene" class="form-input" rows="1" style="resize:none;overflow:hidden" oninput="_fscAutoResize(this);_previewEncounterFromForm()"></textarea>
            </div>
            <div class="form-row">
              <label class="form-label">Wrogowie <span style="font-size:0.7rem;color:var(--t3)">(Nazwa ×N — notatka, jeden na linię)</span></label>
              <textarea id="em-enemies" class="form-input" rows="1" style="resize:none;overflow:hidden;font-family:monospace;font-size:0.82rem" oninput="_fscAutoResize(this);_previewEncounterFromForm()"></textarea>
            </div>
            <div class="form-row">
              <label class="form-label">Cele <span style="font-size:0.7rem;color:var(--t3)">(jeden na linię)</span></label>
              <textarea id="em-objectives" class="form-input" rows="1" style="resize:none;overflow:hidden" oninput="_fscAutoResize(this);_previewEncounterFromForm()"></textarea>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div class="form-row">
                <label class="form-label">XP szacunkowe</label>
                <input id="em-xp" class="form-input" type="number" oninput="_previewEncounterFromForm()">
              </div>
              <div class="form-row">
                <label class="form-label">Notatka o łupach</label>
                <input id="em-loot" class="form-input" oninput="_previewEncounterFromForm()">
              </div>
            </div>
            <div class="form-row">
              <label class="form-label">Uwagi GM</label>
              <textarea id="em-gm-notes" class="form-input" rows="1" style="resize:none;overflow:hidden" oninput="_fscAutoResize(this);_previewEncounterFromForm()"></textarea>
            </div>
          </div>
          <!-- Right column: live preview + collapsed trigger config -->
          <div style="display:flex;flex-direction:column;gap:12px">
            <div style="font-size:0.72rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.06em">Podgląd</div>
            <div id="em-preview" style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:12px;flex:1;overflow-y:auto;max-height:280px;min-height:100px">
              <div style="color:var(--t3);font-size:0.8rem;text-align:center;padding:20px">Wypełnij pola aby zobaczyć podgląd.</div>
            </div>
            <details style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px 12px">
              <summary style="font-size:0.75rem;font-weight:700;color:var(--t3);cursor:pointer;user-select:none;letter-spacing:.05em;text-transform:uppercase;list-style:none">⚙ Automatyczne wyzwalanie ▾</summary>
              <div style="margin-top:10px;display:flex;flex-direction:column;gap:8px">
                <div style="font-size:0.75rem;color:var(--t3);font-weight:600">Typy wyzwalaczy</div>
                <label style="display:flex;align-items:center;gap:8px;font-size:0.82rem;cursor:pointer">
                  <input type="checkbox" id="em-trig-hex" value="hex_enter">
                  <span>hex_enter <span style="color:var(--t3)">— wejście na hex</span></span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;font-size:0.82rem;cursor:pointer">
                  <input type="checkbox" id="em-trig-nturns" value="n_turns" onchange="document.getElementById('em-nturns-row').style.display=this.checked?'flex':'none'">
                  <span>n_turns <span style="color:var(--t3)">— co N spokojnych tur</span></span>
                </label>
                <div id="em-nturns-row" style="display:none;align-items:center;gap:6px;padding-left:20px">
                  <span style="font-size:0.75rem;color:var(--t3)">Co</span>
                  <input id="em-nturns-interval" type="number" min="1" max="20" value="5" class="form-input" style="width:64px;padding:3px 8px">
                  <span style="font-size:0.75rem;color:var(--t3)">tur</span>
                </div>
                <label style="display:flex;align-items:center;gap:8px;font-size:0.82rem;cursor:pointer">
                  <input type="checkbox" id="em-trig-combat" value="combat_end">
                  <span>combat_end <span style="color:var(--t3)">— po walce</span></span>
                </label>
                <div class="form-row" style="margin-top:4px">
                  <label class="form-label">Prawdopodobieństwo</label>
                  <div style="display:flex;align-items:center;gap:10px">
                    <input id="em-probability" type="range" min="0" max="1" step="0.05" value="0.25" style="flex:1" oninput="document.getElementById('em-prob-val').textContent=Math.round(this.value*100)+'%'">
                    <span id="em-prob-val" style="font-size:0.85rem;font-weight:700;color:var(--t1);min-width:36px">25%</span>
                  </div>
                </div>
                <div class="form-row">
                  <label class="form-label">Biomy <span style="font-size:0.7rem;color:var(--t3)">(plains,forest,dungeon…)</span></label>
                  <input id="em-biomes" class="form-input" placeholder="np. forest,plains">
                </div>
                <div class="form-row">
                  <label class="form-label">Tagi <span style="font-size:0.7rem;color:var(--t3)">(przecinek)</span></label>
                  <input id="em-tags" class="form-input" placeholder="np. undead,hostile">
                </div>
              </div>
            </details>
          </div>
        </div>
        <div class="modal-footer" style="justify-content:space-between">
          <button class="btn btn-sm btn-secondary" onclick="document.getElementById('encounter-modal').classList.remove('open')">Anuluj</button>
          <div style="display:flex;gap:8px;align-items:center">
            <select id="em-campaign-picker" class="form-input" style="font-size:0.8rem;padding:4px 10px;min-width:160px"></select>
            <button class="btn btn-sm btn-secondary" id="em-inject-btn" onclick="_injectEncounterFromModal()">⚡ Wstrzyknij</button>
            <button class="btn btn-sm btn-primary" onclick="_saveEncounterEdits()">💾 Zapisz zmiany</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab: Haki -->
    <div id="forge-tab-hooks" style="display:none">
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
        <div class="stab-bar" id="forge-hooks-status-bar">
          <button class="stab active" data-hookstatus="">Wszystkie</button>
          <button class="stab" data-hookstatus="pending">Oczekujące</button>
          <button class="stab" data-hookstatus="approved">Zatwierdzone</button>
          <button class="stab" data-hookstatus="promoted">Promowane</button>
        </div>
        <div class="filter-group" id="forge-hooks-type-filter" style="margin-left:auto">
          <button class="chip on" data-hooktype="">Wszystkie typy</button>
          <button class="chip" data-hooktype="weapon">⚔ Broń</button>
          <button class="chip" data-hooktype="enemy">💀 Wróg</button>
          <button class="chip" data-hooktype="npc">👤 NPC</button>
          <button class="chip" data-hooktype="location">🗺 Lokacja</button>
          <button class="chip" data-hooktype="item">🎒 Przedmiot</button>
        </div>
      </div>
      <div id="forge-hooks-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px"></div>
    </div>

    <!-- Tab: Szablony -->
    <div id="forge-tab-templates" style="display:none">
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <button class="btn btn-primary btn-sm" onclick="openCreateTemplate()">+ Nowy szablon</button>
        <span id="forge-templates-count" style="font-size:0.8rem;color:var(--t3);align-self:center"></span>
      </div>
      <div id="forge-templates-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px"></div>

      <!-- Template Full Editor (hidden by default, shown when editing a template) -->
      <div id="forge-template-editor" style="display:none">
        <div class="forge-tpl-header" style="display:flex;align-items:center;gap:12px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--border)">
          <button class="btn btn-sm btn-secondary" onclick="_closeTemplateEditor()">← Szablony</button>
          <input id="tpl-title" class="form-input" style="font-weight:600;font-size:0.95rem;max-width:320px" placeholder="Tytuł szablonu">
          <span id="tpl-status-badge" style="font-size:0.72rem;font-weight:600;padding:3px 8px;border-radius:var(--r);background:var(--surface);border:1px solid var(--border)"></span>
          <div class="forge-tpl-header-btns" style="margin-left:auto;display:flex;gap:6px" id="tpl-workflow-btns">
            <!-- E12 (#427) — workflow buttons injected by _renderTplWorkflow(status) -->
            <button class="btn btn-sm btn-secondary" id="tpl-publish-btn" onclick="_toggleTemplatePublish()"></button>
            <button class="btn btn-sm btn-secondary" id="tpl-revert-btn" style="display:none" onclick="_revertTemplate()"></button>
            <button class="btn btn-sm btn-primary" onclick="forgeGeneratePlan()" id="tpl-generate-btn">⚡ Generuj plan AI</button>
            <button class="btn btn-sm btn-primary" onclick="saveTemplateEdits()">💾 Zapisz</button>
          </div>
        </div>

        <div class="stab-bar" id="tpl-editor-tabs" style="margin-bottom:14px">
          <button class="stab active" data-tpltab="overview">Przegląd</button>
          <button class="stab" data-tpltab="acts">Akty</button>
          <button class="stab" data-tpltab="characters">Postaci &amp; Lokacje</button>
          <button class="stab" data-tpltab="endings">Zakończenia</button>
          <button class="stab" data-tpltab="items">🎒 Przedmioty</button>
        </div>

        <!-- Tab: Przegląd -->
        <div id="tpl-tab-overview">
          <div class="card" style="padding:16px;margin-bottom:12px">
            <div class="form-row">
              <label class="form-label">Opis</label>
              <textarea id="tpl-description" class="form-input" rows="3" style="resize:vertical"></textarea>
              <button class="btn btn-sm btn-secondary" onclick="forgeGenerateTplDescription(event)" style="margin-top:6px">🤖 Generuj opis</button>
            </div>
            <div class="forge-grid-2col" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px">
              <div class="form-row"><label class="form-label">Klimat / atmosfera</label><input id="tpl-atmosphere" class="form-input" type="text" placeholder="np. mroczna, tajemnicza"></div>
              <div class="form-row"><label class="form-label">Trudność (1-5)</label>
                <div id="tpl-difficulty-stars" style="display:flex;gap:4px;padding:4px 0"></div>
              </div>
            </div>
            <!-- E7 (#422) — required NPCs/beats + player visibility -->
            <div class="forge-grid-2col" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px">
              <div class="form-row"><label class="form-label">Wymagani NPC (klucze, po przecinku)</label><input id="tpl-required-npcs" class="form-input" type="text" placeholder="np. npc_alik, npc_strażnik"></div>
              <div class="form-row"><label class="form-label">Wymagane beaty (klucze, po przecinku)</label><input id="tpl-required-beats" class="form-input" type="text" placeholder="np. beat_intro, beat_finał"></div>
            </div>
            <div class="form-row" style="margin-top:10px">
              <label class="form-label" style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input id="tpl-player-visible" type="checkbox" checked style="width:auto">
                Widoczny dla graczy (w ekranie wyboru gotowej kampanii)
              </label>
            </div>
          </div>
          <div class="card" style="padding:16px">
            <div class="card-header" style="padding:0 0 10px;margin-bottom:10px;border-bottom:1px solid var(--border)">
              <span class="card-title">Powiązane haki</span>
              <button class="btn btn-sm btn-secondary" onclick="_openHookLinkPicker()">+ Dodaj hak</button>
            </div>
            <div id="tpl-hooks-list" style="display:flex;flex-wrap:wrap;gap:6px;min-height:32px">
              <span style="font-size:0.78rem;color:var(--t3)">Brak powiązanych haków.</span>
            </div>
          </div>
        </div>

        <!-- Tab: Akty -->
        <div id="tpl-tab-acts" style="display:none">
          <div id="tpl-acts-list" style="display:flex;flex-direction:column;gap:12px"></div>
        </div>

        <!-- Tab: Postaci & Lokacje -->
        <div id="tpl-tab-characters" style="display:none">
          <div class="forge-grid-3col" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px">
            <div class="card" style="padding:14px">
              <div style="font-size:0.83rem;font-weight:600;color:var(--t1);margin-bottom:10px">Kluczowe Postaci NPC</div>
              <div id="tpl-npcs-list" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn btn-sm btn-secondary" style="margin-top:8px;width:100%" onclick="_addTplNPC()">+ Dodaj NPC</button>
            </div>
            <div class="card" style="padding:14px">
              <div style="font-size:0.83rem;font-weight:600;color:var(--t1);margin-bottom:10px">Kluczowe Wrogowie</div>
              <div id="tpl-enemies-list" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn btn-sm btn-secondary" style="margin-top:8px;width:100%" onclick="_addTplEnemy()">+ Dodaj wroga</button>
            </div>
            <div class="card" style="padding:14px">
              <div style="font-size:0.83rem;font-weight:600;color:var(--t1);margin-bottom:10px">Kluczowe Lokacje</div>
              <div id="tpl-locations-list" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn btn-sm btn-secondary" style="margin-top:8px;width:100%" onclick="_addTplLocation()">+ Dodaj lokację</button>
            </div>
          </div>
        </div>

        <!-- Tab: Zakończenia -->
        <div id="tpl-tab-endings" style="display:none">
          <div class="forge-grid-2col" style="display:grid;grid-template-columns:1fr 1fr;gap:14px" id="tpl-endings-list"></div>
        </div>

        <!-- Tab: Przedmioty -->
        <div id="tpl-tab-items" style="display:none">
          <div class="forge-grid-2col" style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
            <div class="card" style="padding:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <div style="font-size:0.83rem;font-weight:600;color:var(--t1)">Broń kampanii</div>
                <button class="btn btn-sm btn-secondary" onclick="forgeGeneratePlanItem('weapon', event)">🤖 Generuj AI</button>
              </div>
              <div id="tpl-items-weapon-list" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn btn-sm btn-secondary" style="margin-top:8px;width:100%" onclick="_addTplItem('weapon')">+ Dodaj broń</button>
            </div>
            <div class="card" style="padding:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <div style="font-size:0.83rem;font-weight:600;color:var(--t1)">Przedmioty (zbroja, ekwipunek)</div>
                <button class="btn btn-sm btn-secondary" onclick="forgeGeneratePlanItem('item', event)">🤖 Generuj AI</button>
              </div>
              <div id="tpl-items-item-list" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn btn-sm btn-secondary" style="margin-top:8px;width:100%" onclick="_addTplItem('item')">+ Dodaj przedmiot</button>
            </div>
            <div class="card" style="padding:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <div style="font-size:0.83rem;font-weight:600;color:var(--t1)">Mikstury i konsumable</div>
                <button class="btn btn-sm btn-secondary" onclick="forgeGeneratePlanItem('consumable', event)">🤖 Generuj AI</button>
              </div>
              <div id="tpl-items-consumable-list" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn btn-sm btn-secondary" style="margin-top:8px;width:100%" onclick="_addTplItem('consumable')">+ Dodaj miksturę</button>
            </div>
            <div class="card" style="padding:14px">
              <div style="font-size:0.83rem;font-weight:600;color:var(--t1);margin-bottom:4px">Jak to działa?</div>
              <div style="font-size:0.78rem;color:var(--t3);line-height:1.5">
                Przedmioty oznaczone <strong>campaign_specific</strong> nadpisują globalne rekordy DB dla tej kampanii.<br><br>
                Przedmioty ze znacznikiem <strong>hidden</strong> są ukryte — pojawią się tylko gdy GM je odkryje lub LLM je umieści w scenie.<br><br>
                <strong>location_hint</strong> podpowiada AI gdzie ukryć przedmiot (np. "w zbrojowni").
              </div>
            </div>
          </div>

        </div>

        <!-- GM Private (always visible, collapsible) -->
        <details style="margin-top:16px;border:1px solid var(--amber-border);border-radius:var(--r);overflow:hidden">
          <summary style="padding:10px 14px;background:var(--amber-light);cursor:pointer;font-size:0.8rem;font-weight:600;color:var(--amber)">🔒 GM Private (sekrety kampanii)</summary>
          <div style="padding:14px;display:flex;flex-direction:column;gap:10px">
            <div class="form-row"><label class="form-label">Sekretna predyspozycja</label><textarea id="tpl-gm-hint" class="form-input" rows="4" style="resize:vertical" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea></div>
            <div class="form-row"><label class="form-label">Ukryty twist</label><textarea id="tpl-gm-twist" class="form-input" rows="4" style="resize:vertical" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea></div>
            <div class="form-row"><label class="form-label">Plan awaryjny</label><textarea id="tpl-gm-contingency" class="form-input" rows="4" style="resize:vertical" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea></div>
          </div>
        </details>
      </div>

    </div>`;
}

// ── 5 modali (wstrzykiwane do body) ──────────────────────────────────────────
function _modalsHtml() {
  return `
  <!-- ── Effect JSON Builder Overlay (ej-modal) ── -->
  <div class="modal-overlay" id="ej-builder-overlay" style="z-index:2000" onclick="if(event.target===this)closeEffectBuilder()">
    <div class="modal" style="max-width:700px;width:95vw">
      <div class="modal-header">
        <div>
          <div class="modal-title">Edytor efektów mechanicznych</div>
          <div class="modal-subtitle" id="ej-builder-subtitle" style="font-size:0.78rem;color:#888"></div>
        </div>
        <button class="btn-icon" onclick="closeEffectBuilder()">✕</button>
      </div>
      <div class="modal-body" style="max-height:68vh;overflow-y:auto">
        <div id="ej-category-row" style="margin-bottom:12px">
          <label class="form-label" style="display:block;margin-bottom:4px">Kategoria efektu</label>
          <select id="ej-modal-category" class="form-input" style="max-width:300px" onchange="_ejModalCatChange()">
            <option value="">— brak efektu mechanicznego —</option>
          </select>
        </div>
        <div id="ej-modal-effects-list" style="display:flex;flex-direction:column;gap:6px;margin-bottom:10px"></div>
        <button type="button" id="ej-modal-add-btn" style="background:#2d5a1b;color:#fff;border:none;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:0.85rem;margin-bottom:14px;display:none" onclick="_ejModalAddEffect()">+ Dodaj efekt</button>
        <div style="background:#0d0d0d;border:1px solid #222;border-radius:4px;padding:10px">
          <div style="font-size:0.68rem;color:#555;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em">Podgląd JSON</div>
          <pre id="ej-modal-preview" style="margin:0;font-size:0.72rem;color:#8bc34a;word-break:break-all;white-space:pre-wrap;font-family:monospace">— brak efektu —</pre>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeEffectBuilder()">Anuluj</button>
        <button class="btn btn-primary" onclick="_ejModalConfirm()">Zatwierdź efekt</button>
      </div>
    </div>
  </div>

  <!-- Template Entity Edit Modal -->
  <div id="tpl-entity-modal" style="display:none;position:fixed;inset:0;z-index:1100;background:rgba(0,0,0,.55);align-items:center;justify-content:center" onclick="if(event.target===this)closeTplEntityModal()">
    <div style="background:var(--canvas);border:1px solid var(--border);border-radius:var(--r2);width:min(720px,95vw);max-height:90vh;overflow-y:auto;box-shadow:var(--shadow-lg)">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)">
        <div>
          <span id="tpl-entity-modal-type-badge" style="font-size:0.7rem;font-weight:600;padding:2px 8px;border-radius:var(--r);background:var(--surface);border:1px solid var(--border);margin-right:8px"></span>
          <span id="tpl-entity-modal-title" style="font-weight:600;font-size:0.95rem"></span>
        </div>
        <button onclick="closeTplEntityModal()" style="background:none;border:none;cursor:pointer;font-size:1.1rem;color:var(--t3);padding:4px 8px">✕</button>
      </div>
      <div style="padding:16px 20px">
        <label style="display:flex;align-items:center;gap:8px;margin-bottom:14px;padding:8px 12px;background:var(--amber-light);border:1px solid var(--amber-border);border-radius:var(--r);cursor:pointer;font-size:0.82rem;font-weight:500">
          <input type="checkbox" id="tpl-entity-campaign-specific" style="width:15px;height:15px">
          <span>Specyficzne dla kampanii — nadpisuje globalny rekord w DB</span>
        </label>
        <div id="tpl-entity-form"></div>
        <!-- #1085 — swap enemy with one from global pool -->
        <div id="tpl-enemy-swap-section" style="display:none;margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
          <div style="font-size:0.8rem;font-weight:600;color:var(--t2);margin-bottom:8px">Zamień na wroga z puli globalnej</div>
          <div style="display:flex;gap:8px;align-items:center">
            <select id="tpl-enemy-pool-select" class="form-input" style="flex:1;font-size:0.82rem">
              <option value="">— kliknij Wczytaj puli —</option>
            </select>
            <button class="btn btn-sm btn-secondary" onclick="_loadEnemyPoolIntoSelect()">Wczytaj pulę</button>
            <button class="btn btn-sm btn-primary" onclick="_swapTplEnemyFromPool()">Zamień</button>
          </div>
        </div>
      </div>
      <div style="padding:12px 20px;border-top:1px solid var(--border);display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-sm btn-secondary" onclick="closeTplEntityModal()">Anuluj</button>
        <button class="btn btn-sm btn-danger" id="tpl-entity-delete-btn" onclick="_deleteTplEntity()">🗑 Usuń</button>
        <button class="btn btn-sm btn-primary" onclick="saveTplEntityEdits()">💾 Zapisz</button>
      </div>
    </div>
  </div>

  <!-- Forge Generate Plan Dialog -->
  <div id="forge-plan-dialog" style="display:none;position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.55);align-items:center;justify-content:center" onclick="if(event.target===this)document.getElementById('forge-plan-dialog').style.display='none'">
    <div class="card" style="width:420px;padding:24px;display:flex;flex-direction:column;gap:14px;background:var(--canvas);border:1px solid var(--border);border-radius:var(--r2);box-shadow:var(--shadow-lg)">
      <div id="fpd-heading" style="font-weight:700;font-size:1rem">Generuj Plan GM</div>
      <!-- title row — shown only when creating template from idea -->
      <div class="form-row" id="fpd-title-row" style="display:none">
        <label class="form-label">Tytuł szablonu *</label>
        <input id="fpd-title" class="form-input" type="text" placeholder="np. Zamek Drachenfels">
      </div>
      <div class="form-row">
        <label class="form-label">Poziom trudności</label>
        <select id="fpd-difficulty" class="form-input">
          <option value="easy">Łatwa</option>
          <option value="medium" selected>Średnia</option>
          <option value="hard">Trudna</option>
          <option value="epic">Epik</option>
        </select>
      </div>
      <div class="form-row">
        <label class="form-label">Liczba aktów</label>
        <select id="fpd-acts" class="form-input">
          <option value="3">3 akty (krótka)</option>
          <option value="4">4 akty</option>
          <option value="5" selected>5 aktów (średnia)</option>
          <option value="6">6 aktów</option>
          <option value="7">7 aktów (długa)</option>
          <option value="8">8 aktów</option>
          <option value="9">9 aktów (epik)</option>
        </select>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-ghost" onclick="document.getElementById('forge-plan-dialog').style.display='none'">Anuluj</button>
        <button class="btn btn-primary" id="fpd-confirm-btn" onclick="forgeGeneratePlanConfirm()">Generuj</button>
      </div>
    </div>
  </div>

  <!-- Sublocation Edit Dialog -->
  <div id="subloc-edit-dialog" style="display:none;position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.55);align-items:center;justify-content:center" onclick="if(event.target===this)document.getElementById('subloc-edit-dialog').style.display='none'">
    <div style="background:var(--canvas);border:1px solid var(--border);border-radius:var(--r2);width:min(460px,95vw);padding:24px;display:flex;flex-direction:column;gap:14px;box-shadow:var(--shadow-lg)">
      <div style="font-weight:700;font-size:1rem">Edytuj sublokację</div>
      <div class="form-row">
        <label class="form-label">Klucz (slug)</label>
        <input id="sled-key" class="form-input" type="text" placeholder="np. krypta_north">
      </div>
      <div class="form-row">
        <label class="form-label">Nazwa</label>
        <input id="sled-name" class="form-input" type="text" placeholder="np. Północna krypta">
      </div>
      <div class="form-row" style="grid-column:1/-1">
        <label class="form-label">Opis</label>
        <textarea id="sled-description" class="form-input" rows="3" style="resize:vertical" placeholder="Opis sublokacji…"></textarea>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-ghost" onclick="document.getElementById('subloc-edit-dialog').style.display='none'">Anuluj</button>
        <button class="btn btn-primary" onclick="saveSublocEdit()">Zapisz</button>
      </div>
    </div>
  </div>

  <!-- Hook Detail Modal -->
  <div class="modal-overlay" id="hook-modal" onclick="if(event.target===this)this.classList.remove('open')">
    <div class="modal" style="max-width:780px">
      <div class="modal-header">
        <div>
          <div class="modal-title" id="hook-modal-title">Hak</div>
          <div class="modal-subtitle" id="hook-modal-type"></div>
        </div>
        <button class="btn btn-sm btn-secondary" onclick="document.getElementById('hook-modal').classList.remove('open')">✕</button>
      </div>
      <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div class="form-row">
            <label class="form-label">Tytuł</label>
            <input id="hm-title" class="form-input" type="text">
          </div>
          <div class="form-row">
            <label class="form-label">Opis</label>
            <textarea id="hm-description" class="form-input" rows="5" style="resize:vertical"></textarea>
          </div>
          <div style="display:flex;gap:8px;margin-top:4px">
            <span id="hm-status-badge" style="font-size:0.72rem;font-weight:600;padding:2px 8px;border-radius:var(--r);background:var(--surface)"></span>
            <span id="hm-significance-badge" style="font-size:0.72rem;color:var(--t3)"></span>
            <span id="hm-rating" style="font-size:0.72rem;color:var(--t3);margin-left:auto"></span>
          </div>
        </div>
        <div id="hm-draft-form"></div>
        <div id="hm-encounter-panel" style="display:none;margin-top:12px;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)"></div>
      </div>
      <div class="modal-footer" style="justify-content:space-between">
        <div style="display:flex;gap:6px" id="hm-actions"></div>
        <button class="btn btn-primary btn-sm" onclick="saveHookEdits()">💾 Zapisz</button>
      </div>
    </div>
  </div>`;
}

// ── Init ─────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = _sectionHtml();

  // Inject the 5 modals into body once (inline onclick handlers reference them by id)
  if (!document.getElementById('forge-modals-host')) {
    const host = document.createElement('div');
    host.id = 'forge-modals-host';
    host.innerHTML = _modalsHtml();
    document.body.appendChild(host);
  }

  // Expose apiFetch + section invalidation helpers (referenced inside inline onclick strings)
  window.apiFetch = window.apiFetch || apiFetch;
  window._sectionLoaded = _sectionLoaded;
  window._loadForge = _loadForge;
  window._loadForgeTemplates = _loadForgeTemplates;
  window._loadForgeEncounters = _loadForgeEncounters;
  window._loadForgeHooks = _loadForgeHooks;

  // ── Expose EVERY inline-handler function on window (original names) ──
  // Agent AI / pomysły
  window.forgeOpenIdea = forgeOpenIdea;
  window.forgeReloadIdeaInChat = forgeReloadIdeaInChat;
  window.forgeExtractHooks = forgeExtractHooks;
  window.forgeCreateTemplateFromIdea = forgeCreateTemplateFromIdea;
  window._forgeIdeasShelfToggle = _forgeIdeasShelfToggle;
  window._forgeToggleChat = _forgeToggleChat;
  window._forgeNewSession = _forgeNewSession;
  window._forgeMarkDirty = _forgeMarkDirty;
  window._fscAutoResize = _fscAutoResize;
  window._forgeSendEditsToAgent = _forgeSendEditsToAgent;
  window._forgeInputKey = _forgeInputKey;
  window.sendForgeMsg = sendForgeMsg;
  window.saveForgeIdea = saveForgeIdea;
  // Spotkania
  window.openEncounterModal = openEncounterModal;
  window._previewEncounterFromForm = _previewEncounterFromForm;
  window._injectEncounterFromModal = _injectEncounterFromModal;
  window._saveEncounterEdits = _saveEncounterEdits;
  // Haki
  window.openHookModal = openHookModal;
  window.forgeApproveHook = forgeApproveHook;
  window.forgeRejectHook = forgeRejectHook;
  window.forgePromoteHook = forgePromoteHook;
  window.forgeGenerateEncounter = forgeGenerateEncounter;
  window.saveHookEdits = saveHookEdits;
  // Szablony
  window.openTemplateEditor = openTemplateEditor;
  window.openCreateTemplate = openCreateTemplate;
  window._closeTemplateEditor = _closeTemplateEditor;
  window.forgeSetTemplateStatus = forgeSetTemplateStatus;
  window.forgePublishTemplate = forgePublishTemplate;
  window.forgeUnpublishTemplate = forgeUnpublishTemplate;
  window.forgeAllocateHex = forgeAllocateHex;
  window.forgeLaunchCampaignFromTemplate = forgeLaunchCampaignFromTemplate;
  window.forgeGenerateTplDescription = forgeGenerateTplDescription;
  window._toggleTemplatePublish = _toggleTemplatePublish;
  window._revertTemplate = _revertTemplate;
  window.forgeGeneratePlan = forgeGeneratePlan;
  window.saveTemplateEdits = saveTemplateEdits;
  window._setTplDifficulty = _setTplDifficulty;
  window._removeTplHook = _removeTplHook;
  window._openHookLinkPicker = _openHookLinkPicker;
  window._addTplBeat = _addTplBeat;
  window._removeTplBeat = _removeTplBeat;
  window._toggleTplBeatOptional = _toggleTplBeatOptional;  // #1014
  window._addTplNPC = _addTplNPC;
  window._addTplEnemy = _addTplEnemy;
  window._addTplLocation = _addTplLocation;
  window.openGenerateSublocations = openGenerateSublocations;
  window.openSublocEdit = openSublocEdit;
  window.saveSublocEdit = saveSublocEdit;
  window._addTplItem = _addTplItem;
  window.forgeGeneratePlanItem = forgeGeneratePlanItem;
  window._promoteTplDbItem = _promoteTplDbItem;
  window.openTplEntityModal = openTplEntityModal;
  window.closeTplEntityModal = closeTplEntityModal;
  window._deleteTplEntity = _deleteTplEntity;
  window.saveTplEntityEdits = saveTplEntityEdits;
  window._loadEnemyPoolIntoSelect = _loadEnemyPoolIntoSelect;
  window._swapTplEnemyFromPool = _swapTplEnemyFromPool;
  window._addTplReq = _addTplReq;
  window._removeTplReq = _removeTplReq;
  window.forgeGeneratePlanConfirm = forgeGeneratePlanConfirm;
  // openSmartEntryForDbItem (DB item cards) — fallback if not provided by another section
  if (typeof window.openSmartEntryForDbItem !== 'function') window.openSmartEntryForDbItem = openSmartEntryForDbItem;
  // Inline effect-builder (_ej*)
  window._forgeEjOpen = _forgeEjOpen;
  window._ejCategoryChange = _ejCategoryChange;
  window._ejTypeChange = _ejTypeChange;
  window._ejAddEffect = _ejAddEffect;
  window._ejRemoveEffect = _ejRemoveEffect;
  window._ejUpdatePreview = _ejUpdatePreview;
  // Shared modal effect-builder
  window.openEffectBuilder = openEffectBuilder;
  window.closeEffectBuilder = closeEffectBuilder;
  window._ejModalConfirm = _ejModalConfirm;
  window._ejModalCatChange = _ejModalCatChange;
  window._ejModalAddEffect = _ejModalAddEffect;
  window._ejModalRemove = _ejModalRemove;
  window._ejModalTypeChange = _ejModalTypeChange;
  window._ejModalUpdatePreview = _ejModalUpdatePreview;

  // Wire draggable float chat (handle exists now)
  _forgeDragInit();

  await _loadForge();
}
