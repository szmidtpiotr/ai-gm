import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";
import { showConfirm } from "/admin_panel/shared/table.js?v=20";

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

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  container.innerHTML = "";
  container.classList.add("config-section");

  const top = el("div", "warning-banner warning-banner-orange");
  top.textContent =
    "⚠️ Export the current configuration before bulk edits or before committing an import.";
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

  const desc1b = el(
    "p",
    "muted",
    "Catalog snapshot: every catalogue table (items, consumables, loot tables + entries, …) in one JSON file. Use as read-only context for an LLM (e.g. Perplexity) so it knows existing keys before proposing new content. Not valid for “Import Config” commit.",
  );
  card1.appendChild(desc1b);
  const snapBtn = el("button", "secondary-btn", "⬇ Export catalog snapshot (LLM)");
  snapBtn.type = "button";
  snapBtn.addEventListener("click", async () => {
    try {
      const data = await adminFetch("/api/admin/config/catalog-snapshot");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      const d = new Date();
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      a.download = `aigm_catalog_snapshot_${y}${m}${day}.json`;
      a.click();
      URL.revokeObjectURL(blobUrl);
      showToast("Catalog snapshot exported.", "success");
    } catch (e) {
      showToast(parseApiError(e, "Snapshot export failed."), "error");
    }
  });
  card1.appendChild(snapBtn);

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

  /** @type {Record<string, unknown> | null} */
  let lastParsed = null;
  fileInp.addEventListener("change", () => {
    dryBtn.disabled = !fileInp.files || !fileInp.files.length;
    commitBtn.disabled = true;
    lastParsed = null;
    diffWrap.hidden = true;
    diffWrap.innerHTML = "";
  });

  function renderDiff(dryJson, parsed) {
    diffWrap.hidden = false;
    diffWrap.innerHTML = "";
    diffWrap.appendChild(el("h4", "config-diff-heading", "Import Preview — Dry Run"));

    const ver = dryJson.target_version != null ? String(dryJson.target_version) : String(parsed.config_version || "");
    diffWrap.appendChild(el("p", "config-version-line", `Config version: ${ver}`));

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
      renderDiff(res, parsed);
      commitBtn.disabled = false;
      showToast("Dry run complete.", "success");
    } catch (e) {
      lastParsed = null;
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
    const ok = await showConfirm("Commit this import? Current config will be overwritten.", { dangerous: true });
    if (!ok) {
      return;
    }
    const label = commitBtn.textContent;
    commitBtn.disabled = true;
    commitBtn.textContent = "⏳";
    try {
      await adminFetch("/api/admin/config/import", {
        method: "POST",
        body: JSON.stringify(lastParsed),
      });
      showToast("Import committed. Config version bumped.", "success");
      fileInp.value = "";
      lastParsed = null;
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
  const rowBtns = el("div", "technical-btn-row");
  rowBtns.appendChild(dryBtn);
  rowBtns.appendChild(commitBtn);
  card2.appendChild(rowBtns);
  card2.appendChild(diffWrap);

  const cardSlash = el("div", "admin-card slash-commands-card");
  cardSlash.style.gridColumn = "1 / -1";
  cardSlash.appendChild(el("h3", "admin-card-title", "Chat slash commands"));
  cardSlash.appendChild(
    el(
      "p",
      "muted",
      "Descriptions for the in-game chat autocomplete (when players type /). Command names are fixed; only the help text is editable. Stored in the database.",
    ),
  );
  const slashRows = el("div", "slash-commands-rows");
  cardSlash.appendChild(slashRows);
  const slashSave = el("button", "primary-btn", "Save descriptions");
  slashSave.type = "button";
  slashSave.disabled = true;
  slashSave.addEventListener("click", async () => {
    const textareas = slashRows.querySelectorAll("textarea.slash-cmd-desc");
    const commands = Array.from(textareas).map((ta) => ({
      command: ta.dataset.command || "",
      description: ta.value.trim(),
    }));
    const label = slashSave.textContent;
    slashSave.disabled = true;
    slashSave.textContent = "⏳";
    try {
      await adminFetch("/api/admin/slash-commands", {
        method: "PUT",
        body: JSON.stringify({ commands }),
      });
      showToast("Slash command descriptions saved.", "success");
    } catch (e) {
      showToast(parseApiError(e, "Save failed."), "error");
    } finally {
      slashSave.textContent = label;
      slashSave.disabled = false;
    }
  });
  cardSlash.appendChild(slashSave);

  (async () => {
    try {
      const data = await adminFetch("/api/admin/slash-commands");
      const cmds = data.commands || [];
      slashRows.innerHTML = "";
      cmds.forEach((c) => {
        const row = el("div", "slash-cmd-row");
        const head = el("div", "slash-cmd-head");
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
    } catch (e) {
      showToast(parseApiError(e, "Could not load slash command config."), "error");
    }
  })();

  grid.appendChild(card1);
  grid.appendChild(card2);
  grid.appendChild(cardSlash);
  container.appendChild(grid);
}
