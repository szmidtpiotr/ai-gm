# TASK 24 — Admin & Player Settings

**Status:** ❓ Needs Design
**Blocking:** Design discussion needed

---

## What Needs to Be Designed

1. **Player-accessible settings** — What can a player configure: text size, combat bubble preference (toggle exists), voice (TTS/STT), language?
2. **LLM settings for players** — D20: admin sets global LLM, players can override with their own key. "Connect" button exists in player UI. What exactly should the player UI look like — which fields are exposed (model, base URL, API key)? What happens when player's key fails?
3. **Admin panel new sections from Phase 12:**
   - Campaign Workshop + Ideas Bank (Task 07)
   - Pending World Entries review queue (Task 10)
   - Skill Counters matrix (Task 08)
   - Command Visibility toggles (Task 19)
   - Where do these live in the admin panel tab structure?
4. **Voice TTS/STT** — `frontend/voice.js` has toggles visible but integration incomplete. Piper voice service runs on port 8302 (DEV). What is the intended player UX? Toggle on/off per session? Or persists as account setting?
5. **Combat bubbles** — Toggle exists in left panel. What does it control exactly? Are combat messages shown inline in chat or in a separate log? This needs clarification.

## Current State

- Admin panel tabs: Stats, Skills, DC Config, Weapons, Enemies, Conditions, Accounts, User LLM, Locations
- Player LLM: `/api/users/{user_id}/llm-settings` mode=`"custom"`|`"default"`, "Connect" button in left settings panel
- Voice TTS/STT: toggles in right character panel (`frontend/voice.js`) — **toggles visible, Piper service exists, integration incomplete** (known issue)
- Combat bubbles: preference toggle exists in left panel — behavior unclear

## Known Issue — Voice TTS/STT

`frontend/voice.js` — TTS (text-to-speech for GM narration) and STT (speech-to-text for player input) toggles are visible in the UI. The Piper voice service is running (`ai-gm-dev-voice-service-1` on port 8302). However the integration between frontend toggles and the voice service pipeline is incomplete. This needs audit before it can be included in any player-facing settings design.

---

*This file will be filled with full specification after the design discussion.*
