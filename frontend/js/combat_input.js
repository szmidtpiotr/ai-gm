/**
 * Phase 8C — combat-aware chat composer (textarea + composer combat buttons).
 */
(function () {
  class CombatInput {
    constructor() {
      this._textarea = null;
      this._sendBtn = null;
      this._combatSendSlot = null;
      this._btnAttack = null;
      this._btnFlee = null;
      this._enemyTurnInFlight = false;
      this._defaultPlaceholder = "Wpisz /sheet albo opisz akcję...";
      this._inited = false;
    }

    _campaignId() {
      return window.state?.selectedCampaignId ? Number(window.state.selectedCampaignId) : null;
    }

    _getDefaultPlaceholder() {
      return this._defaultPlaceholder;
    }

    init() {
      if (this._inited) return;
      this._textarea = document.getElementById("input");
      if (!this._textarea) return;

      const ph = (this._textarea.getAttribute("placeholder") || "").trim();
      if (ph) this._defaultPlaceholder = ph;

      this._sendBtn = document.getElementById("send-btn");
      this._combatSendSlot = document.getElementById("composer-combat-send-slot");
      this._btnAttack = document.getElementById("composer-combat-attack");
      this._btnFlee = document.getElementById("composer-combat-flee");

      if (this._btnAttack) {
        this._btnAttack.addEventListener("click", () => {
          if (window.combatPanel && typeof window.combatPanel._onAttack === "function") {
            window.combatPanel._onAttack();
          }
        });
      }
      if (this._btnFlee) {
        this._btnFlee.addEventListener("click", () => {
          if (window.combatPanel && typeof window.combatPanel._onFlee === "function") {
            window.combatPanel._onFlee();
          }
        });
      }

      this._inited = true;
    }

    _setComposerCombatMode(on) {
      if (this._sendBtn) {
        this._sendBtn.style.display = on ? "none" : "";
      }
      if (this._combatSendSlot) {
        if (on) {
          this._combatSendSlot.style.display = "flex";
          this._combatSendSlot.setAttribute("aria-hidden", "false");
        } else {
          this._combatSendSlot.style.display = "none";
          this._combatSendSlot.setAttribute("aria-hidden", "true");
        }
      }
    }

    /**
     * Show/hide Postać (fluff) and combat slot in the sheet sidebar during active combat.
     */
    _syncSheetChrome(cs) {
      const fluff = document.querySelector(".sheet-fluff");
      const slot = document.getElementById("combat-panel-slot");
      const active = cs && String(cs.status) === "active";
      if (fluff) {
        fluff.style.display = active ? "none" : "";
      }
      if (slot) {
        if (active) {
          slot.style.setProperty("display", "block");
          slot.setAttribute("aria-hidden", "false");
        } else {
          slot.style.setProperty("display", "none");
          slot.setAttribute("aria-hidden", "true");
        }
      }
    }

    /** Same as _syncSheetChrome; callable from api.js after GET /combat. */
    applySheetCombatChrome(cs) {
      this._syncSheetChrome(cs);
    }

    syncWithCombat(combatState) {
      this.init();
      try {
        if (!this._textarea) return;

        const cs = combatState;
        if (!cs || String(cs.status || "") === "ended") {
          this._textarea.disabled = false;
          this._textarea.placeholder = this._getDefaultPlaceholder();
          this._setComposerCombatMode(false);
          return;
        }

        if (String(cs.status) !== "active") {
          this._textarea.disabled = false;
          this._textarea.placeholder = this._getDefaultPlaceholder();
          this._setComposerCombatMode(false);
          return;
        }

        const cur = String(cs.current_turn || "");
        if (cur === "player") {
          this._textarea.disabled = false;
          this._textarea.placeholder = "Opisz akcję lub użyj przycisków poniżej...";
          this._setComposerCombatMode(true);
          return;
        }

        this._textarea.disabled = true;
        this._textarea.placeholder = "Tura wroga — czekaj...";
        this._setComposerCombatMode(false);
        this._triggerEnemyTurnFromInput();
      } finally {
        this._syncSheetChrome(combatState);
      }
    }

    async _triggerEnemyTurnFromInput() {
      if (this._enemyTurnInFlight) return;
      const cid = this._campaignId();
      if (!cid) return;

      this._enemyTurnInFlight = true;
      try {
        const resp = await fetch(`/api/campaigns/${cid}/combat/enemy-turn`, {
          method: "POST",
          headers: window.getApiHeaders
            ? window.getApiHeaders()
            : { "Content-Type": "application/json" },
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          throw new Error(
            typeof data.detail === "string" ? data.detail : `HTTP ${resp.status}`
          );
        }

        if (data.message && data.hit === undefined && data.combat_state) {
          this.syncWithCombat(data.combat_state);
          return;
        }

        const cs = data.combat_state || null;
        if (window.combatPanel && typeof window.combatPanel.render === "function" && cs) {
          window.combatPanel.render(cs);
        }

        if (typeof window.refreshCombatLogTurns === "function") {
          await window.refreshCombatLogTurns(cid);
        }

        this.syncWithCombat(cs);

        if (
          typeof window.loadCharacterSheet === "function" &&
          window.state.selectedCharacterId
        ) {
          await window.loadCharacterSheet(window.state.selectedCharacterId);
        }

        if (data.player_incapacitated && window.combatPanel?._triggerDeathSavePrompt) {
          window.combatPanel._triggerDeathSavePrompt();
        }
      } catch (e) {
        const msg = e && e.message ? e.message : "Błąd tury wroga";
        if (this._textarea) {
          this._textarea.disabled = false;
          this._textarea.placeholder = this._getDefaultPlaceholder();
        }
        this._setComposerCombatMode(false);
        if (typeof window.addMessage === "function") {
          window.addMessage({
            speaker: "System",
            text: `Walka: ${msg}`,
            role: "error",
          });
        }
      } finally {
        this._enemyTurnInFlight = false;
      }
    }
  }

  window.CombatInput = CombatInput;
  window.combatInput = new CombatInput();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.combatInput.init());
  } else {
    window.combatInput.init();
  }
})();
