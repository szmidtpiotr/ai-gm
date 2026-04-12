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
  // turnNumber: 0   ← DELETE this line
  turnNumbers: {}   // NEW: per‑campaign counters
};