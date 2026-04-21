/**
 * Phase 8B — combat UI (solo). Uses /api/campaigns/:id/combat/* endpoints.
 */
(function () {
  const esc = (s) => (window.escapeHtml ? window.escapeHtml(String(s ?? "")) : String(s ?? ""));

  function hpTier(pct) {
    if (pct > 50) return "high";
    if (pct > 25) return "mid";
    return "low";
  }

  function lootIcon(entry) {
    const t = String(entry?.source_type || "");
    if (t === "weapon") return "⚔️";
    if (t === "consumable") return "🧪";
    return "📦";
  }

  function lootLabel(entry) {
    const k = String(entry?.source_key || "?");
    return k.replace(/_/g, " ");
  }

  class CombatPanel {
    constructor() {
      this._state = null;
      this._accumulatedLoot = [];
      this._busy = false;
      this._host = null;
      this._card = null;
      this._bodyEl = null;
      this._actionsEl = null;
      this._msgEl = null;
      this._enemyOverlay = null;
      this._lootLayer = null;
      this._endLayer = null;
    }

    _campaignId() {
      return window.state?.selectedCampaignId ? Number(window.state.selectedCampaignId) : null;
    }

    ensureDom() {
      const slot = document.getElementById("combat-panel-slot");
      if (!slot) return;

      this._host = document.getElementById("combat-panel-host");
      if (!this._host) {
        this._host = document.createElement("div");
        this._host.id = "combat-panel-host";
        this._host.className = "combat-panel-host combat-panel-host--hidden";
        this._host.setAttribute("aria-live", "polite");
        slot.appendChild(this._host);
      } else if (!slot.contains(this._host)) {
        slot.appendChild(this._host);
      }

      if (this._card) return;

      this._host.innerHTML = `
        <div class="combat-panel-card" hidden>
          <div class="combat-panel-header">
            <h2 class="combat-panel-title">Walka</h2>
            <span class="combat-panel-meta" id="combat-panel-meta"></span>
          </div>
          <div class="combat-panel-body" id="combat-panel-body"></div>
          <div class="combat-msg" id="combat-panel-msg" style="display:none;"></div>
          <div class="combat-actions" id="combat-panel-actions">
            <button type="button" class="combat-btn combat-btn--attack" id="combat-btn-attack">Atak</button>
            <button type="button" class="combat-btn combat-btn--flee" id="combat-btn-flee">Ucieczka</button>
            <button type="button" class="combat-btn combat-btn--item" id="combat-btn-item" disabled>Przedmiot</button>
          </div>
          <div class="combat-enemy-turn-overlay" id="combat-enemy-overlay" style="display:none;" aria-hidden="true">
            <span class="combat-enemy-turn-label">ENEMY TURN</span>
          </div>
        </div>
      `;

      this._card = this._host.querySelector(".combat-panel-card");
      this._bodyEl = this._host.querySelector("#combat-panel-body");
      this._msgEl = this._host.querySelector("#combat-panel-msg");
      this._actionsEl = this._host.querySelector("#combat-panel-actions");
      this._enemyOverlay = this._host.querySelector("#combat-enemy-overlay");

      const loot = document.createElement("div");
      loot.id = "combat-loot-layer";
      loot.className = "combat-loot-modal";
      loot.style.display = "none";
      loot.setAttribute("aria-hidden", "true");
      document.body.appendChild(loot);
      this._lootLayer = loot;

      const end = document.createElement("div");
      end.id = "combat-end-layer";
      end.className = "combat-end-screen";
      end.style.display = "none";
      end.setAttribute("aria-hidden", "true");
      document.body.appendChild(end);
      this._endLayer = end;

      this._host.querySelector("#combat-btn-attack").onclick = () => this._onAttack();
      this._host.querySelector("#combat-btn-flee").onclick = () => this._onFlee();
    }

    show() {
      this.ensureDom();
      if (!this._host || !this._card) return;
      this._host.classList.remove("combat-panel-host--hidden");
      this._card.hidden = false;
    }

    /** Victory / end-of-combat UI (combat_state.status === "ended"). */
    showVictory(combatState) {
      this.ensureDom();
      if (!combatState) return;
      this._state = combatState;
      this.show();
      this.render(combatState);
    }

    _playerAttackRollDbLine(intent, characterName, d20, mod, total, data) {
      const hit = !!data.hit;
      const dmg = data.damage != null ? Number(data.damage) : null;
      const summary = hit
        ? `Atakuję z wynikiem ${total} — trafiam za ${dmg != null ? dmg : "?"} obrażeń!`
        : `Atakuję z wynikiem ${total} — pudło!`;
      const payload = {
        kind: "player_attack",
        intent: (intent || "").trim(),
        summary_line: summary,
        character_name: characterName,
        attack_label: "ATAK (STR)",
        d20,
        modifiers: [{ name: "STR", value: mod }],
        total,
        hit,
        damage: dmg != null ? dmg : 0,
      };
      return `${window.COMBAT_ROLL_PREFIX}\n${JSON.stringify(payload)}`;
    }

    /**
     * Streams GM narrative for this attack; DB user line is already the combat roll JSON.
     */
    async _sendCombatNarrativeFollowUp(dbUserLine) {
      if (typeof window.sendMessage !== "function") return;
      const { inputEl } = window.getEls ? window.getEls() : {};
      if (inputEl) inputEl.value = "";
      window.__pendingNarrativeUserTextForApi = dbUserLine;
      window.__suppressNextUserBubbleForGm = true;
      await window.sendMessage();
    }

    hide() {
      if (this._host) this._host.classList.add("combat-panel-host--hidden");
      if (this._card) this._card.hidden = true;
      this._hideLoot();
      this._hideEnd();
    }

    _setMsg(text, isError) {
      if (!this._msgEl) return;
      if (!text) {
        this._msgEl.style.display = "none";
        this._msgEl.textContent = "";
        this._msgEl.classList.remove("combat-msg--error");
        return;
      }
      this._msgEl.style.display = "block";
      this._msgEl.textContent = text;
      this._msgEl.classList.toggle("combat-msg--error", !!isError);
    }

    render(combatState) {
      this.ensureDom();
      if (!this._bodyEl || !this._card) return;
      this._state = combatState || null;

      const st = combatState;
      if (!st) {
        this._bodyEl.innerHTML = "";
        return;
      }

      const round = Number(st.round || 1);
      const cur = String(st.current_turn || "");
      const combatants = Array.isArray(st.combatants) ? st.combatants : [];

      const nameById = {};
      combatants.forEach((c) => {
        if (c && c.id != null) nameById[String(c.id)] = c.name || c.id;
      });
      const curLabel = cur === "player" ? "Gracz" : String(nameById[cur] || cur || "—");

      const meta = this._host.querySelector("#combat-panel-meta");
      if (meta) {
        meta.textContent = `Runda ${round} · Tura: ${curLabel}`;
      }

      const rowHtml = (c, isPlayer) => {
        const hp = Number(c.hp_current ?? 0);
        const max = Math.max(1, Number(c.hp_max ?? 1));
        const pct = Math.max(0, Math.min(100, (hp / max) * 100));
        const tier = hpTier(pct);
        const conds = Array.isArray(c.conditions) ? c.conditions.filter(Boolean) : [];
        const condHtml =
          conds.length > 0
            ? `<div class="combat-conditions">${conds
                .map((x) => `<span class="combat-condition-badge">${esc(x)}</span>`)
                .join("")}</div>`
            : "";
        return `
            <div class="combat-combatant" data-cid="${esc(c.id)}">
              <div class="combat-combatant-name">
                <span>${esc(c.name || (isPlayer ? "Bohater" : c.id))}</span>
                <span class="muted" style="font-size:11px;">INI ${esc(c.initiative_roll ?? "—")}</span>
              </div>
              <div class="combat-hp-row"><span>HP</span><span>${hp} / ${max} · DEF ${esc(c.defense ?? "—")}</span></div>
              <div class="combat-hp-bar"><div class="combat-hp-fill combat-hp-fill--${tier}" style="width:${pct.toFixed(
                0
              )}%"></div></div>
              ${condHtml}
            </div>
          `;
      };

      const parts = [];
      const player = combatants.find((x) => x && x.type === "player");
      if (player) parts.push(rowHtml(player, true));

      combatants.forEach((c) => {
        if (!c || c.type !== "enemy") return;
        if (Number(c.hp_current ?? 0) <= 0) return;
        parts.push(rowHtml(c, false));
      });

      this._bodyEl.innerHTML = parts.join("") || '<p class="muted">Brak danych walki.</p>';

      const active = String(st.status || "") === "active";
      const playerTurn = cur === "player";
      const atk = this._host.querySelector("#combat-btn-attack");
      const flee = this._host.querySelector("#combat-btn-flee");
      if (atk) atk.disabled = this._busy || !active || !playerTurn;
      if (flee) flee.disabled = this._busy || !active || !playerTurn;
      const panelActions = this._host.querySelector("#combat-panel-actions");
      if (panelActions) {
        panelActions.style.display = "none";
      }

      if (this._enemyOverlay) {
        const showEnemy = active && cur !== "player" && cur.length > 0;
        this._enemyOverlay.style.display = showEnemy ? "flex" : "none";
        this._enemyOverlay.setAttribute("aria-hidden", showEnemy ? "false" : "true");
      }

      const ended = String(st.status || "") === "ended";
      if (ended) {
        this._showEndScreen(st);
      } else {
        this._hideEnd();
      }
    }

    _showEndScreen(st) {
      const reason = String(st.ended_reason || "");
      if (!this._endLayer) return;
      if (reason === "victory") {
        const items = this._accumulatedLoot.length
          ? this._accumulatedLoot
              .map(
                (L) =>
                  `<li class="combat-loot-row"><span class="combat-loot-icon">${lootIcon(L)}</span><span>${esc(
                    lootLabel(L)
                  )}</span><span class="combat-loot-qty">×${esc(L.qty ?? 1)}</span></li>`
              )
              .join("")
          : '<li class="muted">Brak łupów.</li>';
        this._endLayer.innerHTML = `
          <div class="combat-end-inner combat-end-inner--victory">
            <h3 class="combat-end-title">Zwycięstwo! Wszyscy wrogowie pokonani.</h3>
            <p class="muted" style="margin-top:0;">Łupy z walki:</p>
            <ul class="combat-loot-list">${items}</ul>
            <button type="button" class="combat-primary-btn" id="combat-end-continue-v">Kontynuuj</button>
          </div>`;
        this._endLayer.style.display = "flex";
        this._endLayer.querySelector("#combat-end-continue-v").onclick = () => this._finishEndOverlay();
      } else if (reason === "fled") {
        this._endLayer.innerHTML = `
          <div class="combat-end-inner combat-end-inner--fled">
            <h3 class="combat-end-title">Udało ci się uciec!</h3>
            <button type="button" class="combat-primary-btn" id="combat-end-continue-f">Kontynuuj</button>
          </div>`;
        this._endLayer.style.display = "flex";
        this._endLayer.querySelector("#combat-end-continue-f").onclick = () => this._finishEndOverlay();
      } else if (reason === "player_dead") {
        this._triggerDeathSavePrompt();
        this._endLayer.innerHTML = `
          <div class="combat-end-inner combat-end-inner--defeat">
            <h3 class="combat-end-title">Zostałeś pokonany…</h3>
            <button type="button" class="combat-primary-btn secondary" id="combat-end-continue-d">Kontynuuj</button>
          </div>`;
        this._endLayer.style.display = "flex";
        this._endLayer.querySelector("#combat-end-continue-d").onclick = () => this._finishEndOverlay();
      } else {
        this._hideEnd();
      }
    }

    _finishEndOverlay() {
      this._hideEnd();
      this._accumulatedLoot = [];
      this.hide();
      this._state = null;
    }

    _hideEnd() {
      if (this._endLayer) {
        this._endLayer.style.display = "none";
        this._endLayer.innerHTML = "";
      }
    }

    _hideLoot() {
      if (this._lootLayer) {
        this._lootLayer.style.display = "none";
        this._lootLayer.innerHTML = "";
      }
    }

    _showLootPopup(lootArr, onDismiss) {
      if (!this._lootLayer) return;
      const list = Array.isArray(lootArr) ? lootArr : [];
      const inner =
        list.length === 0
          ? '<p class="muted">Wróg nie miał łupów.</p>'
          : `<ul class="combat-loot-list">${list
              .map(
                (L) =>
                  `<li class="combat-loot-row"><span class="combat-loot-icon">${lootIcon(L)}</span><span>${esc(
                    lootLabel(L)
                  )}</span><span class="combat-loot-qty">×${esc(L.qty ?? 1)}</span></li>`
              )
              .join("")}</ul>`;
      this._lootLayer.innerHTML = `
        <div class="combat-loot-inner">
          <h3 style="margin:0 0 10px;font-size:16px;">Łup</h3>
          ${inner}
          <button type="button" class="combat-primary-btn" id="combat-loot-dismiss">Zamknij</button>
        </div>`;
      this._lootLayer.style.display = "flex";
      this._lootLayer.querySelector("#combat-loot-dismiss").onclick = () => {
        this._hideLoot();
        if (typeof onDismiss === "function") onDismiss();
      };
    }

    _showLootPopupAsync(lootArr) {
      return new Promise((resolve) => {
        this._showLootPopup(lootArr, () => resolve());
      });
    }

    _triggerDeathSavePrompt() {
      if (typeof window.updateActionTriggerBtn !== "function") return;
      window.state.activeRollRequest = {
        skill: "death_save",
        dice: "d20",
        description:
          (typeof window.getTestDescription === "function" && window.getTestDescription("death_save")) ||
          "Rzut obronny przed śmiercią.",
      };
      window.updateActionTriggerBtn(true);
    }

    _pushLoot(loot) {
      if (!Array.isArray(loot) || loot.length === 0) return;
      loot.forEach((x) => {
        if (x) this._accumulatedLoot.push(x);
      });
    }

    async fetchAndMaybeShow() {
      const cid = this._campaignId();
      if (!cid) return;
      try {
        const resp = await fetch(`/api/campaigns/${cid}/combat`);
        if (resp.status === 404) {
          this._state = null;
          this.hide();
          return;
        }
        if (!resp.ok) return;
        const data = await resp.json();
        if (String(data.status) === "active") {
          this.show();
          this.render(data);
        } else {
          this.hide();
        }
      } catch (_e) {
        /* ignore */
      }
    }

    applyCombatInitiated(combatState) {
      if (!combatState) return;
      this._accumulatedLoot = [];
      this.render(combatState);
      this.show();
    }

    async _onFlee() {
      const cid = this._campaignId();
      if (!cid || this._busy) return;
      this._busy = true;
      this._setMsg("");
      const { inputEl } = window.getEls ? window.getEls() : {};
      const intentRaw = inputEl ? String(inputEl.value || "").trim() : "";
      try {
        if (intentRaw && typeof window.addMessage === "function") {
          const tn = typeof window.nextTurnNumber === "function" ? window.nextTurnNumber() : null;
          const nm =
            typeof window.currentCharacterName === "function"
              ? window.currentCharacterName()
              : "Gracz";
          window.addMessage({
            speaker: nm,
            text: `${intentRaw}\n\n— Próbuję uciec z walki!`,
            role: "user",
            route: "input",
            turn: tn,
            createdAt: new Date().toISOString(),
          });
          inputEl.value = "";
        }
        const resp = await fetch(`/api/campaigns/${cid}/combat/flee`, {
          method: "POST",
          headers: window.getApiHeaders ? window.getApiHeaders() : { "Content-Type": "application/json" },
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        this.hide();
        if (typeof window.addMessage === "function") {
          window.addMessage({
            speaker: "System",
            text: "Udało ci się uciec!",
            role: "system",
          });
        }
        this._accumulatedLoot = [];
        this._state = null;
      } catch (e) {
        this._setMsg(e.message || "Ucieczka nie powiodła się.", true);
      } finally {
        this._busy = false;
      }
    }

    async _onAttack() {
      if (!this._state || this._state.status !== "active") {
        this._setMsg("Brak aktywnej walki.", true);
        return;
      }
      if (this._state.current_turn !== "player") {
        this._setMsg("Nie twoja tura.", true);
        return;
      }
      const cid = this._campaignId();
      if (!cid || this._busy) return;
      this._busy = true;
      this._setMsg("");
      if (this._state) this.render(this._state);
      try {
        const { inputEl } = window.getEls ? window.getEls() : {};
        const intentRaw = inputEl ? String(inputEl.value || "").trim() : "";

        if (typeof window.loadCharacterSheet === "function" && window.state.selectedCharacterId) {
          await window.loadCharacterSheet(window.state.selectedCharacterId);
        }
        const sheet = window.state.characterSheet || {};
        const str = Number(sheet.stats?.STR ?? 10);
        const mod = window.getStatModifier ? window.getStatModifier(str) : Math.floor((str - 10) / 2);

        const diceResp = await fetch("/api/gm/dice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dice: "1d20" }),
        });
        if (!diceResp.ok) throw new Error(`Kość: HTTP ${diceResp.status}`);
        const diceData = await diceResp.json();
        const d20 = Number(diceData.total ?? 0);
        const total = d20 + mod;

        const res = await fetch(`/api/campaigns/${cid}/combat/resolve-attack`, {
          method: "POST",
          headers: window.getApiHeaders ? window.getApiHeaders() : { "Content-Type": "application/json" },
          body: JSON.stringify({ roll_result: total, attacker: "player" }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

        const cs = data.combat_state || null;

        if (data.hit) {
          this._setMsg(`Trafienie! ${data.damage ?? "?"} obrażeń`);
        } else {
          this._setMsg("Pudło!");
        }

        if (data.enemy_dead) {
          this._pushLoot(data.loot || []);
        }

        const charName =
          typeof window.currentCharacterName === "function"
            ? window.currentCharacterName()
            : String(sheet.name || "Bohater");
        const dbLine = this._playerAttackRollDbLine(intentRaw, charName, d20, mod, total, data);
        const turnNum =
          typeof window.nextTurnNumber === "function" ? window.nextTurnNumber() : null;
        if (typeof window.addMessage === "function") {
          window.addMessage({
            speaker: charName,
            text: dbLine,
            role: "user",
            route: "input",
            turn: turnNum,
            createdAt: new Date().toISOString(),
          });
        }
        if (inputEl) inputEl.value = "";

        if (cs) {
          this._state = cs;
          this.render(cs);
        }

        const endedNow = cs && String(cs.status) === "ended";
        await this._sendCombatNarrativeFollowUp(dbLine);

        if (endedNow) {
          this.showVictory(cs);
          if (typeof window.combatInput?.syncWithCombat === "function") {
            window.combatInput.syncWithCombat(null);
          }
          return;
        }
      } catch (e) {
        this._setMsg(e.message || "Atak nie powiódł się.", true);
      } finally {
        this._busy = false;
        if (this._state) this.render(this._state);
      }
    }
  }

  window.CombatPanel = CombatPanel;
  window.combatPanel = new CombatPanel();

  window.afterTurnsLoaded = async function (campaignId) {
    const cid = window.state?.selectedCampaignId;
    if (!cid || Number(cid) !== Number(campaignId)) return;
    await window.combatPanel.fetchAndMaybeShow();
  };

  window.applyCombatInitiatedFromTurn = function (combatState) {
    window.combatPanel.applyCombatInitiated(combatState);
  };
})();
