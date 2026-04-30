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

function parseCmd(raw) {
  const t = (raw || "").trim().replace(/^\/admin\s*/i, "");
  const parts = t.split(/\s+/);
  const p0 = (parts[0] || "").toLowerCase();
  const p1 = (parts[1] || "").toLowerCase();
  const rest = parts.slice(2).join(" ");

  if (p0 === "add" && (p1 === "gold" || p1 === "health")) {
    const v = rest.toLowerCase() === "max" ? "max" : parseInt(rest, 10);
    return { cmd: `add ${p1}`, value: Number.isNaN(v) ? rest : v };
  }
  if (p0 === "add" && p1 === "weapon") {
    const key = rest ? rest.trim() : undefined;
    return { cmd: "add item", key, kind: "weapon" };
  }
  if (p0 === "add" && p1 === "consumable") {
    const key = rest ? rest.trim() : undefined;
    return { cmd: "add item", key, kind: "consumable" };
  }
  if (p0 === "add" && p1 === "item") return { cmd: "add item", key: rest || undefined };
  if (p0 === "add" && p1 === "stat") {
    const stat = (parts[2] || "").toUpperCase();
    const val = parseInt(parts[3] || "1", 10);
    return { cmd: "add stat", stat, value: Number.isNaN(val) ? 1 : val };
  }
  if (p0 === "set" && (p1 === "gold" || p1 === "level")) {
    const v = parseInt(rest, 10);
    return { cmd: `set ${p1}`, value: Number.isNaN(v) ? 0 : v };
  }
  if (p0 === "set" && p1 === "health") {
    const v = rest.toLowerCase() === "max" ? "max" : parseInt(rest, 10);
    return { cmd: "set health", value: Number.isNaN(v) ? rest : v };
  }
  if (p0 === "set" && p1 === "location") return { cmd: "set location", key: rest || undefined };
  if (p0 === "remove" && p1 === "item") return { cmd: "remove item", key: rest || undefined };
  if (p0 === "clear" && p1 === "inventory") return { cmd: "clear inventory" };
  if (p0 === "combat" && p1 === "end") return { cmd: "combat end" };
  if (p0 === "quest" && (p1 === "add" || p1 === "complete")) return { cmd: `quest ${p1}`, key: rest || undefined };
  if (p0 === "show" && p1 === "state") return { cmd: "show state" };
  return null;
}

export async function init(container) {
  container.innerHTML = "";
  container.classList.add("admin-commands-section");

  const banner = el("div", "warning-banner warning-banner-orange");
  banner.textContent = "⚠️ Komendy modyfikują bazę bezpośrednio. Używaj tylko na DEV/TEST.";
  container.appendChild(banner);

  const charRow = el("div", "field");
  charRow.appendChild(el("label", "", "Postać"));
  const charSelect = document.createElement("select");
  charSelect.className = "admin-cmd-char-select";
  charSelect.style.maxWidth = "360px";
  const defaultOpt = el("option", "", "— wybierz postać —");
  defaultOpt.value = "";
  charSelect.appendChild(defaultOpt);
  charRow.appendChild(charSelect);
  container.appendChild(charRow);

  try {
    const data = await adminFetch("/api/admin/characters");
    (data.items || []).forEach((c) => {
      const opt = el("option", "", `[${c.id}] ${c.name} (${c.campaign_title})`);
      opt.value = String(c.id);
      charSelect.appendChild(opt);
    });
  } catch (e) {
    showToast(parseApiError(e, "Nie można załadować postaci."), "error");
  }

  const termCard = el("div", "admin-card");
  termCard.style.marginTop = "16px";
  termCard.appendChild(el("h3", "admin-card-title", "Terminal"));
  const cmdRow = el("div", "field");
  cmdRow.style.display = "flex";
  cmdRow.style.gap = "8px";
  const cmdInput = document.createElement("input");
  cmdInput.type = "text";
  cmdInput.className = "admin-cmd-input";
  cmdInput.placeholder = "np. add gold 100  lub  set health max";
  cmdInput.style.flex = "1";
  const execBtn = el("button", "primary-btn", "▶ Wykonaj");
  execBtn.type = "button";
  cmdRow.appendChild(cmdInput);
  cmdRow.appendChild(execBtn);
  termCard.appendChild(cmdRow);
  const historyEl = el("div", "admin-cmd-history");
  historyEl.style.cssText =
    "margin-top:10px; font-family:monospace; font-size:12px; max-height:180px; overflow-y:auto;";
  termCard.appendChild(historyEl);
  container.appendChild(termCard);

  const qaCard = el("div", "admin-card");
  qaCard.style.marginTop = "16px";
  qaCard.appendChild(el("h3", "admin-card-title", "Quick Actions"));
  const qaRow = el("div", "");
  qaRow.style.cssText = "display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;";
  const QUICK_ACTIONS = [
    { label: "💛 +100 GP", body: { cmd: "add gold", value: 100 } },
    { label: "❤️ Full Heal", body: { cmd: "set health", value: "max" } },
    { label: "🗑 Clear Inventory", body: { cmd: "clear inventory" } },
    { label: "⚔️ End Combat", body: { cmd: "combat end" } },
  ];
  QUICK_ACTIONS.forEach(({ label, body }) => {
    const btn = el("button", "secondary-btn", label);
    btn.type = "button";
    btn.addEventListener("click", () => {
      void executeRaw(body, label);
    });
    qaRow.appendChild(btn);
  });
  qaCard.appendChild(qaRow);
  container.appendChild(qaCard);

  const stateCard = el("div", "admin-card");
  stateCard.style.marginTop = "16px";
  stateCard.appendChild(el("h3", "admin-card-title", "Stan postaci"));
  const statePre = el("pre", "muted");
  statePre.style.cssText = "white-space:pre-wrap; font-size:12px; margin-top:8px;";
  statePre.textContent = "— wybierz postać i wykonaj komendę —";
  stateCard.appendChild(statePre);
  container.appendChild(stateCard);

  let cmdHistory = [];

  function addHistory(label, result, ok) {
    const time = new Date().toLocaleTimeString();
    cmdHistory.unshift({ time, label, result, ok });
    if (cmdHistory.length > 20) cmdHistory.pop();
    renderHistory();
  }

  function renderHistory() {
    historyEl.innerHTML = "";
    cmdHistory.forEach(({ time, label, result, ok }) => {
      const row = el("div", "");
      row.style.color = ok ? "#4caf50" : "#f44336";
      row.style.borderBottom = "1px solid #333";
      row.style.padding = "2px 0";
      row.textContent = `[${time}] ${ok ? "✅" : "❌"} ${label} -> ${JSON.stringify(result)}`;
      historyEl.appendChild(row);
    });
  }

  async function refreshState(charId) {
    try {
      const res = await adminFetch(`/api/admin/cheat/${charId}`, {
        method: "POST",
        body: JSON.stringify({ cmd: "show state" }),
      });
      const r = res.result || {};
      statePre.textContent = [
        `HP:       ${r.current_hp ?? "?"}/${r.max_hp ?? "?"}`,
        `GP:       ${r.gold_gp ?? "?"}`,
        `Level:    ${r.level ?? "?"}`,
        `Location: ${r.location || "?"}`,
        `Stats:    ${JSON.stringify(r.stats || {})}`,
        `Items:    ${(r.inventory || []).join(", ") || "(brak)"}`,
        `Quests:   ${(r.quests_active || []).join(", ") || "(brak)"}`,
      ].join("\n");
    } catch (_e) {
      // ignore state refresh errors
    }
  }

  async function executeRaw(body, label) {
    const charId = charSelect.value;
    if (!charId) {
      showToast("Wybierz postać.", "info");
      return;
    }
    try {
      const res = await adminFetch(`/api/admin/cheat/${charId}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      addHistory(label, res.result, true);
      await refreshState(charId);
      showToast(`✅ ${label}`, "success");
    } catch (e) {
      const msg = parseApiError(e, e.message || "Błąd");
      addHistory(label, msg, false);
      showToast(`❌ ${msg}`, "error");
    }
  }

  execBtn.addEventListener("click", async () => {
    const raw = cmdInput.value.trim();
    if (!raw) return;
    const body = parseCmd(raw);
    if (!body) {
      showToast(`Nieznana komenda: ${raw}`, "error");
      return;
    }
    await executeRaw(body, raw);
    cmdInput.value = "";
    cmdInput.focus();
  });

  cmdInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      execBtn.click();
    }
  });

  charSelect.addEventListener("change", () => {
    const charId = charSelect.value;
    if (charId) {
      void refreshState(charId);
    }
  });
}
