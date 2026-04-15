window.state = {
  lang: 'pl',
  translations: {},
  campaigns: [],
  characters: [],
  models: [],
  turns: [],
  selectedCampaignId: null,
  selectedCharacterId: null,
  selectedEngine: null,
  activeRollRequest: null,
  // np. { dice: 'd20', label: 'Roll Attack d20' }
  // turnNumber: 0   ← DELETE this line
  turnNumbers: {}   // NEW: per‑campaign counters
};