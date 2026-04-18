window.bootstrap = async function () {
  try {
    if (typeof window.cleanupAbandonedWizardFromSession === 'function') {
      await window.cleanupAbandonedWizardFromSession();
    }

    if (typeof window.initLlmProviderControls === 'function') {
      await window.initLlmProviderControls();
    }

    if (typeof window.loadMechanicMetadata === 'function') {
      await window.loadMechanicMetadata();
    }

    window.bindEvents();
    if (typeof window.initArchiveToggle === 'function') {
      window.initArchiveToggle();
    }
    await window.loadTranslations('pl');
    await window.loadCampaigns();
    if (typeof window.initLlmSettingsCollapse === 'function') {
      window.initLlmSettingsCollapse();
    }

    const userId = window.state?.playerUserId || 1;
    try {
      if (typeof window.loadUserLlmSettings === 'function') {
        await window.loadUserLlmSettings(userId);
      }
    } catch (e) {
      console.warn('User LLM settings load failed:', e);
    }

    if (window.state.selectedCampaignId) {
      const { systemSelectEl, engineSelectEl } = window.getEls();
      const campaign = window.currentCampaign();

      if (campaign?.system_id) {
        systemSelectEl.value = campaign.system_id;
      }

      await window.loadCharacters(window.state.selectedCampaignId);

      await window.loadHealth(userId);
      await window.loadModels(userId);
      window.syncLlmControlsCollapseToCurrentState?.();

      // If user settings did not populate, fall back to campaign model.
      if (!window.state.selectedEngine && campaign?.model_id) {
        window.state.selectedEngine = campaign.model_id;
        engineSelectEl.value = window.state.selectedEngine;
      }

      try {
        await window.loadTurns(window.state.selectedCampaignId);
      } catch (e) {
        console.warn('History load skipped:', e);
      }
    } else {
      await window.loadHealth(userId);
      await window.loadModels(userId);
      window.syncLlmControlsCollapseToCurrentState?.();
    }

    window.updateUiState();

    if (!window.state.turns || window.state.turns.length === 0) {
      window.addMessage({
        speaker: 'System',
        text: window.t('system.ready'),
        role: 'system'
      });
    }
  } catch (e) {
    window.addMessage({
      speaker: 'Błąd',
      text: `Bootstrap failed: ${e.message}`,
      role: 'error'
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  window.initPlayerAuthGate();
});

window.PLAYER_AUTH_STORAGE_KEY = "ai-gm:playerAuth";

window._getStoredPlayerUserId = function () {
  try {
    const raw = localStorage.getItem(window.PLAYER_AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const uid = parsed?.user_id ?? parsed?.userId;
    const n = Number(uid);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch (_err) {
    return null;
  }
};

window._setStoredPlayerUserId = function (userId) {
  localStorage.setItem(window.PLAYER_AUTH_STORAGE_KEY, JSON.stringify({ user_id: Number(userId) }));
};

window._setAuthedUiVisible = function (authed) {
  const gameAppEl = document.getElementById("game-app");
  const overlayEl = document.getElementById("auth-overlay");
  if (!gameAppEl || !overlayEl) return;
  if (authed) {
    overlayEl.style.display = "none";
    overlayEl.setAttribute("aria-hidden", "true");
    gameAppEl.style.display = "block";
  } else {
    overlayEl.style.display = "flex";
    overlayEl.setAttribute("aria-hidden", "false");
    gameAppEl.style.display = "none";
  }
};

window.initPlayerAuthGate = async function () {
  // Early UI setup: block everything until logged in.
  const storedUserId = window._getStoredPlayerUserId();
  const loginBtn = document.getElementById("player-login-btn");
  const statusEl = document.getElementById("player-login-status");
  const usernameEl = document.getElementById("player-username");
  const passwordEl = document.getElementById("player-password");
  const logoutBtn = document.getElementById("player-logout-btn");

  const setLogoutVisible = function (visible) {
    if (!logoutBtn) return;
    logoutBtn.style.display = visible ? "inline-flex" : "none";
  };

  if (logoutBtn) {
    logoutBtn.onclick = () => {
      try {
        localStorage.removeItem(window.PLAYER_AUTH_STORAGE_KEY);
      } catch (_err) {}

      if (window.__healthIntervalId) {
        clearInterval(window.__healthIntervalId);
        window.__healthIntervalId = null;
      }

      window.state = window.state || {};
      window.state.playerUserId = null;
      window._setAuthedUiVisible(false);

      window.location.reload();
    };
  }

  if (!loginBtn || !statusEl || !usernameEl || !passwordEl) {
    // Fail-open: if markup is missing, keep app usable.
    window.bootstrap();
    if (typeof window.initActionPopup === "function") window.initActionPopup();
    return;
  }

  if (storedUserId) {
    window.state = window.state || {};
    window.state.playerUserId = storedUserId;

    if (window.getLlmControlsCollapsedPref && window.getLlmControlsCollapsedPref() === null) {
      localStorage.setItem(window.LLM_SETTINGS_COLLAPSE_PREF_KEY, "1");
    }

    window._setAuthedUiVisible(true);
    setLogoutVisible(true);
    window.bootstrap();
    if (typeof window.initActionPopup === "function") window.initActionPopup();

    // Start LLM health ticker only after login.
    if (!window.__healthIntervalId) {
      window.__healthIntervalId = setInterval(() => window.loadHealth(window.state.playerUserId || null), 15000);
    }
    return;
  }

  window._setAuthedUiVisible(false);
  setLogoutVisible(false);

  loginBtn.onclick = async () => {
    try {
      statusEl.textContent = "Connecting...";
      const username = (usernameEl.value || "").trim();
      const password = passwordEl.value || "";
      if (!username || !password) {
        statusEl.textContent = "Username and password are required.";
        return;
      }

      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);

      const userId = data.user_id;
      if (!userId) throw new Error("Login succeeded but user_id missing.");

      window.state = window.state || {};
      window.state.playerUserId = Number(userId);
      window._setStoredPlayerUserId(userId);

      if (window.getLlmControlsCollapsedPref && window.getLlmControlsCollapsedPref() === null) {
        localStorage.setItem(window.LLM_SETTINGS_COLLAPSE_PREF_KEY, "1");
      }

      window._setAuthedUiVisible(true);
      setLogoutVisible(true);
      statusEl.textContent = "";

      window.bootstrap();
      if (typeof window.initActionPopup === "function") window.initActionPopup();

      if (!window.__healthIntervalId) {
        window.__healthIntervalId = setInterval(() => window.loadHealth(window.state.playerUserId || null), 15000);
      }
    } catch (err) {
      statusEl.textContent = err.message || "Login failed.";
    }
  };
};