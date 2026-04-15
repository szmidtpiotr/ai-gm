window.state = window.state || {};
window.state.characterSheet = window.state.characterSheet || null;
window.state.sheetPanelOpen = window.state.sheetPanelOpen ?? false;
window.API_BASE_URL = window.API_BASE_URL || "/api";
window.SHEET_PANEL_STORAGE_KEY = "ai-gm:sheetPanelOpen";

window.SHEET_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];
window.SHEET_SKILLS = [
  "Athletics",
  "Swordsmanship",
  "Archery",
  "Stealth",
  "Survival",
  "Persuasion",
  "Insight",
  "Arcana",
  "Alchemy",
  "Lore"
];

window.ROLL_VALID_TESTS = new Set([
  "athletics", "stealth", "awareness", "survival", "lore", "investigation",
  "arcana", "medicine", "persuasion", "intimidation",
  "melee_attack", "ranged_attack", "spell_attack",
  "fortitude_save", "reflex_save", "willpower_save", "arcane_save"
]);

window.ROLL_TEST_ALIASES = {
  "Str Save": "fortitude_save",
  "Con Save": "fortitude_save",
  "Dex Save": "reflex_save",
  "Wis Save": "willpower_save",
  "Int Save": "arcane_save",
  "Cha Save": "willpower_save",
  "Athletics": "athletics",
  "Stealth": "stealth",
  "Awareness": "awareness",
  "Perception": "awareness",
  "Survival": "survival",
  "Lore": "lore",
  "Investigation": "investigation",
  "Arcana": "arcana",
  "Medicine": "medicine",
  "Persuasion": "persuasion",
  "Intimidation": "intimidation",
  "Attack": "melee_attack",
  "Melee Attack": "melee_attack",
  "Ranged Attack": "ranged_attack",
  "Spell Attack": "spell_attack",
  "Initiative": "reflex_save"
};

window.resolveRollTestName = function (raw) {
  const source = String(raw || "").trim();
  if (!source) return null;
  const titleKey = source
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
  if (window.ROLL_TEST_ALIASES[titleKey]) {
    return window.ROLL_TEST_ALIASES[titleKey];
  }
  const normalized = source.toLowerCase().replace(/-/g, "_").replace(/\s+/g, "_");
  return window.ROLL_VALID_TESTS.has(normalized) ? normalized : null;
};

window.formatRollTestDisplayName = function (canonicalName) {
  const normalized = String(canonicalName || "").trim().toLowerCase();
  const labels = {
    athletics: "Athletics",
    stealth: "Stealth",
    awareness: "Awareness",
    survival: "Survival",
    lore: "Lore",
    investigation: "Investigation",
    arcana: "Arcana",
    medicine: "Medicine",
    persuasion: "Persuasion",
    intimidation: "Intimidation",
    melee_attack: "Melee Attack",
    ranged_attack: "Ranged Attack",
    spell_attack: "Spell Attack",
    fortitude_save: "Fortitude Save",
    reflex_save: "Reflex Save",
    willpower_save: "Willpower Save",
    arcane_save: "Arcane Save",
  };
  return labels[normalized] || canonicalName;
};

window.getSheetEls = function () {
  return {
    playAreaEl: document.querySelector(".play-area"),
    sheetPanelEl: document.getElementById("sheet-panel"),
    sheetPanelBodyEl: document.getElementById("sheet-panel-body")
  };
};

window.getSheetValue = function (obj, keys, fallback = 0) {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      return obj[key];
    }
  }
  return fallback;
};

window.getStatModifier = function (value) {
  return Math.floor((Number(value) - 10) / 2);
};

window.getArchetypeFromSheet = function (sheet) {
  const value = String(sheet?.archetype || "").trim();
  if (!value) return "Unknown";
  const normalized = value.toLowerCase();
  if (normalized === "mage") return "Mage";
  if (normalized === "warrior") return "Warrior";
  return value;
};

window.setSheetPanelOpen = function (open) {
  window.state.sheetPanelOpen = !!open;
  localStorage.setItem(window.SHEET_PANEL_STORAGE_KEY, window.state.sheetPanelOpen ? "1" : "0");
  const { playAreaEl, sheetPanelEl } = window.getSheetEls();
  if (!sheetPanelEl || !playAreaEl) return;

  playAreaEl.classList.toggle("sheet-open", window.state.sheetPanelOpen);
  sheetPanelEl.setAttribute("aria-hidden", window.state.sheetPanelOpen ? "false" : "true");
  if (window.state.sheetPanelOpen) {
    window.renderCharacterSheetPanel();
  }
};

window.renderCharacterSheetPanel = function () {
  const { sheetPanelBodyEl } = window.getSheetEls();
  if (!sheetPanelBodyEl) return;

  const character = window.currentCharacter ? window.currentCharacter() : null;
  const sheet = window.state.characterSheet;

  if (!character || !sheet) {
    sheetPanelBodyEl.innerHTML = '<div class="muted">Wybierz postać</div>';
    return;
  }

  const archetype = window.getArchetypeFromSheet(sheet);
  const currentHp = Number(window.getSheetValue(sheet, ["current_hp", "hp", "health"], 0));
  const maxHp = Number(window.getSheetValue(sheet, ["max_hp", "hp_max", "maxHealth"], currentHp || 1));
  const hpPercent = Math.max(0, Math.min(100, (currentHp / Math.max(1, maxHp)) * 100));

  const currentMana = Number(window.getSheetValue(sheet, ["current_mana", "mana"], 0));
  const maxMana = Number(window.getSheetValue(sheet, ["max_mana", "mana_max"], currentMana || 1));
  const manaPercent = Math.max(0, Math.min(100, (currentMana / Math.max(1, maxMana)) * 100));

  const statsObj = sheet.stats && typeof sheet.stats === "object" ? sheet.stats : {};
  const skillsObj = sheet.skills && typeof sheet.skills === "object" ? sheet.skills : {};

  const statsHtml = window.SHEET_STATS.map((key) => {
    const raw = window.getSheetValue(statsObj, [key, key.toLowerCase()], 10);
    const value = Number(raw);
    const mod = window.getStatModifier(value);
    const modLabel = mod >= 0 ? `+${mod}` : String(mod);
    return `
      <div class="sheet-stat">
        <span class="sheet-stat-key">${window.escapeHtml(key)}</span>
        <span class="sheet-stat-val">${window.escapeHtml(value)}</span>
        <span class="sheet-stat-mod">${window.escapeHtml(modLabel)}</span>
      </div>
    `;
  }).join("");

  const skillsHtml = window.SHEET_SKILLS.map((skill) => {
    const value = Number(window.getSheetValue(skillsObj, [skill, skill.toLowerCase()], 0));
    const clamped = Math.max(0, Math.min(5, value));
    return `
      <div class="sheet-skill">
        <span>${window.escapeHtml(skill)}</span>
        <strong>${window.escapeHtml(clamped)}/5</strong>
      </div>
    `;
  }).join("");

  sheetPanelBodyEl.innerHTML = `
    <div class="sheet-heading">
      <div class="sheet-name">${window.escapeHtml(character.name || "Bohater")}</div>
      <div class="sheet-archetype">${window.escapeHtml(archetype)}</div>
    </div>

    <div class="sheet-resource">
      <div class="sheet-resource-top">
        <span>HP</span>
        <span>${window.escapeHtml(currentHp)} / ${window.escapeHtml(maxHp)}</span>
      </div>
      <div class="sheet-bar"><div class="sheet-bar-fill hp" style="width:${hpPercent}%"></div></div>
    </div>

    ${archetype.toLowerCase() === "mage" ? `
      <div class="sheet-resource">
        <div class="sheet-resource-top">
          <span>Mana</span>
          <span>${window.escapeHtml(currentMana)} / ${window.escapeHtml(maxMana)}</span>
        </div>
        <div class="sheet-bar"><div class="sheet-bar-fill mana" style="width:${manaPercent}%"></div></div>
      </div>
    ` : ""}

    <div>
      <h4 class="sheet-section-title">Statystyki</h4>
      <div class="sheet-stats-grid">${statsHtml}</div>
    </div>

    <div>
      <h4 class="sheet-section-title">Umiejętności</h4>
      <div class="sheet-skills-grid">${skillsHtml}</div>
    </div>
  `;
};

window.loadCharacterSheet = async function (characterId) {
  if (!characterId) {
    window.state.characterSheet = null;
    window.renderCharacterSheetPanel();
    return;
  }

  try {
    let resp = await fetch(`${window.API_BASE_URL}/characters/${characterId}/sheet`);
    if (!resp.ok) {
      resp = await fetch(`/characters/${characterId}/sheet`);
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    window.state.characterSheet =
      data?.sheet_json && typeof data.sheet_json === "object" ? data.sheet_json : {};
  } catch (_err) {
    window.state.characterSheet = {};
  }

  window.renderCharacterSheetPanel();
};

window.bindCharacterSheetPanel = function () {
  const characterSelect = document.getElementById("character-select");
  if (characterSelect) {
    characterSelect.addEventListener("change", async () => {
      const id = Number(characterSelect.value);
      await window.loadCharacterSheet(id);
    });
  }

  const campaignSelect = document.getElementById("campaign-select");
  if (campaignSelect) {
    campaignSelect.addEventListener("change", async () => {
      const selectedId = Number(document.getElementById("character-select")?.value || 0);
      await window.loadCharacterSheet(selectedId);
    });
  }
};

window.initCharacterSheetPanel = async function () {
  const savedState = localStorage.getItem(window.SHEET_PANEL_STORAGE_KEY);
  if (savedState === "1") window.state.sheetPanelOpen = true;
  if (savedState === "0") window.state.sheetPanelOpen = false;

  window.setSheetPanelOpen(window.state.sheetPanelOpen);
  window.bindCharacterSheetPanel();

  const selectedId = Number(window.state.selectedCharacterId || 0);
  if (selectedId) {
    await window.loadCharacterSheet(selectedId);
  } else {
    window.renderCharacterSheetPanel();
  }
};

if (typeof window.loadCharacters === "function") {
  const originalLoadCharacters = window.loadCharacters;
  window.loadCharacters = async function (...args) {
    const result = await originalLoadCharacters.apply(this, args);
    await window.loadCharacterSheet(Number(window.state.selectedCharacterId || 0));
    return result;
  };
}

document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
    window.initCharacterSheetPanel();
  }, 0);
});
