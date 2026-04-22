/**
 * Slash-command autocomplete for the main game chat textarea (frontend-only).
 */

/** Default copy if API is unavailable */
export const SLASH_COMMANDS = [
  {
    command: "/help",
    description: "Show available commands list",
  },
  {
    command: "/sheet",
    description: "Display your current character sheet",
  },
  {
    command: "/mem [pytanie]",
    description: "Pytanie o przeszłość z podsumowań — bez wpływu na narrację (żółte dymki)",
  },
  {
    command: "/helpme [pytanie]",
    description: "Doradca OOC — wskazówki bez zmiany fabuły (czerwone dymki); nie wpływa na kontekst narracji",
  },
  {
    command: "/roll",
    description: "Roll d20 + modifier for the last GM-requested roll",
  },
  {
    command: "/name <new name>",
    description: "Rename your character",
  },
  {
    command: "/history",
    description: "Show the last 10 turns of the session",
  },
  {
    command: "/export",
    description: "Export the full session to a text file on the server (/data/exports/)",
  },
  {
    command: "/atak",
    description:
      "Silnik walki: samo /atak synchronizuje panel (HP, tura). Z kluczami wroga, np. /atak bandit — start walki przez API bez tagu MG.",
  },
  {
    command: "/search",
    description: "Przeszukaj zabitą postać lub lokację",
    usage: "/search [cel — opcjonalnie]",
  },
];

/** @type {{ command: string, description: string }[]} */
let activeSlashCommands = SLASH_COMMANDS.map((c) => ({ ...c }));

/**
 * Loads merged slash-command text from `GET /api/mechanics/slash-commands` (admin-editable).
 * Safe to call multiple times.
 */
export async function loadSlashCommandCatalog() {
  const rawBase =
    typeof window !== "undefined" && window.API_BASE_URL ? String(window.API_BASE_URL) : "/api";
  const base = rawBase.replace(/\/$/, "");
  try {
    const r = await fetch(`${base}/mechanics/slash-commands`, { credentials: "same-origin" });
    if (!r.ok) {
      return;
    }
    const data = await r.json();
    if (!data.commands || !Array.isArray(data.commands) || !data.commands.length) {
      return;
    }
    const next = data.commands
      .filter((x) => x && typeof x.command === "string" && typeof x.description === "string")
      .map((x) => ({ command: x.command.trim(), description: x.description }));
    if (next.length) {
      activeSlashCommands = next;
      if (typeof window !== "undefined") {
        window.__slashCommandsEnabledKeys = new Set(
          next.map((x) => String(x.command || "").trim()).filter(Boolean)
        );
      }
    }
  } catch (_e) {
    /* keep defaults */
  }
}

/** @type {HTMLElement | null} */
let popupEl = null;

/**
 * Active slash token: "/" at line/word start, no whitespace inside the token before the cursor.
 * @param {string} value
 * @param {number} cursorPos
 */
function getSlashContext(value, cursorPos) {
  const pos = Math.min(Math.max(0, cursorPos), value.length);
  const before = value.slice(0, pos);
  const slashIndex = before.lastIndexOf("/");
  if (slashIndex === -1) {
    return null;
  }
  const prev = slashIndex === 0 ? " " : before[slashIndex - 1];
  if (prev !== " " && prev !== "\n" && prev !== "\t") {
    return null;
  }
  const token = before.slice(slashIndex + 1);
  if (/\s/.test(token)) {
    return null;
  }
  return { slashIndex, query: token };
}

/**
 * @param {string} query
 * @returns {typeof SLASH_COMMANDS}
 */
function filterCommands(query) {
  const q = (query || "").toLowerCase();
  const list = activeSlashCommands;
  return list.filter((c) => {
    const cmd = c.command.toLowerCase();
    const desc = c.description.toLowerCase();
    return cmd.includes(q) || desc.includes(q);
  });
}

function ensurePopup() {
  if (popupEl && document.body.contains(popupEl)) {
    return popupEl;
  }
  const el = document.createElement("div");
  el.id = "slash-popup";
  el.className = "slash-popup";
  el.setAttribute("role", "listbox");
  el.setAttribute("aria-hidden", "true");
  const list = document.createElement("ul");
  list.className = "slash-popup-list";
  el.appendChild(list);
  document.body.appendChild(el);
  popupEl = el;
  return el;
}

/**
 * @param {HTMLElement} popup
 * @param {HTMLTextAreaElement | HTMLInputElement} inputEl
 */
function positionPopup(popup, inputEl) {
  const rect = inputEl.getBoundingClientRect();
  popup.style.position = "fixed";
  popup.style.left = `${rect.left}px`;
  popup.style.width = `${rect.width}px`;
  popup.style.bottom = `${window.innerHeight - rect.top + 8}px`;
  popup.style.top = "auto";
  popup.style.right = "auto";
}

/**
 * @param {HTMLElement} popup
 * @param {{ command: string, description: string }[]} matches
 * @param {number} highlightIndex
 * @param {(cmd: { command: string, description: string }) => void} onPick
 */
function renderList(popup, matches, highlightIndex, onPick) {
  const list = popup.querySelector(".slash-popup-list");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  matches.forEach((cmd, i) => {
    const li = document.createElement("li");
    li.className = "slash-popup-item";
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", i === highlightIndex ? "true" : "false");
    if (i === highlightIndex) {
      li.classList.add("slash-popup-item--active");
    }
    li.dataset.command = cmd.command;

    const name = document.createElement("span");
    name.className = "slash-popup-cmd";
    name.textContent = cmd.command;

    const desc = document.createElement("span");
    desc.className = "slash-popup-desc";
    desc.textContent = cmd.description;

    li.appendChild(name);
    li.appendChild(desc);

    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
    });
    li.addEventListener("click", () => {
      onPick(cmd);
    });

    list.appendChild(li);
  });

  const active = list.querySelector(".slash-popup-item--active");
  if (active) {
    active.scrollIntoView({ block: "nearest" });
  }
}

/**
 * @param {HTMLTextAreaElement | HTMLInputElement} inputEl
 * @param {string} commandWithSlash e.g. "/help"
 */
function applySlashInsert(inputEl, commandWithSlash) {
  const current = inputEl.value;
  const pos = inputEl.selectionStart ?? current.length;
  const ctx = getSlashContext(current, pos);
  if (!ctx) {
    return;
  }
  const next =
    current.slice(0, ctx.slashIndex) + commandWithSlash + " " + current.slice(pos);
  inputEl.value = next;
  const caret = ctx.slashIndex + commandWithSlash.length + 1;
  inputEl.setSelectionRange(caret, caret);
  inputEl.focus();
}

function hidePopup() {
  const popup = document.getElementById("slash-popup");
  if (!popup) {
    return;
  }
  popup.classList.remove("slash-popup--open");
  popup.setAttribute("aria-hidden", "true");
}

/**
 * @param {HTMLTextAreaElement | HTMLInputElement} inputEl
 */
export async function initSlashCommands(inputEl) {
  if (!inputEl || inputEl.dataset.slashCommandsInit) {
    return;
  }
  inputEl.dataset.slashCommandsInit = "1";
  await loadSlashCommandCatalog();

  const popup = ensurePopup();
  let highlightIndex = 0;
  let lastMatches = /** @type {{ command: string, description: string }[]} */ ([]);

  function hideAndClear() {
    lastMatches = [];
    hidePopup();
  }

  function pickCommand(cmd) {
    applySlashInsert(inputEl, cmd.command);
    hideAndClear();
  }

  function syncFromInput() {
    const value = inputEl.value;
    const pos = inputEl.selectionStart ?? value.length;
    const ctx = getSlashContext(value, pos);
    if (!ctx) {
      hideAndClear();
      return;
    }
    const matches = filterCommands(ctx.query);
    if (!matches.length) {
      hideAndClear();
      return;
    }
    lastMatches = matches;
    highlightIndex = Math.min(highlightIndex, matches.length - 1);
    highlightIndex = Math.max(0, highlightIndex);

    positionPopup(popup, inputEl);
    renderList(popup, matches, highlightIndex, pickCommand);
    popup.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => {
      popup.classList.add("slash-popup--open");
    });
  }

  function reposition() {
    if (!popup.classList.contains("slash-popup--open")) {
      return;
    }
    positionPopup(popup, inputEl);
  }

  inputEl.addEventListener("input", () => {
    highlightIndex = 0;
    syncFromInput();
  });

  inputEl.addEventListener("click", syncFromInput);
  inputEl.addEventListener("keyup", (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      return;
    }
    syncFromInput();
  });

  window.addEventListener("scroll", reposition, true);
  window.addEventListener("resize", reposition);

  inputEl.addEventListener(
    "keydown",
    (e) => {
      const value = inputEl.value;
      const pos = inputEl.selectionStart ?? value.length;
      const ctx = getSlashContext(value, pos);
      const popupActive =
        popup.classList.contains("slash-popup--open") && lastMatches.length > 0;

      if (e.key === "Escape" && popupActive) {
        e.preventDefault();
        e.stopImmediatePropagation();
        hideAndClear();
        return;
      }

      if (!ctx || !lastMatches.length) {
        return;
      }

      if (!popup.classList.contains("slash-popup--open")) {
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        e.stopImmediatePropagation();
        highlightIndex = (highlightIndex + 1) % lastMatches.length;
        renderList(popup, lastMatches, highlightIndex, pickCommand);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        e.stopImmediatePropagation();
        highlightIndex = (highlightIndex - 1 + lastMatches.length) % lastMatches.length;
        renderList(popup, lastMatches, highlightIndex, pickCommand);
        return;
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        e.stopImmediatePropagation();
        const cmd = lastMatches[highlightIndex];
        if (cmd) {
          pickCommand(cmd);
        }
        return;
      }

      if (e.key === "Tab" && !e.shiftKey) {
        e.preventDefault();
        e.stopImmediatePropagation();
        const cmd = lastMatches[highlightIndex];
        if (cmd) {
          pickCommand(cmd);
        }
      }
    },
    true,
  );

  syncFromInput();
}
