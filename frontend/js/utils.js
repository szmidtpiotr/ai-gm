window.t = function (key) {
  return window.state.translations[key] || key;
};

window.escapeHtml = function (value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
};

window.formatTimestamp = function (value) {
  if (!value) return '';

  const normalized = String(value).includes('T')
    ? String(value)
    : String(value).replace(' ', 'T');

  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return String(value);

  return date.toLocaleString('pl-PL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

window.currentCampaign = function () {
  return window.state.campaigns.find(
    c => Number(c.id) === Number(window.state.selectedCampaignId)
  ) || null;
};

window.currentCharacter = function () {
  return window.state.characters.find(
    c => Number(c.id) === Number(window.state.selectedCharacterId)
  ) || null;
};

window.currentCharacterName = function () {
  return window.currentCharacter()?.name || window.t('chat.you');
};

window.currentUserId = function () {
  const character = window.currentCharacter ? window.currentCharacter() : null;
  const raw = character?.user_id ?? character?.userid ?? character?.userId;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
};

window.nextTurnNumber = function () {
  window.state.turnNumber += 1;
  return window.state.turnNumber;
};