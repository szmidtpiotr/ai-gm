import { adminFetch, APIError } from "/admin_panel/shared/api.js";
import { getBaseUrl, getToken } from "/admin_panel/shared/auth.js";
import { showToast } from "/admin_panel/shared/toast.js";
import { showConfirm } from "/admin_panel/shared/table.js";

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

function normBase() {
  return String(getBaseUrl() || "").replace(/\/+$/, "");
}

function emitFetchLog(path, method, ok, status) {
  const now = Date.now();
  window.dispatchEvent(
    new CustomEvent("admin-fetch", {
      detail: {
        path,
        method: (method || "GET").toUpperCase(),
        ok,
        status,
        url: "",
        startedAt: now,
        endedAt: now,
      },
    }),
  );
}

/**
 * @param {string} path
 * @param {{ method?: string, body?: BodyInit, headers?: Record<string, string> }} [opts]
 */
async function authBlobFetch(path, opts = {}) {
  const base = normBase();
  if (!base) {
    throw new Error("Not connected");
  }
  const url = `${base}${String(path).startsWith("/") ? path : `/${path}`}`;
  const headers = { ...(opts.headers || {}) };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const method = opts.method || "GET";
  const resp = await fetch(url, { ...opts, method, headers });
  emitFetchLog(path, method, resp.ok, resp.status);
  return resp;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail) {
    const d = err.body.detail;
    return Array.isArray(d) ? d.join("; ") : String(d);
  }
  return fallback;
}

function lokiSourceBadge(data) {
  const stored = String(data.stored || "").trim();
  const env = String(data.from_env || "").trim();
  if (stored) {
    return "db";
  }
  if (env) {
    return "env";
  }
  return "default";
}

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  container.innerHTML = "";
  container.classList.add("technical-section");

  const tabs = el("div", "sub-tabs technical-sub-tabs");
  const ids = [
    { id: "obs", label: "Observability" },
    { id: "db", label: "DB Info" },
    { id: "health", label: "Health" },
    { id: "backup", label: "Backup" },
  ];
  const tabBtns = new Map();
  const panels = new Map();
  ids.forEach((t) => {
    const b = el("button", "sub-tab-btn", t.label);
    b.type = "button";
    b.dataset.techTab = t.id;
    tabs.appendChild(b);
    tabBtns.set(t.id, b);
    const p = el("div", "technical-sub-panel");
    p.dataset.techTab = t.id;
    p.hidden = true;
    panels.set(t.id, p);
  });
  container.appendChild(tabs);
  const body = el("div", "technical-body");
  ids.forEach((t) => body.appendChild(panels.get(t.id)));
  container.appendChild(body);

  let activeId = "obs";
  /** @type {ReturnType<typeof setInterval> | null} */
  let healthTimer = null;
  let healthAuto = true;

  function clearHealthTimer() {
    if (healthTimer) {
      clearInterval(healthTimer);
      healthTimer = null;
    }
  }

  function mountObservability(host) {
    host.innerHTML = "";
    const card = el("div", "admin-card");
    const h3 = el("h3", "admin-card-title", "Loki Log Forwarding");
    card.appendChild(h3);

    const infoWrap = el("div", "admin-readonly-table-wrap");
    const tbl = el("table", "admin-table loki-info-table");
    const tb = el("tbody");
    card.appendChild(infoWrap);
    infoWrap.appendChild(tbl);
    tbl.appendChild(tb);

    const overrideLabel = el("label", "field-label", "Override URL");
    const input = el("input", "technical-url-input");
    input.type = "url";
    input.placeholder = "http://loki:3100";
    const helper = el("p", "muted technical-helper", "Leave empty to use LOKI_URL env variable.");
    const btnRow = el("div", "technical-btn-row");
    const saveBtn = el("button", "primary-btn", "Save");
    saveBtn.type = "button";
    const clearBtn = el("button", "secondary-btn", "Clear");
    clearBtn.type = "button";
    btnRow.appendChild(saveBtn);
    btnRow.appendChild(clearBtn);

    card.appendChild(overrideLabel);
    card.appendChild(input);
    card.appendChild(helper);
    card.appendChild(btnRow);
    host.appendChild(card);

    function row(label, value) {
      const tr = el("tr");
      tr.appendChild(el("td", "loki-row-label", label));
      tr.appendChild(el("td", "", value));
      return tr;
    }

    function rowBadge(label, value, badge) {
      const tr = el("tr");
      tr.appendChild(el("td", "loki-row-label", label));
      const td = el("td", "");
      td.appendChild(document.createTextNode(String(value)));
      td.appendChild(document.createTextNode(" "));
      const sp = el("span", "loki-source-badge", badge);
      td.appendChild(sp);
      tr.appendChild(td);
      return tr;
    }

    async function load() {
      try {
        const data = await adminFetch("/api/admin/settings/loki");
        tb.innerHTML = "";
        tb.appendChild(row("Stored URL", data.stored ? String(data.stored) : "—"));
        tb.appendChild(row("Env URL", data.from_env ? String(data.from_env) : "—"));
        const eff = String(data.loki_url || "").trim() || "—";
        const src = lokiSourceBadge(data);
        tb.appendChild(rowBadge("Effective URL", eff, src));
        input.value = String(data.stored || "");
      } catch (e) {
        showToast(parseApiError(e, "Failed to load Loki settings."), "error");
      }
    }

    saveBtn.addEventListener("click", async () => {
      try {
        await adminFetch("/api/admin/settings/loki", {
          method: "PUT",
          body: JSON.stringify({ loki_url: input.value.trim() }),
        });
        showToast("Loki URL saved.", "success");
        await load();
      } catch (e) {
        showToast(parseApiError(e, "Save failed."), "error");
      }
    });

    clearBtn.addEventListener("click", async () => {
      try {
        await adminFetch("/api/admin/settings/loki", {
          method: "PUT",
          body: JSON.stringify({ loki_url: "" }),
        });
        showToast("Cleared — using env/default", "success");
        await load();
      } catch (e) {
        showToast(parseApiError(e, "Clear failed."), "error");
      }
    });

    void load();
  }

  function mountDbInfo(host) {
    host.innerHTML = "";
    const grid = el("div", "two-col-cards");

    const card1 = el("div", "admin-card");
    card1.appendChild(el("h3", "admin-card-title", "Database Stats"));
    const statsHost = el("div", "db-stats-host");
    const refBtn = el("button", "secondary-btn", "🔄 Refresh");
    refBtn.type = "button";
    const migBtn = el("button", "primary-btn", "▶ Run Migrations");
    migBtn.type = "button";
    const dbBtnRow = el("div", "technical-btn-row");
    dbBtnRow.appendChild(refBtn);
    dbBtnRow.appendChild(migBtn);
    card1.appendChild(statsHost);
    card1.appendChild(dbBtnRow);

    const card2 = el("div", "admin-card");
    card2.appendChild(el("h3", "admin-card-title", "Tables"));
    const tablesHost = el("div", "tables-host");
    card2.appendChild(tablesHost);

    grid.appendChild(card1);
    grid.appendChild(card2);
    host.appendChild(grid);

    async function load() {
      try {
        const data = await adminFetch("/api/admin/db/info");
        statsHost.innerHTML = "";
        const mb = (Number(data.db_size_bytes) / 1024 / 1024).toFixed(2);
        statsHost.appendChild(el("p", "", `DB Path: ${data.db_path}`));
        statsHost.appendChild(el("p", "", `File Size: ${mb} MB`));
        statsHost.appendChild(el("p", "", `SQLite Version: ${data.sqlite_version || "—"}`));

        tablesHost.innerHTML = "";
        const wrap = el("div", "admin-table-wrap");
        const tbl = el("table", "admin-table db-table");
        const thead = el("thead");
        const hr = el("tr");
        hr.appendChild(el("th", "", "Table Name"));
        hr.appendChild(el("th", "", "Row Count"));
        thead.appendChild(hr);
        tbl.appendChild(thead);
        const tb = el("tbody");
        const items = [...(data.tables || [])].sort((a, b) => String(a.name).localeCompare(String(b.name)));
        items.forEach((t) => {
          const tr = el("tr");
          if (Number(t.row_count) === 0) {
            tr.classList.add("db-table-row-zero");
          }
          tr.appendChild(el("td", "db-table-name", String(t.name)));
          tr.appendChild(el("td", "", String(t.row_count)));
          tb.appendChild(tr);
        });
        tbl.appendChild(tb);
        wrap.appendChild(tbl);
        tablesHost.appendChild(wrap);
      } catch (e) {
        showToast(parseApiError(e, "Failed to load DB info."), "error");
      }
    }

    refBtn.addEventListener("click", () => void load());

    migBtn.addEventListener("click", async () => {
      const label = migBtn.textContent;
      migBtn.disabled = true;
      migBtn.textContent = "⏳";
      try {
        await adminFetch("/api/admin/db/migrate", { method: "POST" });
        showToast("Migrations complete.", "success");
      } catch (e) {
        showToast(parseApiError(e, "Migrations failed."), "error");
      } finally {
        migBtn.disabled = false;
        migBtn.textContent = label;
      }
    });

    void load();
  }

  function mountHealth(host) {
    clearHealthTimer();
    host.innerHTML = "";
    healthAuto = true;
    const pauseBtn = el("button", "secondary-btn", "⏸ Pause");
    pauseBtn.type = "button";
    const topRow = el("div", "technical-health-toolbar");
    topRow.appendChild(pauseBtn);
    host.appendChild(topRow);

    const grid = el("div", "two-col-cards");
    const llmCard = el("div", "admin-card health-card");
    const lokiCard = el("div", "admin-card health-card");
    llmCard.appendChild(el("h3", "admin-card-title", "LLM"));
    lokiCard.appendChild(el("h3", "admin-card-title", "Loki"));
    const llmBody = el("div", "health-card-body");
    const lokiBody = el("div", "health-card-body");
    llmCard.appendChild(llmBody);
    lokiCard.appendChild(lokiBody);
    grid.appendChild(llmCard);
    grid.appendChild(lokiCard);
    host.appendChild(grid);

    const ts = el("p", "muted health-last-checked", "");
    host.appendChild(ts);

    function dotClass(reachable, configured) {
      if (configured === false && reachable == null) {
        return "grey";
      }
      if (reachable === true) {
        return "green";
      }
      if (reachable === false) {
        return "red";
      }
      return "grey";
    }

    async function tick() {
      const base = normBase();
      if (!base) {
        return;
      }
      try {
        const resp = await fetch(`${base}/api/health`);
        emitFetchLog("/api/health", "GET", resp.ok, resp.status);
        const data = resp.ok ? await resp.json() : null;
        const now = new Date();
        ts.textContent = `Last checked: ${now.toLocaleTimeString()}`;

        llmBody.innerHTML = "";
        lokiBody.innerHTML = "";

        if (!data) {
          llmBody.appendChild(el("p", "muted", "Health request failed."));
          return;
        }

        const llm = data.llm || {};
        const d1 = el("span", `svc-status-dot ${dotClass(llm.reachable, true)}`);
        llmBody.appendChild(d1);
        llmBody.appendChild(el("p", "", `Provider: ${llm.provider ?? "—"}`));
        if (llm.model != null) {
          llmBody.appendChild(el("p", "", `Model: ${llm.model}`));
        }
        if (llm.base_url) {
          llmBody.appendChild(el("p", "", `Base URL: ${llm.base_url}`));
        }
        llmBody.appendChild(el("p", "", `Reachable: ${llm.reachable === true ? "yes" : llm.reachable === false ? "no" : "unknown"}`));
        if (llm.reachable === false && llm.error) {
          const er = el("p", "health-error-small", String(llm.error));
          llmBody.appendChild(er);
        }

        const loki = data.loki || {};
        const d2 = el("span", `svc-status-dot ${dotClass(loki.reachable, loki.configured)}`);
        lokiBody.appendChild(d2);
        lokiBody.appendChild(
          el("p", "", `Configured: ${loki.configured ? "yes" : "no"}`),
        );
        lokiBody.appendChild(
          el(
            "p",
            "",
            `Reachable: ${loki.reachable === true ? "yes" : loki.reachable === false ? "no" : "unknown"}`,
          ),
        );
        if (loki.url) {
          lokiBody.appendChild(el("p", "", `URL: ${loki.url}`));
        }
        if (loki.source) {
          lokiBody.appendChild(el("p", "", `Source: ${loki.source}`));
        }
        if (!loki.configured) {
          lokiBody.appendChild(el("p", "muted", "Not configured — logs go to stdout only"));
        }
        if (loki.reachable === false && loki.error) {
          lokiBody.appendChild(el("p", "health-error-small", String(loki.error)));
        }
      } catch (_e) {
        ts.textContent = "Last checked: (error)";
      }
    }

    function startTimer() {
      clearHealthTimer();
      if (!healthAuto) {
        return;
      }
      healthTimer = setInterval(() => void tick(), 30000);
    }

    pauseBtn.addEventListener("click", () => {
      healthAuto = !healthAuto;
      pauseBtn.textContent = healthAuto ? "⏸ Pause" : "▶ Resume";
      if (healthAuto) {
        void tick();
        startTimer();
      } else {
        clearHealthTimer();
      }
    });

    void tick();
    startTimer();
  }

  function mountBackup(host) {
    host.innerHTML = "";
    const grid = el("div", "two-col-cards");

    const c1 = el("div", "admin-card");
    c1.appendChild(el("h3", "admin-card-title", "Download Backup"));
    const w1 = el("div", "warning-banner warning-banner-orange");
    w1.textContent = "⚠️ Always backup before bulk edits, imports, or restore operations.";
    c1.appendChild(w1);
    const dl = el("button", "primary-btn", "⬇ Download DB Backup");
    dl.type = "button";
    dl.addEventListener("click", async () => {
      try {
        const resp = await authBlobFetch("/api/admin/db/backup");
        if (!resp.ok) {
          let msg = `HTTP ${resp.status}`;
          try {
            const j = await resp.json();
            if (j.detail) {
              msg = String(j.detail);
            }
          } catch (_e) {
            /* ignore */
          }
          throw new Error(msg);
        }
        const blob = await resp.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `ai_gm_backup_${Date.now()}.db`;
        a.click();
        URL.revokeObjectURL(blobUrl);
        showToast("Download started", "success");
      } catch (e) {
        showToast(e.message || "Download failed.", "error");
      }
    });
    c1.appendChild(dl);

    const c2 = el("div", "admin-card");
    c2.appendChild(el("h3", "admin-card-title", "Restore from File"));
    const w2 = el("div", "warning-banner warning-banner-red");
    w2.textContent =
      "🚨 Restoring will REPLACE the current database. This cannot be undone. The backend may need to be restarted after restore.";
    c2.appendChild(w2);
    const fileInp = el("input", "");
    fileInp.type = "file";
    fileInp.accept = ".db";
    const upBtn = el("button", "primary-btn danger-btn", "🔁 Upload & Restore");
    upBtn.type = "button";
    upBtn.disabled = true;
    fileInp.addEventListener("change", () => {
      upBtn.disabled = !fileInp.files || !fileInp.files.length;
    });
    upBtn.addEventListener("click", async () => {
      const f = fileInp.files && fileInp.files[0];
      if (!f) {
        return;
      }
      const ok = await showConfirm(
        "Are you sure? This will replace the live database with the uploaded file.",
        { dangerous: true },
      );
      if (!ok) {
        return;
      }
      const label = upBtn.textContent;
      upBtn.disabled = true;
      upBtn.textContent = "⏳";
      try {
        const fd = new FormData();
        fd.append("file", f);
        await adminFetch("/api/admin/db/restore", { method: "POST", body: fd });
        showToast("Database restored. Consider restarting the backend.", "success");
        fileInp.value = "";
        upBtn.disabled = true;
      } catch (e) {
        showToast(parseApiError(e, "Restore failed."), "error");
      } finally {
        upBtn.textContent = label;
        upBtn.disabled = !fileInp.files || !fileInp.files.length;
      }
    });
    c2.appendChild(fileInp);
    c2.appendChild(upBtn);

    grid.appendChild(c1);
    grid.appendChild(c2);
    host.appendChild(grid);
  }

  function activate(id) {
    const prev = activeId;
    if (prev === "health" && id !== "health") {
      clearHealthTimer();
    }
    activeId = id;
    tabBtns.forEach((btn, tid) => {
      btn.classList.toggle("active", tid === id);
    });
    panels.forEach((p, tid) => {
      p.hidden = tid !== id;
    });
    const host = panels.get(id);
    if (!host) {
      return;
    }
    host.innerHTML = "";
    if (id === "obs") {
      mountObservability(host);
    } else if (id === "db") {
      mountDbInfo(host);
    } else if (id === "health") {
      mountHealth(host);
    } else if (id === "backup") {
      mountBackup(host);
    }
  }

  tabs.addEventListener("click", (e) => {
    const b = e.target.closest(".sub-tab-btn");
    if (!b || !b.dataset.techTab) {
      return;
    }
    activate(b.dataset.techTab);
  });

  activate("obs");
}
