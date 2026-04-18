window.state = {
  lang: 'pl',
  translations: {},
  campaigns: [],
  characters: [],
  models: [],
  turns: [],
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
  charCreationWizard: null
};