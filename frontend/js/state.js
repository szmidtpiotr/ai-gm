window.state = {
  lang: 'pl',
  translations: {},
  campaigns: [],
  characters: [],
  models: [],
  turns: [],
  /** Ostatnia lista tur z API (bez dopisków walki tylko po stronie klienta). */
  serverTurns: [],
  /** Tury walki dodane lokalnie (np. dymek rzutu wroga), scalane z `serverTurns` w `mergeTurnsForChat`. */
  combatClientTurns: [],
  /** Log silnika walki (GET /combat/turns), syntetyczne dymki — przeżywają F5. */
  combatLogTurns: [],
  /** Wymiany /helpme (tylko klient; nie wysyłane do narracji — serwer i tak używa route=helpme). */
  helpmeLog: [],
  /** Czy pokazywać w czacie "archiwalne" dymki (OOC /helpme, /mem, system, error, separator). Domyślnie ukryte. */
  showArchiveBubbles: false,
  selectedCampaignId: null,
  selectedCharacterId: null,
  selectedEngine: null,
  activeRollRequest: null,
  // np. { dice: 'd20', label: 'Roll Attack d20' }
  // turnNumber: 0   ← DELETE this line
  turnNumbers: {}, // per‑campaign counters
  /** Post-create wizard (stats → skills → identity); null when inactive. */
  charCreationWizard: null,
  /** After POST /campaigns (new campaign), force character modal until first hero exists. */
  expectCharacterCreationForCampaignId: null
};