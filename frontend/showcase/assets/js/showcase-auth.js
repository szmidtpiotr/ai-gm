/* #915 W14 — Unified auth on the showcase.
 *
 * The showcase and the game (/graj/) share one origin, so they share
 * localStorage. This module logs in/registers against the SAME game auth
 * endpoints (/api/auth/*) and writes the SAME localStorage keys the ŻAR client
 * reads (aigm_access_token / aigm_refresh_token / aigm_user_v2). Result: a
 * session started on the showcase IS the game session — "Graj" lands logged in,
 * and no second account system exists.
 *
 * Exposes window.AIGMAuth: { token(), user(), isLoggedIn(), onChange(cb),
 * openLogin(), logout() }.
 */
(function () {
  const ACCESS = "aigm_access_token";
  const REFRESH = "aigm_refresh_token";
  const USER = "aigm_user_v2";
  const listeners = [];

  const token = () => localStorage.getItem(ACCESS);
  function user() {
    try { return JSON.parse(localStorage.getItem(USER) || "null"); }
    catch { return null; }
  }
  const isLoggedIn = () => !!token();
  const onChange = (cb) => { listeners.push(cb); cb(user()); };
  const emit = () => listeners.forEach((cb) => cb(user()));

  function store(payload) {
    localStorage.setItem(ACCESS, payload.access_token);
    if (payload.refresh_token) localStorage.setItem(REFRESH, payload.refresh_token);
    // Shape must match ŻAR CurrentUser so the game hydrates the same session.
    const u = {
      id: payload.user_id,
      username: payload.username,
      email: payload.email,
      displayName: payload.display_name || undefined,
      isAdmin: !!payload.is_admin,
      isTester: !!payload.is_tester,
      role: payload.role,
    };
    localStorage.setItem(USER, JSON.stringify(u));
    emit();
  }

  function logout() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    localStorage.removeItem(USER);
    emit();
  }

  async function post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      throw new Error(data.detail || data.error || "Nie udało się. Sprawdź dane i spróbuj ponownie.");
    }
    return data;
  }

  // ── modal ──────────────────────────────────────────────────────────────────
  let overlay;
  function buildModal() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.className = "auth-overlay";
    overlay.innerHTML = `
      <div class="auth-modal" role="dialog" aria-modal="true">
        <button class="auth-x" aria-label="Zamknij">✕</button>
        <div class="auth-tabs">
          <button data-tab="login" class="active">Zaloguj</button>
          <button data-tab="register">Załóż konto</button>
        </div>
        <form class="auth-form">
          <label>Nazwa gracza<input name="username" autocomplete="username" required></label>
          <label class="auth-email" hidden>E-mail<input name="email" type="email" autocomplete="email"></label>
          <label>Hasło<input name="password" type="password" autocomplete="current-password" required></label>
          <label class="auth-invite" hidden>Kod zaproszenia<input name="invite_code"></label>
          <p class="auth-err" hidden></p>
          <button type="submit" class="btn btn-gold auth-submit">Zaloguj</button>
        </form>
        <p class="auth-hint">Konto działa też w grze — logujesz się raz.</p>
      </div>`;
    document.body.appendChild(overlay);

    const close = () => (overlay.style.display = "none");
    overlay.querySelector(".auth-x").onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };

    let mode = "login";
    const form = overlay.querySelector(".auth-form");
    const err = overlay.querySelector(".auth-err");
    const emailWrap = overlay.querySelector(".auth-email");
    const inviteWrap = overlay.querySelector(".auth-invite");
    const submit = overlay.querySelector(".auth-submit");

    overlay.querySelectorAll(".auth-tabs button").forEach((b) => {
      b.onclick = () => {
        mode = b.dataset.tab;
        overlay.querySelectorAll(".auth-tabs button").forEach((x) => x.classList.toggle("active", x === b));
        const reg = mode === "register";
        emailWrap.hidden = !reg;
        inviteWrap.hidden = !reg;
        submit.textContent = reg ? "Załóż konto" : "Zaloguj";
        err.hidden = true;
      };
    });

    form.onsubmit = async (e) => {
      e.preventDefault();
      err.hidden = true;
      submit.disabled = true;
      const fd = new FormData(form);
      const username = (fd.get("username") || "").trim();
      const password = fd.get("password") || "";
      try {
        if (mode === "login") {
          store(await post("/api/auth/login", { username, password }));
        } else {
          const data = await post("/api/auth/register", {
            username,
            password,
            email: (fd.get("email") || "").trim(),
            invite_code: (fd.get("invite_code") || "").trim() || undefined,
          });
          // register may or may not return tokens; if not, log in right after
          if (data.access_token) store(data);
          else store(await post("/api/auth/login", { username, password }));
        }
        close();
      } catch (ex) {
        err.textContent = ex.message;
        err.hidden = false;
      } finally {
        submit.disabled = false;
      }
    };
    return overlay;
  }

  function openLogin() {
    buildModal().style.display = "flex";
  }

  window.AIGMAuth = { token, user, isLoggedIn, onChange, openLogin, logout };
})();
