import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";
import { showConfirm } from "/admin_panel/shared/table.js?v=23";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) {
    n.className = cls;
  }
  if (text !== undefined && text !== null) {
    n.textContent = text;
  }
  return n;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail) {
    const d = err.body.detail;
    return Array.isArray(d) ? d.join("; ") : String(d);
  }
  return fallback;
}

function backupSummaryLines(result) {
  const backup = result && typeof result === "object" ? result.backup : null;
  if (!backup || typeof backup !== "object") {
    return [];
  }
  const retention = backup.retention && typeof backup.retention === "object" ? backup.retention : null;
  const lines = [];
  if (backup.path) {
    lines.push(`Backup created: ${String(backup.path)}`);
  }
  if (retention) {
    lines.push(
      `Retention: keep recent ${Number(retention.max_age_days || 30)} days, preserve at least ${Number(retention.min_keep || 3)} older backups, max ${Number(retention.keep_last || 10)} files.`,
    );
  }
  if (Array.isArray(backup.pruned) && backup.pruned.length) {
    lines.push(`Pruned by retention: ${backup.pruned.join(", ")}`);
  } else {
    lines.push("Pruned by retention: none");
  }
  return lines;
}

function renderBackupNotice(host, result, headingText = "Pre-import backup") {
  const lines = backupSummaryLines(result);
  if (!lines.length) {
    host.hidden = true;
    host.innerHTML = "";
    return;
  }
  host.hidden = false;
  host.innerHTML = "";
  host.className = "warning-banner";
  host.appendChild(el("strong", "", headingText));
  const list = el("ul", "");
  lines.forEach((line) => {
    list.appendChild(el("li", "", line));
  });
  host.appendChild(list);
}

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  container.innerHTML = "";
  container.classList.add("config-section");

  const top = el("div", "warning-banner warning-banner-orange");
  top.textContent =
    "⚠️ Export the current configuration before bulk edits or before committing an import. Full catalog migrations should use Catalog Snapshot; Import Config is a narrower legacy path.";
  container.appendChild(top);

  const grid = el("div", "two-col-cards");

  const card1 = el("div", "admin-card");
  card1.appendChild(el("h3", "admin-card-title", "Export Config"));
  const desc1 = el(
    "p",
    "muted",
    "Downloads a full JSON snapshot of all game mechanics config (stats, skills, DC, weapons, enemies, conditions). Does not include tokens, audit log, or user accounts.",
  );
  card1.appendChild(desc1);
  const expBtn = el("button", "primary-btn", "⬇ Export Config");
  expBtn.type = "button";
  expBtn.addEventListener("click", async () => {
    try {
      const data = await adminFetch("/api/admin/config/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      const d = new Date();
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      a.download = `aigm_config_${y}${m}${day}.json`;
      a.click();
      URL.revokeObjectURL(blobUrl);
      showToast("Config exported.", "success");
    } catch (e) {
      showToast(parseApiError(e, "Export failed."), "error");
    }
  });
  card1.appendChild(expBtn);

  const card2 = el("div", "admin-card");
  card2.appendChild(el("h3", "admin-card-title", "Import Config"));
  const fileInp = el("input", "");
  fileInp.type = "file";
  fileInp.accept = ".json,application/json";

  const dryBtn = el("button", "secondary-btn", "🔍 Dry Run");
  dryBtn.type = "button";
  dryBtn.disabled = true;

  const commitBtn = el("button", "primary-btn danger-btn", "✅ Commit Import");
  commitBtn.type = "button";
  commitBtn.disabled = true;

  const diffWrap = el("div", "config-diff-wrap");
  diffWrap.hidden = true;
  const importInfo = el("div", "warning-banner");
  importInfo.hidden = true;

  /** @type {Record<string, unknown> | null} */
  let lastParsed = null;
  /** @type {string[]} */
  let lastDryRunWarnings = [];
  fileInp.addEventListener("change", () => {
    dryBtn.disabled = !fileInp.files || !fileInp.files.length;
    commitBtn.disabled = true;
    lastParsed = null;
    lastDryRunWarnings = [];
    diffWrap.hidden = true;
    diffWrap.innerHTML = "";
  });

  function renderDiff(dryJson, parsed) {
    diffWrap.hidden = false;
    diffWrap.innerHTML = "";
    diffWrap.appendChild(el("h4", "config-diff-heading", "Import Preview — Dry Run"));

    const ver = dryJson.target_version != null ? String(dryJson.target_version) : String(parsed.config_version || "");
    diffWrap.appendChild(el("p", "config-version-line", `Config version: ${ver}`));

    if (Array.isArray(dryJson.warnings) && dryJson.warnings.length) {
      const warn = el("div", "warning-banner warning-banner-orange");
      warn.appendChild(el("strong", "", "Warnings:"));
      const list = el("ul", "");
      dryJson.warnings.forEach((msg) => {
        list.appendChild(el("li", "", String(msg)));
      });
      warn.appendChild(list);
      diffWrap.appendChild(warn);
    }

    if (dryJson.note) {
      diffWrap.appendChild(el("p", "muted", String(dryJson.note)));
    }

    const adds = el("div", "config-diff-block");
    adds.appendChild(el("h5", "config-diff-sub", "✅ Rows to add (import file)"));
    const tblA = el("table", "admin-table diff-table diff-add");
    const theadA = el("thead");
    const hra = el("tr");
    hra.appendChild(el("th", "", "Table"));
    hra.appendChild(el("th", "", "Rows in file"));
    theadA.appendChild(hra);
    tblA.appendChild(theadA);
    const tba = el("tbody");
    const tables = parsed.tables && typeof parsed.tables === "object" ? parsed.tables : {};
    Object.keys(tables)
      .sort()
      .forEach((k) => {
        const arr = tables[k];
        const n = Array.isArray(arr) ? arr.length : 0;
        const tr = el("tr");
        tr.appendChild(el("td", "db-table-name", k));
        tr.appendChild(el("td", "", String(n)));
        tba.appendChild(tr);
      });
    tblA.appendChild(tba);
    adds.appendChild(tblA);
    diffWrap.appendChild(adds);

    const upd = el("div", "config-diff-block");
    upd.appendChild(el("h5", "config-diff-sub", "✏️ Rows to update"));
    upd.appendChild(
      el(
        "p",
        "muted",
        "The API does not return per-row diffs. Commit replaces entire config tables with the file contents.",
      ),
    );
    diffWrap.appendChild(upd);

    const sk = el("div", "config-diff-block");
    sk.appendChild(el("h5", "config-diff-sub", "⏭ Rows to skip"));
    sk.appendChild(el("p", "muted", "None (dry run only validates and counts)."));
    diffWrap.appendChild(sk);

    const pre = el("pre", "config-diff-raw");
    pre.textContent = JSON.stringify(dryJson, null, 2);
    diffWrap.appendChild(pre);
  }

  dryBtn.addEventListener("click", async () => {
    const f = fileInp.files && fileInp.files[0];
    if (!f) {
      return;
    }
    const label = dryBtn.textContent;
    dryBtn.disabled = true;
    dryBtn.textContent = "⏳";
    try {
      const text = await f.text();
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== "object" || !parsed.tables) {
        throw new Error("Invalid config file: missing tables.");
      }
      lastParsed = parsed;
      const res = await adminFetch("/api/admin/config/import?dry_run=true", {
        method: "POST",
        body: JSON.stringify(parsed),
      });
      lastDryRunWarnings = Array.isArray(res?.warnings) ? res.warnings.map((x) => String(x)) : [];
      renderDiff(res, parsed);
      commitBtn.disabled = false;
      showToast(
        Array.isArray(res?.warnings) && res.warnings.length ? "Dry run complete with warnings." : "Dry run complete.",
        "success",
      );
    } catch (e) {
      lastParsed = null;
      lastDryRunWarnings = [];
      commitBtn.disabled = true;
      diffWrap.hidden = true;
      showToast(e instanceof SyntaxError ? "Invalid JSON file." : parseApiError(e, "Dry run failed."), "error");
    } finally {
      dryBtn.textContent = label;
      dryBtn.disabled = !fileInp.files || !fileInp.files.length;
    }
  });

  commitBtn.addEventListener("click", async () => {
    if (!lastParsed) {
      showToast("Run a dry run first.", "info");
      return;
    }
    const warningLines = lastDryRunWarnings;
    const ok = await showConfirm(
      "Commit this import? Current config will be overwritten." +
        (warningLines.length ? `\n\nWarnings:\n- ${warningLines.join("\n- ")}` : ""),
      { dangerous: true },
    );
    if (!ok) {
      return;
    }
    const label = commitBtn.textContent;
    commitBtn.disabled = true;
    commitBtn.textContent = "⏳";
    try {
      const res = await adminFetch("/api/admin/config/import", {
        method: "POST",
        body: JSON.stringify(lastParsed),
      });
      renderBackupNotice(importInfo, res, "Automatic backup before import");
      showToast("Import committed. Backup created automatically.", "success");
      fileInp.value = "";
      lastParsed = null;
      lastDryRunWarnings = [];
      diffWrap.hidden = true;
      diffWrap.innerHTML = "";
      dryBtn.disabled = true;
      commitBtn.disabled = true;
    } catch (e) {
      showToast(parseApiError(e, "Import commit failed."), "error");
      commitBtn.disabled = false;
    } finally {
      commitBtn.textContent = label;
    }
  });

  card2.appendChild(fileInp);
  card2.appendChild(
    el(
      "p",
      "muted",
      "Commit import creates an automatic DB backup before any rows are replaced. Retention keeps recent backups for 30 days, always preserves at least 3 older snapshots, and caps the pool at 10 files.",
    ),
  );
  const rowBtns = el("div", "technical-btn-row");
  rowBtns.appendChild(dryBtn);
  rowBtns.appendChild(commitBtn);
  card2.appendChild(rowBtns);
  card2.appendChild(importInfo);
  card2.appendChild(diffWrap);

  const cardSummary = el("div", "admin-card");
  cardSummary.appendChild(el("h3", "admin-card-title", "Summary / History settings"));
  cardSummary.appendChild(
    el(
      "p",
      "muted",
      "Global settings for campaign history rollup and the experimental dual preview (T01 QA path).",
    ),
  );
  const cooldownLabel = el("label", "field-label", "Rollup cooldown (narrative turns)");
  const cooldownInput = el("input", "");
  cooldownInput.type = "number";
  cooldownInput.min = "1";
  cooldownInput.max = "500";
  cooldownInput.step = "1";
  const cooldownHelp = el(
    "p",
    "muted",
    "How many new narrative turns are required before the next LLM rollup refresh is allowed.",
  );
  const modeLabel = el("label", "field-label", "Dual preview access mode");
  const modeSelect = document.createElement("select");
  [
    ["owner", "Campaign owner"],
    ["owner_admin", "Campaign owner + global admin"],
    ["off", "Disabled"],
  ].forEach(([value, label]) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    modeSelect.appendChild(opt);
  });
  const modeHelp = el(
    "p",
    "muted",
    "Controls access to the T01 dual preview button in the History modal. It never writes to the database.",
  );
  const summarySaveBtn = el("button", "primary-btn", "Save summary settings");
  summarySaveBtn.type = "button";
  summarySaveBtn.disabled = true;
  cardSummary.appendChild(cooldownLabel);
  cardSummary.appendChild(cooldownInput);
  cardSummary.appendChild(cooldownHelp);
  cardSummary.appendChild(modeLabel);
  cardSummary.appendChild(modeSelect);
  cardSummary.appendChild(modeHelp);
  cardSummary.appendChild(summarySaveBtn);

  async function loadSummarySettings() {
    const res = await adminFetch("/api/settings/summary");
    const data = res?.data || {};
    cooldownInput.value = String(data.summary_rollup_cooldown_turns ?? 20);
    modeSelect.value = String(data.dual_summary_preview_mode || "owner_admin");
    summarySaveBtn.disabled = false;
  }

  summarySaveBtn.addEventListener("click", async () => {
    const n = Number(cooldownInput.value || 20);
    const label = summarySaveBtn.textContent;
    summarySaveBtn.disabled = true;
    summarySaveBtn.textContent = "⏳";
    try {
      const res = await adminFetch("/api/settings/summary", {
        method: "PATCH",
        body: JSON.stringify({
          summary_rollup_cooldown_turns: Math.max(1, Math.min(500, Math.trunc(n || 20))),
          dual_summary_preview_mode: modeSelect.value || "owner_admin",
        }),
      });
      const data = res?.data || {};
      cooldownInput.value = String(data.summary_rollup_cooldown_turns ?? 20);
      modeSelect.value = String(data.dual_summary_preview_mode || "owner_admin");
      showToast("Summary settings saved.", "success");
    } catch (e) {
      showToast(parseApiError(e, "Save failed."), "error");
    } finally {
      summarySaveBtn.textContent = label;
      summarySaveBtn.disabled = false;
    }
  });

  const cardSlash = el("div", "admin-card slash-commands-card");
  cardSlash.style.gridColumn = "1 / -1";
  cardSlash.appendChild(el("h3", "admin-card-title", "Chat slash commands"));
  cardSlash.appendChild(
    el(
      "p",
      "muted",
      "Lista poleceń jest zawsze zgodna z serwerem (COMMAND_REGISTRY + /search). Dla każdej pozycji: checkbox = czy gracz może użyć tej komendy w czacie; pole tekstowe = opis w podpowiedzi. Zapis w bazie.",
    ),
  );
  const slashRows = el("div", "slash-commands-rows");
  cardSlash.appendChild(slashRows);
  const slashSave = el("button", "primary-btn", "Zapisz komendy");
  slashSave.type = "button";
  slashSave.disabled = true;
  slashSave.addEventListener("click", async () => {
    const rows = slashRows.querySelectorAll(".slash-cmd-row");
    const commands = Array.from(rows).map((row) => {
      const ta = row.querySelector("textarea.slash-cmd-desc");
      const cb = row.querySelector("input.slash-cmd-enabled");
      return {
        command: ta?.dataset.command || "",
        description: (ta?.value || "").trim(),
        enabled: !!(cb && cb.checked),
      };
    });
    const label = slashSave.textContent;
    slashSave.disabled = true;
    slashSave.textContent = "⏳";
    try {
      await adminFetch("/api/admin/slash-commands", {
        method: "PUT",
        body: JSON.stringify({ commands }),
      });
      showToast("Zapisano ustawienia komend czatu.", "success");
    } catch (e) {
      showToast(parseApiError(e, "Save failed."), "error");
    } finally {
      slashSave.textContent = label;
      slashSave.disabled = false;
    }
  });
  cardSlash.appendChild(slashSave);

  async function loadSlashCommandRows() {
    const data = await adminFetch("/api/admin/slash-commands");
    const cmds = data.commands || [];
    slashRows.innerHTML = "";
    cmds.forEach((c) => {
      const row = el("div", "slash-cmd-row");
      const head = el("div", "slash-cmd-head");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "slash-cmd-enabled";
      cb.title = "Włącz / wyłącz dla gracza";
      cb.checked = c.enabled !== false;
      head.appendChild(cb);
      head.appendChild(el("span", "slash-cmd-name", c.command || ""));
      row.appendChild(head);
      const ta = el("textarea", "slash-cmd-desc");
      ta.rows = 2;
      ta.value = c.description != null ? String(c.description) : "";
      ta.dataset.command = c.command || "";
      row.appendChild(ta);
      slashRows.appendChild(row);
    });
    slashSave.disabled = false;
  }

  try {
    await loadSummarySettings();
  } catch (e) {
    showToast(parseApiError(e, "Could not load summary settings."), "error");
  }

  try {
    await loadSlashCommandRows();
  } catch (e) {
    showToast(parseApiError(e, "Could not load slash command config."), "error");
  }

  window.__adminConfigReloadSlash = loadSlashCommandRows;

  grid.appendChild(card1);
  grid.appendChild(card2);
  grid.appendChild(cardSummary);
  grid.appendChild(cardSlash);
  container.appendChild(grid);
}
